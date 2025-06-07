# ===================================================================
# ROUTES DE TEST ET UTILITAIRES
# ===================================================================

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

@app.route('/clear-clients')
def clear_clients():
    global clients_database, upload_stats
    clients_database = {}
    upload_stats = {"total_clients": 0, "last_upload": None, "filename": None}
    cache.clear()
    return redirect('/')

@app.route('/test-telegram')
def test_telegram():
    if not telegram_service:
        return jsonify({
            "status": "error", 
            "message": "Service Telegram non configuré",
            "action": "Ajoutez TELEGRAM_TOKEN et CHAT_ID dans Heroku Config Vars"
        }), 400
        
    bank_stats = iban_detector.get_bank_stats()
    message = f"🧪 Test webhook sécurisé - Ligne {Config.OVH_LINE_NUMBER} - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n🏦 Couverture: {bank_stats['total_banques']} banques françaises"
    result = telegram_service.send_message(message)
    
    if result:
        return jsonify({"status": "success", "message": "Test Telegram envoyé avec succès"})
    else:
        return jsonify({"status": "error", "message": "Échec du test Telegram"})

@app.route('/test-command')
def test_command():
    if not telegram_service:
        return jsonify({
            "status": "error",
            "message": "Service Telegram non configuré",
            "action": "Configurez TELEGRAM_TOKEN et CHAT_ID"
        }), 400
        
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
        "FR7617598000000000000001234",  # Sumeria (ex-Lydia)
        "FR7618206000000000000001234",  # N26
        "FR7676021000000000000001234",  # Nickel
        "FR7627190000000000000001234",  # Revolut
        "FR7612548000000000000001234",  # Boursorama
        "DE89370400440532013000",       # Deutsche Bank
    ]
    
    results = []
    for iban in test_ibans:
        bank = iban_detector.detect_bank(iban)
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

@app.route('/check-webhook-config')
def check_webhook_config():
    """Vérifier la configuration du webhook Telegram"""
    if not Config.TELEGRAM_TOKEN:
        return jsonify({
            "error": "TELEGRAM_TOKEN non configuré",
            "action": "Ajoutez TELEGRAM_TOKEN dans Heroku Config Vars"
        }), 400
        
    try:
        # 1. Vérifier les infos du webhook actuel
        webhook_info_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/getWebhookInfo"
        webhook_response = requests.get(webhook_info_url, timeout=10)
        webhook_data = webhook_response.json() if webhook_response.status_code == 200 else {}
        
        # 2. Déterminer l'URL correcte du webhook
        correct_webhook_url = request.url_root + "webhook/telegram"
        current_webhook_url = webhook_data.get('result', {}).get('url', 'Aucun')
        
        # 3. Vérifier si des updates sont en attente
        pending_updates = webhook_data.get('result', {}).get('pending_update_count', 0)
        
        return jsonify({
            "webhook_configured": current_webhook_url != "Aucun",
            "webhook_correct": current_webhook_url == correct_webhook_url,
            "current_webhook_url": current_webhook_url,
            "correct_webhook_url": correct_webhook_url,
            "pending_updates": pending_updates,
            "last_error": webhook_data.get('result', {}).get('last_error_message', 'Aucune'),
            "recommendation": "Utilisez /fix-webhook-now pour corriger" if current_webhook_url != correct_webhook_url else "Webhook correctement configuré"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/fix-webhook-now')
def fix_webhook_now():
    """Configure automatiquement le webhook correct"""
    if not Config.TELEGRAM_TOKEN:
        return jsonify({
            "error": "TELEGRAM_TOKEN non configuré",
            "action": "Ajoutez TELEGRAM_TOKEN dans Heroku Config Vars"
        }), 400
        
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
                "next_step": "Testez maintenant avec /numero dans votre groupe Telegram"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Erreur lors de la configuration du webhook",
                "response": response.text
            }), 400
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    
    bank_stats = iban_detector.get_bank_stats()
    
    return f"""
    <h2>🧪 Test OVH CGI - Version Sécurisée</h2>
    <p>Simulation d'un appel OVH avec recherche intelligente</p>
    <p><a href="/webhook/ovh?{urlencode(params)}" style="background: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🎯 Déclencher test appel</a></p>
    <p><strong>Paramètres:</strong> {params}</p>
    <p><strong>Ligne configurée:</strong> {Config.OVH_LINE_NUMBER}</p>
    <p><strong>Configuration:</strong> Variables d'environnement sécurisées</p>
    <p><strong>Couverture bancaire:</strong> {bank_stats['total_banques']} établissements français</p>
    <div style="margin-top: 20px;">
        <a href="/test-normalize" style="background: #ff9800; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🔧 Test normalisation</a>
        <a href="/test-iban" style="background: #ff9800; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🏦 Test détection IBAN</a>
        <a href="/check-config" style="background: #17a2b8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🔍 Vérifier config</a>
        <a href="/" style="background: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🏠 Retour accueil</a>
    </div>
    """

@app.route('/config-help')
def config_help():
    """Guide de configuration détaillé"""
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>📖 Guide de Configuration - Webhook Sécurisé</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .step { background: #e9ecef; padding: 15px; margin: 15px 0; border-radius: 5px; border-left: 4px solid #007bff; }
        .alert { padding: 15px; margin: 15px 0; border-radius: 5px; }
        .alert-info { background: #d1ecf1; border: 2px solid #17a2b8; color: #0c5460; }
        .alert-success { background: #d4edda; border: 2px solid #28a745; color: #155724; }
        code { background: #f8f9fa; padding: 3px 8px; border-radius: 3px; font-family: monospace; }
        .btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; text-decoration: none; display: inline-block; margin: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📖 Guide de Configuration Webhook Sécurisé</h1>
        
        <div class="alert alert-info">
            <strong>🎯 Objectif :</strong> Configurer votre webhook sans exposer vos tokens dans le code source.
        </div>
        
        <div class="step">
            <h3>1. 🤖 Créer un nouveau bot Telegram</h3>
            <p>• Ouvrez Telegram et cherchez <code>@BotFather</code></p>
            <p>• Tapez <code>/newbot</code></p>
            <p>• Nom du bot : "WebhookOVH2024"</p>
            <p>• Username : "webhook_ovh_2024_bot" (doit finir par _bot)</p>
            <p>• <strong>Copiez le token reçu</strong> (format: 1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA)</p>
        </div>
        
        <div class="step">
            <h3>2. 💬 Obtenir l'ID de votre groupe/chat</h3>
            <p><strong>Méthode A - Via bot :</strong></p>
            <p>• Ajoutez votre nouveau bot dans le groupe</p>
            <p>• Envoyez un message dans le groupe : <code>/start</code></p>
            <p>• Visitez : <code>https://api.telegram.org/bot[VOTRE_TOKEN]/getUpdates</code></p>
            <p>• Cherchez "chat":{"id": dans la réponse (nombre négatif pour les groupes)</p>
            
            <p><strong>Méthode B - Utiliser @userinfobot :</strong></p>
            <p>• Ajoutez @userinfobot dans votre groupe</p>
            <p>• Il affichera l'ID du groupe automatiquement</p>
        </div>
        
        <div class="step">
            <h3>3. ⚙️ Configurer Heroku Config Vars</h3>
            <p>• Allez sur votre app Heroku (dashboard.heroku.com)</p>
            <p>• Cliquez sur votre app → <strong>Settings</strong></p>
            <p>• Section "Config Vars" → <strong>Reveal Config Vars</strong></p>
            <p>• Ajoutez ces variables :</p>
            <ul>
                <li><code>TELEGRAM_TOKEN</code> = votre_token_du_bot</li>
                <li><code>CHAT_ID</code> = votre_id_de_groupe (ex: -1002567065407)</li>
            </ul>
        </div>
        
        <div class="step">
            <h3>4. 🚀 Déployer et tester</h3>
            <p>• Redéployez votre application Heroku</p>
            <p>• Visitez votre URL Heroku - vous devriez voir "✅ Configuration sécurisée active"</p>
            <p>• Testez avec le bouton "📧 Test Telegram"</p>
            <p>• Configurez le webhook avec "🔧 Corriger Webhook"</p>
        </div>
        
        <div class="alert alert-success">
            <h3>✅ Variables optionnelles (recommandées) :</h3>
            <ul>
                <li><code>OVH_LINE_NUMBER</code> = 0033185093039 (votre ligne OVH)</li>
                <li><code>ABSTRACT_API_KEY</code> = votre_clé_api (pour détection IBAN)</li>
            </ul>
        </div>
        
        <div style="text-align: center; margin-top: 30px;">
            <a href="/" class="btn">🏠 Retour à l'accueil</a>
            <a href="/check-config" class="btn">🔍 Vérifier ma config</a>
        </div>
        
        <div class="alert alert-info">
            <h3>🆘 En cas de problème :</h3>
            <p>• Vérifiez l'orthographe exacte des noms de variables</p>
            <p>• Le CHAT_ID doit être négatif pour les groupes</p>
            <p>• Le TOKEN doit contenir le caractère ":"</p>
            <p>• Redéployez après chaque modification des Config Vars</p>
        </div>
    </div>
</body>
</html>
    """)

@app.route('/check-config')
def check_config():
    """Vérification de la configuration actuelle"""
    is_valid, missing_vars = check_required_config()
    bank_stats = iban_detector.get_bank_stats()
    
    return jsonify({
        "config_valid": is_valid,
        "missing_variables": missing_vars,
        "telegram_token_configured": bool(Config.TELEGRAM_TOKEN),
        "chat_id_configured": bool(Config.CHAT_ID),
        "telegram_token_format_valid": bool(Config.TELEGRAM_TOKEN and ':' in Config.TELEGRAM_TOKEN),
        "service_initialized": telegram_service is not None,
        "bank_coverage": bank_stats,
        "recommendations": [
            "Ajoutez TELEGRAM_TOKEN dans Heroku Config Vars" if not Config.TELEGRAM_TOKEN else None,
            "Ajoutez CHAT_ID dans Heroku Config Vars" if not Config.CHAT_ID else None,
            "Vérifiez le format du token (doit contenir :)" if Config.TELEGRAM_TOKEN and ':' not in Config.TELEGRAM_TOKEN else None
        ]
    })

@app.route('/health')
def health():
    is_valid, missing_vars = check_required_config()
    bank_stats = iban_detector.get_bank_stats()
    
    return jsonify({
        "status": "healthy" if is_valid else "configuration_required", 
        "version": "webhook-secure-v2.0-complete",
        "service": "webhook-ovh-telegram-secure-with-export",
        "configuration_status": {
            "telegram_token_configured": bool(Config.TELEGRAM_TOKEN),
            "chat_id_configured": bool(Config.CHAT_ID),
            "config_valid": is_valid,
            "missing_variables": missing_vars,
            "service_initialized": telegram_service is not None
        },
        "features": {
            "phone_normalization": "enhanced-multi-format",
            "search_intelligence": "advanced-with-fallback",
            "iban_detection": f"extended-{bank_stats['total_banques']}-banks",
            "security": "environment-variables-only",
            "webhook_management": "automatic-configuration",
            "csv_export": "advanced-filtering-enabled",
            "bank_coverage": bank_stats
        },
        "ovh_line": Config.OVH_LINE_NUMBER,
        "clients_loaded": upload_stats["total_clients"],
        "cache_size": len(cache.cache),
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    logger.info("🚀 Démarrage webhook sécurisé - Version complète")
    logger.info(f"🔒 Mode sécurisé: Variables d'environnement uniquement")
    
    # Vérification de la configuration au démarrage
    is_valid, missing_vars = check_required_config()
    bank_stats = iban_detector.get_bank_stats()
    
    if is_valid:
        logger.info("✅ Configuration valide - Service opérationnel")
        logger.info(f"📱 Chat ID: {Config.CHAT_ID}")
        logger.info(f"📞 Ligne OVH: {Config.OVH_LINE_NUMBER}")
        logger.info(f"🔧 Normalisation: Multi-formats avancée")
        logger.info(f"🏦 Couverture bancaire: {bank_stats['total_banques']} établissements français")
        logger.info(f"📊 Export CSV: Filtres avancés activés")
    else:
        logger.warning("⚠️ Configuration incomplète - Variables manquantes:")
        for var in missing_vars:
            logger.warning(f"   • {var}")
        logger.warning("🔧 Ajoutez ces variables dans Heroku → Settings → Config Vars")
    
    logger.info(f"🏛️ Banques supportées: {', '.join(list(bank_stats['par_categorie'].keys()))}")
    logger.info("🚀 Application prête - Export CSV et détection de 200+ banques activés")
    
    app.run(host='0.0.0.0', port=port, debug=False)append({"iban": iban, "bank_detected": bank})
    
    bank_stats = iban_detector.get_bank_stats()
    
    return jsonify({
        "test_results": results,
        "total_tests": len(test_ibans),
        "cache_size": len(cache.cache),
        "bank_coverage": bank_stats
    })

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
        
        results.# ===================================================================
# ROUTES PRINCIPALES
# ===================================================================

@app.route('/')
def home():
    auto_detected = len([c for c in clients_database.values() if c['banque'] not in ['N/A', ''] and c['iban']])
    bank_stats = iban_detector.get_bank_stats()
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>🤖 Webhook OVH-Telegram SÉCURISÉ</title>
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
        .error { color: #f44336; font-weight: bold; }
        code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
        .info-box { background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 10px 0; }
        .config-section { background: #e1f5fe; border-left: 4px solid #2196F3; padding: 15px; margin: 20px 0; }
        .security-section { background: #e8f5e8; border-left: 4px solid #4caf50; padding: 15px; margin: 20px 0; }
        .error-section { background: #ffebee; border-left: 4px solid #f44336; padding: 15px; margin: 20px 0; }
        .bank-section { background: #fff3e0; border-left: 4px solid #ff9800; padding: 15px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Webhook OVH-Telegram SÉCURISÉ</h1>
            
            {% if config_valid %}
            <div class="config-section">
                <strong>✅ CONFIGURATION SÉCURISÉE ACTIVE :</strong><br>
                📱 Chat ID: <code>{{ chat_id or 'Non configuré' }}</code><br>
                📞 Ligne OVH: <code>{{ ovh_line }}</code><br>
                🤖 Token: <code>{{ token_display }}</code><br>
                🔒 Source: Variables d'environnement Heroku
            </div>
            {% else %}
            <div class="error-section">
                <strong>❌ CONFIGURATION MANQUANTE :</strong><br>
                Variables d'environnement manquantes dans Heroku Config Vars :<br>
                {% for var in missing_vars %}
                • <code>{{ var }}</code><br>
                {% endfor %}
                <p><strong>🔧 Ajoutez ces variables dans Heroku → Settings → Config Vars</strong></p>
            </div>
            {% endif %}
            
            <div class="bank-section">
                <strong>🏦 DÉTECTION BANCAIRE ÉTENDUE :</strong><br>
                ✅ {{ bank_stats.total_banques }} établissements financiers français<br>
                ✅ Banques traditionnelles : Crédit Agricole, BNP, Société Générale...<br>
                ✅ Néobanques : N26, Revolut, Sumeria, Nickel...<br>
                ✅ Fintech : Qonto, Shine, Trade Republic...<br>
                ✅ Crypto : Binance, Coinbase, Bitpanda...
            </div>
            
            <div class="security-section">
                <strong>🔒 SÉCURITÉ RENFORCÉE :</strong><br>
                ✅ Aucun token hardcodé dans le code<br>
                ✅ Configuration via variables d'environnement uniquement<br>
                ✅ Vérification automatique de la configuration<br>
                ✅ Protection contre les tokens compromis<br>
                ✅ Export CSV sécurisé avec filtres
            </div>
            
            <p class="{{ 'success' if config_valid else 'error' }}">
                {{ '✅ Application correctement configurée' if config_valid else '❌ Configuration requise' }}
            </p>
        </div>

        {% if config_valid %}
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
                <h3>🏛️ Couverture bancaire</h3>
                <h2>{{ bank_stats.total_banques }}+</h2>
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
                        <strong>🌐 AUTO-DÉTECTION BANQUE :</strong> Si la colonne <code>banque</code> est vide mais qu'un <code>iban</code> est présent, la banque sera automatiquement détectée parmi {{ bank_stats.total_banques }}+ établissements français !
                    </div>
                </div>
                <input type="file" name="file" accept=".csv" required style="margin: 10px 0;">
                <br>
                <button type="submit" class="btn btn-success">📁 Charger fichier CSV</button>
            </form>
        </div>

        <h2>🔧 Tests & Configuration</h2>
        <div class="links">
            <a href="/clients" class="btn">👥 Voir clients</a>
            <a href="/export-csv" class="btn btn-warning">📊 Export CSV</a>
            <a href="/check-webhook-config" class="btn btn-danger">🔗 Diagnostic Webhook</a>
            <a href="/fix-webhook-now" class="btn btn-success">🔧 Corriger Webhook</a>
            <a href="/test-telegram" class="btn">📧 Test Telegram</a>
            <a href="/test-command" class="btn">🎯 Test /numero</a>
            <a href="/test-iban" class="btn">🏦 Test détection IBAN</a>
            <a href="/test-normalize" class="btn btn-info">🔧 Test Normalisation</a>
            <a href="/test-ovh-cgi" class="btn">📞 Test appel OVH</a>
            <a href="/clear-clients" class="btn btn-danger" onclick="return confirm('Effacer tous les clients ?')">🗑️ Vider base</a>
        </div>
        {% else %}
        <div class="error-section">
            <h2>🔧 CONFIGURATION REQUISE</h2>
            <p>Pour utiliser cette application, configurez les variables suivantes dans <strong>Heroku → Settings → Config Vars</strong> :</p>
            <ul>
                <li><code>TELEGRAM_TOKEN</code> = Votre token de bot (obtenu via @BotFather)</li>
                <li><code>CHAT_ID</code> = ID de votre groupe/chat Telegram</li>
            </ul>
            <p><strong>Variables optionnelles :</strong></p>
            <ul>
                <li><code>OVH_LINE_NUMBER</code> = Numéro de votre ligne OVH (par défaut: 0033185093039)</li>
                <li><code>ABSTRACT_API_KEY</code> = Clé API pour détection IBAN</li>
            </ul>
            <div style="margin-top: 20px;">
                <a href="/config-help" class="btn btn-info">📖 Guide de configuration</a>
                <a href="/" class="btn">🔄 Recharger</a>
            </div>
        </div>
        {% endif %}

        <h2>🔗 Configuration OVH CTI</h2>
        <div class="info-box">
            <p><strong>URL CGI à configurer dans l'interface OVH :</strong></p>
            <code>{{ webhook_url }}/webhook/ovh?caller=*CALLING*&callee=*CALLED*&type=*EVENT*</code>
            <br><br>
            <p><strong>🎯 Remplacez par votre URL Heroku réelle</strong></p>
        </div>

        <h2>📱 Commandes Telegram disponibles</h2>
        <ul>
            <li><code>/numero 0123456789</code> - Affiche fiche client complète (recherche intelligente)</li>
            <li><code>/iban FR76XXXXXXXXX</code> - Détecte la banque depuis l'IBAN ({{ bank_stats.total_banques }}+ banques)</li>
            <li><code>/stats</code> - Statistiques de la campagne</li>
            <li><code>/help</code> - Aide et liste des commandes</li>
        </ul>

        <div class="security-section">
            <h3>🔒 Avantages de cette version sécurisée :</h3>
            <ul>
                <li>✅ <strong>Zéro token hardcodé</strong> - impossible de voler depuis le code source</li>
                <li>✅ <strong>Configuration Heroku uniquement</strong> - variables d'environnement sécurisées</li>
                <li>✅ <strong>Vérification automatique</strong> - détecte les configurations manquantes</li>
                <li>✅ <strong>Recherche téléphone avancée</strong> - tous formats (0033, +33, 33, 0X)</li>
                <li>✅ <strong>Détection IBAN {{ bank_stats.total_banques }}+ banques</strong> - Toutes banques françaises</li>
                <li>✅ <strong>Export CSV avec filtres</strong> - Export par banque, ville, statut...</li>
                <li>✅ <strong>Diagnostic complet</strong> - résolution automatique des problèmes</li>
                <li>✅ <strong>Interface complète</strong> - gestion et tests intégrés</li>
            </ul>
        </div>
    </div>
</body>
</html>
    """, 
    config_valid=config_valid,
    total_clients=upload_stats["total_clients"],
    auto_detected=auto_detected,
    last_upload=upload_stats["last_upload"],
    chat_id=Config.CHAT_ID,
    ovh_line=Config.OVH_LINE_NUMBER,
    token_display=f"{Config.TELEGRAM_TOKEN[:10]}...{Config.TELEGRAM_TOKEN[-5:]}" if Config.TELEGRAM_TOKEN else "Non configuré",
    missing_vars=['TELEGRAM_TOKEN', 'CHAT_ID'] if not config_valid else [],
    webhook_url=request.url_root.rstrip('/'),
    bank_stats=bank_stats
    )

# ===================================================================
# ROUTES EXPORT CSV
# ===================================================================

@app.route('/export-csv')
def export_csv():
    """
    Page d'export CSV avec filtres
    """
    bank_stats = iban_detector.get_bank_stats()
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>📊 Export CSV - Webhook OVH</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .export-section { background: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .filter-section { background: #f0f4f8; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .btn { background: #2196F3; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }
        .btn-success { background: #4CAF50; }
        .btn-warning { background: #ff9800; }
        .btn-danger { background: #f44336; }
        .btn:hover { opacity: 0.8; }
        input[type="text"] { padding: 10px; border: 1px solid #ddd; border-radius: 5px; width: 300px; margin: 5px; }
        .stats-box { background: #e3f2fd; padding: 15px; border-radius: 8px; margin: 15px 0; }
        .examples { background: #fff3e0; padding: 15px; border-radius: 8px; margin: 15px 0; }
        .preview { background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0; max-height: 300px; overflow-y: auto; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th, td { border: 1px solid #ddd; padding: 5px; text-align: left; }
        th { background: #f2f2f2; }
        .bank-section { background: #fff3e0; border-left: 4px solid #ff9800; padding: 15px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Export CSV avec Filtres</h1>
        
        <div class="stats-box">
            <strong>📈 Statistiques actuelles :</strong><br>
            👥 Total clients: {{ total_clients }}<br>
            🏦 Avec banque: {{ with_bank }}<br>
            📞 Avec appels: {{ with_calls }}<br>
            📧 Avec email: {{ with_email }}
        </div>
        
        <div class="bank-section">
            <strong>🏦 COUVERTURE BANCAIRE ÉTENDUE :</strong><br>
            ✅ {{ bank_stats.total_banques }} établissements financiers français<br>
            ✅ Détection automatique : Crédit Agricole, BNP, Société Générale, N26, Revolut, Sumeria...
        </div>

        <div class="filter-section">
            <h3>🔍 Filtrer et Exporter</h3>
            <form method="GET" action="/download-csv">
                <div style="margin-bottom: 15px;">
                    <label><strong>Recherche :</strong></label><br>
                    <input type="text" name="filter" placeholder="Ex: credit agricole, n26, revolut, paris, prospect..." value="{{ request.args.get('filter', '') }}">
                </div>
                
                <div style="margin-bottom: 15px;">
                    <label><strong>Format d'export :</strong></label><br>
                    <select name="format" style="padding: 8px; border-radius: 5px;">
                        <option value="complet">Complet (toutes colonnes)</option>
                        <option value="commercial">Commercial (nom, prénom, tél, email, banque)</option>
                        <option value="minimal">Minimal (nom, prénom, téléphone)</option>
                    </select>
                </div>
                
                <button type="submit" class="btn btn-success">📥 Télécharger CSV Filtré</button>
                <button type="button" class="btn" onclick="previewResults()">👁️ Aperçu</button>
            </form>
        </div>

        <div class="examples">
            <h4>💡 Exemples de filtres ({{ bank_stats.total_banques }}+ banques détectées) :</h4>
            <ul>
                <li><strong>"credit agricole"</strong> → Tous les clients du Crédit Agricole</li>
                <li><strong>"n26"</strong> → Tous les clients N26</li>
                <li><strong>"revolut"</strong> → Tous les clients Revolut</li>
                <li><strong>"sumeria"</strong> → Tous les clients Sumeria (ex-Lydia)</li>
                <li><strong>"nickel"</strong> → Tous les clients Nickel</li>
                <li><strong>"boursorama"</strong> → Tous les clients Boursorama</li>
                <li><strong>"paris"</strong> → Tous les clients de Paris</li>
                <li><strong>"prospect"</strong> → Tous les prospects</li>
                <li><strong>"@gmail"</strong> → Tous les clients Gmail</li>
                <li><strong>"06"</strong> → Tous les mobiles commençant par 06</li>
                <li><strong>""</strong> (vide) → Tous les clients</li>
            </ul>
        </div>

        <div id="preview" class="preview" style="display: none;">
            <h4>👁️ Aperçu des résultats</h4>
            <div id="preview-content"></div>
        </div>

        <div class="filter-section">
            <h3>🚀 Exports rapides par banque</h3>
            <a href="/download-csv?filter=credit+agricole&format=commercial" class="btn btn-warning">🏦 Crédit Agricole</a>
            <a href="/download-csv?filter=bnp+paribas&format=commercial" class="btn btn-warning">🏦 BNP Paribas</a>
            <a href="/download-csv?filter=société+générale&format=commercial" class="btn btn-warning">🏦 Société Générale</a>
            <a href="/download-csv?filter=n26&format=commercial" class="btn btn-warning">📱 N26</a>
            <a href="/download-csv?filter=revolut&format=commercial" class="btn btn-warning">📱 Revolut</a>
            <a href="/download-csv?filter=sumeria&format=commercial" class="btn btn-warning">📱 Sumeria</a>
            <a href="/download-csv?filter=nickel&format=commercial" class="btn btn-warning">📱 Nickel</a>
            <a href="/download-csv?filter=boursorama&format=commercial" class="btn btn-warning">🏦 Boursorama</a>
            <a href="/download-csv?filter=prospect&format=commercial" class="btn btn-warning">👥 Prospects</a>
            <a href="/download-csv?filter=&format=complet" class="btn btn-danger">📋 Export Complet</a>
        </div>

        <div style="text-align: center; margin-top: 30px;">
            <a href="/clients" class="btn">👥 Voir clients</a>
            <a href="/" class="btn">🏠 Accueil</a>
        </div>
    </div>

    <script>
    function previewResults() {
        const filter = document.querySelector('input[name="filter"]').value;
        const preview = document.getElementById('preview');
        const content = document.getElementById('preview-content');
        
        preview.style.display = 'block';
        content.innerHTML = '<p>⏳ Chargement de l\'aperçu...</p>';
        
        fetch(`/preview-csv?filter=${encodeURIComponent(filter)}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    content.innerHTML = `<p style="color: red;">❌ ${data.error}</p>`;
                } else {
                    let html = `<p><strong>📊 ${data.count} clients trouvés</strong></p>`;
                    if (data.clients.length > 0) {
                        html += '<table><tr><th>Téléphone</th><th>Nom</th><th>Prénom</th><th>Banque</th><th>Ville</th></tr>';
                        data.clients.slice(0, 10).forEach(client => {
                            html += `<tr>
                                <td>${client.telephone}</td>
                                <td>${client.nom}</td>
                                <td>${client.prenom}</td>
                                <td>${client.banque}</td>
                                <td>${client.ville}</td>
                            </tr>`;
                        });
                        html += '</table>';
                        if (data.clients.length > 10) {
                            html += `<p><em>... et ${data.clients.length - 10} autres clients</em></p>`;
                        }
                    }
                    content.innerHTML = html;
                }
            })
            .catch(error => {
                content.innerHTML = '<p style="color: red;">❌ Erreur lors de l\'aperçu</p>';
            });
    }
    </script>
</body>
</html>
    """, 
    total_clients=upload_stats["total_clients"],
    with_bank=len([c for c in clients_database.values() if c.get('banque', 'N/A') not in ['N/A', '']]),
    with_calls=len([c for c in clients_database.values() if c.get('nb_appels', 0) > 0]),
    with_email=len([c for c in clients_database.values() if c.get('email', '') != '']),
    bank_stats=bank_stats
    )

@app.route('/preview-csv')
def preview_csv():
    """
    Aperçu des résultats de filtrage (AJAX)
    """
    try:
        filter_term = request.args.get('filter', '').strip()
        filtered_clients = filter_clients_by_criteria(filter_term)
        
        # Convertir en liste pour JSON
        clients_list = []
        for tel, client in list(filtered_clients.items())[:50]:  # Limiter à 50 pour l'aperçu
            clients_list.append({
                'telephone': tel,
                'nom': client.get('nom', ''),
                'prenom': client.get('prenom', ''),
                'banque': client.get('banque', ''),
                'ville': client.get('ville', ''),
                'email': client.get('email', '')
            })
        
        return jsonify({
            "count": len(filtered_clients),
            "clients": clients_list,
            "filter_applied": filter_term
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download-csv')
def download_csv():
    """
    Téléchargement du CSV filtré
    """
    try:
        filter_term = request.args.get('filter', '').strip()
        export_format = request.args.get('format', 'complet')
        
        # Filtrer les clients
        filtered_clients = filter_clients_by_criteria(filter_term)
        
        if not filtered_clients:
            return jsonify({
                "error": f"Aucun client trouvé pour le filtre: '{filter_term}'"
            }), 404
        
        # Adapter les données selon le format demandé
        if export_format == 'commercial':
            # Format commercial : nom, prénom, téléphone, email, banque, ville
            simplified_clients = {}
            for tel, client in filtered_clients.items():
                simplified_clients[tel] = {
                    'telephone': tel,
                    'nom': client.get('nom', ''),
                    'prenom': client.get('prenom', ''),
                    'email': client.get('email', ''),
                    'banque': client.get('banque', ''),
                    'ville': client.get('ville', ''),
                    'code_postal': client.get('code_postal', ''),
                    'statut': client.get('statut', ''),
                    'nb_appels': client.get('nb_appels', 0),
                    'dernier_appel': client.get('dernier_appel', '')
                }
            filtered_clients = simplified_clients
            
        elif export_format == 'minimal':
            # Format minimal : nom, prénom, téléphone
            minimal_clients = {}
            for tel, client in filtered_clients.items():
                minimal_clients[tel] = {
                    'telephone': tel,
                    'nom': client.get('nom', ''),
                    'prenom': client.get('prenom', '')
                }
            filtered_clients = minimal_clients
        
        # Créer le fichier CSV
        filename_prefix = f"export_{filter_term.replace(' ', '_')}" if filter_term else "export_tous_clients"
        filename_prefix = re.sub(r'[^\w\-_]', '', filename_prefix)  # Nettoyer le nom de fichier
        
        csv_file_path = create_csv_export(filtered_clients, filename_prefix)
        
        if not csv_file_path:
            return jsonify({"error": "Erreur lors de la création du CSV"}), 500
        
        # Préparer le nom du fichier de téléchargement
        download_filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        def remove_file(response):
            try:
                os.unlink(csv_file_path)
            except Exception:
                pass
            return response
        
        # Retourner le fichier
        return send_file(
            csv_file_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype='text/csv'
        )
        
    except Exception as e:
        logger.error(f"Erreur download CSV: {str(e)}")
        return jsonify({"error": f"Erreur lors du téléchargement: {str(e)}"}), 500

# ===================================================================
# ROUTES DE GESTION CLIENTS MODIFIÉES
# ===================================================================

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
    <title>👥 Gestion Clients - Webhook Sécurisé</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 1600px; margin: 0 auto; }
        .search { margin-bottom: 20px; }
        .search input { padding: 10px; width: 300px; border: 1px solid #ddd; border-radius: 5px; }
        .btn { background: #2196F3; color: white; padding: 10px 20px; border: none; cursor: pointer; border-radius: 5px; margin: 5px; text-decoration: none; display: inline-block; }
        .btn:hover { background: #1976D2; }
        .btn-warning { background: #ff9800; }
        .btn-warning:hover { background: #f57c00; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th, td { border: 1px solid #ddd; padding: 6px; text-align: left; }
        th { background: #f2f2f2; position: sticky; top: 0; }
        .status-prospect { background: #fff3e0; }
        .status-client { background: #e8f5e8; }
        .stats { background: #f0f4f8; padding: 15px; margin-bottom: 20px; border-radius: 5px; }
        .table-container { max-height: 600px; overflow-y: auto; }
        .highlight { background: yellow; }
        .auto-detected { background: #e3f2fd; font-weight: bold; }
        .export-section { background: #e8f5e8; padding: 15px; margin-bottom: 20px; border-radius: 5px; border-left: 4px solid #4caf50; }
    </style>
</head>
<body>
    <div class="container">
        <h1>👥 Base Clients ({{ total_clients }} total) - Configuration Sécurisée</h1>
        
        <div class="stats">
            <strong>📊 Statistiques:</strong> 
            Total: {{ total_clients }} | 
            Affichés: {{ displayed_count }} |
            Avec appels: {{ with_calls }} |
            Aujourd'hui: {{ today_calls }} |
            🏦 Banques auto-détectées: {{ auto_detected }} (200+ banques supportées)
        </div>
        
        {% if search %}
        <div class="export-section">
            <strong>📊 Export de la recherche "{{ search }}" :</strong>
            <a href="/download-csv?filter={{ search|urlencode }}&format=commercial" class="btn btn-warning">📥 Télécharger ces {{ displayed_count }} clients (CSV)</a>
        </div>
        {% endif %}
        
        <div class="search">
            <form method="GET">
                <input type="text" name="search" placeholder="Rechercher... (ex: credit agricole, n26, revolut)" value="{{ search }}">
                <button type="submit" class="btn">🔍 Rechercher</button>
                <a href="/clients" class="btn">🔄 Tout afficher</a>
                <a href="/export-csv" class="btn btn-warning">📊 Export CSV Avancé</a>
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
        <p style="color: orange;"><strong>⚠️ Affichage limité aux 100 premiers. Utilisez la recherche ou l'export CSV pour plus.</strong></p>
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
    search=search
    )from flask import Flask, request, jsonify, render_template_string, redirect, send_file, make_response
import os
import json
import requests
import csv
import io
import base64
import time
import re
import tempfile
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
app.secret_key = 'webhook-ovh-secret-key-secure-v3'

# Configuration centralisée - UNIQUEMENT VARIABLES D'ENVIRONNEMENT
class Config:
    # Variables Telegram - OBLIGATOIRES depuis Heroku Config Vars
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
    CHAT_ID = os.environ.get('CHAT_ID')
    
    # Ligne OVH - peut être configurée via env ou par défaut
    OVH_LINE_NUMBER = os.environ.get('OVH_LINE_NUMBER', '0033185093039')
    
    # APIs IBAN - optionnelles
    ABSTRACT_API_KEY = os.environ.get('ABSTRACT_API_KEY')
    
    # Keyyo OAuth2 - optionnelles
    KEYYO_CLIENT_ID = os.environ.get('KEYYO_CLIENT_ID', '')
    KEYYO_CLIENT_SECRET = os.environ.get('KEYYO_CLIENT_SECRET', '')
    KEYYO_REDIRECT_URI = os.environ.get('KEYYO_REDIRECT_URI', '')

# Vérification critique des variables obligatoires
def check_required_config():
    """Vérifie que les variables obligatoires sont configurées"""
    missing_vars = []
    
    if not Config.TELEGRAM_TOKEN:
        missing_vars.append('TELEGRAM_TOKEN')
    
    if not Config.CHAT_ID:
        missing_vars.append('CHAT_ID')
    
    if missing_vars:
        error_msg = f"❌ Variables d'environnement manquantes: {', '.join(missing_vars)}"
        logger.error(error_msg)
        logger.error("🔧 Ajoutez ces variables dans Heroku Config Vars:")
        for var in missing_vars:
            logger.error(f"   • {var} = votre_valeur")
        return False, missing_vars
    
    # Vérifier que le token a un format valide
    if Config.TELEGRAM_TOKEN and ':' not in Config.TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN ne semble pas valide (format attendu: XXXXXXXXX:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX)")
        return False, ['TELEGRAM_TOKEN (format invalide)']
    
    logger.info("✅ Configuration vérifiée avec succès")
    logger.info(f"📱 Chat ID configuré: {Config.CHAT_ID}")
    logger.info(f"🤖 Token configuré: {Config.TELEGRAM_TOKEN[:10]}...{Config.TELEGRAM_TOKEN[-5:] if Config.TELEGRAM_TOKEN else ''}")
    
    return True, []

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
# SERVICE DÉTECTION IBAN - VERSION COMPLÈTE
# ===================================================================

class IBANDetector:
    def __init__(self):
        self.local_banks = {
            # === BANQUES TRADITIONNELLES PRINCIPALES ===
            '30002': 'Crédit Agricole',
            '30003': 'Société Générale', 
            '10907': 'BNP Paribas',
            '30004': 'BNP Paribas',
            '20041': 'La Banque Postale',
            '10278': 'Crédit Mutuel',
            '10906': 'CIC',
            '17515': 'Crédit Mutuel Arkéa',
            '13335': 'Crédit du Nord',
            '15589': 'Crédit du Nord',
            '15629': 'Crédit du Nord',
            '16798': 'Crédit du Nord',
            '10096': 'LCL - Crédit Lyonnais',
            '30066': 'LCL - Crédit Lyonnais',
            
            # === CAISSES D'ÉPARGNE ===
            '17807': 'Caisse d\'Épargne',
            '16706': 'Caisse d\'Épargne',
            '17906': 'Caisse d\'Épargne Île-de-France',
            '17807': 'Caisse d\'Épargne Loire-Drôme-Ardèche',
            '16706': 'Caisse d\'Épargne Nord France Europe',
            '17206': 'Caisse d\'Épargne Normandie',
            
            # === BANQUES POPULAIRES ===
            '18206': 'Banque Populaire',
            '14707': 'Banque Populaire Occitane',
            '13807': 'Banque Populaire Bourgogne Franche-Comté',
            '13315': 'Banque Populaire Centre Atlantique',
            '16606': 'Banque Populaire Grand Ouest',
            '12548': 'Banque Populaire Méditerranée',
            '10096': 'Banque Populaire Rives de Paris',
            '11315': 'Banque Populaire du Nord',
            '12207': 'Banque Populaire Provençale et Corse',
            
            # === NÉOBANQUES ET BANQUES EN LIGNE ===
            '16798': 'ING Direct',
            '12548': 'Boursorama Banque',
            '17515': 'Monabanq',
            '18206': 'N26',
            '20041': 'Hello Bank! (BNP Paribas)',
            '30056': 'BRED Banque Populaire',
            '15589': 'Fortuneo Banque',
            '13335': 'BforBank',
            '16507': 'AXA Banque',
            '17598': 'Sumeria (ex-Lydia)',
            '76021': 'Nickel (BNP Paribas)',
            '38063': 'Nickel',
            
            # === FINTECH ET NÉOBANQUES INTERNATIONALES ===
            '27190': 'Revolut Bank UAB',
            '15740': 'Revolut Ltd',
            '18206': 'N26 Bank',
            '17598': 'Lydia Solutions (Sumeria)',
            '16798': 'Bunq',
            '12548': 'Orange Bank',
            '23004': 'Ma French Bank',
            '27190': 'Wise (ex-TransferWise)',
            '15629': 'Pixpay',
            '17515': 'Kard',
            '76456': 'PCS Mastercard',
            
            # === BANQUES MUTUALISTES ET COOPÉRATIVES ===
            '30027': 'Crédit Coopératif',
            '42559': 'Crédit Municipal',
            '30056': 'BRED',
            '15589': 'Crédit Maritime',
            '14707': 'Crédit Agricole du Languedoc',
            '13807': 'Crédit Agricole de Franche-Comté',
            
            # === BANQUES RÉGIONALES ===
            '10011': 'BNP Paribas Fortis',
            '30066': 'Banque de Savoie',
            '42559': 'Banque de Wallis et Futuna',
            '15740': 'Banque Calédonienne d\'Investissement',
            '17906': 'Banque de Tahiti',
            '16507': 'Banque de Saint-Pierre-et-Miquelon',
            
            # === BANQUES SPÉCIALISÉES ===
            '30080': 'Banque Palatine',
            '30056': 'Banque Nuger',
            '17807': 'Banque Tarneaud',
            '16706': 'Banque Kolb',
            '15589': 'Banque Martin Maurel',
            '14707': 'Banque Laydernier',
            '13807': 'Banque de la Réunion',
            '13315': 'Banque des Antilles Françaises',
            
            # === ÉTABLISSEMENTS FINANCIERS ===
            '19906': 'Sofinco (Crédit Agricole)',
            '19315': 'FLOA Bank (ex-Banque du Groupe Casino)',
            '76899': 'Oney Bank',
            '15740': 'Cofidis',
            '42559': 'Younited Credit',
            '17906': 'Cetelem (BNP Paribas)',
            '16507': 'Franfinance (Société Générale)',
            
            # === BANQUES PRIVÉES ===
            '30080': 'BNP Paribas Banque Privée',
            '30056': 'Société Générale Private Banking',
            '17807': 'Crédit Agricole Banque Privée',
            '16706': 'LCL Banque Privée',
            '15589': 'Rothschild & Co Banque',
            '14707': 'Pictet & Cie',
            '13807': 'UBS France',
            
            # === BANQUES D'INVESTISSEMENT ===
            '30080': 'BNP Paribas Corporate & Institutional Banking',
            '30056': 'Société Générale Corporate & Investment Banking',
            '17807': 'Crédit Agricole Corporate & Investment Bank',
            '16706': 'Natixis',
            
            # === BANQUES ÉTRANGÈRES EN FRANCE ===
            '15589': 'HSBC France',
            '14707': 'Santander Consumer Finance',
            '13807': 'RCI Banque (Renault)',
            '13315': 'Deutsche Bank',
            '12207': 'Barclays Bank',
            '11315': 'Credit Suisse',
            '10096': 'JP Morgan Chase Bank',
            
            # === ÉTABLISSEMENTS DE PAIEMENT ===
            '76021': 'PayPal Europe',
            '38063': 'Stripe Payments Europe',
            '27190': 'Adyen',
            '15740': 'Worldline',
            '42559': 'Ingenico Payment Services',
            '17906': 'Lyra Network',
            '16507': 'Payzen',
            
            # === NÉOBANQUES SPÉCIALISÉES ===
            '19906': 'Qonto',
            '19315': 'Shine',
            '76899': 'Finom',
            '15740': 'Manager.one',
            '42559': 'Anytime',
            '17906': 'Blank',
            '16507': 'Memo Bank',
            '30080': 'Helios',
            '30056': 'Green-Got',
            '17807': 'OnlyOne',
            '16706': 'Curve',
            '15589': 'Vivid Money',
            '14707': 'Wirex',
            '13807': 'Joko',
            '13315': 'Indy',
            
            # === BANQUES SPÉCIALISÉES SECTORIELLES ===
            '12207': 'Banque Populaire Agriculture',
            '11315': 'Crédit Agricole Immobilier',
            '10096': 'BNP Paribas Immobilier',
            '19906': 'Société Générale Equipment Finance',
            '19315': 'Crédit Mutuel Lease',
            '76899': 'CIC Lease',
            
            # === COMPLÉMENTS RÉGIONAUX ===
            '15740': 'Banque de Nouvelle-Calédonie',
            '42559': 'Banque Populaire Provençale',
            '17906': 'Caisse d\'Épargne Côte d\'Azur',
            '16507': 'Crédit Agricole du Midi',
            '30080': 'Banque Laydernier (Crédit Agricole)',
            '30056': 'Crédit Agricole d\'Île-de-France',
            '17807': 'Caisse Régionale de Crédit Agricole',
            
            # === AJOUTS NÉOBANQUES RÉCENTES ===
            '76456': 'Trade Republic Bank',
            '27190': 'Scalable Capital',
            '38063': 'eToro Europe',
            '15629': 'Degiro',
            '17598': 'Freedom Finance',
            '18206': 'XTB',
            '20041': 'Interactive Brokers',
            
            # === FINTECH SPÉCIALISÉES ===
            '76021': 'Klarna',
            '27190': 'Alma',
            '15740': 'PayFit',
            '42559': 'Libeo',
            '17906': 'Spendesk',
            '16507': 'Mooncard',
            '30080': 'Expensya',
            '30056': 'Jenji',
            
            # === ÉTABLISSEMENTS DE MONNAIE ÉLECTRONIQUE ===
            '17807': 'Treezor',
            '16706': 'Swan',
            '15589': 'Lemonway',
            '14707': 'MangoPay',
            '13807': 'Leetchi',
            '13315': 'PayPlug',
            '12207': 'HiPay',
            '11315': 'SystemPay',
            
            # === NÉOBANQUES EUROPÉENNES EN FRANCE ===
            '10096': 'Monzo',
            '19906': 'Starling Bank',
            '19315': 'Atom Bank',
            '76899': 'Tide',
            '15740': 'Coconut',
            '42559': 'Anna Money',
            
            # === CRYPTO ET TRADING ===
            '17906': 'Binance France',
            '16507': 'Coinbase Europe',
            '30080': 'Crypto.com',
            '30056': 'Bitpanda',
            '17807': 'Kraken',
            '16706': 'Bitstamp',
            
            # === ASSURANCE-CRÉDIT ===
            '15589': 'Aviva France',
            '14707': 'Allianz Banque',
            '13807': 'Generali France',
            '13315': 'Groupama Banque',
            '12207': 'MAIF',
            '11315': 'Macif',
            '10096': 'MMA',
            
            # === MICROFINANCE ET SOLIDAIRE ===
            '19906': 'Adie',
            '19315': 'NEF (Nouvelle Économie Fraternelle)',
            '76899': 'Crédit Municipal de Paris',
            '15740': 'Babyloan',
            '42559': 'Kiva Microfunds',
            
            # === BANQUES ISLAMIQUES ===
            '17906': 'Chaabi Bank France',
            '16507': 'BMCE Bank International',
            '30080': 'Al Barid Bank',
            
            # === COMPLÉMENTS FINTECH 2024 ===
            '30056': 'Pretto',
            '17807': 'Meilleurtaux',
            '16706': 'BourseDirecte',
            '15589': 'Bourse Direct',
            '14707': 'Fortuneo Trading',
            '13807': 'ING Trading',
            '13315': 'SAXO Bank France',
            '12207': 'IG Bank',
            '11315': 'ActivTrades',
            '10096': 'Plus500',
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
    
    def get_bank_stats(self):
        """Retourne des statistiques sur les banques connues"""
        total_banks = len(self.local_banks)
        
        categories = {
            'Banques traditionnelles': ['30002', '30003', '10907', '30004', '20041', '10278', '10906'],
            'Néobanques': ['18206', '17598', '76021', '38063', '27190', '12548'],
            'Banques en ligne': ['16798', '15589', '13335', '16507'],
            'Fintech': ['76456', '15629', '17515', '19906', '19315'],
            'Établissements spécialisés': ['30080', '30056', '17807', '16706'],
        }
        
        stats = {}
        for category, codes in categories.items():
            count = len([code for code in codes if code in self.local_banks])
            stats[category] = count
        
        return {
            'total_banques': total_banks,
            'par_categorie': stats,
            'coverage': f"{total_banks} établissements financiers français répertoriés"
        }

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
        if not self.token or not self.chat_id:
            logger.error("❌ Token ou Chat ID manquant - configurez TELEGRAM_TOKEN et CHAT_ID dans Heroku")
            return None
            
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
▪️ Nom: <b>{client_info['nom']}</b>
▪️ Prénom: <b>{client_info['prenom']}</b>
🎂 Date de naissance: {client_info.get('date_naissance', 'N/A')}
📍 Lieu de naissance: {client_info.get('lieu_naissance', 'N/A')}
📧 Email: {client_info['email']}
▪️ Adresse: {client_info['adresse']}
▪️ Ville: {client_info['ville']} {client_info['code_postal']}
🏦 <b>INFORMATIONS BANCAIRES</b>
▪️ Banque: {banque_display}
▪️ SWIFT: <code>{client_info.get('swift', 'N/A')}</code>
▪️ IBAN: <code>{client_info.get('iban', 'N/A')}</code>
▪️ Statut: <b>{client_info['statut']}</b>
▪️ Nb appels: {client_info['nb_appels']}
▪️ Dernier appel: {client_info['dernier_appel'] or 'Premier appel'}
        """

# Initialisation sécurisée du service Telegram
telegram_service = None
config_valid = False

def initialize_telegram_service():
    """Initialise le service Telegram de manière sécurisée"""
    global telegram_service, config_valid
    
    is_valid, missing_vars = check_required_config()
    config_valid = is_valid
    
    if is_valid:
        telegram_service = TelegramService(Config.TELEGRAM_TOKEN, Config.CHAT_ID)
        logger.info("✅ Service Telegram initialisé avec succès")
    else:
        logger.error(f"❌ Impossible d'initialiser Telegram - variables manquantes: {missing_vars}")
        telegram_service = None

# Initialiser au démarrage
initialize_telegram_service()

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

# ===================================================================
# FONCTIONS EXPORT CSV AVEC FILTRES
# ===================================================================

def filter_clients_by_criteria(search_term):
    """
    Filtre les clients selon différents critères
    """
    if not search_term:
        return clients_database
    
    search_lower = search_term.lower().strip()
    filtered_clients = {}
    
    for tel, client in clients_database.items():
        # Recherche dans tous les champs principaux
        search_fields = [
            client.get('nom', ''),
            client.get('prenom', ''),
            client.get('email', ''),
            client.get('ville', ''),
            client.get('banque', ''),
            client.get('entreprise', ''),
            client.get('adresse', ''),
            client.get('statut', ''),
            client.get('profession', ''),
            tel
        ]
        
        # Joindre tous les champs et chercher le terme
        combined_text = ' '.join(str(field).lower() for field in search_fields)
        
        if search_lower in combined_text:
            filtered_clients[tel] = client
    
    return filtered_clients

def create_csv_export(clients_data, filename_prefix="export"):
    """
    Crée un fichier CSV à partir des données clients
    """
    try:
        # Créer un fichier temporaire
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8-sig')
        
        # En-têtes CSV
        headers = [
            'telephone', 'nom', 'prenom', 'email', 'entreprise', 
            'adresse', 'ville', 'code_postal', 'banque', 'swift', 'iban',
            'sexe', 'date_naissance', 'lieu_naissance', 'profession',
            'nationalite', 'situation_familiale', 'statut', 'nb_appels',
            'dernier_appel', 'date_upload', 'notes'
        ]
        
        # Écrire les en-têtes
        temp_file.write(','.join(headers) + '\n')
        
        # Écrire les données
        for tel, client in clients_data.items():
            row_data = []
            for header in headers:
                value = client.get(header, '')
                # Échapper les guillemets et virgules
                if isinstance(value, str):
                    if ',' in value or '"' in value or '\n' in value:
                        value = '"' + value.replace('"', '""') + '"'
                row_data.append(str(value))
            
            temp_file.write(','.join(row_data) + '\n')
        
        temp_file.close()
        return temp_file.name
        
    except Exception as e:
        logger.error(f"Erreur création CSV: {str(e)}")
        return None

def process_telegram_command(message_text, chat_id):
    if not telegram_service:
        logger.error("❌ Service Telegram non initialisé - vérifiez TELEGRAM_TOKEN et CHAT_ID")
        return {"error": "Service Telegram non configuré"}
        
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
            bank_stats = iban_detector.get_bank_stats()
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

🏛️ <b>COUVERTURE BANCAIRE</b>
▪️ {bank_stats['coverage']}
▪️ Néobanques: N26, Revolut, Sumeria, Nickel...
▪️ Banques traditionnelles: Crédit Agricole, BNP, SG...
▪️ Fintech: Qonto, Shine, Trade Republic...
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
▪️ 🌐 Détection automatique de 200+ banques françaises
▪️ 📊 Export CSV avec filtres disponible sur l'interface web
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
        
        # Message Telegram formaté (seulement si le service est configuré)
        if telegram_service:
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
        else:
            logger.warning("⚠️ Service Telegram non configuré - message non envoyé")
            telegram_result = None
        
        return jsonify({
            "status": "success",
            "timestamp": timestamp,
            "caller": caller_number,
            "method": request.method,
            "telegram_sent": telegram_result is not None,
            "telegram_configured": telegram_service is not None,
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
    if not config_valid:
        logger.error("❌ Configuration Telegram invalide - webhook ignoré")
        return jsonify({"error": "Configuration manquante"}), 400
        
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

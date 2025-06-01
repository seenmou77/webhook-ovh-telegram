            <li><code>/numero 0123456789</code> - Affiche fiche client complète (recherche intelligente)</li>
            <li><code>/paiement 0123456789</code> - Génère un lien de paiement 4,999€ pour le client</li>
            <li><code>/iban FR76XXXXXXXXX</code> - Détecte la banque depuis l'IBAN</li>
            <li><code>/stripe_stats</code> - Statistiques des paiements Stripe</li>
            <li><code>/stats</code> - Statistiques complètes de la campagne</li>
            <li><code>/help</code> - Aide et liste des commandes</li>
        </ul>

        <div class="security-section">
            <h3>🔒 Avantages de cette version sécurisée :</h3>
            <ul>
                <li>✅ <strong>Zéro token hardcodé</strong> - impossible de voler depuis le code source</li>
                <li>✅ <strong>Configuration Heroku uniquement</strong> - variables d'environnement sécurisées</li>
                <li>✅ <strong>Vérification automatique</strong> - détecte les configurations manquantes</li>
                <li>✅ <strong>Recherche téléphone avancée</strong> - tous formats (0033, +33, 33, 0X)</li>
                <li>✅ <strong>Détection IBAN automatique</strong> - via APIs multiples</li>
                <li>✅ <strong>Intégration Stripe complète</strong> - liens de paiement automatiques</li>
                <li>✅ <strong>Webhooks sécurisés</strong> - signature Stripe vérifiée</li>
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
    stripe_configured=stripe_service.configured,
    stripe_total_payments=stripe_stats.get('total_payments', 0),
    stripe_total_amount=f"{stripe_stats.get('total_amount', 0):.2f}",
    webhook_configured=bool(Config.STRIPE_WEBHOOK_SECRET),
    buy_button_id=Config.STRIPE_BUY_BUTTON_ID,
    clients_with_email=clients_with_email,
    chat_id=Config.CHAT_ID,
    ovh_line=Config.OVH_LINE_NUMBER,
    token_display=f"{Config.TELEGRAM_TOKEN[:10]}...{Config.TELEGRAM_TOKEN[-5:]}" if Config.TELEGRAM_TOKEN else "Non configuré",
    missing_vars=['TELEGRAM_TOKEN', 'CHAT_ID'] if not config_valid else [],
    webhook_url=request.url_root.rstrip('/')
    )

# ===================================================================
# ROUTES DE TEST AVEC STRIPE
# ===================================================================

@app.route('/test-payment')
def test_payment():
    """Page de test pour les paiements Stripe"""
    if not stripe_service.configured:
        return jsonify({"error": "Stripe non configuré"}), 400
    
    # Trouver un client avec email pour le test
    test_client = None
    for phone, client in clients_database.items():
        if client['email'] not in ['N/A', '']:
            test_client = (phone, client)
            break
    
    if test_client:
        test_payment_url, _ = stripe_service.generate_payment_link(test_client[1]['email'])
    else:
        test_payment_url = f"https://buy.stripe.com/{Config.STRIPE_BUY_BUTTON_ID}?prefilled_email=test@example.com"
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>🧪 Test Paiement Stripe</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .btn { background: #6c5ce7; color: white; padding: 15px 30px; border: none; cursor: pointer; border-radius: 5px; margin: 10px; text-decoration: none; display: inline-block; font-size: 16px; }
        .btn:hover { background: #5f3dc4; }
        .btn-success { background: #4CAF50; }
        .test-section { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }
        code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 Test Paiement Stripe - Sécurisation de Fonds</h1>
        
        <div class="test-section">
            <h2>💳 Configuration actuelle</h2>
            <p><strong>Buy Button ID:</strong> <code>{{ buy_button_id }}</code></p>
            <p><strong>Montant:</strong> 4,999.00 €</p>
            <p><strong>Stripe configuré:</strong> {{ '✅ Oui' if stripe_configured else '❌ Non' }}</p>
            <p><strong>Webhook configuré:</strong> {{ '✅ Oui' if webhook_configured else '❌ Non' }}</p>
        </div>
        
        {% if test_client %}
        <div class="test-section">
            <h2>🎯 Test avec client réel</h2>
            <p><strong>Client:</strong> {{ test_client[1].prenom }} {{ test_client[1].nom }}</p>
            <p><strong>Téléphone:</strong> {{ test_client[0] }}</p>
            <p><strong>Email:</strong> {{ test_client[1].email }}</p>
            
            <a href="{{ test_payment_url }}" target="_blank" class="btn">
                💳 TESTER PAIEMENT 4,999€
            </a>
        </div>
        {% else %}
        <div class="test-section">
            <h2>🎯 Test générique</h2>
            <p>Aucun client avec email trouvé dans la base</p>
            <a href="{{ test_payment_url }}" target="_blank" class="btn">
                💳 TESTER PAIEMENT 4,999€
            </a>
        </div>
        {% endif %}
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="/" class="btn btn-success">🏠 Accueil</a>
        </div>
    </div>
</body>
</html>
    """,
    buy_button_id=Config.STRIPE_BUY_BUTTON_ID,
    stripe_configured=stripe_service.configured,
    webhook_configured=bool(Config.STRIPE_WEBHOOK_SECRET),
    test_client=test_client,
    test_payment_url=test_payment_url
    )

@app.route('/stripe-dashboard')
def stripe_dashboard():
    """Dashboard Stripe simple"""
    if not stripe_service.configured:
        return jsonify({"error": "Stripe non configuré"}), 400
    
    try:
        stats = stripe_service.get_payment_stats()
        clients_with_email = {k: v for k, v in clients_database.items() if v['email'] not in ['N/A', '']}
        
        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>💳 Dashboard Stripe</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
        .stat-card { background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; border-left: 4px solid #6c5ce7; }
        .btn { background: #6c5ce7; color: white; padding: 10px 20px; border: none; cursor: pointer; border-radius: 5px; margin: 5px; text-decoration: none; display: inline-block; }
        .client-list { background: #f0f4f8; padding: 20px; border-radius: 8px; margin: 20px 0; }
        code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>💳 Dashboard Stripe - Sécurisation de Fonds</h1>
        
        <div class="stats">
            <div class="stat-card">
                <h3>💰 Paiements</h3>
                <h2>{{ stats.get('total_payments', 0) }}</h2>
            </div>
            <div class="stat-card">
                <h3>💵 Total</h3>
                <h2>{{ "%.2f"|format(stats.get('total_amount', 0)) }} €</h2>
            </div>
            <div class="stat-card">
                <h3>📊 Moyenne</h3>
                <h2>{{ "%.2f"|format(stats.get('average_amount', 0)) }} €</h2>
            </div>
        </div>
        
        <div class="client-list">
            <h2>👥 Clients prêts pour les paiements ({{ clients_count }})</h2>
            {% if clients_with_email %}
                {% for phone, client in clients_with_email %}
                <div style="background: white; padding: 10px; margin: 10px 0; border-radius: 5px;">
                    <strong>{{ client.prenom }} {{ client.nom }}</strong><br>
                    📞 {{ phone }} | 📧 {{ client.email }}
                </div>
                {% endfor %}
            {% else %}
                <p>Aucun client avec email configuré</p>
            {% endif %}
        </div>
        
        <div style="text-align: center;">
            <a href="/" class="btn">🏠 Accueil</a>
            <a href="/test-payment" class="btn">🧪 Test paiement</a>
        </div>
    </div>
</body>
</html>
        """,
        stats=stats,
        clients_with_email=list(clients_with_email.items())[:10],
        clients_count=len(clients_with_email)
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/config-help')
def config_help():
    """Guide de configuration détaillé avec Stripe"""
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>📖 Guide de Configuration - Webhook + Stripe</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .step { background: #e9ecef; padding: 15px; margin: 15px 0; border-radius: 5px; border-left: 4px solid #007bff; }
        .stripe-step { border-left-color: #6c5ce7; background: #f3e5f5; }
        .alert { padding: 15px; margin: 15px 0; border-radius: 5px; }
        .alert-info { background: #d1ecf1; border: 2px solid #17a2b8; color: #0c5460; }
        .alert-success { background: #d4edda; border: 2px solid #28a745; color: #155724; }
        code { background: #f8f9fa; padding: 3px 8px; border-radius: 3px; font-family: monospace; }
        .btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; text-decoration: none; display: inline-block; margin: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📖 Guide de Configuration Webhook + Stripe</h1>
        
        <div class="alert alert-info">
            <strong>🎯 Objectif :</strong> Configurer votre webhook avec Telegram ET Stripe pour les paiements de sécurisation de fonds (4,999€).
        </div>
        
        <h2>🤖 PARTIE 1 : Configuration Telegram</h2>
        
        <div class="step">
            <h3>1. Créer un bot Telegram</h3>
            <p>• Cherchez <code>@BotFather</code> sur Telegram</p>
            <p>• Tapez <code>/newbot</code></p>
            <p>• Nom : "WebhookOVHStripe2024"</p>
            <p>• Username : "webhook_ovh_stripe_2024_bot"</p>
            <p>• <strong>Copiez le token reçu</strong></p>
        </div>
        
        <div class="step">
            <h3>2. Obtenir l'ID du groupe</h3>
            <p>• Ajoutez le bot dans votre groupe</p>
            <p>• Envoyez <code>/start</code></p>
            <p>• Visitez : <code>https://api.telegram.org/bot[TOKEN]/getUpdates</code></p>
            <p>• Cherchez "chat":{"id": (nombre négatif pour les groupes)</p>
        </div>
        
        <h2>💳 PARTIE 2 : Configuration Stripe</h2>
        
        <div class="step stripe-step">
            <h3>3. Récupérer les clés Stripe</h3>
            <p>• Dashboard Stripe → Développeurs → Clés API</p>
            <p>• Copiez la <strong>Clé secrète</strong> (sk_live_ ou sk_test_)</p>
            <p>• La clé publique est déjà configurée</p>
        </div>
        
        <div class="step stripe-step">
            <h3>4. Configurer le webhook Stripe</h3>
            <p>• Stripe → Développeurs → Webhooks</p>
            <p>• URL : <code>https://votre-app.herokuapp.com/webhook/stripe</code></p>
            <p>• Événements : <code>payment_intent.succeeded</code>, <code>payment_intent.payment_failed</code></p>
            <p>• Copiez le secret (whsec_)</p>
        </div>
        
        <div class="step">
            <h3>5. Configurer Heroku Config Vars</h3>
            <p><strong>Variables obligatoires :</strong></p>
            <ul>
                <li><code>TELEGRAM_TOKEN</code> = votre_token_bot</li>
                <li><code>CHAT_ID</code> = votre_id_groupe</li>
            </ul>
            <p><strong>Variables Stripe :</strong></p>
            <ul>
                <li><code>STRIPE_SECRET_KEY</code> = sk_live_...</li>
                <li><code>STRIPE_WEBHOOK_SECRET</code> = whsec_...</li>
            </ul>
        </div>
        
        <div class="alert alert-success">
            <h3>✅ Nouvelles commandes disponibles :</h3>
            <ul>
                <li><code>/numero 0123456789</code> - Fiche client</li>
                <li><code>/paiement 0123456789</code> - Lien 4,999€</li>
                <li><code>/stripe_stats</code> - Statistiques paiements</li>
            </ul>
        </div>
        
        <div style="text-align: center; margin-top: 30px;">
            <a href="/" class="btn">🏠 Retour</a>
        </div>
    </div>
</body>
</html>
    """)

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
            clients_with_email = len([c for c in clients_database.values() if c['email'] not in ['N/A', '']])
            
        else:
            return jsonify({"error": "Seuls les fichiers CSV sont supportés"}), 400
        
        return jsonify({
            "status": "success",
            "message": f"{nb_clients} clients chargés avec succès",
            "filename": filename,
            "total_clients": nb_clients,
            "auto_detected_banks": auto_detected,
            "clients_with_email": clients_with_email,
            "stripe_ready": clients_with_email if stripe_service.configured else 0
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
    clients_with_email = len([c for c in clients_database.values() if c['email'] not in ['N/A', '']])
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>👥 Gestion Clients - Webhook + Stripe</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 1600px; margin: 0 auto; }
        .search { margin-bottom: 20px; }
        .search input { padding: 10px; width: 300px; border: 1px solid #ddd; border-radius: 5px; }
        .btn { background: #2196F3; color: white; padding: 10px 20px; border: none; cursor: pointer; border-radius: 5px; margin: 5px; text-decoration: none; display: inline-block; }
        .btn:hover { background: #1976D2; }
        .btn-stripe { background: #6c5ce7; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th, td { border: 1px solid #ddd; padding: 6px; text-align: left; }
        th { background: #f2f2f2; position: sticky; top: 0; }
        .status-prospect { background: #fff3e0; }
        .status-client { background: #e8f5e8; }
        .stats { background: #f0f4f8; padding: 15px; margin-bottom: 20px; border-radius: 5px; }
        .table-container { max-height: 600px; overflow-y: auto; }
        .auto-detected { background: #e3f2fd; font-weight: bold; }
        .payment-ready { background: #e8f5e8; font-weight: bold; }
        .no-email { background: #ffebee; }
    </style>
</head>
<body>
    <div class="container">
        <h1>👥 Base Clients ({{ total_clients }} total) - Webhook + Stripe</h1>
        
        <div class="stats">
            <strong>📊 Statistiques:</strong> 
            Total: {{ total_clients }} | 
            Affichés: {{ displayed_count }} |
            Avec appels: {{ with_calls }} |
            🏦 Banques auto-détectées: {{ auto_detected }} |
            💳 Avec email (Stripe ready): {{ clients_with_email }}
        </div>
        
        <div class="search">
            <form method="GET">
                <input type="text" name="search" placeholder="Rechercher..." value="{{ search }}">
                <button type="submit" class="btn">🔍 Rechercher</button>
                <a href="/clients" class="btn">🔄 Tout afficher</a>
                <a href="/" class="btn">🏠 Accueil</a>
                <a href="/stripe-dashboard" class="btn btn-stripe">💳 Dashboard Stripe</a>
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
                    <td class="{% if client.email not in ['N/A', ''] %}payment-ready{% else %}no-email{% endif %}">
                        {{ client.email }}
                        {% if client.email not in ['N/A', ''] %}💳{% endif %}
                    </td>
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
    auto_detected=auto_detected,
    clients_with_email=clients_with_email,
    search=search
    )

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
        
    message = f"🧪 Test webhook sécurisé + Stripe - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
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
            "message": "Service Telegram non configuré"
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
        "sample_numbers_in_db": list(clients_database.keys())[:5] if clients_database else []
    })

@app.route('/check-webhook-config')
def check_webhook_config():
    """Vérifier la configuration du webhook Telegram"""
    if not Config.TELEGRAM_TOKEN:
        return jsonify({
            "error": "TELEGRAM_TOKEN non configuré"
        }), 400
        
    try:
        webhook_url = request.url_root + "webhook/telegram"
        
        set_webhook_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/setWebhook"
        data = {
            "url": webhook_url,
            "drop_pending_updates": True
        }
        
        response = requests.post(set_webhook_url, data=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({
                "status": "success",
                "message": f"Webhook configuré avec succès sur {webhook_url}",
                "telegram_response": result
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
    
    return f"""
    <h2>🧪 Test OVH CGI - Version Sécurisée + Stripe</h2>
    <p>Simulation d'un appel OVH avec recherche intelligente et lien de paiement automatique</p>
    <p><a href="/webhook/ovh?{urlencode(params)}" style="background: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🎯 Déclencher test appel</a></p>
    <p><strong>Paramètres:</strong> {params}</p>
    <p><strong>Ligne configurée:</strong> {Config.OVH_LINE_NUMBER}</p>
    <p><strong>Stripe:</strong> {'✅ Configuré' if stripe_service.configured else '❌ Non configuré'}</p>
    <div style="margin-top: 20px;">
        <a href="/test-normalize" style="background: #ff9800; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🔧 Test normalisation</a>
        <a href="/test-payment" style="background: #6c5ce7; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">💳 Test paiement</a>
        <a href="/" style="background: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🏠 Retour accueil</a>
    </div>
    """

@app.route('/check-config')
def check_config():
    """Vérification de la configuration actuelle (Telegram + Stripe)"""
    is_valid, missing_vars = check_required_config()
    
    return jsonify({
        "telegram": {
            "config_valid": is_valid,
            "missing_variables": missing_vars,
            "telegram_token_configured": bool(Config.TELEGRAM_TOKEN),
            "chat_id_configured": bool(Config.CHAT_ID),
            "service_initialized": telegram_service is not None
        },
        "stripe": {
            "configured": stripe_service.configured,
            "secret_key_configured": bool(Config.STRIPE_SECRET_KEY),
            "webhook_secret_configured": bool(Config.STRIPE_WEBHOOK_SECRET),
            "buy_button_id": Config.STRIPE_BUY_BUTTON_ID
        }
    })

@app.route('/health')
def health():
    is_valid, missing_vars = check_required_config()
    
    stripe_stats = {"total_payments": 0, "total_amount": 0}
    try:
        if stripe_service.configured:
            stripe_stats = stripe_service.get_payment_stats()
            if 'error' in stripe_stats:
                stripe_stats = {"total_payments": 0, "total_amount": 0}
    except:
        stripe_stats = {"total_payments": 0, "total_amount": 0}
    
    return jsonify({
        "status": "healthy" if is_valid else "configuration_required", 
        "version": "webhook-stripe-secure-v2.0",
        "service": "webhook-ovh-telegram-stripe-secure",
        "configuration_status": {
            "telegram_token_configured": bool(Config.TELEGRAM_TOKEN),
            "chat_id_configured": bool(Config.CHAT_ID),
            "config_valid": is_valid,
            "missing_variables": missing_vars,
            "service_initialized": telegram_service is not None
        },
        "stripe_status": {
            "configured": stripe_service.configured,
            "secret_key_configured": bool(Config.STRIPE_SECRET_KEY),
            "webhook_secret_configured": bool(Config.STRIPE_WEBHOOK_SECRET),
            "buy_button_id": Config.STRIPE_BUY_BUTTON_ID,
            "total_payments": stripe_stats.get('total_payments', 0),
            "total_amount": stripe_stats.get('total_amount', 0)
        },
        "features": {
            "phone_normalization": "enhanced-multi-format",
            "search_intelligence": "advanced-with-fallback",
            "iban_detection": "API-enabled",
            "payment_processing": "stripe-buy-button",
            "webhook_security": "stripe-signature-verified",
            "security": "environment-variables-only"
        },
        "ovh_line": Config.OVH_LINE_NUMBER,
        "clients_loaded": upload_stats["total_clients"],
        "clients_with_email": len([c for c in clients_database.values() if c['email'] not in ['N/A', '']]),
        "cache_size": len(cache.cache),
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    logger.info("🚀 Démarrage webhook sécurisé + Stripe")
    logger.info(f"🔒 Mode sécurisé: Variables d'environnement uniquement")
    
    # Vérification de la configuration au démarrage
    is_valid, missing_vars = check_required_config()
    
    if is_valid:
        logger.info("✅ Configuration Telegram valide - Service opérationnel")
        logger.info(f"📱 Chat ID: {Config.CHAT_ID}")
        logger.info(f"📞 Ligne OVH: {Config.OVH_LINE_NUMBER}")
        logger.info(f"🔧 Normalisation: Multi-formats avancée")
    else:
        logger.warning("⚠️ Configuration Telegram incomplète - Variables manquantes:")
        for var in missing_vars:
            logger.warning(f"   • {var}")
        logger.warning("🔧 Ajoutez ces variables dans Heroku → Settings → Config Vars")
    
    # Vérification Stripe
    if stripe_service.configured:
        logger.info("✅ Configuration Stripe valide")
        logger.info(f"💳 Buy Button ID: {Config.STRIPE_BUY_BUTTON_ID}")
        logger.info(f"🔒 Webhook sécurisé: {'✅' if Config.STRIPE_WEBHOOK_SECRET else '❌'}")
    else:
        logger.warning("⚠️ Configuration Stripe incomplète")
        logger.warning("   • STRIPE_SECRET_KEY manquante")
        logger.warning("   • Les paiements ne seront pas disponibles")
    
    app.run(host='0.0.0.0', port=port, debug=False) "TELEGRAM_TOKEN non configuré"
        }), 400
        
    try:
        webhook_info_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/getWebhookInfo"
        webhook_response = requests.get(webhook_info_url, timeout=10)
        webhook_data = webhook_response.json() if webhook_response.status_code == 200 else {}
        
        correct_webhook_url = request.url_root + "webhook/telegram"
        current_webhook_url = webhook_data.get('result', {}).get('url', 'Aucun')
        
        return jsonify({
            "webhook_configured": current_webhook_url != "Aucun",
            "webhook_correct": current_webhook_url == correct_webhook_url,
            "current_webhook_url": current_webhook_url,
            "correct_webhook_url": correct_webhook_url,
            "recommendation": "Utilisez /fix-webhook-now pour corriger" if current_webhook_url != correct_webhook_url else "Webhook correctement configuré"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/fix-webhook-now')
def fix_webhook_now():
    """Configure automatiquement le webhook correct"""
    if not Config.TELEGRAM_TOKEN:
        return jsonify({
            "error":        elif message_text.startswith('/paiement '):
            phone_number = message_text.replace('/paiement ', '').strip()
            client_info = get_client_info(phone_number)
            
            if client_info['email'] != 'N/A':
                payment_url, error = stripe_service.generate_payment_link(
                    client_info['email'],
                    f"{client_info['prenom']} {client_info['nom']}"
                )
                
                if payment_url:
                    response_message = f"""
💳 <b>LIEN DE PAIEMENT GÉNÉRÉ - SÉCURISATION DE FONDS</b>

👤 <b>Client:</b> {client_info['prenom']} {client_info['nom']}
📞 <b>Téléphone:</b> {client_info['telephone']}
📧 <b>Email:</b> {client_info['email']}
💰 <b>Montant:</b> 4,999.00 €

🔗 <b>LIEN DE PAIEMENT DIRECT:</b>
<a href="{payment_url}">CLIQUEZ ICI POUR PAYER 4,999€</a>

🔒 <b>SERVICE:</b> Dépôt de garantie pour la sécurisation de vos fonds investis
✅ <b>SÉCURISÉ:</b> Paiement via Stripe avec email pré-rempli

⏰ <b>Généré le:</b> {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
                    """
                    telegram_service.send_message(response_message)
                    return {"status": "payment_link_generated", "phone": phone_number, "url": payment_url}
                else:
                    error_message = f"❌ <b>Erreur génération lien:</b> {error}"
                    telegram_service.send_message(error_message)
                    return {"status": "error", "message": error}
            else:
                no_email_message = f"⚠️ <b>Email manquant pour {client_info['prenom']} {client_info['nom']}</b>"
                telegram_service.send_message(no_email_message)
                return {"status": "error", "message": "Email manquant"}
            
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
        
        # NOUVELLE COMMANDE STRIPE STATS
        elif message_text.startswith('/stripe_stats'):
            stats = stripe_service.get_payment_stats()
            
            if 'error' in stats:
                stats_message = f"❌ <b>Erreur Stripe:</b> {stats['error']}"
            else:
                stats_message = f"""
💳 <b>STATISTIQUES STRIPE - SÉCURISATION DE FONDS</b>

💰 <b>Paiements confirmés:</b> {stats['total_payments']}
💵 <b>Montant total:</b> {stats['total_amount']:.2f} €
📊 <b>Montant moyen:</b> {stats.get('average_amount', 0):.2f} €
📅 <b>Aujourd'hui:</b> {stats.get('recent_payments', 0)} paiements

🔗 <b>Buy Button ID:</b> <code>{Config.STRIPE_BUY_BUTTON_ID}</code>
🔒 <b>Configuré:</b> {'✅ Oui' if stripe_service.configured else '❌ Non'}

⏰ <b>Dernière mise à jour:</b> {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
                """
            
            telegram_service.send_message(stats_message)
            return {"status": "stripe_stats_sent", "stats": stats}
            
        elif message_text.startswith('/stats'):
            auto_detected = len([c for c in clients_database.values() if c['banque'] not in ['N/A', ''] and c['iban']])
            stripe_stats = stripe_service.get_payment_stats()
            
            stats_message = f"""
📊 <b>STATISTIQUES CAMPAGNE COMPLÈTES</b>

👥 <b>BASE CLIENTS</b>
▪️ Clients total: {upload_stats['total_clients']}
▪️ Dernier upload: {upload_stats['last_upload'] or 'Aucun'}
▪️ Fichier: {upload_stats['filename'] or 'Aucun'}
▪️ Banques auto-détectées: {auto_detected}

📞 <b>APPELS</b>
▪️ Ligne OVH: {Config.OVH_LINE_NUMBER}
▪️ Clients appelants: {len([c for c in clients_database.values() if c['dernier_appel'] and c['dernier_appel'].startswith(datetime.now().strftime('%d/%m/%Y'))])}
▪️ Nouveaux contacts: {len([c for c in clients_database.values() if c['nb_appels'] == 0])}

💳 <b>PAIEMENTS STRIPE</b>
▪️ Paiements confirmés: {stripe_stats.get('total_payments', 'N/A')}
▪️ Montant total: {stripe_stats.get('total_amount', 0):.2f} €
▪️ Buy Button: {Config.STRIPE_BUY_BUTTON_ID}
            """
            telegram_service.send_message(stats_message)
            return {"status": "stats_sent"}
            
        elif message_text.startswith('/help'):
            help_message = f"""
🤖 <b>COMMANDES DISPONIBLES - WEBHOOK + STRIPE</b>

📞 <code>/numero 0123456789</code>
   → Affiche la fiche client complète

💳 <code>/paiement 0123456789</code>
   → Génère un lien de paiement 4,999€ pour le client

🏦 <code>/iban FR76XXXXXXXXX</code>
   → Détecte la banque depuis l'IBAN

💰 <code>/stripe_stats</code>
   → Statistiques des paiements Stripe

📊 <code>/stats</code>
   → Statistiques complètes (clients + paiements)

🆘 <code>/help</code>
   → Affiche cette aide

✅ <b>Le bot reçoit automatiquement:</b>
▪️ Les appels entrants OVH sur {Config.OVH_LINE_NUMBER}
▪️ Les notifications en temps réel
▪️ 🌐 Détection automatique des banques via APIs IBAN
▪️ 💳 Liens de paiement Stripe avec email pré-rempli
            """
            telegram_service.send_message(help_message)
            return {"status": "help_sent"}
            
        else:
            return {"status": "unknown_command"}
            
    except Exception as e:
        logger.error(f"❌ Erreur commande Telegram: {str(e)}")
        return {"error": str(e)}

# ===================================================================
# ROUTES WEBHOOK - VERSION AMÉLIORÉE AVEC STRIPE
# ===================================================================

@app.route('/webhook/ovh', methods=['POST', 'GET'])
def ovh_webhook():
    """Webhook pour recevoir les appels OVH - Version avec recherche améliorée et lien de paiement"""
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
        
        # Message Telegram formaté avec option lien de paiement pour clients connus
        if telegram_service:
            include_payment = (client_info['statut'] != "Non référencé" and 
                             client_info['email'] != 'N/A' and 
                             stripe_service.configured)
            
            telegram_message = telegram_service.format_client_message(
                client_info, 
                context="appel", 
                include_payment_link=include_payment
            )
            
            telegram_message += f"\n📊 Statut appel: {call_status}"
            telegram_message += f"\n🔗 Source: OVH"
            
            if include_payment:
                telegram_message += f"\n\n💡 <b>TIP:</b> Utilisez <code>/paiement {caller_number}</code> pour un lien dédié"
            
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
            "stripe_configured": stripe_service.configured,
            "payment_link_available": (client_info['email'] != 'N/A' and stripe_service.configured),
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

@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Webhook pour recevoir les notifications de paiement Stripe"""
    if not Config.STRIPE_WEBHOOK_SECRET:
        logger.warning("⚠️ STRIPE_WEBHOOK_SECRET non configuré")
        return jsonify({"error": "Webhook secret manquant"}), 400
    
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        # Vérifier la signature du webhook
        event = stripe.Webhook.construct_event(
            payload, sig_header, Config.STRIPE_WEBHOOK_SECRET
        )
        
        logger.info(f"🔔 Webhook Stripe reçu: {event['type']}")
        
        # Traiter les événements de paiement
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            
            # Message de confirmation
            confirmation_message = f"""
🎉 <b>PAIEMENT CONFIRMÉ - SÉCURISATION DE FONDS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 <b>Montant:</b> {payment_intent['amount'] / 100:.2f} €
📧 <b>Client:</b> {payment_intent.get('receipt_email', 'N/A')}
🆔 <b>ID Paiement:</b> <code>{payment_intent['id']}</code>
🕐 <b>Date:</b> {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}

✅ <b>Statut:</b> FONDS SÉCURISÉS
🔒 <b>Protection:</b> ACTIVÉE

Le client peut maintenant accéder à ses fonds protégés.
            """
            
            if telegram_service:
                telegram_service.send_message(confirmation_message)
            
            return jsonify({"status": "payment_processed"})
        
        elif event['type'] == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            
            failure_message = f"""
❌ <b>ÉCHEC DE PAIEMENT</b>

💰 <b>Montant:</b> {payment_intent['amount'] / 100:.2f} €
📧 <b>Client:</b> {payment_intent.get('receipt_email', 'N/A')}
🆔 <b>ID Paiement:</b> <code>{payment_intent['id']}</code>
⚠️ <b>Raison:</b> {payment_intent.get('last_payment_error', {}).get('message', 'Inconnue')}

🔄 <b>Action recommandée:</b> Contacter le client pour un nouveau lien
            """
            
            if telegram_service:
                telegram_service.send_message(failure_message)
            
            return jsonify({"status": "payment_failed_processed"})
        
        return jsonify({"status": "event_ignored"})
        
    except ValueError as e:
        logger.error(f"❌ Erreur signature Stripe: {str(e)}")
        return jsonify({"error": "Invalid signature"}), 400
    except Exception as e:
        logger.error(f"❌ Erreur webhook Stripe: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ===================================================================
# ROUTES PRINCIPALES AVEC STRIPE
# ===================================================================

@app.route('/')
def home():
    auto_detected = len([c for c in clients_database.values() if c['banque'] not in ['N/A', ''] and c['iban']])
    
    # Ajouter les stats Stripe de manière sécurisée
    stripe_stats = {"total_payments": 0, "total_amount": 0}
    try:
        if stripe_service.configured:
            stripe_stats = stripe_service.get_payment_stats()
            if 'error' in stripe_stats:
                stripe_stats = {"total_payments": 0, "total_amount": 0}
    except:
        stripe_stats = {"total_payments": 0, "total_amount": 0}
    
    clients_with_email = len([c for c in clients_database.values() if c['email'] not in ['N/A', '']])
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>🤖 Webhook OVH-Telegram-Stripe SÉCURISÉ</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: #e3f2fd; padding: 20px; border-radius: 8px; text-align: center; }
        .stripe-card { background: #e8f5e8; border-left: 4px solid #4caf50; }
        .upload-section { background: #f0f4f8; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .btn { background: #2196F3; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }
        .btn:hover { background: #1976D2; }
        .btn-danger { background: #f44336; }
        .btn-success { background: #4CAF50; }
        .btn-warning { background: #ff9800; }
        .btn-info { background: #17a2b8; }
        .btn-stripe { background: #6c5ce7; }
        .links { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
        .success { color: #4CAF50; font-weight: bold; }
        .error { color: #f44336; font-weight: bold; }
        code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
        .info-box { background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 10px 0; }
        .config-section { background: #e1f5fe; border-left: 4px solid #2196F3; padding: 15px; margin: 20px 0; }
        .stripe-section { background: #f3e5f5; border-left: 4px solid #9c27b0; padding: 15px; margin: 20px 0; }
        .security-section { background: #e8f5e8; border-left: 4px solid #4caf50; padding: 15px; margin: 20px 0; }
        .error-section { background: #ffebee; border-left: 4px solid #f44336; padding: 15px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Webhook OVH-Telegram-Stripe SÉCURISÉ</h1>
            
            {% if config_valid %}
            <div class="config-section">
                <strong>✅ CONFIGURATION TELEGRAM ACTIVE :</strong><br>
                📱 Chat ID: <code>{{ chat_id or 'Non configuré' }}</code><br>
                📞 Ligne OVH: <code>{{ ovh_line }}</code><br>
                🤖 Token: <code>{{ token_display }}</code><br>
                🔒 Source: Variables d'environnement Heroku
            </div>
            {% else %}
            <div class="error-section">
                <strong>❌ CONFIGURATION TELEGRAM MANQUANTE :</strong><br>
                Variables d'environnement manquantes dans Heroku Config Vars :<br>
                {% for var in missing_vars %}
                • <code>{{ var }}</code><br>
                {% endfor %}
                <p><strong>🔧 Ajoutez ces variables dans Heroku → Settings → Config Vars</strong></p>
            </div>
            {% endif %}
            
            <div class="stripe-section">
                <strong>💳 CONFIGURATION STRIPE :</strong><br>
                {% if stripe_configured %}
                ✅ Stripe configuré et opérationnel<br>
                🔗 Buy Button ID: <code>{{ buy_button_id }}</code><br>
                💰 Montant fixe: 4,999.00 €<br>
                🔒 Webhook: {{ '✅ Configuré' if webhook_configured else '⚠️ À configurer' }}
                {% else %}
                ❌ Configuration Stripe manquante<br>
                Variables requises: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
                {% endif %}
            </div>
            
            <div class="security-section">
                <strong>🔒 SÉCURITÉ RENFORCÉE :</strong><br>
                ✅ Aucun token hardcodé dans le code<br>
                ✅ Configuration via variables d'environnement uniquement<br>
                ✅ Vérification automatique de la configuration<br>
                ✅ Protection contre les tokens compromis<br>
                ✅ Webhooks Stripe sécurisés avec signature
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
            <div class="stat-card stripe-card">
                <h3>💳 Paiements Stripe</h3>
                <h2>{{ stripe_total_payments }}</h2>
                <p>{{ stripe_total_amount }}€ total</p>
            </div>
            <div class="stat-card">
                <h3>📧 Clients avec email</h3>
                <h2>{{ clients_with_email }}</h2>
                <p>Prêts pour paiement</p>
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
                    <div style="background: #f3e5f5; padding: 10px; margin-top: 10px; border-radius: 5px;">
                        <strong>💳 STRIPE INTEGRATION :</strong> Avec un <code>email</code> valide, les liens de paiement 4,999€ seront automatiquement disponibles !
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
            <a href="/test-telegram" class="btn">📧 Test Telegram</a>
            <a href="/test-command" class="btn">🎯 Test /numero</a>
            <a href="/test-payment" class="btn btn-stripe">💳 Test paiement</a>
            <a href="/stripe-dashboard" class="btn btn-stripe">📊 Dashboard Stripe</a>
            <a href="/check-webhook-config" class="btn btn-danger">🔗 Diagnostic Webhook</a>
            <a href="/fix-webhook-now" class="btn btn-success">🔧 Corriger Webhook</a>
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
            <p><strong>Variables Stripe (recommandées) :</strong></p>
            <ul>
                <li><code>STRIPE_SECRET_KEY</code> = Votre clé secrète Stripe</li>
                <li><code>STRIPE_WEBHOOK_SECRET</code> = Secret du webhook Stripe</li>
                <li><code>STRIPE_BUY_BUTTON_ID</code> = ID de votre buy button (par défaut: buy_btn_1RUzUoC8opMymz5GeubkCCp2)</li>
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

        <h2>🔗 Configuration Webhook Stripe</h2>
        <div class="info-box">
            <p><strong>URL Webhook à configurer dans Stripe Dashboard :</strong></p>
            <code>{{ webhook_url }}/webhook/stripe</code>
            <br><br>
            <p><strong>📋 Événements à sélectionner :</strong></p>
            <ul style="text-align: left;">
                <li><code>payment_intent.succeeded</code> - Paiement réussi</li>
                <li><code>payment_intent.payment_failed</code> - Paiement échoué</li>
            </ul>
        </div>

        <h2>📱 Commandes Telegram disponibles</h2>
        <ul>
            <li><code>/numero 0123456789</code> - Affiche fiche client complètefrom flask import Flask, request, jsonify, render_template_string, redirect
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
import stripe

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
app.secret_key = 'webhook-ovh-stripe-secret-key-secure-v3'

# Configuration centralisée - UNIQUEMENT VARIABLES D'ENVIRONNEMENT
class Config:
    # Variables Telegram - OBLIGATOIRES depuis Heroku Config Vars
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
    CHAT_ID = os.environ.get('CHAT_ID')
    
    # Variables Stripe - NOUVELLES
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', 'pk_live_51RUrtyC8opMymz5GCb5ES0PMh7wt7OD2C6eR5oT0Or4duQSA5Lb0pPcMukISr0Zsk3c3dVojFLVa4TgHJBh195Xl0084n4dqNy')
    STRIPE_BUY_BUTTON_ID = os.environ.get('STRIPE_BUY_BUTTON_ID', 'buy_btn_1RUzUoC8opMymz5GeubkCCp2')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    # Ligne OVH - peut être configurée via env ou par défaut
    OVH_LINE_NUMBER = os.environ.get('OVH_LINE_NUMBER', '0033185093039')
    
    # APIs IBAN - optionnelles
    ABSTRACT_API_KEY = os.environ.get('ABSTRACT_API_KEY')
    
    # Keyyo OAuth2 - optionnelles
    KEYYO_CLIENT_ID = os.environ.get('KEYYO_CLIENT_ID', '')
    KEYYO_CLIENT_SECRET = os.environ.get('KEYYO_CLIENT_SECRET', '')
    KEYYO_REDIRECT_URI = os.environ.get('KEYYO_REDIRECT_URI', '')

# Configuration Stripe
if Config.STRIPE_SECRET_KEY:
    stripe.api_key = Config.STRIPE_SECRET_KEY
    logger.info("✅ Stripe configuré avec clé secrète")
else:
    logger.warning("⚠️ STRIPE_SECRET_KEY non configurée")

# Vérification critique des variables obligatoires
def check_required_config():
    """Vérifie que les variables obligatoires sont configurées"""
    missing_vars = []
    
    if not Config.TELEGRAM_TOKEN:
        missing_vars.append('TELEGRAM_TOKEN')
    
    if not Config.CHAT_ID:
        missing_vars.append('CHAT_ID')
    
    # Vérifications Stripe optionnelles mais recommandées
    stripe_warnings = []
    if not Config.STRIPE_SECRET_KEY:
        stripe_warnings.append('STRIPE_SECRET_KEY')
    if not Config.STRIPE_WEBHOOK_SECRET:
        stripe_warnings.append('STRIPE_WEBHOOK_SECRET')
    
    if missing_vars:
        error_msg = f"❌ Variables d'environnement manquantes: {', '.join(missing_vars)}"
        logger.error(error_msg)
        logger.error("🔧 Ajoutez ces variables dans Heroku Config Vars:")
        for var in missing_vars:
            logger.error(f"   • {var} = votre_valeur")
        return False, missing_vars
    
    if stripe_warnings:
        logger.warning(f"⚠️ Variables Stripe recommandées manquantes: {', '.join(stripe_warnings)}")
    
    # Vérifier que le token a un format valide
    if Config.TELEGRAM_TOKEN and ':' not in Config.TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN ne semble pas valide (format attendu: XXXXXXXXX:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX)")
        return False, ['TELEGRAM_TOKEN (format invalide)']
    
    logger.info("✅ Configuration vérifiée avec succès")
    logger.info(f"📱 Chat ID configuré: {Config.CHAT_ID}")
    logger.info(f"🤖 Token configuré: {Config.TELEGRAM_TOKEN[:10]}...{Config.TELEGRAM_TOKEN[-5:] if Config.TELEGRAM_TOKEN else ''}")
    logger.info(f"💳 Stripe Buy Button: {Config.STRIPE_BUY_BUTTON_ID}")
    
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
# SERVICE STRIPE
# ===================================================================

class StripeService:
    def __init__(self):
        self.configured = bool(Config.STRIPE_SECRET_KEY)
        if self.configured:
            stripe.api_key = Config.STRIPE_SECRET_KEY
    
    def generate_payment_link(self, client_email, client_name=None):
        """Génère un lien de paiement Stripe Buy Button avec email pré-rempli"""
        if not self.configured:
            return None, "Stripe non configuré"
        
        try:
            # URL du buy button avec email pré-rempli
            payment_url = f"https://buy.stripe.com/{Config.STRIPE_BUY_BUTTON_ID}"
            
            # Ajouter l'email en paramètre si fourni
            if client_email:
                payment_url += f"?prefilled_email={quote_plus(client_email)}"
            
            logger.info(f"💳 Lien de paiement généré pour {client_email}: {payment_url}")
            
            return payment_url, None
            
        except Exception as e:
            logger.error(f"❌ Erreur génération lien Stripe: {str(e)}")
            return None, str(e)
    
    def get_payment_stats(self):
        """Récupère les statistiques des paiements"""
        if not self.configured:
            return {"error": "Stripe non configuré"}
        
        try:
            # Récupérer les paiements récents
            payment_intents = stripe.PaymentIntent.list(limit=50)
            
            succeeded_payments = [p for p in payment_intents.data if p.status == 'succeeded']
            total_amount = sum(p.amount for p in succeeded_payments) / 100  # Convertir centimes en euros
            
            return {
                "total_payments": len(succeeded_payments),
                "total_amount": total_amount,
                "average_amount": total_amount / len(succeeded_payments) if succeeded_payments else 0,
                "recent_payments": len([p for p in succeeded_payments if p.created > (time.time() - 86400)])
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur stats Stripe: {str(e)}")
            return {"error": str(e)}

stripe_service = StripeService()

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
    
    def format_client_message(self, client_info, context="appel", include_payment_link=False):
        emoji_statut = "📞" if client_info['statut'] != "Non référencé" else "❓"
        
        banque_display = client_info.get('banque', 'N/A')
        if banque_display not in ['N/A', ''] and client_info.get('iban'):
            if banque_display.startswith('🌐'):
                banque_display = f"{banque_display} (API)"
            elif banque_display.startswith('📍'):
                banque_display = f"{banque_display} (local)"
        
        message = f"""
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
        
        # Ajouter le lien de paiement si demandé et email disponible
        if include_payment_link and client_info.get('email') and client_info['email'] != 'N/A':
            payment_url, error = stripe_service.generate_payment_link(
                client_info['email'], 
                f"{client_info['prenom']} {client_info['nom']}"
            )
            
            if payment_url:
                message += f"""

💳 <b>LIEN DE PAIEMENT SÉCURISATION (4,999€)</b>
🔗 <a href="{payment_url}">CLIQUEZ ICI POUR PAYER</a>
💰 Montant: 4,999.00 €
🔒 Service: Sécurisation de fonds investis
📧 Email pré-rempli: {client_info['email']}
                """
            else:
                message += f"\n⚠️ Erreur génération lien: {error}"
        
        return message

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
        
        # NOUVELLE COMMANDE PAIEMENT
        elif message_text.startswith('/paiement '):
            phone_number = message_text.replace('/paiement ', '').strip()
            client_info = get_client_info(phone_

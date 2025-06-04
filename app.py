# ===================================================================
# ROUTES DE TEST DTMF ET ADMINISTRATION
# ===================================================================

@app.route('/dtmf-admin')
def dtmf_admin():
    """Interface d'administration DTMF"""
    active_calls = dtmf_manager.get_active_calls()
    active_dtmf = dtmf_manager.get_active_dtmf_sessions()
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>📞 Administration DTMF - Temps Réel</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #007bff; }
        .dtmf-active { border-left-color: #28a745; }
        .btn { background: #007bff; color: white; padding: 8px 15px; border: none; border-radius: 3px; margin: 5px; text-decoration: none; display: inline-block; }
        .btn-success { background: #28a745; }
        .btn-warning { background: #ffc107; color: black; }
        .btn-danger { background: #dc3545; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background: #f2f2f2; }
        .stats { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 30px; }
        .refresh { float: right; }
    </style>
    <script>
        function refreshPage() {
            location.reload();
        }
        // Auto-refresh toutes les 5 secondes
        setInterval(refreshPage, 5000);
    </script>
</head>
<body>
    <div class="container">
        <h1>📞 Administration DTMF - Temps Réel
            <button onclick="refreshPage()" class="btn refresh">🔄 Actualiser</button>
        </h1>
        
        <div class="stats">
            <div class="card">
                <h3>📞 Appels Actifs</h3>
                <h2>{{ active_calls|length }}</h2>
            </div>
            <div class="card dtmf-active">
                <h3>🔢 Sessions DTMF</h3>
                <h2>{{ active_dtmf|length }}</h2>
            </div>
            <div class="card">
                <h3>⚙️ Configuration</h3>
                <p>{{ dtmf_config.digits_expected }} chiffres<br>{{ dtmf_config.timeout }}s timeout</p>
            </div>
        </div>
        
        <h2>📞 Appels en Cours</h2>
        <table>
            <tr>
                <th>📞 Numéro</th>
                <th>⏱️ Durée</th>
                <th>👨‍💼 Agent</th>
                <th>🔢 DTMF</th>
                <th>🎯 Actions</th>
            </tr>
            {% for caller, call_data in active_calls.items() %}
            <tr>
                <td><strong>{{ caller }}</strong></td>
                <td>{{ (current_time - call_data.start_time)|int }}s</td>
                <td>{{ call_data.agent_name }}</td>
                <td>
                    {% if caller in active_dtmf %}
                    <span style="color: green;">🟢 Actif ({{ active_dtmf[caller].digits or '⏳' }})</span>
                    {% else %}
                    <span style="color: gray;">⚪ Inactif</span>
                    {% endif %}
                </td>
                <td>
                    {% if caller not in active_dtmf %}
                    <a href="/start-dtmf/{{ caller }}" class="btn btn-success">🔢 Démarrer DTMF</a>
                    {% endif %}
                    <a href="/end-call/{{ caller }}" class="btn btn-danger">📴 Terminer</a>
                </td>
            </tr>
            {% endfor %}
            {% if not active_calls %}
            <tr><td colspan="5" style="text-align: center; color: gray;">Aucun appel actif</td></tr>
            {% endif %}
        </table>
        
        <h2>🔢 Sessions DTMF Actives</h2>
        <table>
            <tr>
                <th>📞 Numéro</th>
                <th>👨‍💼 Agent</th>
                <th>🔢 Code Actuel</th>
                <th>📊 Progression</th>
                <th>⏰ Temps Restant</th>
                <th>🎯 Actions</th>
            </tr>
            {% for caller, session in active_dtmf.items() %}
            <tr>
                <td><strong>{{ caller }}</strong></td>
                <td>{{ session.requested_by }}</td>
                <td><code>{{ session.digits or '(vide)' }}</code></td>
                <td>{{ session.digits|length }}/{{ dtmf_config.digits_expected }}</td>
                <td>{{ (session.timeout - (current_time - session.timestamp))|int }}s</td>
                <td>
                    <a href="/cancel-dtmf/{{ caller }}" class="btn btn-warning">❌ Annuler</a>
                </td>
            </tr>
            {% endfor %}
            {% if not active_dtmf %}
            <tr><td colspan="6" style="text-align: center; color: gray;">Aucune session DTMF active</td></tr>
            {% endif %}
        </table>
        
        <h2>🧪 Tests & Outils</h2>
        <div>
            <a href="/test-dtmf-workflow" class="btn btn-success">🧪 Test Workflow Complet</a>
            <a href="/simulate-dtmf?caller=0767328146&digit=1" class="btn">🔢 Simuler DTMF</a>
            <a href="/test-telegram" class="btn">📱 Test Telegram</a>
            <a href="/" class="btn">🏠 Retour Accueil</a>
        </div>
        
        <div style="margin-top: 30px; padding: 15px; background: #e9ecef; border-radius: 5px;">
            <h3>💡 Instructions pour les agents :</h3>
            <ol>
                <li>📞 <strong>Appel reçu</strong> → Notification automatique dans Telegram</li>
                <li>🎤 <strong>Demander au client</strong> → "Pouvez-vous taper votre code d'identification sur le téléphone ?"</li>
                <li>📱 <strong>Dans Telegram, taper :</strong> <code>/dtmf-request NUMERO_CLIENT</code></li>
                <li>🔢 <strong>Client tape son code</strong> → Résultat affiché automatiquement</li>
                <li>✅ <strong>Continuer l'entretien</strong> selon la validation du code</li>
            </ol>
        </div>
        
        <p style="color: gray; text-align: center; margin-top: 30px;">
            🔄 Page actualisée automatiquement toutes les 5 secondes
        </p>
    </div>
</body>
</html>
    """,
    active_calls=active_calls,
    active_dtmf=active_dtmf,
    current_time=time.time(),
    dtmf_config={
        'digits_expected': DTMFConfig.DTMF_DIGITS_EXPECTED,
        'timeout': DTMFConfig.DTMF_TIMEOUT
    }
    )

@app.route('/start-dtmf/<caller_number>')
def start_dtmf_route(caller_number):
    """Démarre une session DTMF via l'interface web"""
    agent_name = request.args.get('agent', 'Agent Web')
    reason = request.args.get('reason', 'identification via interface')
    
    success = dtmf_manager.request_dtmf(caller_number, agent_name, reason)
    
    if success:
        return jsonify({
            "status": "dtmf_started",
            "caller": caller_number,
            "agent": agent_name,
            "message": f"Session DTMF démarrée pour {caller_number}"
        })
    else:
        return jsonify({
            "status": "error",
            "message": "Impossible de démarrer la session DTMF"
        }), 400

@app.route('/end-call/<caller_number>')
def end_call_route(caller_number):
    """Termine un appel via l'interface web"""
    dtmf_manager.end_call(caller_number)
    return redirect('/dtmf-admin')

@app.route('/cancel-dtmf/<caller_number>')
def cancel_dtmf_route(caller_number):
    """Annule une session DTMF"""
    if caller_number in dtmf_manager.sessions:
        del dtmf_manager.sessions[caller_number]
        logger.info(f"🔢 Session DTMF annulée pour {caller_number}")
    return redirect('/dtmf-admin')

@app.route('/test-dtmf-workflow')
def test_dtmf_workflow():
    """Test complet du workflow DTMF"""
    test_caller = "0767328146"
    agent_name = "Agent Test"
    
    # 1. Simuler un appel entrant
    dtmf_manager.register_call(test_caller, {'agent_name': agent_name})
    
    # 2. Agent demande DTMF
    dtmf_manager.request_dtmf(test_caller, agent_name, "test workflow complet")
    
    # 3. Simuler que le client tape 1234
    dtmf_manager.add_digit(test_caller, '1')
    time.sleep(0.2)
    dtmf_manager.add_digit(test_caller, '2')
    time.sleep(0.2)
    dtmf_manager.add_digit(test_caller, '3')
    time.sleep(0.2)
    dtmf_manager.add_digit(test_caller, '4')
    
    return jsonify({
        "status": "workflow_test_completed",
        "scenario": "Workflow complet testé",
        "caller": test_caller,
        "agent": agent_name,
        "code_tested": "1234",
        "messages_sent": "5+ messages Telegram envoyés",
        "steps": [
            "✅ 1. Appel enregistré",
            "✅ 2. Agent demande DTMF", 
            "✅ 3. Progression DTMF (4 étapes)",
            "✅ 4. Code complet validé",
            "✅ 5. Fiche client complète envoyée"
        ],
        "next_action": "Vérifiez votre groupe Telegram pour voir tous les messages"
    })

@app.route('/simulate-dtmf')
def simulate_dtmf():
    """Simulate DTMF pour test"""
    caller = request.args.get('caller', '0767328146')
    digit = request.args.get('digit', '1')
    
    if not digit.isdigit() or len(digit) != 1:
        return jsonify({"error": "Le paramètre 'digit' doit être un chiffre unique"}), 400
    
    complete = dtmf_manager.add_digit(caller, digit)
    session = dtmf_manager.get_active_dtmf_sessions().get(caller)
    
    return jsonify({
        "status": "dtmf_simulated",
        "caller": caller,
        "digit_added": digit,
        "code_complete": complete,
        "current_digits": session['digits'] if session else '',
        "session_status": session['status'] if session else 'none',
        "next_step": f"Utilisez /simulate-dtmf?caller={caller}&digit=X pour continuer" if not complete else "Code complet traité"
    })

# ===================================================================
# ROUTES UTILITAIRES (INCHANGÉES MAIS ADAPTÉES)
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
    <title>👥 Gestion Clients - Webhook DTMF</title>
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
        .auto-detected { background: #e3f2fd; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>👥 Base Clients ({{ total_clients }} total) - Version DTMF</h1>
        
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
                <a href="/dtmf-admin" class="btn">🔢 Admin DTMF</a>
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
                    <th>🔢 Actions</th>
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
                    <td>
                        <a href="/start-dtmf/{{ tel }}?agent=WebAdmin" style="background: #4caf50; color: white; padding: 3px 8px; border-radius: 3px; text-decoration: none; font-size: 11px;">🔢 DTMF</a>
                    </td>
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
        
    message = f"🧪 Test webhook DTMF - Ligne {Config.OVH_LINE_NUMBER} - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
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
    test_numbers = [
        "0033745431189",
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
    if not Config.TELEGRAM_TOKEN:
        return jsonify({
            "error": "TELEGRAM_TOKEN non configuré"
        }), 400
        
    try:
        webhook_info_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/getWebhookInfo"
        webhook_response = requests.get(webhook_info_url, timeout=10)
        webhook_data = webhook_response.json() if webhook_response.status_code == 200 else {}
        
        correct_webhook_url = request.url_root + "webhook/telegram"
        current_webhook_url = webhook_data.get('result', {}).get('url', 'Aucun')
        
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
    
    return f"""
    <h2>🧪 Test OVH CGI - Version DTMF</h2>
    <p>Simulation d'un appel OVH avec support DTMF</p>
    <p><a href="/webhook/ovh?{urlencode(params)}" style="background: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🎯 Déclencher test appel</a></p>
    <p><strong>Paramètres:</strong> {params}</p>
    <p><strong>Ligne configurée:</strong> {Config.OVH_LINE_NUMBER}</p>
    <p><strong>DTMF:</strong> Ajoutez &dtmf=1 pour simuler un chiffre</p>
    <div style="margin-top: 20px;">
        <a href="/test-dtmf-workflow" style="background: #ff9800; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🧪 Test workflow DTMF</a>
        <a href="/dtmf-admin" style="background: #17a2b8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🔢 Admin DTMF</a>
        <a href="/" style="background: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🏠 Retour accueil</a>
    </div>
    """

@app.route('/health')
def health():
    is_valid, missing_vars = check_required_config()
    
    return jsonify({
        "status": "healthy" if is_valid else "configuration_required", 
        "version": "webhook-dtmf-v1.0",
        "service": "webhook-ovh-telegram-dtmf",
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
            "iban_detection": "API-enabled",
            "security": "environment-variables-only",
            "webhook_management": "automatic-configuration",
            "dtmf_support": "on-demand-agent-controlled"
        },
        "dtmf_status": {
            "active_calls": len(dtmf_manager.get_active_calls()),
            "active_dtmf_sessions": len(dtmf_manager.get_active_dtmf_sessions()),
            "timeout": DTMFConfig.DTMF_TIMEOUT,
            "digits_expected": DTMFConfig.DTMF_DIGITS_EXPECTED,
            "validation_enabled": DTMFConfig.DTMF_ENABLE_VALIDATION
        },
        "ovh_line": Config.OVH_LINE_NUMBER,
        "clients_loaded": upload_stats["total_clients"],
        "cache_size": len(cache.cache),
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    })

# ===================================================================
# ROUTES SUPPLÉMENTAIRES POUR DTMF
# ===================================================================

@app.route('/config-help')
def config_help():
    """Guide de configuration détaillé avec DTMF"""
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>📖 Guide Configuration - Webhook DTMF</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .step { background: #e9ecef; padding: 15px; margin: 15px 0; border-radius: 5px; border-left: 4px solid #007bff; }
        .alert { padding: 15px; margin: 15px 0; border-radius: 5px; }
        .alert-info { background: #d1ecf1; border: 2px solid #17a2b8; color: #0c5460; }
        .alert-success { background: #d4edda; border: 2px solid #28a745; color: #155724; }
        .alert-warning { background: #fff3cd; border: 2px solid #ffc107; color: #856404; }
        code { background: #f8f9fa; padding: 3px 8px; border-radius: 3px; font-family: monospace; }
        .btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; text-decoration: none; display: inline-block; margin: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📖 Guide Configuration Webhook avec DTMF</h1>
        
        <div class="alert alert-info">
            <strong>🎯 Objectif :</strong> Configurer votre webhook avec support DTMF pour l'identification des clients.
        </div>
        
        <div class="step">
            <h3>1. 🤖 Variables Telegram (Obligatoires)</h3>
            <p>Dans Heroku → Settings → Config Vars, ajoutez :</p>
            <ul>
                <li><code>TELEGRAM_TOKEN</code> = Token de votre bot (@BotFather)</li>
                <li><code>CHAT_ID</code> = ID de votre groupe Telegram</li>
            </ul>
        </div>
        
        <div class="step">
            <h3>2. 📞 Variables DTMF (Optionnelles)</h3>
            <p>Pour personnaliser le comportement DTMF :</p>
            <ul>
                <li><code>DTMF_TIMEOUT</code> = 30 (secondes d'attente, défaut: 30)</li>
                <li><code>DTMF_DIGITS_EXPECTED</code> = 4 (nb chiffres attendus, défaut: 4)</li>
                <li><code>DTMF_ENABLE_VALIDATION</code> = true (validation automatique, défaut: true)</li>
                <li><code>OVH_LINE_NUMBER</code> = 0033185093039 (votre ligne)</li>
            </ul>
        </div>
        
        <div class="step">
            <h3>3. 🔗 Configuration 3CX/OVH</h3>
            <p><strong>URLs à configurer dans votre IPBX :</strong></p>
            <p><strong>Appels entrants :</strong><br>
            <code>https://votre-app.herokuapp.com/webhook/ovh?caller=*CALLING*&callee=*CALLED*&type=*EVENT*</code></p>
            
            <p><strong>DTMF (codes tapés) :</strong><br>
            <code>https://votre-app.herokuapp.com/webhook/ovh?caller=*CALLING*&dtmf=*DTMF*</code></p>
        </div>
        
        <div class="step">
            <h3>4. ✅ Validation des codes clients</h3>
            <p>Le système valide automatiquement les codes avec :</p>
            <ul>
                <li>🏦 <strong>IBAN</strong> → 4 derniers chiffres</li>
                <li>📞 <strong>Téléphone</strong> → 4 derniers chiffres</li>
                <li>📮 <strong>Code postal</strong> → Code exact</li>
                <li>🎂 <strong>Année naissance</strong> → 4 chiffres</li>
                <li>🔑 <strong>Codes génériques</strong> → 1234, 0000, 9999, 1111</li>
            </ul>
        </div>
        
        <div class="alert alert-success">
            <h3>🔄 Workflow pour les agents :</h3>
            <ol>
                <li>📞 <strong>Appel reçu</strong> → Notification Telegram automatique</li>
                <li>🎤 <strong>Agent dit</strong> → "Tapez votre code d'identification sur le téléphone"</li>
                <li>📱 <strong>Agent tape</strong> → <code>/dtmf-request 0123456789</code> dans Telegram</li>
                <li>🔢 <strong>Client tape</strong> → Code capturé automatiquement</li>
                <li>✅ <strong>Validation</strong> → Résultat affiché en temps réel</li>
                <li>💼 <strong>Continue</strong> → Entretien selon validation</li>
            </ol>
        </div>
        
        <div class="alert alert-warning">
            <h3>⚠️ Points importants :</h3>
            <ul>
                <li>Le DTMF ne démarre QUE quand l'agent le demande</li>
                <li>Session expire après {{ timeout }}s sans activité</li>
                <li>Validation personnalisable selon vos besoins</li>
                <li>Interface d'administration temps réel disponible</li>
            </ul>
        </div>
        
        <div style="text-align: center; margin-top: 30px;">
            <a href="/" class="btn">🏠 Retour à l'accueil</a>
            <a href="/dtmf-admin" class="btn">🔢 Admin DTMF</a>
            <a href="/test-dtmf-workflow" class="btn">🧪 Test workflow</a>
        </div>
    </div>
</body>
</html>
    """, timeout=DTMFConfig.DTMF_TIMEOUT)

@app.route('/check-config')
def check_config():
    """Vérification complète de la configuration"""
    is_valid, missing_vars = check_required_config()
    
    return jsonify({
        "config_valid": is_valid,
        "missing_variables": missing_vars,
        "telegram_token_configured": bool(Config.TELEGRAM_TOKEN),
        "chat_id_configured": bool(Config.CHAT_ID),
        "telegram_token_format_valid": bool(Config.TELEGRAM_TOKEN and ':' in Config.TELEGRAM_TOKEN),
        "service_initialized": telegram_service is not None,
        "dtmf_config": {
            "timeout": DTMFConfig.DTMF_TIMEOUT,
            "digits_expected": DTMFConfig.DTMF_DIGITS_EXPECTED,
            "validation_enabled": DTMFConfig.DTMF_ENABLE_VALIDATION
        },
        "active_sessions": {
            "calls": len(dtmf_manager.get_active_calls()),
            "dtmf": len(dtmf_manager.get_active_dtmf_sessions())
        },
        "recommendations": [
            "Ajoutez TELEGRAM_TOKEN dans Heroku Config Vars" if not Config.TELEGRAM_TOKEN else None,
            "Ajoutez CHAT_ID dans Heroku Config Vars" if not Config.CHAT_ID else None,
            "Vérifiez le format du token (doit contenir :)" if Config.TELEGRAM_TOKEN and ':' not in Config.TELEGRAM_TOKEN else None,
            "Configurez les URLs DTMF dans votre IPBX" if is_valid else None
        ]
    })

# ===================================================================
# DÉMARRAGE DE L'APPLICATION
# ===================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    logger.info("🚀 Démarrage webhook avec DTMF à la demande")
    logger.info(f"🔒 Mode sécurisé: Variables d'environnement uniquement")
    
    # Vérification de la configuration au démarrage
    is_valid, missing_vars = check_required_config()
    
    if is_valid:
        logger.info("✅ Configuration valide - Service opérationnel")
        logger.info(f"📱 Chat ID: {Config.CHAT_ID}")
        logger.info(f"📞 Ligne OVH: {Config.OVH_LINE_NUMBER}")
        logger.info(f"🔢 DTMF: {DTMFConfig.DTMF_DIGITS_EXPECTED} chiffres, {DTMFConfig.DTMF_TIMEOUT}s timeout")
        logger.info(f"✅ Validation DTMF: {'Activée' if DTMFConfig.DTMF_ENABLE_VALIDATION else 'Désactivée'}")
        logger.info(f"🔧 Normalisation: Multi-formats avancée")
        
        # URLs de configuration pour 3CX/OVH
        logger.info("🔗 URLs à configurer dans votre IPBX :")
        logger.info(f"   📞 Appels: /webhook/ovh?caller=*CALLING*&callee=*CALLED*&type=*EVENT*")
        logger.info(f"   🔢 DTMF: /webhook/ovh?caller=*CALLING*&dtmf=*DTMF*")
        
        # Commandes Telegram disponibles
        logger.info("📱 Commandes Telegram disponibles :")
        logger.info("   🔢 /dtmf-request 0123456789 - Demander code client")
        logger.info("   📞 /calls - Appels actifs")
        logger.info("   📊 /stats - Statistiques")
        logger.info("   📋 /numero 0123456789 - Fiche client")
        
    else:
        logger.warning("⚠️ Configuration incomplète - Variables manquantes:")
        for var in missing_vars:
            logger.warning(f"   • {var}")
        logger.warning("🔧 Ajoutez ces variables dans Heroku → Settings → Config Vars")
        logger.warning("📖 Consultez /config-help pour le guide complet")
    
    logger.info(f"🌐 Démarrage sur le port {port}")
    logger.info("🔢 DTMF: Capture à la demande seulement (pas automatique)")
    logger.info("👨‍💼 Workflow: Agent → /dtmf-request → Client tape → Validation auto")
    
    app.run(host='0.0.0.0', port=port, debug=False)

# ===================================================================
# DOCUMENTATION INTÉGRÉE
# ===================================================================
"""
🤖 WEBHOOK OVH-TELEGRAM AVEC DTMF À LA DEMANDE

📋 FONCTIONNALITÉS PRINCIPALES :
- ✅ Réception d'appels OVH/3CX vers Telegram
- ✅ Recherche intelligente de clients (multi-formats)
- ✅ Détection automatique des banques via IBAN
- ✅ Capture DTMF à la demande par l'agent
- ✅ Validation automatique des codes clients
- ✅ Interface d'administration temps réel
- ✅ Configuration sécurisée (variables d'environnement)

🔢 WORKFLOW DTMF :
1. 📞 Appel entrant → Notification Telegram automatique
2. 👨‍💼 Agent demande au client de taper son code
3. 📱 Agent tape /dtmf-request NUMERO dans Telegram
4. 🔢 Client tape son code → Capture automatique
5. ✅ Validation en temps réel → Résultat affiché
6. 💼 Agent continue selon la validation

⚙️ VARIABLES D'ENVIRONNEMENT :
OBLIGATOIRES :
- TELEGRAM_TOKEN : Token du bot Telegram
- CHAT_ID : ID du groupe/chat Telegram

OPTIONNELLES :
- OVH_LINE_NUMBER : Numéro de ligne (défaut: 0033185093039)
- DTMF_TIMEOUT : Timeout en secondes (défaut: 30)
- DTMF_DIGITS_EXPECTED : Nb chiffres attendus (défaut: 4)
- DTMF_ENABLE_VALIDATION : Validation auto (défaut: true)
- ABSTRACT_API_KEY : Clé API pour IBAN

🔗 URLS À CONFIGURER DANS 3CX/OVH :
- Appels: /webhook/ovh?caller=*CALLING*&callee=*CALLED*&type=*EVENT*
- DTMF: /webhook/ovh?caller=*CALLING*&dtmf=*DTMF*

📱 COMMANDES TELEGRAM :
- /dtmf-request 0123456789 [Agent] [Raison] : Demander code client
- /calls : Appels actifs et sessions DTMF
- /dtmf : Sessions DTMF en cours
- /end-call 0123456789 : Terminer un appel
- /numero 0123456789 : Fiche client complète
- /stats : Statistiques de la campagne
- /iban FR76XXX : Détection banque
- /help : Aide complète

🛠️ ROUTES D'ADMINISTRATION :
- / : Page d'accueil avec statistiques
- /dtmf-admin : Interface temps réel DTMF
- /clients : Gestion des clients
- /config-help : Guide de configuration
- /test-dtmf-workflow : Test complet

✅ VALIDATION AUTOMATIQUE DES CODES :
- IBAN : 4 derniers chiffres
- Téléphone : 4 derniers chiffres  
- Code postal : Code exact
- Année naissance : 4 chiffres
- Codes génériques : 1234, 0000, 9999, 1111

🔒 SÉCURITÉ :
- Aucun token hardcodé dans le code
- Configuration via variables d'environnement uniquement
- Vérification automatique de la configuration
- Rate limiting et cache intégrés

Version : 1.0 - DTMF à la demande
Auteur : Webhook OVH-Telegram avec support DTMF
"""from flask import Flask, request, jsonify, render_template_string, redirect
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
app.secret_key = 'webhook-ovh-secret-key-secure-v3'

# Configuration centralisée - UNIQUEMENT VARIABLES D'ENVIRONNEMENT
class Config:
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
    CHAT_ID = os.environ.get('CHAT_ID')
    OVH_LINE_NUMBER = os.environ.get('OVH_LINE_NUMBER', '0033185093039')
    ABSTRACT_API_KEY = os.environ.get('ABSTRACT_API_KEY')

# Configuration DTMF - NOUVELLE
class DTMFConfig:
    DTMF_TIMEOUT = int(os.environ.get('DTMF_TIMEOUT', '30'))
    DTMF_DIGITS_EXPECTED = int(os.environ.get('DTMF_DIGITS_EXPECTED', '4'))
    DTMF_ENABLE_VALIDATION = os.environ.get('DTMF_ENABLE_VALIDATION', 'true').lower() == 'true'

def check_required_config():
    missing_vars = []
    
    if not Config.TELEGRAM_TOKEN:
        missing_vars.append('TELEGRAM_TOKEN')
    if not Config.CHAT_ID:
        missing_vars.append('CHAT_ID')
    
    if missing_vars:
        logger.error(f"❌ Variables d'environnement manquantes: {', '.join(missing_vars)}")
        return False, missing_vars
    
    if Config.TELEGRAM_TOKEN and ':' not in Config.TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN invalide")
        return False, ['TELEGRAM_TOKEN (format invalide)']
    
    logger.info("✅ Configuration vérifiée avec succès")
    logger.info(f"🔢 DTMF: {DTMFConfig.DTMF_DIGITS_EXPECTED} chiffres, {DTMFConfig.DTMF_TIMEOUT}s timeout")
    
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
# GESTIONNAIRE DTMF À LA DEMANDE
# ===================================================================

class DTMFSessionManager:
    def __init__(self):
        self.sessions = {}
        self.call_sessions = {}
    
    def register_call(self, caller_number, call_data=None):
        self.call_sessions[caller_number] = {
            'start_time': time.time(),
            'status': 'active',
            'dtmf_requested': False,
            'agent_name': call_data.get('agent_name', 'Agent') if call_data else 'Agent',
            'call_id': call_data.get('call_id', '') if call_data else '',
            'notes': []
        }
        logger.info(f"📞 Appel enregistré pour {caller_number}")
    
    def request_dtmf(self, caller_number, agent_name="Agent", reason="identification"):
        if caller_number not in self.call_sessions:
            self.register_call(caller_number, {'agent_name': agent_name})
        
        self.call_sessions[caller_number]['dtmf_requested'] = True
        self.call_sessions[caller_number]['agent_name'] = agent_name
        
        self.sessions[caller_number] = {
            'digits': '',
            'timestamp': time.time(),
            'status': 'waiting',
            'caller': caller_number,
            'requested_by': agent_name,
            'reason': reason,
            'timeout': DTMFConfig.DTMF_TIMEOUT
        }
        
        logger.info(f"🔢 DTMF demandé par {agent_name} pour {caller_number}")
        
        if telegram_service:
            self.notify_dtmf_request(caller_number, agent_name, reason)
        
        return True
    
    def notify_dtmf_request(self, caller_number, agent_name, reason):
        client_info = get_client_info_advanced(caller_number)
        
        message = f"""
🔢 <b>AGENT DEMANDE CODE CLIENT</b>

👨‍💼 <b>AGENT</b>
▪️ Agent: <b>{agent_name}</b>
▪️ Action: Demande d'identification
▪️ Raison: {reason}
▪️ Heure: {datetime.now().strftime("%H:%M:%S")}

📞 <b>CLIENT</b>
▪️ Numéro: <code>{caller_number}</code>
▪️ Nom: <b>{client_info['nom']} {client_info['prenom']}</b>
▪️ Statut: {client_info['statut']}
▪️ Entreprise: {client_info['entreprise']}

⏳ <b>EN ATTENTE CODE DTMF...</b>
▪️ Chiffres attendus: {DTMFConfig.DTMF_DIGITS_EXPECTED}
▪️ Timeout: {DTMFConfig.DTMF_TIMEOUT}s
▪️ Le code s'affichera ici automatiquement

💡 <i>L'agent peut dire au client de taper son code sur le téléphone</i>
        """
        telegram_service.send_message(message)
    
    def add_digit(self, caller_number, digit):
        if caller_number not in self.sessions:
            logger.warning(f"🔢 DTMF reçu de {caller_number} mais aucune session active - ignoré")
            return False
        
        session = self.sessions[caller_number]
        if session['status'] != 'waiting':
            return False
        
        if time.time() - session['timestamp'] > session['timeout']:
            session['status'] = 'expired'
            self.notify_dtmf_timeout(caller_number)
            return False
        
        session['digits'] += digit
        session['timestamp'] = time.time()
        
        logger.info(f"🔢 DTMF reçu de {caller_number}: {digit} (total: {session['digits']})")
        
        if telegram_service:
            self.notify_dtmf_progress(caller_number, digit, session['digits'])
        
        if len(session['digits']) >= DTMFConfig.DTMF_DIGITS_EXPECTED:
            session['status'] = 'complete'
            self.process_complete_code(caller_number, session['digits'])
            return True
        
        return False
    
    def notify_dtmf_progress(self, caller_number, digit, current_digits):
        remaining = DTMFConfig.DTMF_DIGITS_EXPECTED - len(current_digits)
        progress_bar = "🟢" * len(current_digits) + "⚪" * remaining
        
        message = f"""
🔢 <b>CODE EN COURS...</b>

📞 Client: <code>{caller_number}</code>
🔢 Chiffre reçu: <b>{digit}</b>
📊 Progression: {progress_bar} ({len(current_digits)}/{DTMFConfig.DTMF_DIGITS_EXPECTED})
⏳ Reste: {remaining} chiffre{'s' if remaining > 1 else ''}
        """
        telegram_service.send_message(message)
    
    def notify_dtmf_timeout(self, caller_number):
        session = self.sessions.get(caller_number)
        agent_name = session.get('requested_by', 'Agent') if session else 'Agent'
        
        message = f"""
⏰ <b>TIMEOUT CODE DTMF</b>

📞 Client: <code>{caller_number}</code>
👨‍💼 Agent: {agent_name}
🔢 Reçu: {session['digits'] if session else 'Aucun'} / {DTMFConfig.DTMF_DIGITS_EXPECTED}
⚠️ Session expirée après {DTMFConfig.DTMF_TIMEOUT}s

💡 <i>Utilisez /dtmf-request {caller_number} pour relancer</i>
        """
        telegram_service.send_message(message)
    
    def process_complete_code(self, caller_number, code):
        session = self.sessions[caller_number]
        agent_name = session.get('requested_by', 'Agent')
        reason = session.get('reason', 'identification')
        
        logger.info(f"✅ Code DTMF complet reçu de {caller_number}: {code}")
        
        if DTMFConfig.DTMF_ENABLE_VALIDATION:
            validation_result = self.validate_client_code(caller_number, code)
        else:
            validation_result = {"valid": True, "message": "Validation désactivée"}
        
        client_info = get_client_info_advanced(caller_number)
        
        if caller_number in self.call_sessions:
            self.call_sessions[caller_number]['notes'].append(f"Code DTMF: {code} ({validation_result['message']})")
        
        self.send_complete_dtmf_to_telegram(caller_number, code, client_info, validation_result, agent_name, reason)
        del self.sessions[caller_number]
    
    def send_complete_dtmf_to_telegram(self, caller_number, code, client_info, validation_result, agent_name, reason):
        status_emoji = "✅" if validation_result["valid"] else "❌"
        
        message = f"""
{status_emoji} <b>CODE CLIENT COMPLET</b>

👨‍💼 <b>AGENT</b>
▪️ Agent: <b>{agent_name}</b>
▪️ Raison: {reason}
▪️ Heure: {datetime.now().strftime("%H:%M:%S")}

📞 <b>IDENTIFICATION</b>
▪️ Numéro: <code>{caller_number}</code>
▪️ Code saisi: <code>{code}</code>
▪️ Validation: <b>{validation_result["message"]}</b>

👤 <b>CLIENT IDENTIFIÉ</b>
▪️ Nom: <b>{client_info['nom']} {client_info['prenom']}</b>
▪️ Statut: <b>{client_info['statut']}</b>
▪️ Entreprise: {client_info['entreprise']}
▪️ Email: {client_info['email']}
▪️ Ville: {client_info['ville']} {client_info['code_postal']}

🏦 <b>INFORMATIONS BANCAIRES</b>
▪️ Banque: {client_info.get('banque', 'N/A')}
▪️ IBAN: <code>{client_info.get('iban', 'N/A')}</code>
▪️ SWIFT: <code>{client_info.get('swift', 'N/A')}</code>

📊 <b>HISTORIQUE</b>
▪️ Nb appels: {client_info['nb_appels']}
▪️ Dernier appel: {client_info['dernier_appel'] or 'Premier appel'}

💼 <b>ACTION SUIVANTE</b>
{'🎯 Client validé - Poursuivre entretien' if validation_result["valid"] else '⚠️ Code incorrect - Vérifier identité'}
        """
        telegram_service.send_message(message)
    
    def validate_client_code(self, caller_number, code):
        client_info = get_client_info_advanced(caller_number)
        
        if client_info['statut'] == "Non référencé":
            return {"valid": False, "message": "❌ Client non référencé"}
        
        # Validation par IBAN (4 derniers chiffres)
        if client_info.get('iban'):
            iban_digits = re.sub(r'[^\d]', '', client_info['iban'])
            if len(iban_digits) >= 4 and code == iban_digits[-4:]:
                return {"valid": True, "message": "✅ Code IBAN validé"}
        
        # Validation par téléphone (4 derniers chiffres)
        phone_digits = re.sub(r'[^\d]', '', caller_number)
        if len(phone_digits) >= 4 and code == phone_digits[-4:]:
            return {"valid": True, "message": "✅ Code téléphone validé"}
        
        # Validation par code postal
        if client_info.get('code_postal') and code == client_info['code_postal']:
            return {"valid": True, "message": "✅ Code postal validé"}
        
        # Validation par date de naissance (année)
        if client_info.get('date_naissance'):
            date_match = re.search(r'(\d{4})', client_info['date_naissance'])
            if date_match and code == date_match.group(1)[-4:]:
                return {"valid": True, "message": "✅ Année naissance validée"}
        
        # Codes génériques
        valid_codes = ['1234', '0000', '9999', '1111']
        if code in valid_codes:
            return {"valid": True, "message": "✅ Code générique validé"}
        
        return {"valid": False, "message": "❌ Code incorrect"}
    
    def end_call(self, caller_number):
        if caller_number in self.call_sessions:
            call_data = self.call_sessions[caller_number]
            duration = time.time() - call_data['start_time']
            logger.info(f"📞 Fin d'appel pour {caller_number} (durée: {int(duration)}s)")
            del self.call_sessions[caller_number]
        
        if caller_number in self.sessions:
            del self.sessions[caller_number]
    
    def get_active_calls(self):
        return self.call_sessions
    
    def get_active_dtmf_sessions(self):
        current_time = time.time()
        expired = []
        for caller, session in self.sessions.items():
            if current_time - session['timestamp'] > session['timeout']:
                expired.append(caller)
        
        for caller in expired:
            self.notify_dtmf_timeout(caller)
            del self.sessions[caller]
        
        return self.sessions

dtmf_manager = DTMFSessionManager()

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
            return cached_result
        
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
        if not self.token or not self.chat_id:
            logger.error("❌ Token ou Chat ID manquant")
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
                logger.error(f"❌ Erreur Telegram: {response.status_code}")
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

telegram_service = None
config_valid = False

def initialize_telegram_service():
    global telegram_service, config_valid
    
    is_valid, missing_vars = check_required_config()
    config_valid = is_valid
    
    if is_valid:
        telegram_service = TelegramService(Config.TELEGRAM_TOKEN, Config.CHAT_ID)
        logger.info("✅ Service Telegram initialisé")
    else:
        logger.error(f"❌ Variables manquantes: {missing_vars}")
        telegram_service = None

initialize_telegram_service()

# ===================================================================
# GESTION CLIENTS ET DONNÉES
# ===================================================================

clients_database = {}
upload_stats = {
    "total_clients": 0,
    "last_upload": None,
    "filename": None
}

def normalize_phone(phone):
    if not phone:
        return None
    
    cleaned = re.sub(r'[^\d+]', '', str(phone))
    
    patterns = [
        (r'^0033(\d{9})$', lambda m: '0' + m.group(1)),
        (r'^\+33(\d{9})$', lambda m: '0' + m.group(1)),
        (r'^33(\d{9})$', lambda m: '0' + m.group(1)),
        (r'^0(\d{9})$', lambda m: '0' + m.group(1)),
        (r'^(\d{9})$', lambda m: '0' + m.group(1)),
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
    if not phone_number:
        return create_unknown_client(phone_number)
    
    search_formats = []
    
    normalized = normalize_phone(phone_number)
    if normalized:
        search_formats.append(normalized)
    
    cleaned = re.sub(r'[^\d+]', '', str(phone_number))
    
    if cleaned.startswith('0033'):
        national = '0' + cleaned[4:]
        search_formats.extend([national, '+33' + cleaned[4:], '33' + cleaned[4:]])
    elif cleaned.startswith('+33'):
        national = '0' + cleaned[3:]
        search_formats.extend([national, '0033' + cleaned[3:], '33' + cleaned[3:]])
    elif cleaned.startswith('33') and len(cleaned) == 11:
        national = '0' + cleaned[2:]
        search_formats.extend([national, '+33' + cleaned[2:], '0033' + cleaned[2:]])
    elif cleaned.startswith('0') and len(cleaned) == 10:
        without_zero = cleaned[1:]
        search_formats.extend(['+33' + without_zero, '0033' + without_zero, '33' + without_zero])
    
    search_formats = list(dict.fromkeys(search_formats))
    
    for format_to_try in search_formats:
        if format_to_try in clients_database:
            client = clients_database[format_to_try].copy()
            clients_database[format_to_try]["nb_appels"] += 1
            clients_database[format_to_try]["dernier_appel"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            logger.info(f"✅ Client trouvé: {format_to_try}")
            return client
    
    for format_to_try in search_formats:
        if len(format_to_try) >= 9:
            suffix = format_to_try[-9:]
            for tel, client in clients_database.items():
                if tel.endswith(suffix):
                    client_copy = client.copy()
                    clients_database[tel]["nb_appels"] += 1
                    clients_database[tel]["dernier_appel"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    logger.info(f"✅ Client trouvé par suffixe: {tel}")
                    return client_copy
    
    logger.warning(f"❌ Client non trouvé: {phone_number}")
    return create_unknown_client(phone_number)

def get_client_info(phone_number):
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
                logger.info(f"🏦 Banque détectée pour {telephone}: {banque}")
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
        logger.error("❌ Service Telegram non initialisé")
        return {"error": "Service Telegram non configuré"}
        
    try:
        # NOUVELLE COMMANDE: Demander DTMF
        if message_text.startswith('/dtmf-request '):
            phone_number = message_text.replace('/dtmf-request ', '').strip()
            
            parts = phone_number.split(' ')
            phone = parts[0]
            agent_name = parts[1] if len(parts) > 1 else "Agent"
            reason = ' '.join(parts[2:]) if len(parts) > 2 else "identification"
            
            if dtmf_manager.request_dtmf(phone, agent_name, reason):
                return {
                    "status": "dtmf_requested", 
                    "phone": phone, 
                    "agent": agent_name,
                    "message": f"Demande DTMF envoyée pour {phone}"
                }
            else:
                return {"error": "Impossible de démarrer DTMF"}
        
        # NOUVELLE COMMANDE: Appels actifs
        elif message_text.startswith('/calls'):
            active_calls = dtmf_manager.get_active_calls()
            active_dtmf = dtmf_manager.get_active_dtmf_sessions()
            
            calls_list = ""
            for caller, call_data in active_calls.items():
                duration = int(time.time() - call_data['start_time'])
                dtmf_status = "🔢 DTMF actif" if caller in active_dtmf else "⏳ Standby"
                calls_list += f"📞 {caller} ({duration}s) - {dtmf_status}\n"
            
            message = f"""
📞 <b>APPELS ACTIFS</b>

👥 Appels en cours: {len(active_calls)}
🔢 Sessions DTMF: {len(active_dtmf)}

<b>Détails:</b>
{calls_list if calls_list else "Aucun appel actif"}

💡 <b>Commandes utiles:</b>
▪️ <code>/dtmf-request 0123456789 Agent Nom</code>
▪️ <code>/end-call 0123456789</code>
            """
            
            telegram_service.send_message(message)
            return {"status": "calls_list_sent"}
        
        # NOUVELLE COMMANDE: Terminer appel
        elif message_text.startswith('/end-call '):
            phone_number = message_text.replace('/end-call ', '').strip()
            dtmf_manager.end_call(phone_number)
            
            message = f"📞 Appel terminé pour {phone_number}"
            telegram_service.send_message(message)
            return {"status": "call_ended", "phone": phone_number}
        
        # COMMANDE: Sessions DTMF
        elif message_text.startswith('/dtmf'):
            active_dtmf = dtmf_manager.get_active_dtmf_sessions()
            
            sessions_details = ""
            for caller, session in active_dtmf.items():
                remaining_time = session['timeout'] - (time.time() - session['timestamp'])
                progress = f"{len(session['digits'])}/{DTMFConfig.DTMF_DIGITS_EXPECTED}"
                sessions_details += f"📞 {caller}\n"
                sessions_details += f"   👨‍💼 Agent: {session['requested_by']}\n"
                sessions_details += f"   🔢 Code: {session['digits']} ({progress})\n"
                sessions_details += f"   ⏰ Reste: {int(remaining_time)}s\n\n"
            
            message = f"""
🔢 <b>SESSIONS DTMF</b>

📊 Sessions actives: {len(active_dtmf)}
⚙️ Config: {DTMFConfig.DTMF_DIGITS_EXPECTED} chiffres, {DTMFConfig.DTMF_TIMEOUT}s timeout

{sessions_details if sessions_details else "Aucune session DTMF active"}

💡 <i>Utilisez /dtmf-request 0123456789 pour démarrer</i>
            """
            
            telegram_service.send_message(message)
            return {"status": "dtmf_sessions_sent"}
        
        # Commandes existantes
        elif message_text.startswith('/numero '):
            phone_number = message_text.replace('/numero ', '').strip()
            client_info = get_client_info(phone_number)
            response_message = telegram_service.format_client_message(client_info, context="recherche")
            telegram_service.send_message(response_message)
            return {"status": "command_processed", "command": "numero", "phone": phone_number}
            
        elif message_text.startswith('/iban '):
            iban = message_text.replace('/iban ', '').strip()
            detected_bank = iban_detector.detect_bank(iban)
            response_message = f"""
🏦 <b>ANALYSE IBAN</b>

💳 IBAN: <code>{iban}</code>
🏛️ Banque: <b>{detected_bank}</b>
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

🔢 <b>DTMF</b>
▪️ Appels actifs: {len(dtmf_manager.get_active_calls())}
▪️ Sessions DTMF: {len(dtmf_manager.get_active_dtmf_sessions())}
            """
            telegram_service.send_message(stats_message)
            return {"status": "stats_sent"}
            
        elif message_text.startswith('/help'):
            help_message = """
🤖 <b>COMMANDES DISPONIBLES</b>

📋 <b>CONSULTATION</b>
📞 <code>/numero 0123456789</code> → Fiche client
📊 <code>/stats</code> → Statistiques
🏦 <code>/iban FR76XXX</code> → Détection banque

📞 <b>GESTION APPELS</b>
📱 <code>/calls</code> → Appels en cours
🔢 <code>/dtmf-request 0123456789</code> → Demander code client
🔢 <code>/dtmf-request 0123456789 Agent Martin</code> → Avec nom agent
📴 <code>/end-call 0123456789</code> → Terminer appel
🔢 <code>/dtmf</code> → Sessions DTMF actives

⚙️ <b>SYSTÈME</b>
⚙️ <code>/config</code> → Configuration
🆘 <code>/help</code> → Cette aide

✨ <b>WORKFLOW AGENT</b>
1️⃣ Appel entrant → Notification automatique
2️⃣ Agent demande identification → <code>/dtmf-request NUMERO</code>
3️⃣ Client tape son code → Résultat automatique ici
4️⃣ Agent continue selon validation
            """
            telegram_service.send_message(help_message)
            return {"status": "help_sent"}
        
        else:
            return {"status": "unknown_command"}
            
    except Exception as e:
        logger.error(f"❌ Erreur commande: {str(e)}")
        return {"error": str(e)}

# ===================================================================
# ROUTES WEBHOOK - VERSION AVEC DTMF
# ===================================================================

@app.route('/webhook/ovh', methods=['POST', 'GET'])
def ovh_webhook():
    """Webhook OVH avec gestion DTMF à la demande"""
    try:
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        if request.method == 'GET':
            caller_number = request.args.get('caller', 'Inconnu')
            called_number = request.args.get('callee', 'Inconnu') 
            event_type = request.args.get('type', 'unknown')
            dtmf_digit = request.args.get('dtmf', None)
            
            # DTMF reçu - traiter seulement si session active
            if dtmf_digit:
                logger.info(f"🔢 DTMF reçu: {dtmf_digit} de {caller_number}")
                complete = dtmf_manager.add_digit(caller_number, dtmf_digit)
                
                return jsonify({
                    "status": "dtmf_processed" if complete else "dtmf_received",
                    "caller": caller_number,
                    "dtmf_digit": dtmf_digit,
                    "code_complete": complete,
                    "timestamp": timestamp
                })
            
            # Gestion des événements d'appel
            if event_type in ['start_ringing', 'answer', 'incoming']:
                # Nouvel appel - enregistrer mais pas de DTMF automatique
                dtmf_manager.register_call(caller_number, {
                    'event_type': event_type,
                    'called_number': called_number
                })
                
                client_info = get_client_info_advanced(caller_number)
                
                if telegram_service:
                    message = telegram_service.format_client_message(client_info, context="appel")
                    message += f"\n📊 Événement: {event_type}"
                    message += f"\n💡 <i>Agent peut demander identification avec</i> <code>/dtmf-request {caller_number}</code>"
                    telegram_service.send_message(message)
                
                return jsonify({
                    "status": "call_registered",
                    "caller": caller_number,
                    "event": event_type,
                    "client_found": client_info['statut'] != "Non référencé",
                    "dtmf_auto_start": False
                })
            
            elif event_type in ['hangup', 'end']:
                # Fin d'appel
                dtmf_manager.end_call(caller_number)
                return jsonify({"status": "call_ended", "caller": caller_number})
        
        else:
            # Méthode POST
            data = request.get_json() or {}
            caller_number = data.get('callerIdNumber', 'Inconnu')
            dtmf_digit = data.get('dtmf', None)
            event_type = data.get('event', data.get('status', 'incoming'))
            
            if dtmf_digit:
                complete = dtmf_manager.add_digit(caller_number, dtmf_digit)
                return jsonify({
                    "status": "dtmf_processed" if complete else "dtmf_received",
                    "caller": caller_number,
                    "dtmf_digit": dtmf_digit,
                    "code_complete": complete
                })
            
            # Autres événements...
            dtmf_manager.register_call(caller_number, data)
            client_info = get_client_info_advanced(caller_number)
            
            if telegram_service:
                message = telegram_service.format_client_message(client_info, context="appel")
                message += f"\n📊 Statut: {event_type}"
                message += f"\n💡 Commande: <code>/dtmf-request {caller_number}</code>"
                telegram_service.send_message(message)
        
        return jsonify({"status": "success", "timestamp": timestamp})
        
    except Exception as e:
        logger.error(f"❌ Erreur webhook: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    if not config_valid:
        logger.error("❌ Configuration Telegram invalide")
        return jsonify({"error": "Configuration manquante"}), 400
        
    try:
        data = request.get_json()
        logger.info(f"📥 Webhook Telegram reçu")
        
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
    active_calls = len(dtmf_manager.get_active_calls())
    active_dtmf = len(dtmf_manager.get_active_dtmf_sessions())
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>🤖 Webhook OVH-Telegram avec DTMF</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: #e3f2fd; padding: 20px; border-radius: 8px; text-align: center; }
        .stat-card.dtmf { background: #e8f5e8; }
        .stat-card.calls { background: #fff3e0; }
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
        .dtmf-section { background: #e8f5e8; border-left: 4px solid #4caf50; padding: 15px; margin: 20px 0; }
        .error-section { background: #ffebee; border-left: 4px solid #f44336; padding: 15px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Webhook OVH-Telegram avec DTMF</h1>
            
            {% if config_valid %}
            <div class="config-section">
                <strong>✅ CONFIGURATION ACTIVE :</strong><br>
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
            
            <div class="dtmf-section">
                <strong>🔢 DTMF À LA DEMANDE :</strong><br>
                ✅ Capture DTMF seulement quand l'agent le demande<br>
                ✅ Validation automatique des codes clients<br>
                ✅ Progression en temps réel vers Telegram<br>
                ✅ Timeout configurable ({{ dtmf_timeout }}s par défaut)
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
            <div class="stat-card calls">
                <h3>📞 Appels actifs</h3>
                <h2>{{ active_calls }}</h2>
            </div>
            <div class="stat-card dtmf">
                <h3>🔢 Sessions DTMF</h3>
                <h2>{{ active_dtmf }}</h2>
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

        <h2>🔧 Tests & Configuration</h2>
        <div class="links">
            <a href="/clients" class="btn">👥 Voir clients</a>
            <a href="/dtmf-admin" class="btn btn-success">🔢 Admin DTMF</a>
            <a href="/test-dtmf-workflow" class="btn btn-warning">🧪 Test workflow DTMF</a>
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
                <li><code>OVH_LINE_NUMBER</code> = Numéro de votre ligne OVH</li>
                <li><code>DTMF_TIMEOUT</code> = Timeout DTMF en secondes (défaut: 30)</li>
                <li><code>DTMF_DIGITS_EXPECTED</code> = Nb chiffres attendus (défaut: 4)</li>
                <li><code>DTMF_ENABLE_VALIDATION</code> = Activer validation (défaut: true)</li>
            </ul>
        </div>
        {% endif %}

        <h2>🔗 Configuration 3CX/OVH CTI avec DTMF</h2>
        <div class="info-box">
            <p><strong>URLs à configurer dans l'interface 3CX/OVH :</strong></p>
            <p><strong>1. Appels entrants :</strong><br>
            <code>{{ webhook_url }}/webhook/ovh?caller=*CALLING*&callee=*CALLED*&type=*EVENT*</code></p>
            
            <p><strong>2. DTMF (Chiffres tapés) :</strong><br>
            <code>{{ webhook_url }}/webhook/ovh?caller=*CALLING*&callee=*CALLED*&dtmf=*DTMF*</code></p>
            
            <p><strong>🎯 Remplacez par votre URL Heroku réelle</strong></p>
        </div>

        <h2>📱 Commandes Telegram DTMF</h2>
        <ul>
            <li><code>/dtmf-request 0123456789</code> - Agent demande code client</li>
            <li><code>/dtmf-request 0123456789 Agent Martin</code> - Avec nom d'agent</li>
            <li><code>/calls</code> - Appels actifs et sessions DTMF</li>
            <li><code>/dtmf</code> - Sessions DTMF en cours</li>
            <li><code>/end-call 0123456789</code> - Terminer un appel</li>
            <li><code>/numero 0123456789</code> - Fiche client</li>
            <li><code>/stats</code> - Statistiques complètes</li>
        </ul>

        <div class="dtmf-section">
            <h3>🔢 Workflow DTMF pour les agents :</h3>
            <ol>
                <li>📞 <strong>Appel entrant</strong> → Notification Telegram automatique</li>
                <li>🎤 <strong>Agent demande</strong> → "Pouvez-vous taper votre code sur le téléphone ?"</li>
                <li>📱 <strong>Agent tape</strong> → <code>/dtmf-request 0123456789</code> dans Telegram</li>
                <li>🔢 <strong>Client tape</strong> → Code capturé automatiquement</li>
                <li>✅ <strong>Validation</strong> → Résultat affiché en temps réel</li>
                <li>💼 <strong>Suite entretien</strong> → Agent continue selon validation</li>
            </ol>
        </div>
    </div>
</body>
</html>
    """, 
    config_valid=config_valid,
    total_clients=upload_stats["total_clients"],
    auto_detected=auto_detected,
    active_calls=active_calls,
    active_dtmf=active_dtmf,
    last_upload=upload_stats["last_upload"],
    chat_id=Config.CHAT_ID,
    ovh_line=Config.OVH_LINE_NUMBER,
    token_display=f"{Config.TELEGRAM_TOKEN[:10]}...{Config.TELEGRAM_TOKEN[-5:]}" if Config.TELEGRAM_TOKEN else "Non configuré",
    missing_vars=['TELEGRAM_TOKEN', 'CHAT_ID'] if not config_valid else [],
    webhook_url=request.url_root.rstrip('/'),
    dtmf_timeout=DTMFConfig.DTMF_TIMEOUT
    )

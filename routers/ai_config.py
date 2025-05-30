# routers/ai_config.py
@router.get("/ai-config", response_class=HTMLResponse)
async def ai_config_page(customer: dict = Depends(get_current_customer)):
    """AI configuration dashboard"""
    
    # Get current AI settings
    ai_settings = await db_service.execute_query(
        "SELECT * FROM ai_settings WHERE customer_id = ?",
        (customer['id'],), fetch='one'
    )
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 AI Configuration - AI Lead Robot</title>
        <style>
            /* Your styling */
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Configure Your AI Sales Agent</h1>
            
            <div class="config-section">
                <h3>👤 AI Personality</h3>
                <form id="aiPersonalityForm">
                    <div class="form-group">
                        <label>AI Name</label>
                        <input type="text" name="ai_name" value="{ai_settings.get('ai_name', 'Alex')}" placeholder="Alex">
                    </div>
                    
                    <div class="form-group">
                        <label>AI Role</label>
                        <input type="text" name="ai_role" value="{ai_settings.get('ai_role', 'Sales Representative')}" placeholder="Sales Representative">
                    </div>
                    
                    <div class="form-group">
                        <label>Communication Tone</label>
                        <select name="tone">
                            <option value="professional">Professional</option>
                            <option value="friendly">Friendly & Casual</option>
                            <option value="consultative">Consultative</option>
                            <option value="direct">Direct & Brief</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>Company Description</label>
                        <textarea name="company_description" placeholder="We help companies...">{ai_settings.get('company_description', '')}</textarea>
                    </div>
                    
                    <div class="form-group">
                        <label>Value Proposition</label>
                        <textarea name="value_proposition" placeholder="Our key benefits are...">{ai_settings.get('value_proposition', '')}</textarea>
                    </div>
                    
                    <button type="submit" class="btn">💾 Save AI Settings</button>
                </form>
            </div>
            
            <div class="config-section">
                <h3>📧 Email Response Templates</h3>
                <div class="template-editor">
                    <h4>Initial Outreach Template</h4>
                    <textarea id="outreachTemplate" placeholder="Hi {{name}}, I noticed you work at {{company}}...">{ai_settings.get('outreach_template', '')}</textarea>
                    
                    <h4>Follow-up Templates</h4>
                    <div class="template-types">
                        <div>
                            <label>Interested Response</label>
                            <textarea placeholder="Great to hear you're interested...">{ai_settings.get('interested_template', '')}</textarea>
                        </div>
                        <div>
                            <label>Objection Handling</label>
                            <textarea placeholder="I understand your concern about...">{ai_settings.get('objection_template', '')}</textarea>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="config-section">
                <h3>⚡ Zapier Integration</h3>
                <div class="zapier-setup">
                    <p>Connect your AI agent to your CRM and tools:</p>
                    
                    <div class="webhook-info">
                        <label>Your Webhook URL:</label>
                        <input type="text" readonly value="{settings.app_url}/webhook/zapier/{customer['id']}/{{webhook_id}}" id="webhookUrl">
                        <button onclick="copyWebhookUrl()">📋 Copy</button>
                    </div>
                    
                    <div class="zapier-templates">
                        <h4>Pre-built Zapier Templates:</h4>
                        <button onclick="setupZapierTemplate('crm')" class="btn">🏢 CRM Integration</button>
                        <button onclick="setupZapierTemplate('slack')" class="btn">💬 Slack Notifications</button>
                        <button onclick="setupZapierTemplate('calendar')" class="btn">📅 Calendar Booking</button>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // JavaScript for AI configuration
            async function saveAISettings() {{
                // Implementation for saving AI settings
            }}
            
            function copyWebhookUrl() {{
                // Copy webhook URL to clipboard
            }}
            
            function setupZapierTemplate(type) {{
                // Open Zapier with pre-configured template
                const templates = {{
                    'crm': 'https://zapier.com/shared/create-deal-from-hot-lead',
                    'slack': 'https://zapier.com/shared/notify-team-hot-lead',
                    'calendar': 'https://zapier.com/shared/book-demo-call'
                }};
                window.open(templates[type], '_blank');
            }}
        </script>
    </body>
    </html>
    """

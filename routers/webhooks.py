from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from typing import List
from services.auth_service import get_current_customer
from services.webhook_service import zapier_service
from models import ZapierWebhookConfig, WebhookTestRequest

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/zapier")
async def create_zapier_webhook(
    config: ZapierWebhookConfig,
    customer: dict = Depends(get_current_customer)
):
    """Create a new Zapier webhook configuration"""
    
    try:
        webhook_id = await zapier_service.save_webhook_config(
            customer['id'],
            str(config.webhook_url),
            config.events
        )
        
        return {
            "webhook_id": webhook_id,
            "status": "created",
            "message": "Zapier webhook configured successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating webhook: {str(e)}")

@router.get("/zapier")
async def get_zapier_webhooks(customer: dict = Depends(get_current_customer)):
    """Get customer's Zapier webhook configurations"""
    
    try:
        configs = await zapier_service.get_customer_webhooks(customer['id'])
        return {"webhooks": configs}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching webhooks: {str(e)}")

@router.post("/zapier/test")
async def test_zapier_webhook(
    request: WebhookTestRequest,
    customer: dict = Depends(get_current_customer)
):
    """Test a Zapier webhook with sample data"""
    
    test_lead_data = {
        "id": "test-lead-id",
        "email": "test@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "company": "Test Company",
        "phone": "+1234567890",
        "source": "test",
        "qualification_score": 75,
        "qualification_stage": "warm_lead"
    }
    
    success = await zapier_service.send_to_zapier(request.webhook_url, test_lead_data)
    
    return {
        "success": success,
        "message": "Test webhook sent" if success else "Test webhook failed"
    }

# Fix the setup page - this was missing the auth dependency fix
@router.get("/setup", response_class=HTMLResponse)
async def webhook_setup_page(api_key: str = Query(..., description="Customer API key")):
    """Zapier webhook setup page - Fixed to not require auth header"""
    
    # Verify API key from query parameter instead of auth header
    from services.auth_service import auth_service
    customer = await auth_service.verify_api_key(api_key)
    if not customer:
        return HTMLResponse("""
        <div style="text-align: center; font-family: Arial; margin: 100px;">
            <h1>❌ Invalid API Key</h1>
            <p>Please provide a valid API key in the URL</p>
            <a href="/">← Back to Home</a>
        </div>
        """, status_code=401)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>⚡ Zapier Setup - AI Lead Robot</title>
        <style>
            body {{ font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; background: #f5f7fa; }}
            .container {{ background: white; padding: 40px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .step {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #667eea; }}
            .btn {{ background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; cursor: pointer; border: none; }}
            .btn:hover {{ background: #5a6fd8; }}
            input {{ width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; margin: 10px 0; box-sizing: border-box; }}
            .success {{ background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .error {{ background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .zapier-demo {{ background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>⚡ Zapier Integration Setup</h1>
            <p>Connect your AI Lead Robot to 6,000+ apps with Zapier!</p>
            
            <div class="zapier-demo">
                <h3>🎯 What This Does:</h3>
                <p>Every time someone fills out your lead form, we'll automatically send their information to any app you choose:</p>
                <ul>
                    <li>📧 <strong>Email Marketing:</strong> Mailchimp, ConvertKit, ActiveCampaign</li>
                    <li>🏢 <strong>CRM Systems:</strong> Salesforce, HubSpot, Pipedrive</li>
                    <li>💬 <strong>Team Notifications:</strong> Slack, Microsoft Teams</li>
                    <li>📊 <strong>Spreadsheets:</strong> Google Sheets, Airtable</li>
                    <li>🔔 <strong>Project Management:</strong> Notion, Trello, Asana</li>
                </ul>
            </div>
            
            <div class="step">
                <h3>Step 1: Create a Zapier Account</h3>
                <p>If you don't have one already:</p>
                <a href="https://zapier.com/sign-up" target="_blank" class="btn">Sign up for Zapier (Free)</a>
            </div>
            
            <div class="step">
                <h3>Step 2: Create a New Zap</h3>
                <ol>
                    <li>In Zapier, click <strong>"Create Zap"</strong></li>
                    <li>For the trigger, search for <strong>"Webhooks by Zapier"</strong></li>
                    <li>Choose <strong>"Catch Hook"</strong> as the trigger event</li>
                    <li>Copy the webhook URL Zapier gives you (it will look like: <code>https://hooks.zapier.com/hooks/catch/...</code>)</li>
                </ol>
            </div>
            
            <div class="step">
                <h3>Step 3: Configure Your Webhook</h3>
                <form id="webhookForm">
                    <label><strong>Paste your Zapier Webhook URL here:</strong></label>
                    <input type="url" id="webhookUrl" placeholder="https://hooks.zapier.com/hooks/catch/..." required>
                    
                    <div style="margin: 20px 0;">
                        <button type="button" onclick="testWebhook()" class="btn" style="background: #28a745;">🧪 Test Webhook</button>
                        <button type="submit" class="btn">💾 Save Webhook</button>
                    </div>
                </form>
                
                <div id="result"></div>
            </div>
            
            <div class="step">
                <h3>Step 4: Test with Sample Data</h3>
                <p>Click <strong>"Test Webhook"</strong> above to send sample lead data to your Zapier webhook. You should see the data appear in your Zap within a few seconds.</p>
            </div>
            
            <div class="step">
                <h3>Step 5: Configure Your Action in Zapier</h3>
                <p>Back in Zapier, add an action to send the lead data wherever you want:</p>
                <ul>
                    <li><strong>For CRM:</strong> Choose your CRM app and "Create Contact" action</li>
                    <li><strong>For Email:</strong> Choose your email tool and "Add Subscriber" action</li>
                    <li><strong>For Slack:</strong> Choose Slack and "Send Message" action</li>
                </ul>
                
                <div style="background: #f1f1f1; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <strong>Sample data you'll receive:</strong>
                    <pre style="margin: 10px 0; font-size: 12px;">{{
  "event": "lead_qualified",
  "timestamp": "2025-05-30T12:00:00Z",
  "lead": {{
    "email": "john@company.com",
    "first_name": "John",
    "last_name": "Doe",
    "company": "Test Company",
    "phone": "+1234567890",
    "qualification_score": 75,
    "qualification_stage": "warm_lead"
  }}
}}</pre>
                </div>
            </div>
            
            <div class="step">
                <h3>Step 6: Turn On Your Zap</h3>
                <p>Once you've configured everything, make sure to <strong>turn on</strong> your Zap in Zapier!</p>
            </div>
            
            <div style="text-align: center; margin-top: 40px; padding: 20px; background: #e8f5e9; border-radius: 8px;">
                <h3>🎉 You're All Set!</h3>
                <p>Every new lead will now automatically be sent to your chosen apps via Zapier.</p>
                <a href="/dashboard?api_key={api_key}" class="btn">← Back to Dashboard</a>
            </div>
        </div>
        
        <script>
            async function testWebhook() {{
                const webhookUrl = document.getElementById('webhookUrl').value;
                if (!webhookUrl) {{
                    document.getElementById('result').innerHTML = '<div class="error">❌ Please enter a webhook URL</div>';
                    return;
                }}
                
                document.getElementById('result').innerHTML = '<div style="color: #666;">🔄 Sending test webhook...</div>';
                
                try {{
                    const response = await fetch('/webhooks/zapier/test', {{
                        method: 'POST',
                        headers: {{ 
                            'Content-Type': 'application/json',
                            'Authorization': 'Bearer {api_key}'
                        }},
                        body: JSON.stringify({{ webhook_url: webhookUrl }})
                    }});
                    
                    const result = await response.json();
                    
                    if (result.success) {{
                        document.getElementById('result').innerHTML = '<div class="success">✅ Test webhook sent successfully! Check your Zapier dashboard for the data.</div>';
                    }} else {{
                        document.getElementById('result').innerHTML = '<div class="error">❌ Test webhook failed. Please check your URL and try again.</div>';
                    }}
                }} catch (error) {{
                    document.getElementById('result').innerHTML = '<div class="error">❌ Error testing webhook. Please try again.</div>';
                }}
            }}
            
            document.getElementById('webhookForm').addEventListener('submit', async (e) => {{
                e.preventDefault();
                
                const webhookUrl = document.getElementById('webhookUrl').value;
                if (!webhookUrl) {{
                    document.getElementById('result').innerHTML = '<div class="error">❌ Please enter a webhook URL</div>';
                    return;
                }}
                
                try {{
                    const response = await fetch('/webhooks/zapier', {{
                        method: 'POST',
                        headers: {{ 
                            'Content-Type': 'application/json',
                            'Authorization': 'Bearer {api_key}'
                        }},
                        body: JSON.stringify({{
                            webhook_url: webhookUrl,
                            events: ["lead_qualified"],
                            active: true
                        }})
                    }});
                    
                    const result = await response.json();
                    
                    if (response.ok) {{
                        document.getElementById('result').innerHTML = '<div class="success">✅ Webhook saved successfully! Your leads will now be sent to Zapier.</div>';
                    }} else {{
                        document.getElementById('result').innerHTML = '<div class="error">❌ Error saving webhook: ' + result.detail + '</div>';
                    }}
                }} catch (error) {{
                    document.getElementById('result').innerHTML = '<div class="error">❌ Error saving webhook. Please try again.</div>';
                }}
            }});
        </script>
    </body>
    </html>
    """

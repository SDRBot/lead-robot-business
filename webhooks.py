from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, HttpUrl
from typing import List
from services.auth_service import get_current_customer
from services.webhook_service import zapier_service
from models import ZapierWebhookConfig

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
    webhook_url: str,
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
    
    async with zapier_service:
        success = await zapier_service.send_to_zapier(webhook_url, test_lead_data)
    
    return {
        "success": success,
        "message": "Test webhook sent" if success else "Test webhook failed"
    }

@router.get("/setup", response_class=HTMLResponse)
async def webhook_setup_page(api_key: str):
    """Zapier webhook setup page"""
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>⚡ Zapier Setup - AI Lead Robot</title>
        <style>
            body {{ font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; background: #f5f7fa; }}
            .container {{ background: white; padding: 40px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .step {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #667eea; }}
            .btn {{ background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; }}
            input {{ width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; margin: 10px 0; box-sizing: border-box; }}
            .success {{ background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .error {{ background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>⚡ Zapier Integration Setup</h1>
            <p>Connect your AI Lead Robot to 6,000+ apps with Zapier!</p>
            
            <div class="step">
                <h3>Step 1: Create a Zapier Account</h3>
                <p>If you don't have one already:</p>
                <a href="https://zapier.com/sign-up" target="_blank" class="btn">Sign up for Zapier</a>
            </div>
            
            <div class="step">
                <h3>Step 2: Create a New Zap</h3>
                <ol>
                    <li>In Zapier, click "Create Zap"</li>
                    <li>For the trigger, search for "Webhooks by Zapier"</li>
                    <li>Choose "Catch Hook" as the trigger event</li>
                    <li>Copy the webhook URL Zapier gives you</li>
                </ol>
            </div>
            
            <div class="step">
                <h3>Step 3: Configure Your Webhook</h3>
                <form id="webhookForm">
                    <label>Zapier Webhook URL:</label>
                    <input type="url" id="webhookUrl" placeholder="https://hooks.zapier.com/hooks/catch/..." required>
                    
                    <button type="button" onclick="testWebhook()" class="btn">🧪 Test Webhook</button>
                    <button type="submit" class="btn">💾 Save Webhook</button>
                </form>
                
                <div id="result"></div>
            </div>
            
            <div class="step">
                <h3>Step 4: Test with Sample Data</h3>
                <p>Click "Test Webhook" above to send sample lead data to your Zapier webhook. You should see the data appear in your Zap.</p>
            </div>
            
            <div class="step">
                <h3>Step 5: Configure Your Action</h3>
                <p>In Zapier, add an action to send the lead data to your CRM, email tool, or any other app!</p>
                <p><strong>Sample data structure:</strong></p>
                <pre style="background: #f1f1f1; padding: 10px; border-radius: 5px;">
{{
  "event": "lead_qualified",
  "timestamp": "2025-05-30T12:00:00Z",
  "lead": {{
    "email": "john@company.com",
    "first_name": "John",
    "company": "Test Company",
    "qualification_score": 75
  }}
}}
                </pre>
            </div>
            
            <p style="text-align: center; margin-top: 30px;">
                <a href="/dashboard?api_key={api_key}" class="btn">← Back to Dashboard</a>
            </p>
    </div>
        
        <script>
            async function testWebhook() {
                const webhookUrl = document.getElementById('webhookUrl').value;
                if (!webhookUrl) {
                    document.getElementById('result').innerHTML = '<div class="error">Please enter a webhook URL</div>';
                    return;
                }
                
                try {
                    const response = await fetch('/webhooks/zapier/test', {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'Authorization': 'Bearer {api_key}'
                        },
                        body: JSON.stringify({ webhook_url: webhookUrl })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        document.getElementById('result').innerHTML = '<div class="success">✅ Test webhook sent successfully! Check your Zapier dashboard.</div>';
                    } else {
                        document.getElementById('result').innerHTML = '<div class="error">❌ Test webhook failed. Please check your URL.</div>';
                    }
                } catch (error) {
                    document.getElementById('result').innerHTML = '<div class="error">❌ Error testing webhook</div>';
                }
            }
            
            document.getElementById('webhookForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const webhookUrl = document.getElementById('webhookUrl').value;
                
                try {
                    const response = await fetch('/webhooks/zapier', {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'Authorization': 'Bearer {api_key}'
                        },
                        body: JSON.stringify({
                            webhook_url: webhookUrl,
                            events: ["lead_qualified"],
                            active: true
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        document.getElementById('result').innerHTML = '<div class="success">✅ Webhook saved successfully!</div>';
                    } else {
                        document.getElementById('result').innerHTML = '<div class="error">❌ Error saving webhook</div>';
                    }
                } catch (error) {
                    document.getElementById('result').innerHTML = '<div class="error">❌ Error saving webhook</div>';
                }
            });
        </script>
    </body>
    </html>
    """

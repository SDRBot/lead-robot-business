# website.py - Business website for customer signups
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
import uuid
import stripe
import os

app = FastAPI(title="Lead Robot Business")

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@app.get("/", response_class=HTMLResponse)
def home_page():
    """Business homepage"""
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 Smart Lead Robot - Qualify Leads Automatically!</title>
        <style>
            body { 
                font-family: Arial; 
                max-width: 800px; 
                margin: 0 auto; 
                padding: 20px;
                background: #f0f8ff;
            }
            .hero { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; 
                padding: 50px; 
                text-align: center; 
                border-radius: 15px;
                margin-bottom: 30px;
            }
            .plan { 
                background: white; 
                padding: 30px; 
                margin: 20px 0; 
                border-radius: 10px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                text-align: center;
            }
            .btn {
                background: #667eea;
                color: white;
                padding: 15px 30px;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
            }
            .btn:hover { background: #5a6fd8; }
        </style>
    </head>
    <body>
        <div class="hero">
            <h1>🤖 Smart Lead Robot</h1>
            <h2>Turn Website Visitors Into Qualified Leads Automatically!</h2>
            <p>Our AI robot qualifies your leads 24/7, so you only talk to people ready to buy!</p>
        </div>
        
        <h2 style="text-align: center;">Choose Your Plan:</h2>
        
        <div class="plan">
            <h3>🥤 Starter Plan</h3>
            <h2>$99/month</h2>
            <ul style="text-align: left; max-width: 300px; margin: 0 auto;">
                <li>✅ 500 leads per month</li>
                <li>✅ AI qualification</li>
                <li>✅ Email automation</li>
                <li>✅ Basic analytics</li>
            </ul>
            <br>
            <a href="/checkout/starter" class="btn">Start Free Trial</a>
        </div>
        
        <div class="plan">
            <h3>🚀 Professional Plan</h3>
            <h2>$299/month</h2>
            <ul style="text-align: left; max-width: 300px; margin: 0 auto;">
                <li>✅ 2,000 leads per month</li>
                <li>✅ Everything in Starter</li>
                <li>✅ CRM integrations</li>
                <li>✅ Advanced analytics</li>
                <li>✅ Priority support</li>
            </ul>
            <br>
            <a href="/checkout/professional" class="btn">Start Free Trial</a>
        </div>
    </body>
    </html>
    """
    return html

@app.get("/checkout/{plan}")
async def create_checkout_session(plan: str):
    """Create Stripe checkout session"""
    
    prices = {
        "starter": {"amount": 9900, "name": "Starter Plan - 500 leads/month"},
        "professional": {"amount": 29900, "name": "Professional Plan - 2000 leads/month"}
    }
    
    if plan not in prices:
        return HTMLResponse("Plan not found", status_code=404)
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': prices[plan]["name"],
                    },
                    'unit_amount': prices[plan]["amount"],
                    'recurring': {'interval': 'month'}
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f"{os.getenv('WEBSITE_URL', 'https://your-site.onrender.com')}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{os.getenv('WEBSITE_URL', 'https://your-site.onrender.com')}/cancel",
            metadata={'plan': plan}
        )
        
        return RedirectResponse(url=checkout_session.url, status_code=303)
        
    except Exception as e:
        return HTMLResponse(f"Error: {str(e)}", status_code=500)

@app.get("/success", response_class=HTMLResponse)
async def payment_success(session_id: str):
    """Payment success page"""
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        customer_email = session.customer_details.email
        plan = session.metadata.plan
        
        # Create customer account
        customer_id = str(uuid.uuid4())
        secret_key = f"sk_live_{str(uuid.uuid4()).replace('-', '')}"
        
        conn = sqlite3.connect('leads.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO customers (id, company_name, email, plan, secret_key, stripe_customer_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (customer_id, "New Customer", customer_email, plan, secret_key, session.customer))
        
        conn.commit()
        conn.close()
        
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Welcome to Lead Robot!</title>
            <style>
                body {{ 
                    font-family: Arial; 
                    max-width: 600px; 
                    margin: 50px auto; 
                    padding: 20px;
                    text-align: center;
                }}
                .success {{
                    background: #e8f5e8;
                    padding: 30px;
                    border-radius: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="success">
                <h1>🎉 Welcome to Lead Robot!</h1>
                <p><strong>Your API Key:</strong></p>
                <code>{secret_key}</code>
                <h3>Start using your robot:</h3>
                <pre>
curl -X POST "https://your-site.onrender.com/api/leads" \\
     -H "Content-Type: application/json" \\
     -H "X-API-Key: {secret_key}" \\
     -d '{{"email": "test@company.com", "first_name": "John"}}'
                </pre>
                <p>Check your email for detailed setup instructions!</p>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        return HTMLResponse(f"Error: {str(e)}", status_code=500)

@app.get("/cancel", response_class=HTMLResponse)
def payment_cancelled():
    return HTMLResponse("""
    <h1>Payment Cancelled</h1>
    <p><a href="/">← Back to homepage</a></p>
    """)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

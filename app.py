# app.py - Complete AI Lead Qualification System with Stripe Integration
import os
import json
import uuid
import sqlite3
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import stripe

# Load environment variables
load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Create FastAPI app
app = FastAPI(title="AI Lead Qualification System with Payments")

# Security
security = HTTPBearer()

# Data models
class LeadInput(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    source: str = "api"
    initial_message: Optional[str] = None

# Pricing plans
PRICING_PLANS = {
    "starter": {
        "name": "Starter Plan",
        "price": 99,
        "leads_limit": 500,
        "description": "Perfect for small businesses",
        "features": [
            "500 leads per month",
            "AI-powered qualification", 
            "Email automation",
            "Basic analytics",
            "Email support"
        ]
    },
    "professional": {
        "name": "Professional Plan", 
        "price": 299,
        "leads_limit": 2000,
        "description": "Great for growing businesses",
        "features": [
            "2,000 leads per month",
            "Everything in Starter",
            "CRM integrations", 
            "Advanced analytics",
            "Priority support",
            "API access"
        ]
    }
}

# Database functions
def get_db_connection():
    conn = sqlite3.connect('leads.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize the database with all necessary tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Customers table (paying customers)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            stripe_customer_id TEXT UNIQUE,
            stripe_subscription_id TEXT,
            plan TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            api_key TEXT UNIQUE NOT NULL,
            leads_limit INTEGER NOT NULL,
            leads_used_this_month INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Leads table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            email TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            company TEXT,
            phone TEXT,
            source TEXT,
            qualification_score INTEGER DEFAULT 0,
            qualification_stage TEXT DEFAULT 'new',
            conversation_data TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        )
    ''')
    
    # Analytics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics (
            id TEXT PRIMARY KEY,
            customer_id TEXT,
            event_type TEXT NOT NULL,
            data TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

# Initialize database
init_database()

# Initialize external services
def init_services():
    """Initialize OpenAI and SendGrid safely"""
    services = {"openai": None, "sendgrid": None}
    
    # Try to initialize OpenAI
    try:
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            from openai import OpenAI
            services["openai"] = OpenAI(api_key=openai_key)
            print("✅ OpenAI initialized successfully")
        else:
            print("⚠️ OPENAI_API_KEY not set")
    except Exception as e:
        print(f"❌ OpenAI initialization failed: {e}")
    
    # Try to initialize SendGrid
    try:
        sendgrid_key = os.getenv("SENDGRID_API_KEY")
        if sendgrid_key:
            from sendgrid import SendGridAPIClient
            services["sendgrid"] = SendGridAPIClient(api_key=sendgrid_key)
            print("✅ SendGrid initialized successfully")
        else:
            print("⚠️ SENDGRID_API_KEY not set")
    except Exception as e:
        print(f"❌ SendGrid initialization failed: {e}")
    
    return services

SERVICES = init_services()

# Authentication functions
def verify_api_key(api_key: str):
    """Verify API key and return customer info"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM customers 
        WHERE api_key = ? AND status = 'active'
    """, (api_key,))
    
    customer = cursor.fetchone()
    conn.close()
    
    if customer:
        return dict(customer)
    return None

def get_current_customer(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current authenticated customer"""
    customer = verify_api_key(credentials.credentials)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return customer

def check_usage_limit(customer_id: str) -> bool:
    """Check if customer is within their usage limits"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT leads_limit, leads_used_this_month 
        FROM customers WHERE id = ?
    """, (customer_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        limit, used = result
        return used < limit
    return False

# Email functions
def send_email(to_email: str, subject: str, content: str) -> bool:
    """Send email using SendGrid"""
    
    if not SERVICES["sendgrid"]:
        print(f"⚠️ Would send email to {to_email}: {subject}")
        return False
    
    try:
        from sendgrid.helpers.mail import Mail
        
        message = Mail(
            from_email=os.getenv("FROM_EMAIL", "hello@yourcompany.com"),
            to_emails=to_email,
            subject=subject,
            html_content=content
        )
        
        response = SERVICES["sendgrid"].send(message)
        print(f"✅ Email sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False

def send_welcome_email(customer_email: str, plan: str, api_key: str):
    """Send welcome email to new customers"""
    
    plan_info = PRICING_PLANS[plan]
    
    subject = "🎉 Welcome to AI Lead Robot!"
    
    content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px; }}
            .content {{ padding: 30px; background: #f8f9fa; border-radius: 10px; margin: 20px 0; }}
            .api-key {{ background: #e9ecef; padding: 15px; border-radius: 5px; font-family: monospace; word-break: break-all; }}
            .features {{ background: white; padding: 20px; border-radius: 8px; margin: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🤖 Welcome to AI Lead Robot!</h1>
            <p>Your intelligent lead qualification system is ready!</p>
        </div>
        
        <div class="content">
            <h2>Your Account Details:</h2>
            <p><strong>Plan:</strong> {plan_info['name']} (${plan_info['price']}/month)</p>
            <p><strong>Monthly Lead Limit:</strong> {plan_info['leads_limit']} leads</p>
            
            <h3>🔑 Your API Key:</h3>
            <div class="api-key">{api_key}</div>
            
            <div class="features">
                <h3>✨ What you get:</h3>
                <ul>
    """
    
    for feature in plan_info['features']:
        content += f"<li>{feature}</li>"
    
    content += f"""
                </ul>
            </div>
            
            <h3>🚀 Quick Start Guide:</h3>
            <p><strong>1. Test your API:</strong></p>
            <pre style="background: #f1f3f4; padding: 10px; border-radius: 5px; overflow-x: auto;">
curl -X POST "https://your-domain.onrender.com/api/leads" \\
     -H "Content-Type: application/json" \\
     -H "Authorization: Bearer {api_key}" \\
     -d '{{"email": "test@company.com", "first_name": "John", "company": "Test Co"}}'
            </pre>
            
            <p><strong>2. View your dashboard:</strong><br>
            <a href="https://your-domain.onrender.com/dashboard?api_key={api_key}">Click here to see your leads</a></p>
            
            <p><strong>3. Integration help:</strong><br>
            Reply to this email and we'll help you integrate with your website and CRM!</p>
        </div>
        
        <div style="text-align: center; color: #666; margin-top: 30px;">
            <p>Questions? Just reply to this email!</p>
            <p>🤖 Happy lead qualifying!</p>
        </div>
    </body>
    </html>
    """
    
    return send_email(customer_email, subject, content)

# Stripe functions
def create_checkout_session(plan: str, success_url: str, cancel_url: str):
    """Create Stripe checkout session"""
    
    if plan not in PRICING_PLANS:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    plan_info = PRICING_PLANS[plan]
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f"AI Lead Robot - {plan_info['name']}",
                        'description': f"{plan_info['description']} - {plan_info['leads_limit']} leads/month",
                    },
                    'unit_amount': plan_info['price'] * 100,
                    'recurring': {'interval': 'month'}
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={'plan': plan},
            allow_promotion_codes=True,
        )
        
        return checkout_session.url
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating checkout: {str(e)}")

def handle_successful_payment(session_id: str):
    """Handle successful payment and create customer account"""
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        
        customer_email = session.customer_details.email
        plan = session.metadata.plan
        stripe_customer_id = session.customer
        stripe_subscription_id = session.subscription
        
        # Generate API key
        api_key = f"sk_live_{str(uuid.uuid4()).replace('-', '')}"
        
        # Create customer in database
        customer_id = str(uuid.uuid4())
        plan_info = PRICING_PLANS[plan]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO customers (
                id, email, stripe_customer_id, stripe_subscription_id, 
                plan, api_key, leads_limit, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            customer_id, customer_email, stripe_customer_id, stripe_subscription_id,
            plan, api_key, plan_info['leads_limit'], datetime.now(), datetime.now()
        ))
        
        # Log the signup
        cursor.execute("""
            INSERT INTO analytics (id, customer_id, event_type, data, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), customer_id, "customer_signup", 
            json.dumps({"plan": plan, "email": customer_email}), datetime.now()
        ))
        
        conn.commit()
        conn.close()
        
        # Send welcome email
        send_welcome_email(customer_email, plan, api_key)
        
        return {
            "customer_id": customer_id,
            "customer_email": customer_email,
            "plan": plan,
            "api_key": api_key,
            "subscription_id": stripe_subscription_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing payment: {str(e)}")

# Routes - Public pages
@app.get("/", response_class=HTMLResponse)
async def home():
    """Homepage with marketing and pricing"""
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 AI Lead Robot - Qualify Leads Automatically</title>
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0; padding: 0; background: #f5f7fa; 
            }
            .hero { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; padding: 80px 20px; text-align: center;
            }
            .hero h1 { font-size: 3em; margin: 0; }
            .hero p { font-size: 1.2em; margin: 20px 0; }
            .container { max-width: 1200px; margin: 0 auto; padding: 0 20px; }
            .features { 
                display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 30px; padding: 80px 0; 
            }
            .feature { 
                background: white; padding: 40px; border-radius: 15px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1); text-align: center;
            }
            .feature h3 { color: #333; margin-top: 0; }
            .plans { 
                display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                gap: 40px; padding: 60px 0; 
            }
            .plan { 
                background: white; padding: 40px; border-radius: 15px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1); position: relative;
            }
            .popular { border: 3px solid #667eea; transform: scale(1.05); }
            .popular::before {
                content: "🔥 MOST POPULAR";
                position: absolute; top: -15px; left: 50%; transform: translateX(-50%);
                background: #667eea; color: white; padding: 8px 20px; border-radius: 20px;
                font-size: 12px; font-weight: bold;
            }
            .price { font-size: 3em; font-weight: bold; color: #667eea; margin: 20px 0; }
            .btn {
                background: #667eea; color: white; padding: 15px 30px; border: none;
                border-radius: 8px; font-size: 18px; font-weight: bold; cursor: pointer;
                text-decoration: none; display: inline-block; width: 100%; text-align: center;
                transition: all 0.3s;
            }
            .btn:hover { background: #5a6fd8; transform: translateY(-2px); }
            .features-list { text-align: left; margin: 30px 0; }
            .features-list li { margin: 10px 0; padding-left: 25px; position: relative; }
            .features-list li::before { content: "✅"; position: absolute; left: 0; }
        </style>
    </head>
    <body>
        <div class="hero">
            <div class="container">
                <h1>🤖 AI Lead Robot</h1>
                <p>Stop wasting time on unqualified leads. Our AI automatically qualifies your leads and sends you only the hot ones ready to buy.</p>
                <a href="#pricing" class="btn" style="width: auto; margin-top: 20px;">Start Free Trial</a>
            </div>
        </div>
        
        <div class="container">
            <div class="features">
                <div class="feature">
                    <h3>🧠 AI-Powered Qualification</h3>
                    <p>Our AI analyzes every lead response to determine buying intent, budget, authority, and timeline automatically.</p>
                </div>
                <div class="feature">
                    <h3>📧 Automated Follow-Up</h3>
                    <p>Personalized email sequences that adapt based on lead responses. Never miss a follow-up again.</p>
                </div>
                <div class="feature">
                    <h3>🎯 Hot Lead Alerts</h3>
                    <p>Get instant notifications when a lead is ready to buy. Focus your time on qualified prospects only.</p>
                </div>
                <div class="feature">
                    <h3>📊 Smart Analytics</h3>
                    <p>Track conversion rates, lead sources, and qualification metrics with detailed reporting dashboards.</p>
                </div>
                <div class="feature">
                    <h3>🔗 CRM Integration</h3>
                    <p>Seamlessly connect with Salesforce, HubSpot, Pipedrive and 1000+ other tools via Zapier.</p>
                </div>
                <div class="feature">
                    <h3>⚡ 5-Minute Setup</h3>
                    <p>Add one line of code to your website and start qualifying leads immediately. No complex setup required.</p>
                </div>
            </div>
            
            <div id="pricing" style="text-align: center; padding: 40px 0;">
                <h2 style="font-size: 2.5em; margin-bottom: 20px;">Simple, Transparent Pricing</h2>
                <p style="font-size: 1.2em; color: #666;">Start with a 14-day free trial. Cancel anytime.</p>
            </div>
            
            <div class="plans">
                <div class="plan">
                    <h3>Starter Plan</h3>
                    <div class="price">$99<span style="font-size: 0.4em;">/mo</span></div>
                    <ul class="features-list">
                        <li>500 leads per month</li>
                        <li>AI-powered qualification</li>
                        <li>Email automation</li>
                        <li>Basic analytics</li>
                        <li>Email support</li>
                    </ul>
                    <a href="/checkout/starter" class="btn">Start Free Trial</a>
                </div>
                
                <div class="plan popular">
                    <h3>Professional Plan</h3>
                    <div class="price">$299<span style="font-size: 0.4em;">/mo</span></div>
                    <ul class="features-list">
                        <li>2,000 leads per month</li>
                        <li>Everything in Starter</li>
                        <li>CRM integrations</li>
                        <li>Advanced analytics</li>
                        <li>Priority support</li>
                        <li>API access</li>
                        <li>Custom workflows</li>
                    </ul>
                    <a href="/checkout/professional" class="btn">Start Free Trial</a>
                </div>
            </div>
        </div>
        
        <div style="background: #2c3e50; color: white; padding: 60px 0; margin-top: 80px; text-align: center;">
            <div class="container">
                <h2>Ready to 10x Your Lead Conversion?</h2>
                <p>Join hundreds of businesses already using AI Lead Robot</p>
                <a href="/checkout/professional" class="btn" style="background: #e74c3c;">Start Free Trial Today</a>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/checkout/{plan}")
async def checkout(plan: str, request: Request):
    """Create Stripe checkout session"""
    
    base_url = str(request.base_url).rstrip('/')
    success_url = f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/#pricing"
    
    try:
        checkout_url = create_checkout_session(plan, success_url, cancel_url)
        return RedirectResponse(url=checkout_url, status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/success", response_class=HTMLResponse)
async def payment_success(session_id: str):
    """Payment success page"""
    
    try:
        payment_info = handle_successful_payment(session_id)
        plan_info = PRICING_PLANS[payment_info['plan']]
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>🎉 Welcome to AI Lead Robot!</title>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; 
                    padding: 20px; text-align: center; background: #f5f7fa;
                }}
                .success {{
                    background: white; padding: 50px; border-radius: 15px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                }}
                .api-key {{
                    background: #f8f9fa; padding: 20px; border-radius: 8px;
                    font-family: monospace; font-size: 14px; margin: 20px 0;
                    word-break: break-all; border: 2px dashed #667eea;
                }}
                .next-steps {{
                    background: #e8f5e9; padding: 30px; border-radius: 10px;
                    margin: 30px 0; text-align: left;
                }}
                .btn {{
                    background: #667eea; color: white; padding: 15px 30px;
                    text-decoration: none; border-radius: 8px; display: inline-block;
                    margin: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="success">
                <h1>🎉 Welcome to AI Lead Robot!</h1>
                <h2>Payment Successful!</h2>
                
                <p><strong>Plan:</strong> {plan_info['name']}</p>
                <p><strong>Monthly Limit:</strong> {plan_info['leads_limit']} leads</p>
                <p><strong>Email:</strong> {payment_info['customer_email']}</p>
                
                <h3>🔑 Your API Key:</h3>
                <div class="api-key">{payment_info['api_key']}</div>
                <p><em>⚠️ Save this key securely - you'll need it to access your account!</em></p>
                
                <div class="next-steps">
                    <h3>🚀 What happens next:</h3>
                    <ol>
                        <li><strong>Check your email</strong> - We've sent detailed setup instructions</li>
                        <li><strong>Test your API</strong> - Use the code examples in your email</li>
                        <li><strong>Integrate with your website</strong> - Add lead capture in 5 minutes</li>
                        <li><strong>Connect your CRM</strong> - Automatically send qualified leads</li>
                        <li><strong>Watch the magic happen</strong> - AI qualifies leads 24/7</li>
                    </ol>
                </div>
                
                <h3>🎯 Quick Start:</h3>
                <p>Test your API right now:</p>
                <pre style="background: #f1f1f1; padding: 15px; text-align: left; border-radius: 5px; overflow-x: auto;">
curl -X POST "{str(request.base_url).rstrip('/')}/api/leads" \\
     -H "Content-Type: application/json" \\
     -H "Authorization: Bearer {payment_info['api_key']}" \\
     -d '{{"email": "test@company.com", "first_name": "John"}}'
                </pre>
                
                <a href="/dashboard?api_key={payment_info['api_key']}" class="btn">📊 View Dashboard</a>
                <a href="/docs" class="btn">📚 API Documentation</a>
            </div>
        </body>
        </html>
        """
        
    except Exception as e:
        return HTMLResponse(f"<h1>Error: {str(e)}</h1>", status_code=500)

@app.get("/cancel", response_class=HTMLResponse)
def payment_cancelled():
    """Payment cancelled page"""
    
    return """
    <div style="text-align: center; font-family: Arial; margin: 100px auto; max-width: 600px;">
        <h1>😞 Payment Cancelled</h1>
        <p>No problem! You can start your free trial anytime.</p>
        <a href="/#pricing" style="background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px;">
            ← Back to Pricing
        </a>
    </div>
    """

# Customer dashboard
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(api_key: str = None):
    """Customer dashboard"""
    
    if not api_key:
        return HTMLResponse("""
        <div style="text-align: center; font-family: Arial; margin: 100px;">
            <h1>🔐 Dashboard Access Required</h1>
            <p>Please provide your API key to access your dashboard.</p>
            <form method="get">
                <input type="text" name="api_key" placeholder="Enter your API key" style="padding: 10px; width: 300px;">
                <button type="submit" style="padding: 10px 20px; background: #667eea; color: white; border: none;">Access Dashboard</button>
            </form>
        </div>
        """)
    
    customer = verify_api_key(api_key)
    if not customer:
        return HTMLResponse("<h1>Invalid API key</h1>", status_code=401)
    
    # Get customer stats
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE customer_id = ?", (customer['id'],))
    total_leads = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM leads 
        WHERE customer_id = ? AND qualification_stage IN ('hot_lead', 'warm_lead')
    """, (customer['id'],))
    qualified_leads = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT * FROM leads WHERE customer_id = ? 
        ORDER BY created_at DESC LIMIT 10
    """, (customer['id'],))
    recent_leads = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    plan_info = PRICING_PLANS[customer['plan']]
    usage_percent = (customer['leads_used_this_month'] / customer['leads_limit']) * 100
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>📊 Dashboard - AI Lead Robot</title>
        <style>
            body {{ 
                font-family: Arial, sans-serif; margin: 0; padding: 20px; 
                background: #f5f7fa; max-width: 1200px; margin: 0 auto;
            }}
            .header {{ 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; padding: 30px; border-radius: 15px; margin-bottom: 30px;
            }}
            .metrics {{ 
                display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px; margin-bottom: 30px;
            }}
            .metric {{ 
                background: white; padding: 25px; border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center;
            }}
            .metric h3 {{ margin: 0 0 10px 0; color: #666; font-size: 14px; }}
            .metric .value {{ font-size: 32px; font-weight: bold; margin: 0; }}
            .usage-bar {{ 
                background: #e9ecef; height: 20px; border-radius: 10px; 
                overflow: hidden; margin: 10px 0;
            }}
            .usage-fill {{ 
                background: linear-gradient(90deg, #28a745, #ffc107, #dc3545);
                height: 100%; width: {min(usage_percent, 100)}%;
            }}
            table {{ 
                width: 100%; background: white; border-radius: 10px; 
                box-shadow: 0 2px 10px rgba(0,0,0,0.1); border-collapse: collapse;
            }}
            th, td {{ padding: 15px; text-align: left; border-bottom: 1px solid #eee; }}
            th {{ background: #f8f9fa; font-weight: bold; }}
           .badge {{ 
               padding: 4px 8px; border-radius: 4px; font-size: 12px;
               font-weight: bold; text-transform: uppercase;
           }}
           .badge.hot {{ background: #ffe6e6; color: #e74c3c; }}
           .badge.warm {{ background: #fff3e0; color: #f39c12; }}
           .badge.qualified {{ background: #e3f2fd; color: #3498db; }}
           .badge.new {{ background: #f8f9fa; color: #666; }}
           .btn {{ 
               background: #667eea; color: white; padding: 10px 20px; 
               border: none; border-radius: 5px; text-decoration: none;
               display: inline-block; margin: 5px;
           }}
           .api-section {{ 
               background: #e8f5e9; padding: 20px; border-radius: 10px; 
               margin: 20px 0;
           }}
           .api-key {{ 
               background: #f8f9fa; padding: 10px; border-radius: 5px;
               font-family: monospace; word-break: break-all; margin: 10px 0;
           }}
       </style>
   </head>
   <body>
       <div class="header">
           <h1>📊 AI Lead Robot Dashboard</h1>
           <p>Welcome back! Here's how your lead qualification is performing.</p>
           <p><strong>Plan:</strong> {plan_info['name']} | <strong>Email:</strong> {customer['email']}</p>
       </div>
       
       <div class="metrics">
           <div class="metric">
               <h3>Total Leads</h3>
               <div class="value" style="color: #2ecc71;">{total_leads}</div>
           </div>
           <div class="metric">
               <h3>Qualified Leads</h3>
               <div class="value" style="color: #e74c3c;">{qualified_leads}</div>
           </div>
           <div class="metric">
               <h3>Conversion Rate</h3>
               <div class="value" style="color: #3498db;">{round((qualified_leads/max(total_leads,1))*100, 1)}%</div>
           </div>
           <div class="metric">
               <h3>Monthly Usage</h3>
               <div class="value" style="color: #9b59b6;">{customer['leads_used_this_month']}/{customer['leads_limit']}</div>
               <div class="usage-bar">
                   <div class="usage-fill"></div>
               </div>
           </div>
       </div>
       
       <div class="api-section">
           <h3>🔑 Your API Integration</h3>
           <p><strong>API Key:</strong></p>
           <div class="api-key">{api_key}</div>
           
           <p><strong>Quick Integration Example:</strong></p>
           <pre style="background: #f1f1f1; padding: 15px; border-radius: 5px; overflow-x: auto;">
curl -X POST "{str(request.base_url).rstrip('/')}/api/leads" \\
    -H "Content-Type: application/json" \\
    -H "Authorization: Bearer {api_key}" \\
    -d '{{"email": "lead@company.com", "first_name": "John", "company": "Acme Corp"}}'
           </pre>
           
           <a href="/docs" class="btn">📚 Full API Documentation</a>
           <a href="/test-form?api_key={api_key}" class="btn">🧪 Test Lead Capture</a>
       </div>
       
       <h2>📋 Recent Leads</h2>
       <table>
           <tr>
               <th>Email</th>
               <th>Name</th>
               <th>Company</th>
               <th>Score</th>
               <th>Stage</th>
               <th>Created</th>
           </tr>
   """
   
    for lead in recent_leads:
       created_date = lead['created_at'][:16] if lead['created_at'] else 'N/A'
       stage_class = lead['qualification_stage'].replace('_lead', '')
       
       html += f"""
           <tr>
               <td>{lead['email']}</td>
               <td>{lead['first_name'] or 'N/A'}</td>
               <td>{lead['company'] or 'N/A'}</td>
               <td>{lead['qualification_score']}</td>
               <td><span class="badge {stage_class}">{lead['qualification_stage'].replace('_', ' ').title()}</span></td>
               <td>{created_date}</td>
           </tr>
       """
   
    html += f"""
       </table>
       
       <div style="margin-top: 40px; text-align: center; color: #666;">
           <p>🤖 Your AI Lead Robot is working 24/7 to qualify your leads!</p>
           <p><a href="mailto:support@yourcompany.com">Need help? Contact Support</a></p>
       </div>
       
       <script>
           // Auto-refresh every 5 minutes
           setTimeout(() => location.reload(), 300000);
       </script>
   </body>
   </html>
   """
   
    return HTMLResponse(html)

@app.get("/test-form", response_class=HTMLResponse)
async def test_form(api_key: str):
   """Test lead capture form for customers"""
   
   customer = verify_api_key(api_key)
   if not customer:
       return HTMLResponse("<h1>Invalid API key</h1>", status_code=401)
   
   return f"""
   <!DOCTYPE html>
   <html>
   <head>
       <title>🧪 Test Lead Capture - AI Lead Robot</title>
       <style>
           body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
           .form-container {{ background: white; padding: 40px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
           h1 {{ color: #333; text-align: center; }}
           .form-group {{ margin-bottom: 20px; }}
           label {{ display: block; margin-bottom: 5px; font-weight: bold; color: #555; }}
           input, textarea {{ width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }}
           button {{ background: #667eea; color: white; padding: 15px 30px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; width: 100%; }}
           button:hover {{ background: #5a6fd8; }}
           .result {{ padding: 15px; border-radius: 5px; margin-top: 20px; }}
           .success {{ background: #d4edda; color: #155724; }}
           .error {{ background: #f8d7da; color: #721c24; }}
       </style>
   </head>
   <body>
       <div class="form-container">
           <h1>🧪 Test Your Lead Capture</h1>
           <p>Use this form to test your AI lead qualification system:</p>
           
            <form id="testForm">
               <div class="form-group">
                   <label>Email Address *</label>
                   <input type="email" name="email" required placeholder="test@company.com">
               </div>
               
               <div class="form-group">
                   <label>First Name</label>
                   <input type="text" name="first_name" placeholder="John">
               </div>
               
               <div class="form-group">
                   <label>Last Name</label>
                   <input type="text" name="last_name" placeholder="Smith">
               </div>
               
               <div class="form-group">
                   <label>Company</label>
                   <input type="text" name="company" placeholder="Acme Corp">
               </div>
               
               <div class="form-group">
                   <label>Phone</label>
                   <input type="tel" name="phone" placeholder="+1234567890">
               </div>
               
               <div class="form-group">
                   <label>Initial Message (Optional)</label>
                   <textarea name="initial_message" rows="3" placeholder="Tell us about your biggest challenge..."></textarea>
               </div>
               
               <button type="submit">🚀 Test Lead Qualification</button>
           </form>
           
           <div id="result"></div>
           
           <div style="margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 8px;">
               <p><strong>💡 What happens when you submit:</strong></p>
               <ol>
                   <li>Lead gets saved to your database</li>
                   <li>AI analyzes the information</li>
                   <li>Welcome email sent automatically</li>
                   <li>Lead appears in your dashboard</li>
                   <li>Qualification score calculated</li>
               </ol>
           </div>
           
           <p style="text-align: center; margin-top: 20px;">
               <a href="/dashboard?api_key={api_key}" style="color: #667eea;">← Back to Dashboard</a>
           </p>
       </div>
       
       <script>
           document.getElementById('testForm').addEventListener('submit', async (e) => {{
               e.preventDefault();
               
               const formData = new FormData(e.target);
               const data = {{
                   email: formData.get('email'),
                   first_name: formData.get('first_name'),
                   last_name: formData.get('last_name'),
                   company: formData.get('company'),
                   phone: formData.get('phone'),
                   initial_message: formData.get('initial_message'),
                   source: 'test_form'
               }};
               
               try {{
                   const response = await fetch('/api/leads', {{
                       method: 'POST',
                       headers: {{ 
                           'Content-Type': 'application/json',
                           'Authorization': 'Bearer {api_key}'
                       }},
                       body: JSON.stringify(data)
                   }});
                   
                   const result = await response.json();
                   
                   if (response.ok) {{
                       document.getElementById('result').innerHTML = 
                           '<div class="result success">✅ Success! Lead captured and processed. Check your dashboard and email!</div>';
                       e.target.reset();
                   }} else {{
                       throw new Error(result.detail);
                   }}
               }} catch (error) {{
                   document.getElementById('result').innerHTML = 
                       '<div class="result error">❌ Error: ' + error.message + '</div>';
               }}
           }});
       </script>
   </body>
   </html>
   """

# Protected API endpoints
@app.post("/api/leads")
async def create_lead(lead: LeadInput, customer: dict = Depends(get_current_customer)):
   """Create a new lead (requires API key)"""
   
   # Check usage limits
   if not check_usage_limit(customer['id']):
       raise HTTPException(
           status_code=429, 
           detail=f"Monthly limit of {customer['leads_limit']} leads exceeded"
       )
   
   lead_id = str(uuid.uuid4())
   
   try:
       conn = get_db_connection()
       cursor = conn.cursor()
       
       # Insert lead
       cursor.execute('''
           INSERT INTO leads (
               id, customer_id, email, first_name, last_name, 
               company, phone, source, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
       ''', (
           lead_id, customer['id'], lead.email, lead.first_name, lead.last_name,
           lead.company, lead.phone, lead.source, datetime.now(), datetime.now()
       ))
       
       # Update usage counter
       cursor.execute('''
           UPDATE customers 
           SET leads_used_this_month = leads_used_this_month + 1, updated_at = ?
           WHERE id = ?
       ''', (datetime.now(), customer['id']))
       
       # Log analytics
       cursor.execute('''
           INSERT INTO analytics (id, customer_id, event_type, data, timestamp)
           VALUES (?, ?, ?, ?, ?)
       ''', (
           str(uuid.uuid4()), customer['id'], "lead_created",
           json.dumps({"source": lead.source, "email": lead.email}),
           datetime.now()
       ))
       
       conn.commit()
       conn.close()
       
       # Send welcome email to lead
       email_sent = False
       if lead.first_name and SERVICES["sendgrid"]:
           subject = f"Thanks for your interest, {lead.first_name}!"
           content = f"""
           <div style="font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px;">
               <h2>Hi {lead.first_name}!</h2>
               <p>Thanks for your interest! We'd love to learn more about {lead.company or 'your company'}.</p>
               <p><strong>Quick question:</strong> What's your biggest challenge right now?</p>
               <p>Just reply to this email and let us know!</p>
               <p>Best regards,<br>The Team</p>
           </div>
           """
           email_sent = send_email(lead.email, subject, content)
       
       return {
           "lead_id": lead_id,
           "status": "created",
           "email_sent": email_sent,
           "message": "Lead captured successfully!",
           "usage": {
               "used": customer['leads_used_this_month'] + 1,
               "limit": customer['leads_limit']
           }
       }
   
   except Exception as e:
       raise HTTPException(status_code=500, detail=f"Error creating lead: {str(e)}")

@app.get("/api/leads")
async def get_leads(customer: dict = Depends(get_current_customer), skip: int = 0, limit: int = 50):
   """Get customer's leads"""
   
   conn = get_db_connection()
   cursor = conn.cursor()
   
   cursor.execute('''
       SELECT * FROM leads WHERE customer_id = ?
       ORDER BY created_at DESC LIMIT ? OFFSET ?
   ''', (customer['id'], limit, skip))
   
   leads = [dict(row) for row in cursor.fetchall()]
   
   cursor.execute("SELECT COUNT(*) FROM leads WHERE customer_id = ?", (customer['id'],))
   total = cursor.fetchone()[0]
   
   conn.close()
   
   return {
       "leads": leads,
       "total": total,
       "skip": skip,
       "limit": limit
   }

@app.get("/api/analytics")
async def get_analytics(customer: dict = Depends(get_current_customer)):
   """Get customer analytics"""
   
   conn = get_db_connection()
   cursor = conn.cursor()
   
   # Basic metrics
   cursor.execute("SELECT COUNT(*) FROM leads WHERE customer_id = ?", (customer['id'],))
   total_leads = cursor.fetchone()[0]
   
   cursor.execute("""
       SELECT COUNT(*) FROM leads 
       WHERE customer_id = ? AND qualification_stage = 'hot_lead'
   """, (customer['id'],))
   hot_leads = cursor.fetchone()[0]
   
   cursor.execute("""
       SELECT COUNT(*) FROM leads 
       WHERE customer_id = ? AND qualification_stage = 'warm_lead'
   """, (customer['id'],))
   warm_leads = cursor.fetchone()[0]
   
   # Lead sources
   cursor.execute("""
       SELECT source, COUNT(*) as count
       FROM leads WHERE customer_id = ?
       GROUP BY source ORDER BY count DESC
   """, (customer['id'],))
   lead_sources = [{"source": row[0], "count": row[1]} for row in cursor.fetchall()]
   
   conn.close()
   
   conversion_rate = (hot_leads + warm_leads) / max(total_leads, 1) * 100
   
   return {
       "total_leads": total_leads,
       "hot_leads": hot_leads,
       "warm_leads": warm_leads,
       "conversion_rate": round(conversion_rate, 1),
       "usage": {
           "used": customer['leads_used_this_month'],
           "limit": customer['leads_limit'],
           "percentage": round((customer['leads_used_this_month'] / customer['leads_limit']) * 100, 1)
       },
       "lead_sources": lead_sources
   }

# Webhook for Stripe
@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request):
   """Handle Stripe webhooks"""
   
   payload = await request.body()
   sig_header = request.headers.get('stripe-signature')
   endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
   
   if not endpoint_secret:
       return {"status": "webhook_secret_not_configured"}
   
   try:
       event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
       
       if event['type'] == 'invoice.payment_succeeded':
           # Reset monthly usage counter
           subscription_id = event['data']['object']['subscription']
           
           conn = get_db_connection()
           cursor = conn.cursor()
           
           cursor.execute("""
               UPDATE customers 
               SET leads_used_this_month = 0, updated_at = ?
               WHERE stripe_subscription_id = ?
           """, (datetime.now(), subscription_id))
           
           conn.commit()
           conn.close()
           
       elif event['type'] == 'invoice.payment_failed':
           # Handle failed payment - could pause service
           subscription_id = event['data']['object']['subscription']
           
           conn = get_db_connection()
           cursor = conn.cursor()
           
           cursor.execute("""
               UPDATE customers 
               SET status = 'payment_failed', updated_at = ?
               WHERE stripe_subscription_id = ?
           """, (datetime.now(), subscription_id))
           
           conn.commit()
           conn.close()
           
       elif event['type'] == 'customer.subscription.deleted':
           # Handle cancellation
           subscription_id = event['data']['object']['id']
           
           conn = get_db_connection()
           cursor = conn.cursor()
           
           cursor.execute("""
               UPDATE customers 
               SET status = 'cancelled', updated_at = ?
               WHERE stripe_subscription_id = ?
           """, (datetime.now(), subscription_id))
           
           conn.commit()
           conn.close()
       
       return {"status": "success"}
       
   except Exception as e:
       raise HTTPException(status_code=400, detail=str(e))

# Health check
@app.get("/health")
def health_check():
   """Health check endpoint"""
   return {
       "status": "healthy",
       "services": {
           "openai": "active" if SERVICES["openai"] else "offline",
           "sendgrid": "active" if SERVICES["sendgrid"] else "offline",
           "stripe": "active" if stripe.api_key else "offline"
       },
       "timestamp": datetime.now().isoformat()
   }

if __name__ == "__main__":
   print("🚀 Starting AI Lead Qualification System with Stripe Integration...")
   print("✅ System ready!")
   
   import uvicorn
   uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

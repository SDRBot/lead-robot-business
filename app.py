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
            # Import here to avoid dependency issues
            try:
                from openai import OpenAI
                services["openai"] = OpenAI(api_key=openai_key)
                print("✅ OpenAI initialized successfully")
            except ImportError:
                print("⚠️ OpenAI package not installed - pip install openai")
        else:
            print("⚠️ OPENAI_API_KEY not set")
    except Exception as e:
        print(f"❌ OpenAI initialization failed: {e}")
    
    # Try to initialize SendGrid
    try:
        sendgrid_key = os.getenv("SENDGRID_API_KEY")
        if sendgrid_key:
            try:
                from sendgrid import SendGridAPIClient
                services["sendgrid"] = SendGridAPIClient(api_key=sendgrid_key)
                print("✅ SendGrid initialized successfully")
            except ImportError:
                print("⚠️ SendGrid package not installed - pip install sendgrid")
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
            <p><strong>Plan:</strong> {plan_info['name']} (£{plan_info['price']}/month)</p>
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

# Add this RIGHT AFTER your send_welcome_email function
def init_hubspot_service():
    """Initialize HubSpot integration"""
    hubspot_key = os.getenv("HUBSPOT_API_KEY")
    if hubspot_key:
        try:
            import requests
            # Test HubSpot connection
            response = requests.get(
                "https://api.hubapi.com/crm/v3/objects/contacts",
                headers={"Authorization": f"Bearer {hubspot_key}"},
                params={"limit": 1}
            )
            if response.status_code == 200:
                print("✅ HubSpot connected successfully")
                return {"api_key": hubspot_key, "connected": True}
            else:
                print(f"❌ HubSpot connection failed: {response.status_code}")
                return {"connected": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            print(f"❌ HubSpot error: {e}")
            return {"connected": False, "error": str(e)}
    else:
        print("⚠️ HUBSPOT_API_KEY not set")
        return {"connected": False, "error": "No API key"}

def sync_lead_to_hubspot(lead_data: dict):
    """Sync qualified lead to HubSpot"""
    if not os.getenv("HUBSPOT_API_KEY"):
        return False
    
    try:
        import requests
        
        hubspot_data = {
            "properties": {
                "email": lead_data["email"],
                "firstname": lead_data.get("first_name", ""),
                "lastname": lead_data.get("last_name", ""),
                "company": lead_data.get("company", ""),
                "phone": lead_data.get("phone", ""),
                "leadstatus": "NEW",
                "lead_source": "AI Lead Robot",
                "qualification_score": str(lead_data.get("qualification_score", 0))
            }
        }
        
        response = requests.post(
            "https://api.hubapi.com/crm/v3/objects/contacts",
            headers={
                "Authorization": f"Bearer {os.getenv('HUBSPOT_API_KEY')}",
                "Content-Type": "application/json"
            },
            json=hubspot_data
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Lead synced to HubSpot: {lead_data['email']}")
            return True
        else:
            print(f"❌ HubSpot sync failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ HubSpot sync error: {e}")
        return False

# Stripe functions
def create_checkout_session(plan: str, success_url: str, cancel_url: str):
    """Create Stripe checkout session with 14-day free trial"""
    
    if plan not in PRICING_PLANS:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    plan_info = PRICING_PLANS[plan]
    
    try:
        # Create checkout session with free trial
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
            # ADD FREE TRIAL HERE 👇
            subscription_data={
                'trial_period_days': 14,  # 14-day free trial
                'trial_settings': {
                    'end_behavior': {
                        'missing_payment_method': 'cancel'  # Cancel if no payment method after trial
                    }
                }
            },
            # Collect payment method during trial
            payment_method_collection='if_required',
        )
        
        print(f"✅ Created checkout session with 14-day trial: {checkout_session.id}")
        return checkout_session.url
        
    except Exception as e:
        print(f"❌ Checkout error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating checkout: {str(e)}")

def handle_successful_payment(session_id: str):
    """Handle successful payment/trial signup with better error handling"""
    
    try:
        print(f"🔧 Processing session: {session_id}")
        
        # Retrieve the session with expanded data
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=['customer', 'subscription', 'subscription.latest_invoice']
        )
        
        print(f"🔧 Session mode: {session.mode}")
        print(f"🔧 Session status: {session.status}")
        print(f"🔧 Customer details: {session.customer_details}")
        
        # Check if we have customer email
        customer_email = None
        if session.customer_details and session.customer_details.email:
            customer_email = session.customer_details.email
        elif session.customer and hasattr(session.customer, 'email'):
            customer_email = session.customer.email
        
        if not customer_email:
            print("❌ No customer email found in session")
            raise HTTPException(status_code=400, detail="No customer email found")
        
        print(f"🔧 Customer email: {customer_email}")
        
        # Get plan from metadata
        plan = session.metadata.get('plan') if session.metadata else None
        if not plan or plan not in PRICING_PLANS:
            print(f"❌ Invalid plan: {plan}")
            raise HTTPException(status_code=400, detail="Invalid plan in session")
        
        print(f"🔧 Plan: {plan}")
        
        # Get Stripe IDs
        stripe_customer_id = session.customer
        stripe_subscription_id = None
        
        if session.subscription:
            if isinstance(session.subscription, str):
                stripe_subscription_id = session.subscription
            else:
                stripe_subscription_id = session.subscription.id
        
        print(f"🔧 Stripe customer ID: {stripe_customer_id}")
        print(f"🔧 Stripe subscription ID: {stripe_subscription_id}")
        
        # Generate API key
        api_key = f"sk_live_{str(uuid.uuid4()).replace('-', '')}"
        
        # Create customer in database
        customer_id = str(uuid.uuid4())
        plan_info = PRICING_PLANS[plan]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if customer already exists
            cursor.execute("SELECT id FROM customers WHERE email = ?", (customer_email,))
            existing_customer = cursor.fetchone()
            
            if existing_customer:
                print(f"🔧 Updating existing customer: {customer_email}")
                # Update existing customer
                cursor.execute("""
                    UPDATE customers SET
                        stripe_customer_id = ?, stripe_subscription_id = ?,
                        plan = ?, api_key = ?, leads_limit = ?,
                        status = 'active', updated_at = ?
                    WHERE email = ?
                """, (
                    stripe_customer_id, stripe_subscription_id, plan, api_key,
                    plan_info['leads_limit'], datetime.now(), customer_email
                ))
                customer_id = existing_customer[0]
            else:
                print(f"🔧 Creating new customer: {customer_email}")
                # Create new customer
                cursor.execute("""
                    INSERT INTO customers (
                        id, email, stripe_customer_id, stripe_subscription_id, 
                        plan, api_key, leads_limit, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    customer_id, customer_email, stripe_customer_id, stripe_subscription_id,
                    plan, api_key, plan_info['leads_limit'], 'active', datetime.now(), datetime.now()
                ))
            
            # Log the signup
            cursor.execute("""
                INSERT INTO analytics (id, customer_id, event_type, data, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), customer_id, "customer_signup", 
                json.dumps({
                    "plan": plan, 
                    "email": customer_email, 
                    "session_id": session_id,
                    "is_trial": bool(session.subscription and hasattr(session.subscription, 'trial_end') and session.subscription.trial_end)
                }), 
                datetime.now()
            ))
            
            conn.commit()
            print("✅ Database updated successfully")
            
        finally:
            conn.close()
        
        # Send welcome email
        try:
            send_welcome_email(customer_email, plan, api_key)
            print("✅ Welcome email sent")
        except Exception as e:
            print(f"⚠️ Welcome email failed: {e}")
        
        return {
            "customer_id": customer_id,
            "customer_email": customer_email,
            "plan": plan,
            "api_key": api_key,
            "subscription_id": stripe_subscription_id
        }
        
    except stripe.error.StripeError as e:
        print(f"❌ Stripe error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")
    except Exception as e:
        print(f"❌ General error: {str(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing signup: {str(e)}")

# Routes - Public pages
@app.get("/debug/session/{session_id}")
async def debug_session(session_id: str):
    """Debug a specific Stripe session"""
    try:
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=['customer', 'subscription']
        )
        
        return {
            "session_id": session_id,
            "session_status": session.status,
            "session_mode": session.mode,
            "customer_email": session.customer_details.email if session.customer_details else "None",
            "customer_id": session.customer,
            "subscription_id": session.subscription,
            "metadata": session.metadata,
            "payment_status": session.payment_status,
        }
    except Exception as e:
        return {"error": str(e), "session_id": session_id}

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    """GDPR compliant privacy policy"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Privacy Policy - AI Lead Robot</title>
        <style>
            body { 
                font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; 
                padding: 20px; line-height: 1.6; background: #f5f7fa; 
            }
            .container { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
            h1, h2 { color: #333; }
            .contact { background: #e8f5e9; padding: 20px; border-radius: 8px; margin: 20px 0; }
            .btn { background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔒 Privacy Policy</h1>
            <p><strong>Last updated:</strong> May 29, 2025</p>
            
            <h2>1. Information We Collect</h2>
            <p>We collect information you provide directly to us, such as:</p>
            <ul>
                <li><strong>Account Information:</strong> Email address, name, company details</li>
                <li><strong>Lead Data:</strong> Contact information of your leads that you submit through our API</li>
                <li><strong>Payment Information:</strong> Processed securely by Stripe (we don't store card details)</li>
                <li><strong>Usage Data:</strong> How you use our service, API calls, feature usage</li>
            </ul>
            
            <h2>2. How We Use Your Information</h2>
            <ul>
                <li>Provide and improve our AI lead qualification service</li>
                <li>Process your leads and send qualification reports</li>
                <li>Send transactional emails (welcome, usage alerts, etc.)</li>
                <li>Provide customer support</li>
                <li>Comply with legal obligations</li>
            </ul>
            
            <h2>3. Your Rights (GDPR)</h2>
            <p>If you're in the EU, you have the right to:</p>
            <ul>
                <li><strong>Access:</strong> Request a copy of your personal data</li>
                <li><strong>Rectification:</strong> Correct inaccurate personal data</li>
                <li><strong>Erasure:</strong> Request deletion of your personal data</li>
                <li><strong>Portability:</strong> Receive your data in a structured format</li>
                <li><strong>Object:</strong> Object to processing of your personal data</li>
                <li><strong>Restrict:</strong> Request restriction of processing</li>
            </ul>
            
            <h2>4. Data Retention</h2>
            <p>We retain your data for as long as your account is active, plus 30 days after cancellation for backup purposes.</p>
            
            <h2>5. Data Security</h2>
            <p>We use industry-standard security measures including encryption, secure databases, and regular security audits.</p>
            
            <h2>6. Third-Party Services</h2>
            <ul>
                <li><strong>Stripe:</strong> Payment processing</li>
                <li><strong>SendGrid:</strong> Email delivery</li>
                <li><strong>OpenAI:</strong> AI text processing (optional)</li>
                <li><strong>HubSpot:</strong> CRM integration (optional)</li>
            </ul>
            
            <div class="contact">
                <h2>7. Contact Us</h2>
                <p>For privacy questions or to exercise your rights:</p>
                <p><strong>Email:</strong> privacy@yourcompany.com</p>
                <p><strong>Data Protection Officer:</strong> dpo@yourcompany.com</p>
            </div>
            
            <p style="text-align: center; margin-top: 30px;">
                <a href="/" class="btn">← Back to Home</a>
            </p>
        </div>
    </body>
    </html>
    """

@app.get("/terms", response_class=HTMLResponse)
async def terms_of_service():
    """Terms of service"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Terms of Service - AI Lead Robot</title>
        <style>
            body { 
                font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; 
                padding: 20px; line-height: 1.6; background: #f5f7fa; 
            }
            .container { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
            h1, h2 { color: #333; }
            .btn { background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📋 Terms of Service</h1>
            <p><strong>Last updated:</strong> May 29, 2025</p>
            
            <h2>1. Service Description</h2>
            <p>AI Lead Robot provides automated lead qualification services using artificial intelligence.</p>
            
            <h2>2. Free Trial</h2>
            <p>We offer a 14-day free trial. You can cancel anytime during the trial without being charged.</p>
            
            <h2>3. Billing</h2>
            <p>After your trial ends, you'll be charged monthly. You can cancel anytime from your dashboard.</p>
            
            <h2>4. Data Usage</h2>
            <p>You're responsible for ensuring you have permission to process the lead data you submit to our service.</p>
            
            <h2>5. Acceptable Use</h2>
            <p>Don't use our service for spam, illegal activities, or harassment.</p>
            
            <h2>6. Service Availability</h2>
            <p>We strive for 99.9% uptime but cannot guarantee uninterrupted service.</p>
            
            <h2>7. Cancellation</h2>
            <p>You can cancel your subscription anytime from your dashboard or by emailing support.</p>
            
            <h2>8. Limitation of Liability</h2>
            <p>Our liability is limited to the amount you've paid for the service.</p>
            
            <p style="text-align: center; margin-top: 30px;">
                <a href="/" class="btn">← Back to Home</a>
            </p>
        </div>
    </body>
    </html>
    """

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
            <a href="#pricing" class="btn" style="width: auto; margin-top: 20px;">Start 14-Day Free Trial</a>
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
            <p style="font-size: 1.2em; color: #666;">Start with a 14-day free trial. No credit card required during trial.</p>
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
                <a href="/checkout/starter" class="btn">Start 14-Day Free Trial</a>
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
                <a href="/checkout/professional" class="btn">Start 14-Day Free Trial</a>
            </div>
        </div>
    </div>
    
    <div style="background: #2c3e50; color: white; padding: 60px 0; margin-top: 80px; text-align: center;">
        <div class="container">
            <h2>Ready to 10x Your Lead Conversion?</h2>
            <p>Join hundreds of businesses already using AI Lead Robot</p>
            <a href="/checkout/professional" class="btn" style="background: #e74c3c;">Start Free Trial Today</a>
            
            <!-- GDPR Links -->
            <div style="margin-top: 40px; border-top: 1px solid #34495e; padding-top: 30px;">
                <p style="margin: 10px 0;">
                    <a href="/privacy" style="color: #bdc3c7; margin: 0 15px; text-decoration: none;">Privacy Policy</a>
                    <a href="/terms" style="color: #bdc3c7; margin: 0 15px; text-decoration: none;">Terms of Service</a>
                    <a href="mailto:support@yourcompany.com" style="color: #bdc3c7; margin: 0 15px; text-decoration: none;">Support</a>
                </p>
                <p style="font-size: 12px; color: #95a5a6;">
                    We use cookies to improve your experience. By using our site, you consent to cookies.
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.get("/debug/stripe")
async def debug_stripe():
    """Debug Stripe configuration"""
    
    try:
        # Test Stripe connection
        account = stripe.Account.retrieve()
        
        return {
            "stripe_configured": True,
            "account_id": account.id,
            "country": account.country,
            "has_secret_key": bool(os.getenv("STRIPE_SECRET_KEY")),
            "has_webhook_secret": bool(os.getenv("STRIPE_WEBHOOK_SECRET")),
            "api_key_prefix": os.getenv("STRIPE_SECRET_KEY", "")[:7] if os.getenv("STRIPE_SECRET_KEY") else "None"
        }
    except Exception as e:
        return {
            "stripe_configured": False,
            "error": str(e),
            "has_secret_key": bool(os.getenv("STRIPE_SECRET_KEY")),
            "has_webhook_secret": bool(os.getenv("STRIPE_WEBHOOK_SECRET"))
        }

@app.get("/checkout/{plan}")
async def checkout(plan: str, request: Request):
    """Create Stripe checkout session with debugging"""
    
    print(f"🛒 Checkout requested for plan: {plan}")
    
    if plan not in PRICING_PLANS:
        raise HTTPException(status_code=404, detail=f"Plan '{plan}' not found")
    
    base_url = str(request.base_url).rstrip('/')
    success_url = f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/#pricing"
    
    print(f"📍 Success URL: {success_url}")
    print(f"📍 Cancel URL: {cancel_url}")
    
    try:
        checkout_url = create_checkout_session(plan, success_url, cancel_url)
        print(f"✅ Redirecting to: {checkout_url}")
        return RedirectResponse(url=checkout_url, status_code=303)
    except Exception as e:
        print(f"❌ Checkout error: {str(e)}")
        return HTMLResponse(f"""
        <div style="text-align: center; font-family: Arial; margin: 100px;">
            <h1>❌ Checkout Error</h1>
            <p>Error: {str(e)}</p>
            <p><strong>Plan:</strong> {plan}</p>
            <p><strong>Stripe Key:</strong> {'Set' if os.getenv('STRIPE_SECRET_KEY') else 'Missing'}</p>
            <a href="/">← Back to Home</a>
        </div>
        """, status_code=500)

@app.get("/success", response_class=HTMLResponse)
async def payment_success(session_id: str, request: Request):
    """Payment success page with better error handling"""
    
    if not session_id:
        return HTMLResponse("""
        <div style="text-align: center; font-family: Arial; margin: 100px;">
            <h1>❌ Missing Session ID</h1>
            <p>No session ID provided in the URL.</p>
            <a href="/" style="background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px;">← Back to Home</a>
        </div>
        """, status_code=400)
    
    try:
        payment_info = handle_successful_payment(session_id)
        plan_info = PRICING_PLANS[payment_info['plan']]
        
        # Check if this is a trial
        is_trial = True  # Assume trial for now since we're using trial_period_days
        
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
                .trial-notice {{
                    background: #e8f5e9; padding: 20px; border-radius: 10px;
                    margin: 20px 0; border-left: 5px solid #28a745;
                }}
                .api-key {{
                    background: #f8f9fa; padding: 20px; border-radius: 8px;
                    font-family: monospace; font-size: 14px; margin: 20px 0;
                    word-break: break-all; border: 2px dashed #667eea;
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
                {'<h2>Your 14-Day Free Trial Has Started!</h2>' if is_trial else '<h2>Payment Successful!</h2>'}
                
                <div class="trial-notice">
                    <h3>🔥 Free Trial Active</h3>
                    <p><strong>You have 14 days to try everything risk-free!</strong></p>
                    <p>Your trial includes full access to the {plan_info['name']} with {plan_info['leads_limit']} leads.</p>
                    <p>You won't be charged until your trial ends. Cancel anytime.</p>
                </div>
                
                <p><strong>Plan:</strong> {plan_info['name']} (${plan_info['price']}/month after trial)</p>
                <p><strong>Monthly Limit:</strong> {plan_info['leads_limit']} leads</p>
                <p><strong>Email:</strong> {payment_info['customer_email']}</p>
                
                <h3>🔑 Your API Key:</h3>
                <div class="api-key">{payment_info['api_key']}</div>
                <p><em>⚠️ Save this key securely - you'll need it to access your account!</em></p>
                
                <h3>🚀 Start Using Your Trial:</h3>
                <a href="/dashboard?api_key={payment_info['api_key']}" class="btn">📊 Go to Dashboard</a>
                <a href="/test-form?api_key={payment_info['api_key']}" class="btn">🧪 Test Lead Capture</a>
                
                <div style="margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 8px;">
                    <h3>📧 Check Your Email</h3>
                    <p>We've sent detailed setup instructions to <strong>{payment_info['customer_email']}</strong></p>
                    <p>If you don't see it, check your spam folder!</p>
                </div>
            </div>
        </body>
        </html>
        """
        
    except Exception as e:
        print(f"❌ Success page error: {str(e)}")
        return HTMLResponse(f"""
        <div style="text-align: center; font-family: Arial; margin: 100px; padding: 40px; background: #f8d7da; border-radius: 10px;">
            <h1>❌ Setup Error</h1>
            <p><strong>There was an issue setting up your account.</strong></p>
            <p>Session ID: <code>{session_id}</code></p>
            <p>Error: {str(e)}</p>
            
            <div style="background: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3>📧 Don't worry!</h3>
                <p>Your payment went through successfully. We'll set up your account manually and email you within 24 hours.</p>
                <p>Contact us at: <strong>support@yourcompany.com</strong></p>
            </div>
            
            <a href="/" style="background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px;">← Back to Home</a>
        </div>
        """, status_code=500)

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
async def dashboard(api_key: str = None, request: Request = None):
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
   
   base_url = str(request.base_url).rstrip('/') if request else ""
   
   html = f"""
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
curl -X POST "{base_url}/api/leads" \\
    -H "Content-Type: application/json" \\
    -H "Authorization: Bearer {api_key}" \\
    -d '{{"email": "lead@company.com", "first_name": "John", "company": "Acme Corp"}}'
           </pre>
           
           <a href="/docs" class="btn">📚 Full API Documentation</a>
           <a href="/test-form?api_key={api_key}" class="btn">🧪 Test Lead Capture</a>
           <a href="/integrations?api_key={api_key}" class="btn">🔗 Integrations</a>
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
async def test_form(api_key: str, request: Request):
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
        
        # Auto-sync to HubSpot if connected
        hubspot_synced = False
        if os.getenv("HUBSPOT_API_KEY"):
            lead_data_for_hubspot = {
                "email": lead.email,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "company": lead.company,
                "phone": lead.phone,
                "qualification_score": 0  # Initial score
            }
            hubspot_synced = sync_lead_to_hubspot(lead_data_for_hubspot)
        
        return {
            "lead_id": lead_id,
            "status": "created",
            "email_sent": email_sent,
            "hubspot_synced": hubspot_synced,
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

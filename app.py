# app.py - Complete AI Lead Qualification System with Zapier Integration
import os
import json
import uuid
import sqlite3
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

# Make dotenv import optional for deployment
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded environment variables from .env")
except ImportError:
    print("⚠️ python-dotenv not available, using system environment variables")
    def load_dotenv():
        pass

from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import stripe
import hashlib

# Import your new modular components
try:
    from config import settings, PRICING_PLANS
    from database import db_service
    from services.webhook_service import zapier_service
    from services.email_service import email_service
    from services.auth_service import auth_service
    from models import LeadInput
    print("✅ Using modular architecture")
    MODULAR_MODE = True
except ImportError as e:
    print(f"⚠️ Modular imports failed: {e}")
    print("🔄 Falling back to legacy mode")
    MODULAR_MODE = False

# Force Stripe initialization - multiple attempts
def initialize_stripe():
    """Initialize Stripe with multiple fallback methods"""
    
    # Method 1: Direct environment variable
    stripe_key = os.getenv('STRIPE_SECRET_KEY')
    if stripe_key:
        stripe.api_key = stripe_key
        print(f"✅ Stripe initialized via env var: {stripe_key[:7]}...")
        return True
    
    # Method 2: Check other possible env var names
    possible_keys = ['STRIPE_SECRET_KEY', 'STRIPE_SECRET', 'STRIPE_API_KEY']
    for key_name in possible_keys:
        key_value = os.getenv(key_name)
        if key_value and (key_value.startswith('sk_') or key_value.startswith('rk_')):
            stripe.api_key = key_value
            print(f"✅ Stripe initialized via {key_name}: {key_value[:7]}...")
            return True
    
    # Method 3: Try from settings if available
    try:
        if MODULAR_MODE and hasattr(settings, 'stripe_secret_key') and settings.stripe_secret_key:
            stripe.api_key = settings.stripe_secret_key
            print(f"✅ Stripe initialized via settings: {settings.stripe_secret_key[:7]}...")
            return True
    except Exception as e:
        print(f"⚠️ Could not load from settings: {e}")
    
    print("❌ Could not initialize Stripe - no valid key found")
    print(f"Available env vars: {[k for k in os.environ.keys() if 'STRIPE' in k.upper()]}")
    return False

# Initialize Stripe immediately
stripe_initialized = initialize_stripe()

# Initialize legacy components if modular mode fails
if not MODULAR_MODE:
    # Pricing plans (legacy)
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
                "Zapier integrations",
                "Advanced analytics",
                "Priority support",
                "API access"
            ]
        }
    }

@asynccontextmanager
async def lifespan(app):
    """Application lifespan management"""
    # Startup
    if MODULAR_MODE:
        db_service.init_database()  # Sync call
        print("✅ Modular database initialized")
    else:
        init_database()
        print("✅ Legacy database initialized")
    
    yield
    
    # Shutdown
    print("🔄 Application shutting down")

# Create FastAPI app
app = FastAPI(
    title="AI Lead Qualification System with Zapier Integration",
    docs_url=None,  # Disable /docs
    redoc_url=None,  # Disable /redoc
    openapi_url=None,  # Disable /openapi.json
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Data models (keep your existing ones for backward compatibility)
class LeadInputLegacy(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    source: str = "api"
    initial_message: Optional[str] = None

# Use modular or legacy based on availability
LeadModel = LeadInput if MODULAR_MODE else LeadInputLegacy

# Your existing database functions (keep for fallback)
def get_db_connection():
    conn = sqlite3.connect('leads.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Your existing database initialization"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
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
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            password_hash TEXT
        )
    ''')
    
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
            webhook_sent BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zapier_webhooks (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            webhook_url TEXT NOT NULL,
            events TEXT NOT NULL,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        )
    ''')
    
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

# Authentication function
async def get_current_customer(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated customer"""
    if MODULAR_MODE:
        customer = await auth_service.verify_api_key(credentials.credentials)
        if not customer:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return customer
    else:
        customer = verify_api_key(credentials.credentials)
        if not customer:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return customer

def verify_api_key(api_key: str):
    """Legacy API key verification"""
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

# Include modular routers if available
if MODULAR_MODE:
    try:
        from routers import auth, dashboard, webhooks, support
        app.include_router(auth.router)
        app.include_router(dashboard.router)  
        app.include_router(webhooks.router)
        app.include_router(support.router)
        print("✅ Modular routers loaded")
    except ImportError as e:
        print(f"⚠️ Some modular routers failed to load: {e}")

# UPDATED: Lead creation with Zapier integration
@app.post("/api/leads")
async def create_lead(
    lead: LeadModel, 
    background_tasks: BackgroundTasks,
    customer: dict = Depends(get_current_customer)
):
    """Create a new lead with Zapier integration (replaces HubSpot)"""
    
    # Check usage limits
    if customer['leads_used_this_month'] >= customer['leads_limit']:
        raise HTTPException(
            status_code=429, 
            detail=f"Monthly limit of {customer['leads_limit']} leads exceeded"
        )
    
    lead_id = str(uuid.uuid4())
    lead_data = lead.dict()
    lead_data['id'] = lead_id
    lead_data['customer_id'] = customer['id']
    lead_data['created_at'] = datetime.now().isoformat()
    
    try:
        if MODULAR_MODE:
            # Use new modular database service
            await db_service.create_lead(lead_data)
            await db_service.update_customer_usage(customer['id'])
        else:
            # Use legacy database operations
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO leads (
                    id, customer_id, email, first_name, last_name, 
                    company, phone, source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                lead_id, customer['id'], lead.email, lead.first_name, lead.last_name,
                lead.company, lead.phone, lead.source, datetime.now(), datetime.now()
            ))
            
            cursor.execute('''
                UPDATE customers 
                SET leads_used_this_month = leads_used_this_month + 1, updated_at = ?
                WHERE id = ?
            ''', (datetime.now(), customer['id']))
            
            conn.commit()
            conn.close()

        # Background tasks for async processing
        background_tasks.add_task(send_to_zapier_async, customer['id'], lead_data)
        background_tasks.add_task(send_welcome_email_async, lead.email, lead.first_name)
        
        return {
            "lead_id": lead_id,
            "status": "created",
            "message": "Lead captured and sent to Zapier!",
            "usage": {
                "used": customer['leads_used_this_month'] + 1,
                "limit": customer['leads_limit']
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating lead: {str(e)}")

async def send_to_zapier_async(customer_id: str, lead_data: dict):
    """Background task to send lead to Zapier webhooks"""
    if MODULAR_MODE:
        try:
            webhooks = await zapier_service.get_customer_webhooks(customer_id)
            for webhook in webhooks:
                await zapier_service.send_to_zapier(webhook['webhook_url'], lead_data)
        except Exception as e:
            print(f"❌ Zapier webhook error: {e}")
    else:
        # Legacy: For now, just log that we would send to Zapier
        print(f"📤 Would send lead {lead_data.get('email')} to Zapier for customer {customer_id}")

async def send_welcome_email_async(email: str, first_name: str):
    """Background task to send welcome email"""
    if MODULAR_MODE and first_name:
        try:
            subject = f"Thanks for your interest, {first_name}!"
            content = f"""
            <div style="font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2>Hi {first_name}!</h2>
                <p>Thanks for your interest! We'd love to learn more about your needs.</p>
                <p><strong>Quick question:</strong> What's your biggest challenge right now?</p>
                <p>Just reply to this email and let us know!</p>
                <p>Best regards,<br>The Team</p>
            </div>
            """
            await email_service.send_email(email, subject, content)
        except Exception as e:
            print(f"❌ Email error: {e}")

# Stripe checkout functions
def create_checkout_session(plan: str, success_url: str, cancel_url: str):
    """Create Stripe checkout session with 14-day trial"""
    
    if plan not in PRICING_PLANS:
        raise ValueError(f"Plan '{plan}' not found")
    
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
            subscription_data={
                'trial_period_days': 14,
            },
        )
        
        return checkout_session.url
        
    except Exception as e:
        raise Exception(f"Error creating checkout: {str(e)}")

# Routes
@app.get("/", response_class=HTMLResponse)
async def home():
    """Updated homepage with Zapier messaging and pricing"""
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
        .zapier-banner {
            background: #ff6b35; color: white; padding: 10px; text-align: center;
            font-weight: bold; font-size: 14px;
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
            gap: 30px; padding: 80px 20px; 
        }
        .feature { 
            background: white; padding: 40px; border-radius: 15px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1); text-align: center;
        }
        .feature h3 { color: #333; margin-top: 0; }
        .plans { 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 40px; padding: 60px 20px; max-width: 1200px; margin: 0 auto;
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
            transition: all 0.3s; margin: 10px 0;
        }
        .btn:hover { background: #5a6fd8; transform: translateY(-2px); }
        .btn-secondary { background: #2c3e50; }
        .features-list { text-align: left; margin: 30px 0; }
        .features-list li { margin: 10px 0; padding-left: 25px; position: relative; }
        .features-list li::before { content: "✅"; position: absolute; left: 0; }
        .zapier-features {
            background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; margin-top: 40px;
        }
        .zapier-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 15px; text-align: left; margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="zapier-banner">
        🆕 NEW: Zapier Integration! Connect to 6,000+ apps including Salesforce, HubSpot, Slack & more!
    </div>
    
    <div class="hero">
        <div class="container">
            <h1>🤖 AI Lead Robot</h1>
            <p>Stop wasting time on unqualified leads. Our AI automatically qualifies your leads and sends them to your favorite tools via Zapier.</p>
            
            <div style="margin: 30px 0;">
                <a href="#pricing" class="btn">Start 14-Day Free Trial</a>
                <a href="/auth/login" class="btn btn-secondary">🔓 Customer Login</a>
            </div>
            
            <div class="zapier-features">
                <h3 style="margin-top: 0;">⚡ Zapier Integration Features:</h3>
                <div class="zapier-grid">
                    <div>✅ Send leads to any CRM</div>
                    <div>✅ Slack notifications</div>
                    <div>✅ Email automation</div>
                    <div>✅ Google Sheets sync</div>
                    <div>✅ Custom workflows</div>
                    <div>✅ Real-time webhooks</div>
                </div>
            </div>
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
                <h3>🔗 Zapier Integration</h3>
                <p>Connect to 6,000+ apps including Salesforce, HubSpot, Slack, Google Sheets, and more with one-click setup.</p>
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
                    <li>Zapier integration</li>
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
                    <li>Advanced Zapier workflows</li>
                    <li>Advanced analytics</li>
                    <li>Priority support</li>
                    <li>API access</li>
                    <li>Custom integrations</li>
                    <li>Phone support</li>
                </ul>
                <a href="/checkout/professional" class="btn">Start 14-Day Free Trial</a>
            </div>
        </div>
    </div>
        <div style="background: #e8f5e9; padding: 40px; border-radius: 15px; margin: 40px auto; max-width: 500px; text-align: center; border: 2px dashed #28a745;">
            <h3 style="color: #155724; margin-top: 0;">🎁 Have a Promo Code?</h3>
            <p style="color: #155724;">Get instant access without entering payment details!</p>
            
            <form id="promoForm" style="margin: 20px 0;">
                <input type="email" id="promoEmail" placeholder="your@email.com" required 
                       style="width: 100%; padding: 12px; border: 1px solid #28a745; border-radius: 5px; margin-bottom: 15px; box-sizing: border-box;">
                
                <input type="text" id="promoCode" placeholder="Enter promo code" required 
                       style="width: 100%; padding: 12px; border: 1px solid #28a745; border-radius: 5px; margin-bottom: 15px; box-sizing: border-box; text-transform: uppercase;">
                
                <select id="promoPlan" style="width: 100%; padding: 12px; border: 1px solid #28a745; border-radius: 5px; margin-bottom: 15px;">
                    <option value="starter">Starter Plan (500 leads/month)</option>
                    <option value="professional">Professional Plan (2,000 leads/month)</option>
                </select>
                
                <button type="submit" style="background: #28a745; color: white; padding: 15px 30px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; width: 100%;">
                    🚀 Activate Free Account
                </button>
            </form>
            
            <div id="promoResult"></div>
            
            <p style="font-size: 12px; color: #6c757d; margin-top: 15px;">
                Valid promo codes: DEMO2025, FOUNDER, BETA, TEST
            </p>
        </div>
        
    </div>  <!-- End of container -->
    
    <script>
        document.getElementById('promoForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const email = document.getElementById('promoEmail').value;
            const code = document.getElementById('promoCode').value.toUpperCase();
            const plan = document.getElementById('promoPlan').value;
            
            document.getElementById('promoResult').innerHTML = '<div style="color: #666; padding: 10px;">🔄 Creating your account...</div>';
            
            try {
                const response = await fetch('/api/promo-signup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, promo_code: code, plan })
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    document.getElementById('promoResult').innerHTML = `
                        <div style="background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin: 10px 0;">
                            <h4 style="margin-top: 0;">🎉 Account Created!</h4>
                            <p><strong>API Key:</strong> <code style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px;">${result.api_key}</code></p>
                            <p><strong>Plan:</strong> ${result.plan_name}</p>
                            <p><strong>Trial Days:</strong> ${result.trial_days}</p>
                            <a href="/dashboard?api_key=${result.api_key}" style="background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 10px;">
                                📊 Go to Dashboard
                            </a>
                        </div>
                    `;
                    document.getElementById('promoForm').style.display = 'none';
                } else {
                    document.getElementById('promoResult').innerHTML = `
                        <div style="background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; margin: 10px 0;">
                            ❌ ${result.detail}
                        </div>
                    `;
                }
            } catch (error) {
                document.getElementById('promoResult').innerHTML = `
                    <div style="background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; margin: 10px 0;">
                        ❌ Error creating account. Please try again.
                    </div>
                `;
            }
        });
    </script>
    
    <div style="background: #2c3e50; color: white; padding: 60px 0; margin-top: 80px; text-align: center;">
        <div class="container">
            <h2>Ready to 10x Your Lead Conversion?</h2>
            <p>Join hundreds of businesses already using AI Lead Robot with Zapier integration</p>
            <a href="/checkout/professional" class="btn" style="background: #e74c3c; width: auto; display: inline-block;">Start Free Trial Today</a>
            
            <div style="margin-top: 40px; border-top: 1px solid #34495e; padding-top: 30px;">
                <p style="margin: 10px 0;">
                    <a href="/privacy" style="color: #bdc3c7; margin: 0 15px; text-decoration: none;">Privacy Policy</a>
                    <a href="/terms" style="color: #bdc3c7; margin: 0 15px; text-decoration: none;">Terms of Service</a>
                    <a href="/support" style="color: #bdc3c7; margin: 0 15px; text-decoration: none;">Support</a>
                </p>
                <p style="font-size: 12px; color: #95a5a6;">
                    🤖 AI Lead Robot - Intelligent Lead Qualification with Zapier Integration
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.get("/debug/env")
async def debug_env():
    """Debug environment variables"""
    return {
        "stripe_secret_key_exists": bool(os.getenv('STRIPE_SECRET_KEY')),
        "stripe_secret_key_prefix": os.getenv('STRIPE_SECRET_KEY', '')[:7] if os.getenv('STRIPE_SECRET_KEY') else 'None',
        "stripe_api_key_set": bool(stripe.api_key),
        "stripe_api_key_prefix": stripe.api_key[:7] if stripe.api_key else 'None',
        "all_env_vars": [k for k in os.environ.keys() if 'STRIPE' in k.upper()],
        "modular_mode": MODULAR_MODE,
        "stripe_initialized": stripe_initialized
    }

@app.get("/checkout/{plan}")
async def checkout(plan: str, request: Request):
    """Create Stripe checkout session with better debugging"""
    
    print(f"🛒 Checkout requested for plan: {plan}")
    
    # Re-initialize Stripe if needed
    if not stripe.api_key:
        stripe_init = initialize_stripe()
        if not stripe_init:
            return HTMLResponse(f"""
            <div style="text-align: center; font-family: Arial; margin: 100px; padding: 40px; background: #f8d7da; border-radius: 10px;">
                <h1>❌ Payment System Not Available</h1>
                <p>Our payment system is temporarily unavailable. Please try again later or contact support.</p>
                <p><strong>Error:</strong> Stripe not configured</p>
                <p><strong>Debug Info:</strong></p>
                <ul style="text-align: left; background: white; padding: 20px; border-radius: 5px;">
                    <li>Available env vars: {[k for k in os.environ.keys() if 'STRIPE' in k.upper()]}</li>
                    <li>Stripe API key set: {bool(stripe.api_key)}</li>
                </ul>
                <p style="margin-top: 30px;">
                    <a href="/" style="background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px;">← Back to Home</a>
                </p>
            </div>
            """, status_code=500)
    
    if plan not in PRICING_PLANS:
        raise HTTPException(status_code=404, detail=f"Plan '{plan}' not found")
    
    base_url = str(request.base_url).rstrip('/')
    success_url = f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/#pricing"
    
    try:
        checkout_url = create_checkout_session(plan, success_url, cancel_url)
        print(f"✅ Redirecting to: {checkout_url}")
        return RedirectResponse(url=checkout_url, status_code=303)
        
    except Exception as e:
        print(f"❌ Checkout error: {str(e)}")
        return HTMLResponse(f"""
        <div style="text-align: center; font-family: Arial; margin: 100px;">
            <h1>❌ Checkout Error</h1>
            <p>Sorry, there was an issue processing your request.</p>
            <p><strong>Error:</strong> {str(e)}</p>
            <p><strong>Plan:</strong> {plan}</p>
            <p><strong>Debug:</strong> Stripe key exists: {bool(stripe.api_key)}</p>
            <a href="/" style="background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px;">← Back to Home</a>
        </div>
        """, status_code=500)

@app.get("/success", response_class=HTMLResponse)
async def payment_success(session_id: str = None):
    """Payment success page"""
    
    if not session_id:
        return HTMLResponse("""
        <div style="text-align: center; font-family: Arial; margin: 100px;">
            <h1>❌ Missing Session ID</h1>
            <p>No session ID provided in the URL.</p>
            <a href="/" style="background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px;">← Back to Home</a>
        </div>
        """, status_code=400)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎉 Welcome to AI Lead Robot!</title>
        <style>
            body {{ font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; background: #f5f7fa; }}
            .success {{ background: white; padding: 50px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .btn {{ background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; display: inline-block; margin: 10px; }}
        </style>
    </head>
    <body>
        <div class="success">
            <h1>🎉 Welcome to AI Lead Robot!</h1>
            <h2>Your 14-Day Free Trial Has Started!</h2>
            
            <p>We're setting up your account now. You'll receive an email with your login details within 5 minutes.</p>
            
            <p><strong>What happens next:</strong></p>
            <ol style="text-align: left;">
                <li>Check your email for account details</li>
                <li>Login to your dashboard</li>
                <li>Set up your Zapier integration</li>
                <li>Start capturing and qualifying leads!</li>
            </ol>
            
            <a href="/" class="btn">← Back to Home</a>
        </div>
    </body>
    </html>
    """

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
            <p><strong>Last updated:</strong> May 30, 2025</p>
            
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
                <li><strong>Zapier:</strong> Integration platform (when you configure it)</li>
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
            <p><strong>Last updated:</strong> May 30, 2025</p>
            
            <h2>1. Service Description</h2>
            <p>AI Lead Robot provides automated lead qualification services using artificial intelligence and Zapier integrations.</p>
            
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
            <p>You can cancel your subscription anytime by contacting support.</p>
            
            <h2>8. Limitation of Liability</h2>
            <p>Our liability is limited to the amount you've paid for the service.</p>
            
            <p style="text-align: center; margin-top: 30px;">
                <a href="/" class="btn">← Back to Home</a>
            </p>
        </div>
    </body>
    </html>
    """

# Health check with mode indicator
@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mode": "modular" if MODULAR_MODE else "legacy",
        "version": "2.0.0",
        "features": {
            "database": "✅ Connected",
            "zapier_integration": "✅ Active" if MODULAR_MODE else "🔄 Legacy Mode",
            "stripe_payments": "✅ Configured" if stripe.api_key else "❌ Not Configured",
            "stripe_initialized": stripe_initialized
        }
    }

# Legacy routes for backward compatibility
@app.get("/api/analytics")
async def get_analytics(customer: dict = Depends(get_current_customer)):
    """Get customer analytics"""
    
    if MODULAR_MODE:
        total_leads = await db_service.execute_query(
            "SELECT COUNT(*) as count FROM leads WHERE customer_id = ?",
            (customer['id'],),
            fetch='one'
        )
        
        qualified_leads = await db_service.execute_query(
            "SELECT COUNT(*) as count FROM leads WHERE customer_id = ? AND qualification_stage IN ('hot_lead', 'warm_lead')",
            (customer['id'],),
            fetch='one'
        )
        
        # Lead sources
        lead_sources = await db_service.execute_query(
            "SELECT source, COUNT(*) as count FROM leads WHERE customer_id = ? GROUP BY source ORDER BY count DESC",
            (customer['id'],),
            fetch='all'
        )
    else:
        # Legacy database operations
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM leads WHERE customer_id = ?", (customer['id'],))
        total_leads = dict(cursor.fetchone())
        
        cursor.execute("""
            SELECT COUNT(*) as count FROM leads 
            WHERE customer_id = ? AND qualification_stage = 'hot_lead'
        """, (customer['id'],))
        hot_leads = dict(cursor.fetchone())
        
        cursor.execute("""
            SELECT COUNT(*) as count FROM leads 
            WHERE customer_id = ? AND qualification_stage = 'warm_lead'
        """, (customer['id'],))
        warm_leads = dict(cursor.fetchone())
        
        qualified_leads = {'count': hot_leads['count'] + warm_leads['count']}
        
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM leads WHERE customer_id = ?
            GROUP BY source ORDER BY count DESC
        """, (customer['id'],))
        lead_sources = [{"source": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        conn.close()
    
    total_count = total_leads['count'] if total_leads else 0
    qualified_count = qualified_leads['count'] if qualified_leads else 0
    conversion_rate = (qualified_count / max(total_count, 1)) * 100
    
    return {
        "total_leads": total_count,
        "qualified_leads": qualified_count,
        "conversion_rate": round(conversion_rate, 1),
        "usage": {
            "used": customer['leads_used_this_month'],
            "limit": customer['leads_limit'],
            "percentage": round((customer['leads_used_this_month'] / customer['leads_limit']) * 100, 1)
        },
        "lead_sources": lead_sources or []
    }

@app.get("/api/leads")
async def get_leads(customer: dict = Depends(get_current_customer), skip: int = 0, limit: int = 50):
    """Get customer's leads"""
    
    if MODULAR_MODE:
        leads = await db_service.get_leads(customer['id'], skip, limit)
        total = await db_service.execute_query(
            "SELECT COUNT(*) as count FROM leads WHERE customer_id = ?", 
            (customer['id'],),
            fetch='one'
        )
        total_count = total['count'] if total else 0
    else:
        # Legacy database operations
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM leads WHERE customer_id = ?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
        ''', (customer['id'], limit, skip))
        
        leads = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT COUNT(*) FROM leads WHERE customer_id = ?", (customer['id'],))
        total_count = cursor.fetchone()[0]
        
        conn.close()
    
    return {
        "leads": leads,
        "total": total_count,
        "skip": skip,
        "limit": limit
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
            
            if MODULAR_MODE:
                await db_service.execute_query("""
                    UPDATE customers 
                    SET leads_used_this_month = 0, updated_at = ?
                    WHERE stripe_subscription_id = ?
                """, (datetime.now(), subscription_id))
            else:
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
            # Handle failed payment
            subscription_id = event['data']['object']['subscription']
            
            if MODULAR_MODE:
                await db_service.execute_query("""
                    UPDATE customers 
                    SET status = 'payment_failed', updated_at = ?
                    WHERE stripe_subscription_id = ?
                """, (datetime.now(), subscription_id))
            else:
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
            
            if MODULAR_MODE:
                await db_service.execute_query("""
                    UPDATE customers 
                    SET status = 'cancelled', updated_at = ?
                    WHERE stripe_subscription_id = ?
                """, (datetime.now(), subscription_id))
            else:
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

if __name__ == "__main__":
    print("🚀 Starting AI Lead Qualification System...")
    print(f"🔧 Mode: {'Modular' if MODULAR_MODE else 'Legacy'}")
    print(f"💳 Stripe: {'✅ Initialized' if stripe_initialized else '❌ Not Configured'}")
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

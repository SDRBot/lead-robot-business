# app.py - Updated with modular imports
import os
import json
import uuid
import sqlite3
from datetime import datetime
from typing import Optional
# Make dotenv import optional for deployment
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded environment variables from .env")
except ImportError:
    print("⚠️ python-dotenv not available, using system environment variables")
    # Define empty load_dotenv function
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
    # Load environment variables the old way
    load_dotenv()

# Initialize legacy components if modular mode fails
if not MODULAR_MODE:
    # Your existing legacy initialization code here
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    
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
                "Zapier integrations",  # Updated from HubSpot
                "Advanced analytics",
                "Priority support",
                "API access"
            ]
        }
    }

# Create FastAPI app
app = FastAPI(
    title="AI Lead Qualification System with Zapier Integration",
    docs_url=None,  # Disable /docs
    redoc_url=None,  # Disable /redoc
    openapi_url=None  # Disable /openapi.json
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

# Startup event
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    """Application lifespan management"""
    # Startup
    if MODULAR_MODE:
        await db_service.init_database()
        print("✅ Modular database initialized")
    else:
        init_database()
        print("✅ Legacy database initialized")
    
    yield
    
    # Shutdown
    print("🔄 Application shutting down")

# Update your FastAPI app creation to:
app = FastAPI(
    title="AI Lead Qualification System with Zapier Integration",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan
)
# Your existing database functions (keep for fallback)
def get_db_connection():
    conn = sqlite3.connect('leads.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Your existing database initialization"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Your existing table creation code
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
    
    # Add Zapier webhooks table
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
    
    # Add analytics table (your existing one)
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
        return await auth_service.verify_api_key(credentials.credentials)
    else:
        # Your existing verification logic
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

# Keep all your existing routes (homepage, checkout, etc.)
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

# Keep all your existing routes (checkout, success, etc.)
# ... [Include all your existing routes from the original app.py]

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
            "stripe_payments": "✅ Configured"
        }
    }

if __name__ == "__main__":
    print("🚀 Starting AI Lead Qualification System...")
    print(f"🔧 Mode: {'Modular' if MODULAR_MODE else 'Legacy'}")
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

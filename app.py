# app.py - Production-ready AI Email Agent for Render deployment
import os
import json
import uuid
import sqlite3
import html
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ai_email_agent")

# Environment variables with Render-specific defaults
PORT = int(os.environ.get("PORT", 8000))
HOST = os.environ.get("HOST", "0.0.0.0")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")

from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, EmailStr
import stripe

# Initialize Stripe for production
def initialize_stripe():
    """Initialize Stripe for production deployment"""
    stripe_key = os.environ.get('STRIPE_SECRET_KEY')
    if stripe_key and stripe_key.startswith('sk_'):
        stripe.api_key = stripe_key
        logger.info("✅ Stripe initialized for production")
        return True
    else:
        logger.warning("⚠️ Stripe not configured - payment features disabled")
        return False

stripe_initialized = initialize_stripe()

# Production pricing plans
PRICING_PLANS = {
    "starter": {
        "name": "Starter Plan",
        "price": 99,
        "leads_limit": 500,
        "description": "Perfect for small businesses",
        "features": [
            "500 email conversations per month",
            "AI-powered qualification", 
            "Email automation",
            "Basic analytics",
            "Zapier integration",
            "Email support"
        ]
    },
    "professional": {
        "name": "Professional Plan", 
        "price": 299,
        "leads_limit": 2000,
        "description": "Great for growing businesses",
        "features": [
            "2,000 email conversations per month",
            "Everything in Starter",
            "Advanced AI training",
            "Team management",
            "Advanced analytics",
            "Priority support",
            "API access",
            "Custom integrations"
        ]
    }
}

# Database setup for production
def get_db_path():
    """Get database path - persistent on Render"""
    if ENVIRONMENT == "production":
        # On Render, use /opt/render/project/src/ for persistence
        db_dir = Path("/opt/render/project/src")
        db_dir.mkdir(exist_ok=True)
        return db_dir / "leads.db"
    return Path("leads.db")

def get_db_connection():
    """Get database connection with production optimizations"""
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(str(db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Production SQLite optimizations
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=1000")
        conn.execute("PRAGMA temp_store=MEMORY")
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

def init_database():
    """Initialize database with production settings"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Core tables - optimized for production
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                stripe_customer_id TEXT UNIQUE,
                stripe_subscription_id TEXT,
                plan TEXT NOT NULL DEFAULT 'starter',
                status TEXT DEFAULT 'active',
                api_key TEXT UNIQUE NOT NULL,
                leads_limit INTEGER NOT NULL DEFAULT 500,
                leads_used_this_month INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_conversations (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                lead_email TEXT NOT NULL,
                lead_name TEXT DEFAULT '',
                company TEXT DEFAULT '',
                subject TEXT NOT NULL,
                last_message TEXT,
                message_count INTEGER DEFAULT 0,
                interest_score INTEGER DEFAULT 0,
                status TEXT DEFAULT 'new',
                ai_suggested_response TEXT DEFAULT '',
                next_action TEXT DEFAULT '',
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
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
                source TEXT DEFAULT 'api',
                qualification_score INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
        ''')
        
        # Create indexes for production performance
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_customers_api_key ON customers(api_key)',
            'CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)',
            'CREATE INDEX IF NOT EXISTS idx_conversations_customer ON email_conversations(customer_id)',
            'CREATE INDEX IF NOT EXISTS idx_conversations_status ON email_conversations(status)',
            'CREATE INDEX IF NOT EXISTS idx_leads_customer ON leads(customer_id)'
        ]
        
        for index in indexes:
            cursor.execute(index)
        
        conn.commit()
        conn.close()
        logger.info("✅ Production database initialized")
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

# Initialize database on startup
init_database()

# FastAPI app with production settings
app = FastAPI(
    title="AI Email Agent System",
    description="Intelligent email conversation automation with AI-powered lead qualification",
    version="2.0.0",
    docs_url=None if ENVIRONMENT == "production" else "/docs",
    redoc_url=None if ENVIRONMENT == "production" else "/redoc",
    openapi_url=None if ENVIRONMENT == "production" else "/openapi.json"
)

# CORS for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for your domain
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

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

class EmailConversationInput(BaseModel):
    from_email: EmailStr
    to_email: EmailStr
    subject: str
    content: str
    lead_name: Optional[str] = None
    company: Optional[str] = None

# Error handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid input data", "errors": exc.errors()}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Authentication
def verify_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """Verify API key"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE api_key = ? AND status = 'active'", (api_key,))
        customer = cursor.fetchone()
        conn.close()
        return dict(customer) if customer else None
    except Exception as e:
        logger.error(f"API key verification error: {e}")
        return None

async def get_current_customer(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get authenticated customer"""
    customer = verify_api_key(credentials.credentials)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return customer

# AI Helper Functions
def calculate_interest_score(email_content: str) -> int:
    """Calculate lead interest score"""
    if not email_content:
        return 0
    
    content_lower = email_content.lower()
    score = 30
    
    positive_indicators = {
        'interested': 15, 'demo': 20, 'pricing': 18, 'budget': 25,
        'buy': 20, 'purchase': 20, 'meeting': 15, 'call': 12,
        'urgent': 15, 'decision': 18, 'timeline': 12
    }
    
    negative_indicators = {
        'not interested': -30, 'unsubscribe': -40, 'stop': -25,
        'spam': -35, 'too expensive': -15
    }
    
    for word, weight in positive_indicators.items():
        if word in content_lower:
            score += weight
    
    for word, weight in negative_indicators.items():
        if word in content_lower:
            score += weight
    
    score += min(email_content.count('?') * 8, 20)
    
    if len(email_content) > 100:
        score += min(len(email_content) // 50, 15)
    
    return max(0, min(100, score))

def generate_ai_response(email_content: str, customer_data: dict) -> str:
    """Generate AI response"""
    content_lower = email_content.lower()
    
    if any(word in content_lower for word in ['pricing', 'price', 'cost']):
        return "Hi! Thanks for your interest in our pricing. I'd love to understand your specific needs better so I can provide the most relevant pricing information. Could we schedule a quick 15-minute call to discuss your requirements?"
    
    elif any(word in content_lower for word in ['demo', 'demonstration']):
        return "Hi! I'd be delighted to show you a demo of our solution. When would be a good time for you this week? I can walk you through a personalized demo that focuses on your specific use case."
    
    elif any(word in content_lower for word in ['interested', 'tell me more']):
        return "Hi! Thanks for reaching out and expressing interest. I'd love to learn more about your current situation and see how we can help you achieve your goals. Would you be available for a brief conversation this week?"
    
    else:
        return "Hi! Thanks for your email. I'd love to learn more about your current challenges to see how we might be able to help. When would be a good time for a quick conversation?"

# === CORE API ENDPOINTS ===

@app.get("/", response_class=HTMLResponse)
async def home():
    """Homepage"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 AI Email Agent - Automate Your Sales Conversations</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
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
            .btn {
                background: #667eea; color: white; padding: 15px 30px; border: none;
                border-radius: 8px; font-size: 18px; font-weight: bold; cursor: pointer;
                text-decoration: none; display: inline-block; margin: 10px;
                transition: all 0.3s;
            }
            .btn:hover { background: #5a6fd8; transform: translateY(-2px); }
            .btn-secondary { background: #2c3e50; }
            .features { 
                display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 30px; padding: 60px 20px; 
            }
            .feature { 
                background: white; padding: 30px; border-radius: 15px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1); text-align: center;
            }
        </style>
    </head>
    <body>
        <div class="hero">
            <div class="container">
                <h1>🤖 AI Email Agent</h1>
                <p>Your AI assistant that reads, scores, and responds to sales emails automatically.</p>
                
                <div style="margin: 30px 0;">
                    <a href="/dashboard" class="btn">📊 Get Started</a>
                    <a href="/health" class="btn btn-secondary">🔍 System Status</a>
                </div>
            </div>
        </div>
        
        <div class="container">
            <div class="features">
                <div class="feature">
                    <h3>🧠 AI-Powered Analysis</h3>
                    <p>Automatically analyzes emails and scores lead interest from 0-100</p>
                </div>
                <div class="feature">
                    <h3>📧 Smart Responses</h3>
                    <p>Generates human-like email responses based on content and context</p>
                </div>
                <div class="feature">
                    <h3>⚡ Zapier Integration</h3>
                    <p>Connects to 6,000+ apps including CRM, Slack, and more</p>
                </div>
            </div>
        </div>
        
        <div style="background: #2c3e50; color: white; padding: 60px 0; text-align: center;">
            <div class="container">
                <h2>Ready to Automate Your Email Responses?</h2>
                <a href="/dashboard" class="btn">Get Started Now</a>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(api_key: str = None):
    """Dashboard with API key management"""
    if not api_key:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>📊 Dashboard - AI Email Agent</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: Arial; background: #f5f7fa; margin: 0; padding: 20px; }
                .container { 
                    max-width: 500px; margin: 50px auto; background: white; 
                    padding: 40px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                    text-align: center;
                }
                .form-group { margin: 20px 0; text-align: left; }
                label { display: block; margin-bottom: 5px; font-weight: bold; }
                input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
                .btn { 
                    background: #667eea; color: white; padding: 12px 24px; border: none; 
                    border-radius: 5px; cursor: pointer; width: 100%; font-size: 16px;
                }
                .btn:hover { background: #5a6fd8; }
                .demo-section { background: #e8f5e9; padding: 20px; border-radius: 8px; margin: 20px 0; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📊 AI Email Agent Dashboard</h1>
                <p>Enter your API key to access your dashboard, or create a free account</p>
                
                <form method="get">
                    <div class="form-group">
                        <label for="api_key">API Key:</label>
                        <input type="text" name="api_key" id="api_key" placeholder="sk_..." required>
                    </div>
                    <button type="submit" class="btn">Access Dashboard</button>
                </form>
                
                <div class="demo-section">
                    <h4>🆓 Try it Free</h4>
                    <p>Get instant access with promo code <strong>TEST</strong></p>
                    <form id="signupForm">
                        <input type="email" id="email" placeholder="your@email.com" required style="margin-bottom: 10px;">
                        <button type="submit" class="btn">Create Free Account</button>
                    </form>
                    <div id="result" style="margin-top: 10px;"></div>
                </div>
                
                <p><a href="/" style="color: #667eea;">← Back to Home</a></p>
            </div>
            
            <script>
                document.getElementById('signupForm').addEventListener('submit', async (e) => {
                    e.preventDefault();
                    const email = document.getElementById('email').value;
                    
                    document.getElementById('result').innerHTML = '<p>Creating account...</p>';
                    
                    try {
                        const response = await fetch('/api/promo-signup', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ 
                                email: email, 
                                promo_code: 'TEST', 
                                plan: 'starter' 
                            })
                        });
                        
                        const result = await response.json();
                        
                        if (response.ok) {
                            document.getElementById('result').innerHTML = `
                                <div style="background: #d4edda; color: #155724; padding: 15px; border-radius: 5px;">
                                    <strong>✅ Account Created!</strong><br>
                                    <small>API Key: ${result.api_key}</small><br>
                                    <button onclick="window.location.href='/dashboard?api_key=${result.api_key}'" 
                                            style="background: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; margin-top: 5px; cursor: pointer;">
                                        Open Dashboard
                                    </button>
                                </div>
                            `;
                        } else {
                            document.getElementById('result').innerHTML = `
                                <div style="background: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px;">
                                    ❌ ${result.detail}
                                </div>
                            `;
                        }
                    } catch (error) {
                        document.getElementById('result').innerHTML = `
                            <div style="background: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px;">
                                ❌ Error creating account
                            </div>
                        `;
                    }
                });
            </script>
        </body>
        </html>
        """)
    
    # Verify API key and show dashboard
    customer = verify_api_key(api_key)
    if not customer:
        return HTMLResponse("""
        <div style="text-align: center; font-family: Arial; margin: 100px auto; max-width: 500px; padding: 40px; background: #f8d7da; border-radius: 15px;">
            <h1 style="color: #721c24;">❌ Invalid API Key</h1>
            <p>The API key provided is invalid or expired.</p>
            <a href="/dashboard" style="color: #667eea;">← Try Again</a>
        </div>
        """)
    
    # Get stats
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM leads WHERE customer_id = ?", (customer['id'],))
        total_leads = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM email_conversations WHERE customer_id = ?", (customer['id'],))
        total_conversations = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM email_conversations WHERE customer_id = ? AND interest_score >= 70", (customer['id'],))
        hot_leads = cursor.fetchone()[0]
        
        conn.close()
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        total_leads = total_conversations = hot_leads = 0
    
    plan_info = PRICING_PLANS.get(customer['plan'], PRICING_PLANS['starter'])
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>📊 Dashboard - AI Email Agent</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: Arial; margin: 0; background: #f5f7fa; }}
            .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
            .header {{ 
                background: linear-gradient(135deg, #667eea, #764ba2); 
                color: white; padding: 30px; border-radius: 15px; margin-bottom: 30px; 
            }}
            .metrics {{ 
                display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                gap: 20px; margin: 30px 0; 
            }}
            .metric {{ 
                background: white; padding: 25px; border-radius: 10px; 
                box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; 
            }}
            .metric h3 {{ margin: 0 0 10px 0; color: #666; font-size: 14px; }}
            .value {{ font-size: 32px; font-weight: bold; color: #667eea; }}
            .btn {{ 
                background: #667eea; color: white; padding: 10px 20px; 
                text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px; 
            }}
            .card {{ 
                background: white; padding: 30px; border-radius: 15px; 
                box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin: 20px 0; 
            }}
            .api-key {{ 
                background: #f8f9fa; padding: 15px; border-radius: 5px; 
                font-family: monospace; word-break: break-all; margin: 10px 0; 
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 AI Email Agent Dashboard</h1>
                <p>Welcome back! Here's your email automation overview.</p>
                <p><strong>Plan:</strong> {html.escape(plan_info['name'])} | <strong>Email:</strong> {html.escape(customer['email'])}</p>
            </div>
            
            <div class="metrics">
                <div class="metric">
                    <h3>Total Leads</h3>
                    <div class="value">{total_leads}</div>
                </div>
                <div class="metric">
                    <h3>Email Conversations</h3>
                    <div class="value">{total_conversations}</div>
                </div>
                <div class="metric">
                    <h3>Hot Leads (70+)</h3>
                    <div class="value">{hot_leads}</div>
                </div>
                <div class="metric">
                    <h3>Monthly Usage</h3>
                    <div class="value">{customer['leads_used_this_month']}/{customer['leads_limit']}</div>
                </div>
            </div>
            
            <div class="card">
                <h3>🔑 Your API Key</h3>
                <div class="api-key">{html.escape(api_key)}</div>
                <p>Use this API key to integrate with your email system or CRM.</p>
                
                <h4>📧 Test API:</h4>
                <button onclick="testAPI()" class="btn">🧪 Send Test Email</button>
                <div id="testResult" style="margin-top: 10px;"></div>
            </div>
            
            <div class="card">
                <h3>📚 Quick Actions</h3>
                <a href="/health" class="btn">🔍 System Health</a>
                <a href="/" class="btn">🏠 Home</a>
                <button onclick="location.reload()" class="btn">🔄 Refresh</button>
            </div>
        </div>
        
        <script>
            async function testAPI() {{
                const testData = {{
                    from_email: "test@example.com",
                    to_email: "{html.escape(customer['email'])}",
                    subject: "Test Email - AI Agent",
                    content: "Hi, I'm interested in learning more about your solution. Can you tell me about pricing and schedule a demo?",
                    lead_name: "Test User",
                    company: "Test Company"
                }};
                
                document.getElementById('testResult').innerHTML = '<p style="color: #666;">🤖 Processing test email...</p>';
                
                try {{
                    const response = await fetch('/api/email-conversation', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                            'Authorization': 'Bearer {api_key}'
                        }},
                        body: JSON.stringify(testData)
                    }});
                    
                    const result = await response.json();
                    
                    if (response.ok) {{
                        document.getElementById('testResult').innerHTML = `
                            <div style="background: #d4edda; color: #155724; padding: 15px; border-radius: 5px;">
                                ✅ Test email processed successfully!<br>
                                <small>Conversation ID: ${{result.conversation_id}}</small><br>
                                <em>AI response will be generated in a few seconds.</em>
                            </div>
                        `;
                        setTimeout(() => location.reload(), 3000);
                    }} else {{
                        document.getElementById('testResult').innerHTML = `
                            <div style="background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px;">
                                ❌ Test failed: ${{result.detail}}
                            </div>
                        `;
                    }}
                }} catch (error) {{
                    document.getElementById('testResult').innerHTML = `
                        <div style="background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px;">
                            ❌ Error: ${{error.message}}
                        </div>
                    `;
                }}
            }}
        </script>
    </body>
    </html>
    """

@app.post("/api/email-conversation")
async def process_email_conversation(
    email_data: EmailConversationInput,
    background_tasks: BackgroundTasks,
    customer: dict = Depends(get_current_customer)
):
    """Process incoming email and generate AI response"""
    try:
        conversation_id = str(uuid.uuid4())
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create or update conversation
        cursor.execute("""
            INSERT OR REPLACE INTO email_conversations (
                id, customer_id, lead_email, lead_name, company, subject,
                last_message, message_count, last_activity, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conversation_id, customer['id'], email_data.from_email,
            email_data.lead_name or '', email_data.company or '', email_data.subject,
            email_data.content[:500], 1, datetime.now(), datetime.now()
        ))
        
        conn.commit()
        conn.close()
        
        # Generate AI response in background
        background_tasks.add_task(generate_ai_response_async, customer['id'], conversation_id, email_data.content)
        
        return {
            "conversation_id": conversation_id,
            "status": "processed",
            "message": "Email received and AI response being generated"
        }
        
    except Exception as e:
        logger.error(f"Error processing email: {e}")
        raise HTTPException(status_code=500, detail="Error processing email")

@app.post("/api/promo-signup")
async def promo_signup(request: Request):
    """Create account with promo code"""
    try:
        body = await request.json()
        email = body.get('email')
        promo_code = body.get('promo_code', '').upper()
        plan = body.get('plan', 'starter')
        
        # Valid promo codes
        valid_codes = {
            'TEST': {'trial_days': 14, 'plan_override': None},
            'DEMO': {'trial_days': 30, 'plan_override': None},
            'BETA': {'trial_days': 60, 'plan_override': 'professional'}
        }
        
        if promo_code not in valid_codes:
            raise HTTPException(status_code=400, detail=f"Invalid promo code: {promo_code}")
        
        # Check if customer exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="Account with this email already exists")
        
        # Create customer
        api_key = f"sk_live_{str(uuid.uuid4()).replace('-', '')}"
        customer_id = str(uuid.uuid4())
        plan_info = PRICING_PLANS[plan]
        
        cursor.execute('''
            INSERT INTO customers (id, email, plan, api_key, leads_limit, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (customer_id, email, plan, api_key, plan_info['leads_limit'], 'active', datetime.now()))
        
        conn.commit()
        conn.close()
        
        logger.info(f"New account created: {email} with promo {promo_code}")
        
        return {
            "success": True,
            "customer_id": customer_id,
            "email": email,
            "api_key": api_key,
            "plan": plan,
            "plan_name": plan_info['name'],
            "trial_days": valid_codes[promo_code]['trial_days'],
            "message": "Account created successfully!"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Promo signup error: {e}")
        raise HTTPException(status_code=500, detail="Error creating account")

# Background tasks
async def generate_ai_response_async(customer_id: str, conversation_id: str, email_content: str):
    """Generate AI response in background"""
    try:
        # Get customer data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        customer = dict(cursor.fetchone())
        
        # Generate AI analysis
        interest_score = calculate_interest_score(email_content)
        suggested_response = generate_ai_response(email_content, customer)
        
        next_action = "Schedule demo call" if interest_score >= 70 else "Follow up with information"
        
        # Update conversation
        cursor.execute("""
            UPDATE email_conversations 
            SET interest_score = ?, ai_suggested_response = ?, next_action = ?
            WHERE id = ?
        """, (interest_score, suggested_response, next_action, conversation_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"AI response generated: score {interest_score}/100")
        
    except Exception as e:
        logger.error(f"AI response generation error: {e}")

# Health check for Render
@app.get("/health")
def health_check():
    """Health check endpoint for Render"""
    try:
        # Test database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Health check DB error: {e}")
        db_status = "unhealthy"
    
    return {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "environment": ENVIRONMENT,
        "database": db_status,
        "stripe_configured": stripe_initialized
    }

# Render deployment entry point
if __name__ == "__main__":
    logger.info(f"🚀 Starting AI Email Agent on Render")
    logger.info(f"🌍 Environment: {ENVIRONMENT}")
    logger.info(f"🔌 Port: {PORT}")
    logger.info(f"💳 Stripe: {'✅' if stripe_initialized else '❌'}")
    
    import uvicorn
    uvicorn.run(
        app, 
        host=HOST, 
        port=PORT,
        log_level="info"
    )

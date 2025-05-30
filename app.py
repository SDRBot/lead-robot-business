# app.py - Fixed AI Email Agent System with Zapier Integration
import os
import json
import uuid
import sqlite3
import html
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ai_email_agent")

# Make dotenv import optional for deployment
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("✅ Loaded environment variables from .env")
except ImportError:
    logger.warning("⚠️ python-dotenv not available, using system environment variables")

from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, EmailStr, ValidationError
import stripe
import hashlib

# Custom Exception Classes
class DatabaseError(Exception):
    """Custom database exception"""
    pass

class CustomerNotFoundError(Exception):
    """Customer not found exception"""
    pass

class UsageLimitExceededError(Exception):
    """Usage limit exceeded exception"""
    pass

# Import your modular components
try:
    from config import settings, PRICING_PLANS
    from database import db_service
    from services.webhook_service import zapier_service
    from services.email_service import email_service
    from services.auth_service import auth_service
    from models import LeadInput
    logger.info("✅ Using modular architecture")
    MODULAR_MODE = True
except ImportError as e:
    logger.warning(f"⚠️ Modular imports failed: {e}")
    logger.info("🔄 Falling back to legacy mode")
    MODULAR_MODE = False

# Stripe initialization with better error handling
def initialize_stripe() -> bool:
    """Initialize Stripe with multiple fallback methods"""
    
    # Method 1: Direct environment variable
    stripe_key = os.getenv('STRIPE_SECRET_KEY')
    if stripe_key and (stripe_key.startswith('sk_') or stripe_key.startswith('rk_')):
        stripe.api_key = stripe_key
        logger.info(f"✅ Stripe initialized via env var: {stripe_key[:7]}...")
        return True
    
    # Method 2: Check other possible env var names
    possible_keys = ['STRIPE_SECRET_KEY', 'STRIPE_SECRET', 'STRIPE_API_KEY']
    for key_name in possible_keys:
        key_value = os.getenv(key_name)
        if key_value and (key_value.startswith('sk_') or key_value.startswith('rk_')):
            stripe.api_key = key_value
            logger.info(f"✅ Stripe initialized via {key_name}: {key_value[:7]}...")
            return True
    
    # Method 3: Try from settings if available
    try:
        if MODULAR_MODE and hasattr(settings, 'stripe_secret_key') and settings.stripe_secret_key:
            stripe.api_key = settings.stripe_secret_key
            logger.info(f"✅ Stripe initialized via settings")
            return True
    except Exception as e:
        logger.warning(f"⚠️ Could not load from settings: {e}")
    
    logger.error("❌ Could not initialize Stripe - no valid key found")
    available_keys = [k for k in os.environ.keys() if 'STRIPE' in k.upper()]
    logger.info(f"Available env vars: {available_keys}")
    return False

# Initialize Stripe
stripe_initialized = initialize_stripe()

# Pricing plans fallback
if not MODULAR_MODE:
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

# Database initialization with better error handling
def get_db_connection():
    """Get database connection with error handling"""
    try:
        conn = sqlite3.connect('leads.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise DatabaseError(f"Could not connect to database: {e}")

def init_database():
    """Initialize database with comprehensive schema"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Customers table
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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                password_hash TEXT
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
                source TEXT DEFAULT 'api',
                qualification_score INTEGER DEFAULT 0,
                qualification_stage TEXT DEFAULT 'new',
                conversation_data TEXT DEFAULT '[]',
                webhook_sent BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
        ''')
        
        # AI Email Agents table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_email_agents (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT 'Alex',
                role TEXT DEFAULT 'Sales Representative',
                personality TEXT DEFAULT 'professional',
                company_context TEXT DEFAULT '',
                value_proposition TEXT DEFAULT '',
                response_guidelines TEXT DEFAULT '',
                email_signature TEXT DEFAULT '',
                auto_respond BOOLEAN DEFAULT TRUE,
                response_delay_minutes INTEGER DEFAULT 15,
                working_hours_start TEXT DEFAULT '09:00',
                working_hours_end TEXT DEFAULT '17:00',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
        ''')
        
        # Email Conversations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_conversations (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                lead_email TEXT NOT NULL,
                lead_name TEXT DEFAULT '',
                company TEXT DEFAULT '',
                subject TEXT NOT NULL,
                thread_id TEXT,
                last_message TEXT,
                message_count INTEGER DEFAULT 0,
                interest_score INTEGER DEFAULT 0,
                status TEXT DEFAULT 'new',
                ai_suggested_response TEXT DEFAULT '',
                next_action TEXT DEFAULT '',
                conversation_summary TEXT DEFAULT '',
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
        ''')
        
        # Email Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                from_email TEXT NOT NULL,
                to_email TEXT NOT NULL,
                subject TEXT,
                content TEXT NOT NULL,
                from_lead BOOLEAN DEFAULT TRUE,
                ai_generated BOOLEAN DEFAULT FALSE,
                sent_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES email_conversations (id)
            )
        ''')
        
        # Zapier Webhooks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS zapier_webhooks (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                webhook_url TEXT NOT NULL,
                events TEXT NOT NULL DEFAULT '["lead_created", "hot_lead_detected"]',
                active BOOLEAN DEFAULT TRUE,
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
                data TEXT DEFAULT '{}',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
        ''')
        
        # Create indexes for performance
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_customers_api_key ON customers(api_key)',
            'CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)',
            'CREATE INDEX IF NOT EXISTS idx_leads_customer ON leads(customer_id)',
            'CREATE INDEX IF NOT EXISTS idx_conversations_customer ON email_conversations(customer_id)',
            'CREATE INDEX IF NOT EXISTS idx_conversations_status ON email_conversations(status)',
            'CREATE INDEX IF NOT EXISTS idx_conversations_score ON email_conversations(interest_score)',
            'CREATE INDEX IF NOT EXISTS idx_messages_conversation ON email_messages(conversation_id)',
            'CREATE INDEX IF NOT EXISTS idx_webhooks_customer ON zapier_webhooks(customer_id)',
            'CREATE INDEX IF NOT EXISTS idx_analytics_customer ON analytics(customer_id)'
        ]
        
        for index in indexes:
            cursor.execute(index)
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise DatabaseError(f"Could not initialize database: {e}")

# App lifespan management
@asynccontextmanager
async def lifespan(app):
    """Application lifespan management with error handling"""
    try:
        # Startup
        if MODULAR_MODE:
            db_service.init_database()
            logger.info("✅ Modular database initialized")
        else:
            init_database()
            logger.info("✅ Legacy database initialized")
        
        yield
        
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise
    finally:
        # Shutdown
        logger.info("🔄 Application shutting down")

# Create FastAPI app with security settings
app = FastAPI(
    title="AI Email Agent System with Zapier Integration",
    description="Intelligent email conversation automation with AI-powered lead qualification",
    version="2.0.0",
    docs_url=None,  # Disable in production
    redoc_url=None,  # Disable in production
    openapi_url=None,  # Disable in production
    lifespan=lifespan
)

# Security middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Data models with proper validation
class LeadInputLegacy(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    source: str = "api"
    initial_message: Optional[str] = None

class EmailConversationInput(BaseModel):
    from_email: EmailStr
    to_email: EmailStr
    subject: str
    content: str
    lead_name: Optional[str] = None
    company: Optional[str] = None

class AIAgentConfig(BaseModel):
    name: str = "Alex"
    role: str = "Sales Representative"
    personality: str = "professional"
    company_context: str = ""
    value_proposition: str = ""
    response_guidelines: str = ""
    email_signature: str = ""
    auto_respond: bool = True
    response_delay_minutes: int = 15

# Use modular or legacy based on availability
LeadModel = LeadInput if MODULAR_MODE else LeadInputLegacy

# Error handlers
@app.exception_handler(DatabaseError)
async def database_error_handler(request: Request, exc: DatabaseError):
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Database service temporarily unavailable"}
    )

@app.exception_handler(CustomerNotFoundError)
async def customer_not_found_handler(request: Request, exc: CustomerNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": "Customer not found"}
    )

@app.exception_handler(UsageLimitExceededError)
async def usage_limit_handler(request: Request, exc: UsageLimitExceededError):
    return JSONResponse(
        status_code=429,
        content={"detail": "Usage limit exceeded. Please upgrade your plan."}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid input data", "errors": exc.errors()}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred"}
    )

# Authentication with proper error handling
async def get_current_customer(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated customer with validation"""
    try:
        api_key = credentials.credentials
        
        if not api_key or len(api_key) < 10:
            raise HTTPException(status_code=401, detail="Invalid API key format")
        
        if MODULAR_MODE:
            customer = await auth_service.verify_api_key(api_key)
        else:
            customer = verify_api_key(api_key)
        
        if not customer:
            raise CustomerNotFoundError("Invalid API key")
        
        return customer
        
    except CustomerNotFoundError:
        raise HTTPException(status_code=401, detail="Invalid API key")
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

def verify_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """Legacy API key verification with security"""
    try:
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
        
    except Exception as e:
        logger.error(f"API key verification error: {e}")
        return None

# Helper functions for AI processing
def calculate_interest_score(email_content: str) -> int:
    """Calculate lead interest score with better algorithm"""
    if not email_content:
        return 0
    
    content_lower = email_content.lower()
    score = 30  # Base score
    
    # Positive indicators with weights
    positive_indicators = {
        'interested': 15,
        'demo': 20,
        'pricing': 18,
        'budget': 25,
        'buy': 20,
        'purchase': 20,
        'meeting': 15,
        'call': 12,
        'urgent': 15,
        'asap': 15,
        'decision': 18,
        'timeline': 12,
        'when': 8,
        'how much': 15,
        'cost': 10
    }
    
    # Negative indicators
    negative_indicators = {
        'not interested': -30,
        'unsubscribe': -40,
        'stop': -25,
        'remove': -20,
        'spam': -35,
        'too expensive': -15,
        'no budget': -20,
        'maybe later': -10
    }
    
    # Apply positive scoring
    for word, weight in positive_indicators.items():
        if word in content_lower:
            score += weight
    
    # Apply negative scoring
    for word, weight in negative_indicators.items():
        if word in content_lower:
            score += weight  # weight is already negative
    
    # Question indicators (shows engagement)
    question_count = email_content.count('?')
    score += min(question_count * 8, 20)  # Cap at 20 points
    
    # Length indicates engagement (but cap it)
    if len(email_content) > 100:
        score += min(len(email_content) // 50, 15)
    
    return max(0, min(100, score))

def generate_ai_response(email_content: str, agent: Dict[str, Any]) -> str:
    """Generate AI response with better templates"""
    if not email_content or not agent:
        return "Thank you for your email. We'll get back to you soon."
    
    name = agent.get('name', 'Alex')
    role = agent.get('role', 'Sales Representative')
    company_context = agent.get('company_context', 'We help businesses grow')
    value_prop = agent.get('value_proposition', 'AI-powered solutions')
    
    content_lower = email_content.lower()
    
    # More sophisticated response templates
    if any(word in content_lower for word in ['pricing', 'price', 'cost', 'how much']):
        return f"""Hi! Thanks for your interest in our pricing. I'd love to understand your specific needs better so I can provide the most relevant pricing information.

{company_context} and our {value_prop} typically help companies achieve significant results.

Could we schedule a quick 15-minute call to discuss your requirements? I can then provide you with a customized proposal.

Best regards,
{name}
{role}"""
    
    elif any(word in content_lower for word in ['demo', 'demonstration', 'show me']):
        return f"""Hi! I'd be delighted to show you a demo of our solution.

{company_context} and I think you'll be impressed with what our {value_prop} can accomplish for your business.

When would be a good time for you this week? I can walk you through a personalized demo that focuses on your specific use case.

Best regards,
{name}
{role}"""
    
    elif any(word in content_lower for word in ['budget', 'investment', 'roi']):
        return f"""Hi! I appreciate you thinking about the investment aspect.

{company_context} and our {value_prop} typically pay for themselves within the first few months through improved efficiency and results.

I'd love to discuss your budget parameters and show you exactly how we can deliver value within your investment range. Would you be available for a brief call this week?

Best regards,
{name}
{role}"""
    
    elif any(word in content_lower for word in ['interested', 'tell me more', 'learn more']):
        return f"""Hi! Thanks for reaching out and expressing interest.

{company_context} through our {value_prop}. I'd love to learn more about your current situation and see how we can help you achieve your goals.

Would you be available for a brief 15-minute conversation this week to discuss your specific needs?

Best regards,
{name}
{role}"""
    
    else:
        return f"""Hi! Thanks for your email.

{company_context} and I'd love to learn more about your current challenges to see how our {value_prop} might be able to help.

When would be a good time for a quick conversation? I'm confident we can provide significant value for your business.

Best regards,
{name}
{role}"""

def determine_next_action(interest_score: int) -> str:
    """Determine next action based on interest score"""
    if interest_score >= 80:
        return "Priority: Schedule demo call immediately"
    elif interest_score >= 60:
        return "Send pricing information and book meeting"
    elif interest_score >= 40:
        return "Follow up with case studies and testimonials"
    elif interest_score >= 20:
        return "Send helpful resources and nurture"
    else:
        return "Add to low-priority nurture sequence"

# Utility function for safe HTML escaping
def safe_html_format(template: str, **kwargs) -> str:
    """Safely format HTML template with escaped variables"""
    escaped_kwargs = {k: html.escape(str(v)) if v else '' for k, v in kwargs.items()}
    return template.format(**escaped_kwargs)

# Include modular routers if available
if MODULAR_MODE:
    try:
        from routers import auth, dashboard, webhooks, support, admin, conversations, ai_config
        app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
        app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])  
        app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
        app.include_router(support.router, prefix="/api/support", tags=["support"])
        app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
        app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
        app.include_router(ai_config.router, prefix="/api/ai-config", tags=["ai-config"])
        logger.info("✅ Modular routers loaded")
    except ImportError as e:
        logger.warning(f"⚠️ Some modular routers failed to load: {e}")

# Core API Endpoints

@app.post("/api/leads")
async def create_lead(
    lead: LeadModel, 
    background_tasks: BackgroundTasks,
    customer: dict = Depends(get_current_customer)
):
    """Create a new lead with comprehensive validation and processing"""
    
    try:
        # Check usage limits
        if customer['leads_used_this_month'] >= customer['leads_limit']:
            raise UsageLimitExceededError(
                f"Monthly limit of {customer['leads_limit']} leads exceeded"
            )
        
        lead_id = str(uuid.uuid4())
        lead_data = lead.dict()
        lead_data['id'] = lead_id
        lead_data['customer_id'] = customer['id']
        lead_data['created_at'] = datetime.now().isoformat()
        
        # Validate email format (additional check)
        if not lead.email or '@' not in lead.email:
            raise HTTPException(status_code=422, detail="Valid email address required")
        
        if MODULAR_MODE:
            await db_service.create_lead(lead_data)
            await db_service.update_customer_usage(customer['id'])
        else:
            # Legacy database operations with better error handling
            conn = get_db_connection()
            cursor = conn.cursor()
            
            try:
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
                
            except sqlite3.IntegrityError as e:
                conn.rollback()
                if 'UNIQUE constraint failed' in str(e):
                    raise HTTPException(status_code=409, detail="Lead with this email already exists")
                raise HTTPException(status_code=500, detail="Database constraint violation")
            finally:
                conn.close()

        # Background tasks for async processing
        background_tasks.add_task(send_to_zapier_async, customer['id'], lead_data)
        if lead.first_name:
            background_tasks.add_task(send_welcome_email_async, lead.email, lead.first_name)
        
        # Log analytics
        background_tasks.add_task(log_analytics_event, customer['id'], "lead_created", {
            "lead_id": lead_id,
            "source": lead.source,
            "has_phone": bool(lead.phone),
            "has_company": bool(lead.company)
        })
        
        return {
            "lead_id": lead_id,
            "status": "created",
            "message": "Lead captured and processing started",
            "usage": {
                "used": customer['leads_used_this_month'] + 1,
                "limit": customer['leads_limit'],
                "remaining": customer['leads_limit'] - customer['leads_used_this_month'] - 1
            }
        }
        
    except (UsageLimitExceededError, HTTPException):
        raise
    except Exception as e:
        logger.error(f"Error creating lead: {e}")
        raise HTTPException(status_code=500, detail="Error processing lead")

@app.post("/api/email-conversation")
async def process_email_conversation(
    email_data: EmailConversationInput,
    background_tasks: BackgroundTasks,
    customer: dict = Depends(get_current_customer)
):
    """Process incoming email and generate AI response"""
    
    try:
        # Validate input
        if not email_data.content.strip():
            raise HTTPException(status_code=422, detail="Email content cannot be empty")
        
        if len(email_data.content) > 10000:  # Reasonable limit
            raise HTTPException(status_code=422, detail="Email content too long")
        
        conversation_id = str(uuid.uuid4())
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if conversation already exists (within last 30 days)
            cursor.execute("""
                SELECT * FROM email_conversations 
                WHERE customer_id = ? AND lead_email = ? 
                AND created_at > datetime('now', '-30 days')
                ORDER BY created_at DESC LIMIT 1
            """, (customer['id'], email_data.from_email))
            
            existing_conversation = cursor.fetchone()
            
            if existing_conversation:
                conversation_id = existing_conversation['id']
                # Update message count and last activity
                cursor.execute("""
                    UPDATE email_conversations 
                    SET message_count = message_count + 1, 
                        last_message = ?, 
                        last_activity = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    email_data.content[:500], 
                    datetime.now(), 
                    datetime.now(),
                    conversation_id
                ))
            else:
                # Create new conversation
                cursor.execute('''
                    INSERT INTO email_conversations (
                        id, customer_id, lead_email, lead_name, company, subject,
                        last_message, message_count, last_activity, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    conversation_id, customer['id'], email_data.from_email,
                    email_data.lead_name or '', email_data.company or '', email_data.subject,
                    email_data.content[:500], 1, datetime.now(), datetime.now(), datetime.now()
                ))
            
            # Save the message
            message_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO email_messages (
                    id, conversation_id, from_email, to_email, subject, content,
                    from_lead, ai_generated, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                message_id, conversation_id, email_data.from_email, email_data.to_email,
                email_data.subject, email_data.content, True, False, datetime.now()
            ))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()
        
        # Generate AI response in background
        background_tasks.add_task(
            generate_ai_response_async, 
            customer['id'], 
            conversation_id, 
            email_data.content
        )
        
        return {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "status": "processed",
            "message": "Email received and AI response being generated"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing email: {e}")
        raise HTTPException(status_code=500, detail="Error processing email")

# Background tasks
async def generate_ai_response_async(customer_id: str, conversation_id: str, email_content: str):
    """Background task to generate AI response with error handling"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get customer's AI agent configuration
        cursor.execute("""
            SELECT * FROM ai_email_agents 
            WHERE customer_id = ? AND is_active = 1 LIMIT 1
        """, (customer_id,))
        
        agent = cursor.fetchone()
        
        if not agent:
            # Create default agent
            agent_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO ai_email_agents (
                    id, customer_id, name, company_context, value_proposition,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                agent_id, customer_id, 'Alex', 
                'We help businesses grow with AI automation',
                'Increase sales conversion with intelligent responses',
                datetime.now(), datetime.now()
            ))
            
            cursor.execute("SELECT * FROM ai_email_agents WHERE id = ?", (agent_id,))
            agent = cursor.fetchone()
        
        agent = dict(agent)
        
        # Generate AI analysis
        interest_score = calculate_interest_score(email_content)
        suggested_response = generate_ai_response(email_content, agent)
        next_action = determine_next_action(interest_score)
        
        # Update conversation with AI analysis
        cursor.execute("""
            UPDATE email_conversations 
            SET interest_score = ?, 
                ai_suggested_response = ?, 
                next_action = ?,
                updated_at = ?
            WHERE id = ?
        """, (interest_score, suggested_response, next_action, datetime.now(), conversation_id))
        
        conn.commit()
        conn.close()
        
        # Send to Zapier if high score
        if interest_score >= 70:
            await send_hot_lead_to_zapier(customer_id, conversation_id, interest_score)
        
        logger.info(f"AI response generated for conversation {conversation_id}, score: {interest_score}")
        
    except Exception as e:
        logger.error(f"AI response generation error: {e}")

async def send_to_zapier_async(customer_id: str, lead_data: dict):
    """Background task to send lead to Zapier webhooks"""
    try:
        if MODULAR_MODE:
            webhooks = await zapier_service.get_customer_webhooks(customer_id)
            for webhook in webhooks:
                await zapier_service.send_to_zapier(webhook['webhook_url'], lead_data)
        else:
            # Legacy: Get webhooks and send
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT webhook_url FROM zapier_webhooks 
                WHERE customer_id = ? AND active = 1
            """, (customer_id,))
            
            webhooks = cursor.fetchall()
            conn.close()
            
            # Here you would implement the actual webhook sending
            for webhook in webhooks:
                logger.info(f"📤 Sending lead to Zapier: {webhook['webhook_url']}")
                # Implementation would go here
                
    except Exception as e:
        logger.error(f"❌ Zapier webhook error: {e}")

async def send_welcome_email_async(email: str, first_name: str):
    """Background task to send welcome email"""
    try:
        if MODULAR_MODE:
            subject = f"Thanks for your interest, {first_name}!"
            content = f"""
            <div style="font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2>Hi {html.escape(first_name)}!</h2>
                <p>Thanks for your interest! We'd love to learn more about your needs.</p>
                <p><strong>Quick question:</strong> What's your biggest challenge right now?</p>
                <p>Just reply to this email and let us know!</p>
                <p>Best regards,<br>The Team</p>
            </div>
            """
            await email_service.send_email(email, subject, content)
            logger.info(f"Welcome email sent to {email}")
        else:
            logger.info(f"📧 Would send welcome email to {email}")
    except Exception as e:
        logger.error(f"❌ Welcome email error: {e}")

async def send_hot_lead_to_zapier(customer_id: str, conversation_id: str, interest_score: int):
    """Send hot lead notification to Zapier"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM email_conversations WHERE id = ?", (conversation_id,))
        conversation = cursor.fetchone()
        
        if not conversation:
            return
        
        conversation = dict(conversation)
        
        lead_data = {
            "event": "hot_lead_detected",
            "conversation_id": conversation_id,
            "lead_email": conversation['lead_email'],
            "lead_name": conversation['lead_name'],
            "company": conversation['company'],
            "interest_score": interest_score,
            "last_message": conversation['last_message'],
            "suggested_response": conversation['ai_suggested_response'],
            "next_action": conversation['next_action'],
            "timestamp": datetime.now().isoformat()
        }
        
        cursor.execute("""
            SELECT webhook_url FROM zapier_webhooks 
            WHERE customer_id = ? AND active = 1
        """, (customer_id,))
        
        webhooks = cursor.fetchall()
        conn.close()
        
        for webhook in webhooks:
            logger.info(f"🔥 Hot lead alert sent to Zapier: {interest_score}/100")
            # Webhook implementation would go here
            
    except Exception as e:
        logger.error(f"❌ Hot lead Zapier error: {e}")

async def log_analytics_event(customer_id: str, event_type: str, data: dict):
    """Log analytics event"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO analytics (id, customer_id, event_type, data, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()), customer_id, event_type, 
            json.dumps(data), datetime.now()
        ))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Analytics logging error: {e}")

# Health check endpoint
@app.get("/health")
def health_check():
    """Comprehensive health check"""
    try:
        # Test database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        db_status = "✅ Connected"
    except Exception:
        db_status = "❌ Connection Failed"
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "mode": "modular" if MODULAR_MODE else "legacy",
        "version": "2.0.0",
        "features": {
            "database": db_status,
            "zapier_integration": "✅ Active" if MODULAR_MODE else "🔄 Legacy Mode",
            "stripe_payments": "✅ Configured" if stripe.api_key else "❌ Not Configured",
            "stripe_initialized": stripe_initialized,
            "ai_email_agent": "✅ Active"
        }
    }

# Debug endpoints (remove in production)
@app.get("/debug/routes")
async def debug_routes():
    """Debug: List all registered routes"""
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods) if route.methods else [],
                "name": getattr(route, 'name', 'N/A')
            })
    return {"routes": routes, "total_routes": len(routes)}

@app.get("/debug/env")
async def debug_env():
    """Debug environment variables (remove in production)"""
    return {
        "stripe_secret_key_exists": bool(os.getenv('STRIPE_SECRET_KEY')),
        "stripe_secret_key_prefix": os.getenv('STRIPE_SECRET_KEY', '')[:7] if os.getenv('STRIPE_SECRET_KEY') else 'None',
        "stripe_api_key_set": bool(stripe.api_key),
        "modular_mode": MODULAR_MODE,
        "stripe_initialized": stripe_initialized,
        "database_file_exists": os.path.exists('leads.db')
    }

if __name__ == "__main__":
    logger.info("🚀 Starting AI Email Agent System...")
    logger.info(f"🔧 Mode: {'Modular' if MODULAR_MODE else 'Legacy'}")
    logger.info(f"💳 Stripe: {'✅ Initialized' if stripe_initialized else '❌ Not Configured'}")
    
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=int(os.environ.get("PORT", 8000)),
        log_level="info"
    )

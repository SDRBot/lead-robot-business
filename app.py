# app.py - Your original lead qualification robot
import os
import json
import uuid
import sqlite3
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, EmailStr
from openai import OpenAI
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import requests

# Load environment variables
load_dotenv()

# Initialize APIs
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
sendgrid_client = SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))

app = FastAPI(title="AI Lead Qualification System")

# Data models
class LeadInput(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    source: str = "api"

# Database functions
def get_db_connection():
    conn = sqlite3.connect('leads.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create customers table (for paying customers)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            plan TEXT DEFAULT 'basic',
            monthly_payment REAL DEFAULT 99.00,
            created_date TEXT,
            secret_key TEXT UNIQUE,
            stripe_customer_id TEXT
        )
    ''')
    
    # Create leads table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            first_name TEXT,
            last_name TEXT,
            company TEXT,
            phone TEXT,
            source TEXT,
            qualification_score INTEGER DEFAULT 0,
            qualification_stage TEXT DEFAULT 'new',
            conversation_data TEXT DEFAULT '[]',
            customer_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_database()

# Check if customer has paid
def check_if_customer_paid(api_key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE secret_key = ?", (api_key,))
    customer = cursor.fetchone()
    conn.close()
    
    if customer:
        return {
            "paid": True,
            "customer_id": customer['id'],
            "company_name": customer['company_name'],
            "plan": customer['plan']
        }
    else:
        return {"paid": False}

# Middleware to check payments
@app.middleware("http")
async def check_payment_middleware(request: Request, call_next):
    # Skip check for public pages
    if request.url.path in ["/", "/signup", "/checkout", "/success", "/cancel", "/docs", "/redoc"]:
        response = await call_next(request)
        return response
    
    # Check API key for API endpoints
    if request.url.path.startswith("/api/"):
        api_key = request.headers.get("X-API-Key")
        
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"error": "Please provide your API key in the X-API-Key header"}
            )
        
        customer_info = check_if_customer_paid(api_key)
        
        if not customer_info["paid"]:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid API key. Please sign up at our website."}
            )
        
        request.state.customer_id = customer_info["customer_id"]
        request.state.company_name = customer_info["company_name"]
    
    response = await call_next(request)
    return response

# API Endpoints
@app.post("/api/leads")
async def create_lead(lead: LeadInput, request: Request):
    """Create a new lead and start qualification process"""
    
    lead_id = str(uuid.uuid4())
    customer_id = request.state.customer_id
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO leads (id, email, first_name, last_name, company, phone, source, customer_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            lead_id, lead.email, lead.first_name, lead.last_name,
            lead.company, lead.phone, lead.source, customer_id,
            datetime.now(), datetime.now()
        ))
        
        conn.commit()
        conn.close()
        
        # Send welcome email (simplified for now)
        await send_initial_welcome_email({
            "id": lead_id,
            "email": lead.email,
            "first_name": lead.first_name,
            "company": lead.company
        })
        
        return {
            "lead_id": lead_id,
            "status": "created",
            "message": "Lead created and welcome email sent!"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating lead: {str(e)}")

async def send_initial_welcome_email(lead_data):
    """Send initial welcome email to new leads"""
    
    name = lead_data.get('first_name', 'there')
    company = lead_data.get('company', 'your company')
    
    subject = f"Thanks for your interest, {name}!"
    
    content = f"""
    <h2>Hi {name}!</h2>
    <p>Thanks for reaching out! I'm excited to learn more about {company}.</p>
    <p><strong>Quick question:</strong> What's your biggest challenge with lead management right now?</p>
    <p>Just reply to this email with your thoughts!</p>
    <p>Best regards,<br>Your AI Assistant</p>
    """
    
    try:
        message = Mail(
            from_email=os.getenv("FROM_EMAIL", "hello@yourcompany.com"),
            to_emails=lead_data['email'],
            subject=subject,
            html_content=content
        )
        
        response = sendgrid_client.send(message)
        return True
    except Exception as e:
        print(f"Email sending error: {e}")
        return False

@app.get("/api/leads")
async def get_leads(request: Request):
    """Get all leads for this customer"""
    
    customer_id = request.state.customer_id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM leads 
        WHERE customer_id = ?
        ORDER BY created_at DESC 
        LIMIT 50
    ''', (customer_id,))
    
    leads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {"leads": leads, "total": len(leads)}

if __name__ == "__main__":
    print("🚀 Starting AI Lead Qualification System...")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

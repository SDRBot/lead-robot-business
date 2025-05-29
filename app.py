# app.py - Simple working version
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

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(title="AI Lead Qualification System")

# Simple data model
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
    """Initialize the database with tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

# Initialize database when app starts
init_database()

# Initialize external services safely
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

# Initialize services
SERVICES = init_services()

# Simple email function
def send_simple_email(to_email: str, subject: str, content: str) -> bool:
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

# API Routes
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard"""
    
    # Get basic stats
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM leads")
    total_leads = cursor.fetchone()[0]
    
    cursor.execute("SELECT * FROM leads ORDER BY created_at DESC LIMIT 5")
    recent_leads = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    # Create simple dashboard
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 AI Lead Qualification Dashboard</title>
        <style>
            body {{ 
                font-family: Arial, sans-serif; 
                max-width: 1000px; 
                margin: 0 auto; 
                padding: 20px;
                background: #f5f7fa;
            }}
            .header {{ 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; 
                padding: 30px; 
                border-radius: 15px; 
                text-align: center;
                margin-bottom: 30px;
            }}
            .metric {{ 
                background: white; 
                padding: 20px; 
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
                text-align: center;
                margin-bottom: 20px;
            }}
            .metric h3 {{ margin: 0; color: #666; }}
            .metric .value {{ font-size: 32px; font-weight: bold; color: #2ecc71; }}
            table {{ 
                width: 100%; 
                background: white; 
                border-radius: 10px; 
                overflow: hidden;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            th, td {{ padding: 15px; text-align: left; border-bottom: 1px solid #eee; }}
            th {{ background: #f8f9fa; font-weight: bold; }}
            .btn {{
                background: #667eea;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                text-decoration: none;
                display: inline-block;
                margin: 10px 0;
            }}
            .status {{
                padding: 10px;
                margin: 10px 0;
                border-radius: 5px;
            }}
            .good {{ background: #d4edda; color: #155724; }}
            .warning {{ background: #fff3cd; color: #856404; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🤖 AI Lead Qualification System</h1>
            <p>Your intelligent lead management system is running!</p>
        </div>
        
        <div class="metric">
            <h3>Total Leads Captured</h3>
            <div class="value">{total_leads}</div>
        </div>
        
        <div class="status {'good' if SERVICES['openai'] else 'warning'}">
            🧠 AI Engine: {'✅ Active' if SERVICES['openai'] else '⚠️ Offline (API key needed)'}
        </div>
        
        <div class="status {'good' if SERVICES['sendgrid'] else 'warning'}">
            📧 Email System: {'✅ Active' if SERVICES['sendgrid'] else '⚠️ Offline (API key needed)'}
        </div>
        
        <a href="/capture" class="btn">🎯 Test Lead Capture Form</a>
        <a href="/docs" class="btn">📚 API Documentation</a>
        
        <h2>Recent Leads</h2>
        <table>
            <tr>
                <th>Email</th>
                <th>Name</th>
                <th>Company</th>
                <th>Source</th>
                <th>Created</th>
            </tr>
    """
    
    for lead in recent_leads:
        created_date = lead['created_at'][:16] if lead['created_at'] else 'N/A'
        html += f"""
            <tr>
                <td>{lead['email']}</td>
                <td>{lead['first_name'] or 'N/A'}</td>
                <td>{lead['company'] or 'N/A'}</td>
                <td>{lead['source']}</td>
                <td>{created_date}</td>
            </tr>
        """
    
    html += """
        </table>
        
        <div style="margin-top: 40px; text-align: center; color: #666;">
            <p>🚀 Your lead qualification system is online and ready!</p>
        </div>
    </body>
    </html>
    """
    
    return html

@app.get("/capture", response_class=HTMLResponse)
async def lead_capture_form():
    """Simple lead capture form"""
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎯 Lead Capture</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            .form-container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
            input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }
            button { background: #667eea; color: white; padding: 12px 30px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; width: 100%; }
            button:hover { background: #5a6fd8; }
            .success { background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin-top: 20px; }
            .error { background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="form-container">
            <h1>🎯 Lead Capture Test</h1>
            <p>Test your lead qualification system:</p>
            
            <form id="leadForm">
                <div class="form-group">
                    <label>Email Address *</label>
                    <input type="email" name="email" required>
                </div>
                
                <div class="form-group">
                    <label>First Name</label>
                    <input type="text" name="first_name">
                </div>
                
                <div class="form-group">
                    <label>Company</label>
                    <input type="text" name="company">
                </div>
                
                <button type="submit">🚀 Submit Lead</button>
            </form>
            
            <div id="result"></div>
        </div>
        
        <script>
            document.getElementById('leadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData(e.target);
                const data = {
                    email: formData.get('email'),
                    first_name: formData.get('first_name'),
                    company: formData.get('company'),
                    source: 'website_form'
                };
                
                try {
                    const response = await fetch('/api/leads', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        document.getElementById('result').innerHTML = 
                            '<div class="success">✅ Lead captured successfully! Check the dashboard.</div>';
                        e.target.reset();
                    } else {
                        throw new Error(result.detail);
                    }
                } catch (error) {
                    document.getElementById('result').innerHTML = 
                        '<div class="error">❌ Error: ' + error.message + '</div>';
                }
            });
        </script>
    </body>
    </html>
    """

@app.post("/api/leads")
async def create_lead(lead: LeadInput):
    """Create a new lead"""
    
    lead_id = str(uuid.uuid4())
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO leads (id, email, first_name, last_name, company, phone, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            lead_id, lead.email, lead.first_name, lead.last_name,
            lead.company, lead.phone, lead.source,
            datetime.now(), datetime.now()
        ))
        
        conn.commit()
        conn.close()
        
        # Try to send welcome email
        email_sent = False
        if lead.first_name:
            welcome_subject = f"Thanks for your interest, {lead.first_name}!"
            welcome_content = f"""
            <h2>Hi {lead.first_name}!</h2>
            <p>Thanks for your interest! We'll be in touch soon.</p>
            <p>Best regards,<br>Your Team</p>
            """
            email_sent = send_simple_email(lead.email, welcome_subject, welcome_content)
        
        return {
            "lead_id": lead_id,
            "status": "created",
            "email_sent": email_sent,
            "message": "Lead captured successfully!"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating lead: {str(e)}")

@app.get("/api/leads")
async def get_leads():
    """Get all leads"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM leads ORDER BY created_at DESC")
    leads = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return {"leads": leads, "total": len(leads)}

@app.get("/test")
def test_endpoint():
    """Simple test endpoint"""
    return {
        "status": "working",
        "message": "Your API is running!",
        "services": {
            "openai": "active" if SERVICES["openai"] else "offline",
            "sendgrid": "active" if SERVICES["sendgrid"] else "offline"
        }
    }

if __name__ == "__main__":
    print("🚀 Starting AI Lead Qualification System...")
    print("✅ System ready!")
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

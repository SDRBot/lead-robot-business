# app.py - Complete AI Lead Qualification System
import os
import json
import uuid
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from openai import OpenAI
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import requests
import asyncio
from contextlib import asynccontextmanager

# Load environment variables
load_dotenv()

# Initialize APIs
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
sendgrid_client = SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))

# Database setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    init_database()
    yield

app = FastAPI(
    title="AI Lead Qualification System",
    description="Automatically capture, qualify, and manage leads using AI",
    version="1.0.0",
    lifespan=lifespan
)

# Data models
class LeadInput(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    source: str = "api"
    initial_message: Optional[str] = None

class EmailWebhook(BaseModel):
    from_email: str
    subject: str
    text: str
    html: Optional[str] = None

# Database functions
def get_db_connection():
    conn = sqlite3.connect('leads.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
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
            conversation_data TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_contact TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    # Create conversations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            lead_id TEXT,
            channel TEXT DEFAULT 'email',
            messages TEXT DEFAULT '[]',
            status TEXT DEFAULT 'active',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads (id)
        )
    ''')
    
    # Create analytics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            lead_id TEXT,
            data TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# AI Analysis Functions
def analyze_lead_response(message: str, conversation_history: list) -> Dict[str, Any]:
    """Use OpenAI to analyze lead responses and extract qualification data"""
    
    conversation_context = "\n".join([
        f"{msg['sender']}: {msg['content']}" 
        for msg in conversation_history[-5:]  # Last 5 messages for context
    ])
    
    prompt = f"""
    Analyze this lead's email response and extract qualification information:
    
    CONVERSATION HISTORY:
    {conversation_context}
    
    LATEST MESSAGE: "{message}"
    
    Extract and return ONLY valid JSON with these exact fields:
    {{
        "company_size": "solo/small/medium/large/enterprise/unknown",
        "budget_range": "low/medium/high/enterprise/unknown",
        "authority_level": "low/medium/high/unknown",
        "timeline": "urgent/1-3months/3-6months/6months+/unknown",
        "pain_points": ["list", "of", "identified", "pain", "points"],
        "interest_level": "high/medium/low/none",
        "next_question": "What specific question should we ask next?",
        "qualification_score": 0-100,
        "sentiment": "positive/neutral/negative",
        "ready_for_demo": true/false,
        "key_insights": "Brief summary of key insights from this response"
    }}
    
    Focus on extracting real signals of buying intent, company size, budget authority, and timeline.
    """
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        
        analysis = json.loads(response.choices[0].message.content)
        return analysis
    
    except Exception as e:
        print(f"AI Analysis error: {e}")
        return {
            "company_size": "unknown",
            "budget_range": "unknown",
            "authority_level": "unknown",
            "timeline": "unknown",
            "pain_points": [],
            "interest_level": "medium",
            "next_question": "Could you tell me more about your current challenges?",
            "qualification_score": 30,
            "sentiment": "neutral",
            "ready_for_demo": False,
            "key_insights": "Unable to analyze - using default values"
        }

def generate_personalized_response(lead_data: dict, analysis: dict, conversation_history: list) -> str:
    """Generate personalized email response based on lead analysis"""
    
    lead_name = lead_data.get('first_name', 'there')
    company = lead_data.get('company', 'your company')
    
    conversation_context = "\n".join([
        f"{msg['sender']}: {msg['content']}" 
        for msg in conversation_history[-3:]
    ])
    
    prompt = f"""
    Generate a personalized follow-up email for this lead:
    
    LEAD INFO:
    - Name: {lead_name}
    - Company: {company}
    - Current qualification score: {analysis.get('qualification_score', 30)}
    - Interest level: {analysis.get('interest_level', 'medium')}
    - Ready for demo: {analysis.get('ready_for_demo', False)}
    
    CONVERSATION CONTEXT:
    {conversation_context}
    
    AI ANALYSIS:
    - Company size: {analysis.get('company_size', 'unknown')}
    - Budget range: {analysis.get('budget_range', 'unknown')}
    - Timeline: {analysis.get('timeline', 'unknown')}
    - Pain points: {', '.join(analysis.get('pain_points', []))}
    - Sentiment: {analysis.get('sentiment', 'neutral')}
    
    NEXT QUESTION TO ASK: {analysis.get('next_question', 'Tell me about your current process')}
    
    Write a warm, personalized email that:
    1. Acknowledges their response
    2. Shows you understand their situation
    3. Asks the next qualifying question naturally
    4. Keeps them engaged
    5. If they're highly qualified (score > 70), suggest a demo/call
    
    Keep it conversational, helpful, and under 150 words.
    Include a clear call-to-action.
    """
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        print(f"Response generation error: {e}")
        return f"""Hi {lead_name},

Thanks for your response! I'd love to learn more about {company} and how we might be able to help.

{analysis.get('next_question', 'Could you tell me more about your current challenges?')}

Looking forward to hearing from you!

Best regards,
Your AI Assistant"""

# Qualification scoring engine
def calculate_qualification_score(analysis: dict, lead_data: dict) -> int:
    """Calculate lead qualification score based on multiple factors"""
    
    score = 0
    
    # Company size scoring (0-25 points)
    size_scores = {
        "enterprise": 25,
        "large": 20,
        "medium": 15,
        "small": 10,
        "solo": 5
    }
    score += size_scores.get(analysis.get("company_size", "unknown"), 0)
    
    # Budget range scoring (0-25 points)
    budget_scores = {
        "enterprise": 25,
        "high": 20,
        "medium": 15,
        "low": 5
    }
    score += budget_scores.get(analysis.get("budget_range", "unknown"), 0)
    
    # Authority level scoring (0-20 points)
    authority_scores = {
        "high": 20,
        "medium": 12,
        "low": 5
    }
    score += authority_scores.get(analysis.get("authority_level", "unknown"), 0)
    
    # Timeline scoring (0-20 points)
    timeline_scores = {
        "urgent": 20,
        "1-3months": 15,
        "3-6months": 10,
        "6months+": 5
    }
    score += timeline_scores.get(analysis.get("timeline", "unknown"), 0)
    
    # Interest level scoring (0-10 points)
    interest_scores = {
        "high": 10,
        "medium": 6,
        "low": 2,
        "none": 0
    }
    score += interest_scores.get(analysis.get("interest_level", "medium"), 0)
    
    return min(score, 100)

def determine_qualification_stage(score: int, analysis: dict) -> str:
    """Determine lead qualification stage based on score and analysis"""
    
    if analysis.get("ready_for_demo", False) and score >= 70:
        return "hot_lead"
    elif score >= 60:
        return "warm_lead"
    elif score >= 40:
        return "qualified"
    elif score >= 20:
        return "nurture"
    else:
        return "unqualified"

# Email functions
async def send_email(to_email: str, subject: str, content: str) -> bool:
    """Send email using SendGrid"""
    
    try:
        message = Mail(
            from_email=os.getenv("FROM_EMAIL"),
            to_emails=to_email,
            subject=subject,
            html_content=content
        )
        
        response = sendgrid_client.send(message)
        return response.status_code in [200, 202]
    
    except Exception as e:
        print(f"Email sending error: {e}")
        return False

async def send_initial_welcome_email(lead_data: dict) -> bool:
    """Send initial welcome email to new leads"""
    
    name = lead_data.get('first_name', 'there')
    company = lead_data.get('company', 'your company')
    
    subject = f"Thanks for your interest, {name}!"
    
    content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #333;">Hi {name}!</h2>
        
        <p>Thanks for reaching out! I'm excited to learn more about {company} and how we might be able to help.</p>
        
        <p><strong>Quick question to get started:</strong></p>
        <p>What's the biggest challenge you're facing with [your current process/solution] right now?</p>
        
        <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 0;"><strong>💡 Why I'm asking:</strong> This helps me understand your specific situation so I can provide the most relevant information and solutions.</p>
        </div>
        
        <p>Just reply to this email with your thoughts!</p>
        
        <p>Best regards,<br>
        <strong>Your AI Assistant</strong><br>
        <em>P.S. - I'm an AI assistant designed to help qualify and connect you with the right solutions. All conversations are reviewed by our team.</em></p>
    </div>
    """
    
    return await send_email(lead_data['email'], subject, content)

# API Endpoints
@app.post("/api/leads")
async def create_lead(lead: LeadInput):
    """Create a new lead and start qualification process"""
    
    lead_id = str(uuid.uuid4())
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert lead
        cursor.execute('''
            INSERT INTO leads (id, email, first_name, last_name, company, phone, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            lead_id, lead.email, lead.first_name, lead.last_name,
            lead.company, lead.phone, lead.source,
            datetime.now(), datetime.now()
        ))
        
        # Create conversation record
        conversation_id = str(uuid.uuid4())
        initial_messages = []
        
        if lead.initial_message:
            initial_messages.append({
                "id": str(uuid.uuid4()),
                "sender": "lead",
                "content": lead.initial_message,
                "timestamp": datetime.now().isoformat()
            })
        
        cursor.execute('''
            INSERT INTO conversations (id, lead_id, messages, started_at, last_activity)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            conversation_id, lead_id, json.dumps(initial_messages),
            datetime.now(), datetime.now()
        ))
        
        # Log analytics
        cursor.execute('''
            INSERT INTO analytics (id, event_type, lead_id, data, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()), "lead_created", lead_id,
            json.dumps({"source": lead.source, "email": lead.email}),
            datetime.now()
        ))
        
        conn.commit()
        conn.close()
        
        # Send welcome email
        lead_data = {
            "id": lead_id,
            "email": lead.email,
            "first_name": lead.first_name,
            "company": lead.company
        }
        
        email_sent = await send_initial_welcome_email(lead_data)
        
        return {
            "lead_id": lead_id,
            "status": "created",
            "email_sent": email_sent,
            "message": "Lead created and welcome email sent!"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating lead: {str(e)}")

@app.post("/api/webhook/email")
async def handle_email_webhook(webhook: EmailWebhook):
    """Handle incoming email responses from leads"""
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Find lead by email
        cursor.execute("SELECT * FROM leads WHERE email = ?", (webhook.from_email,))
        lead_row = cursor.fetchone()
        
        if not lead_row:
            conn.close()
            return {"status": "lead_not_found"}
        
        lead_data = dict(lead_row)
        
        # Get conversation history
        cursor.execute("SELECT * FROM conversations WHERE lead_id = ? ORDER BY started_at DESC LIMIT 1", (lead_data['id'],))
        conversation_row = cursor.fetchone()
        
        if conversation_row:
            conversation_history = json.loads(conversation_row['messages'])
        else:
            conversation_history = []
        
        # Analyze the response with AI
        analysis = analyze_lead_response(webhook.text, conversation_history)
        
        # Calculate new qualification score
        new_score = calculate_qualification_score(analysis, lead_data)
        new_stage = determine_qualification_stage(new_score, analysis)
        
        # Add new message to conversation
        new_message = {
            "id": str(uuid.uuid4()),
            "sender": "lead",
            "content": webhook.text,
            "timestamp": datetime.now().isoformat(),
            "subject": webhook.subject,
            "analysis": analysis
        }
        conversation_history.append(new_message)
        
        # Generate AI response
        ai_response = generate_personalized_response(lead_data, analysis, conversation_history)
        
        # Add AI response to conversation
        ai_message = {
            "id": str(uuid.uuid4()),
            "sender": "ai",
            "content": ai_response,
            "timestamp": datetime.now().isoformat(),
            "type": "email_response"
        }
        conversation_history.append(ai_message)
        
        # Update lead qualification
        cursor.execute('''
            UPDATE leads 
            SET qualification_score = ?, qualification_stage = ?, updated_at = ?, last_contact = ?
            WHERE id = ?
        ''', (new_score, new_stage, datetime.now(), datetime.now(), lead_data['id']))
        
        # Update conversation
        if conversation_row:
            cursor.execute('''
                UPDATE conversations 
                SET messages = ?, last_activity = ?
                WHERE id = ?
            ''', (json.dumps(conversation_history), datetime.now(), conversation_row['id']))
        
        # Log analytics
        cursor.execute('''
            INSERT INTO analytics (id, event_type, lead_id, data, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()), "email_received", lead_data['id'],
            json.dumps({
                "score": new_score,
                "stage": new_stage,
                "analysis": analysis
            }),
            datetime.now()
        ))
        
        conn.commit()
        conn.close()
        
        # Send AI response email
        subject = f"Re: {webhook.subject}" if webhook.subject else "Following up on your message"
        email_sent = await send_email(webhook.from_email, subject, ai_response)
        
        # Send to CRM if highly qualified
        if new_score >= 70:
            await send_to_crm(lead_data['id'])
        
        return {
            "status": "processed",
            "lead_id": lead_data['id'],
            "qualification_score": new_score,
            "qualification_stage": new_stage,
            "email_sent": email_sent,
            "analysis": analysis
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing email: {str(e)}")

@app.post("/api/leads/{lead_id}/send-to-crm")
async def send_to_crm(lead_id: str):
    """Send qualified lead to CRM via Zapier webhook"""
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        lead_row = cursor.fetchone()
        
        if not lead_row:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        lead_data = dict(lead_row)
        
        # Only send qualified leads
        if lead_data['qualification_score'] < 50:
            raise HTTPException(status_code=400, detail="Lead not qualified enough for CRM")
        
        zapier_url = os.getenv("ZAPIER_WEBHOOK_URL")
        if not zapier_url or zapier_url == "we-will-add-this-later":
            return {"status": "skipped", "message": "CRM webhook not configured"}
        
        # Prepare CRM data
        crm_data = {
            "email": lead_data['email'],
            "first_name": lead_data['first_name'],
            "last_name": lead_data['last_name'],
            "company": lead_data['company'],
            "phone": lead_data['phone'],
            "qualification_score": lead_data['qualification_score'],
            "qualification_stage": lead_data['qualification_stage'],
            "source": lead_data['source'],
            "created_at": lead_data['created_at'],
            "notes": f"AI Qualified Lead - Score: {lead_data['qualification_score']}/100, Stage: {lead_data['qualification_stage']}"
        }
        
        # Send to CRM
        response = requests.post(zapier_url, json=crm_data, timeout=30)
        
        if response.status_code == 200:
            # Log successful CRM sync
            cursor.execute('''
                INSERT INTO analytics (id, event_type, lead_id, data, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), "crm_sync", lead_id,
                json.dumps({"status": "success", "response_code": response.status_code}),
                datetime.now()
            ))
            conn.commit()
            conn.close()
            
            return {"status": "sent_to_crm", "message": "Lead successfully sent to CRM"}
        else:
            raise HTTPException(status_code=500, detail=f"CRM sync failed: {response.status_code}")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending to CRM: {str(e)}")

@app.get("/api/leads")
async def get_leads(skip: int = 0, limit: int = 50):
    """Get all leads with pagination"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM leads 
        ORDER BY created_at DESC 
        LIMIT ? OFFSET ?
    ''', (limit, skip))
    
    leads = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT COUNT(*) FROM leads")
    total = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "leads": leads,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@app.get("/api/leads/{lead_id}")
async def get_lead(lead_id: str):
    """Get specific lead with conversation history"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
    lead_row = cursor.fetchone()
    
    if not lead_row:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    lead_data = dict(lead_row)
    
    # Get conversation history
    cursor.execute("SELECT * FROM conversations WHERE lead_id = ?", (lead_id,))
    conversation_rows = cursor.fetchall()
    
    conversations = []
    for row in conversation_rows:
        conv_data = dict(row)
        conv_data['messages'] = json.loads(conv_data['messages'])
        conversations.append(conv_data)
    
    conn.close()
    
    lead_data['conversations'] = conversations
    return lead_data

@app.get("/api/analytics")
async def get_analytics():
    """Get analytics dashboard data"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Basic metrics
    cursor.execute("SELECT COUNT(*) FROM leads")
    total_leads = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE qualification_stage = 'hot_lead'")
    hot_leads = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE qualification_stage = 'warm_lead'")
    warm_leads = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE qualification_stage = 'qualified'")
    qualified_leads = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(qualification_score) FROM leads WHERE qualification_score > 0")
    avg_score = cursor.fetchone()[0] or 0
    
    # Conversion rates
    conversion_rate = (hot_leads + warm_leads) / total_leads * 100 if total_leads > 0 else 0
    
    # Recent activity
    cursor.execute('''
        SELECT email, company, qualification_score, qualification_stage, created_at
        FROM leads 
        ORDER BY created_at DESC 
        LIMIT 10
    ''')
    recent_leads = [dict(row) for row in cursor.fetchall()]
    
    # Lead sources
    cursor.execute('''
        SELECT source, COUNT(*) as count
        FROM leads 
        GROUP BY source
        ORDER BY count DESC
    ''')
    lead_sources = [{"source": row[0], "count": row[1]} for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "total_leads": total_leads,
        "hot_leads": hot_leads,
        "warm_leads": warm_leads,
        "qualified_leads": qualified_leads,
        "avg_qualification_score": round(avg_score, 1),
        "conversion_rate": round(conversion_rate, 1),
        "recent_leads": recent_leads,
        "lead_sources": lead_sources
    }

# Dashboard HTML
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard interface"""
    
    analytics = await get_analytics()
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 AI Lead Qualification Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0; padding: 20px; background: #f5f7fa; color: #333;
            }}
            .header {{ 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; padding: 30px; border-radius: 15px; margin-bottom: 30px;
                text-align: center;
            }}
            .metrics {{ 
                display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px; margin-bottom: 30px;
            }}
            .metric {{ 
                background: white; padding: 25px; border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center;
            }}
            .metric h3 {{ margin: 0 0 10px 0; color: #666; font-size: 14px; text-transform: uppercase; }}
            .metric .value {{ font-size: 32px; font-weight: bold; margin: 0; }}
            .hot {{ color: #e74c3c; }}
            .warm {{ color: #f39c12; }}
            .qualified {{ color: #3498db; }}
            .total {{ color: #2ecc71; }}
            .conversion {{ color: #9b59b6; }}
            .table-container {{ 
                background: white; border-radius: 10px; overflow: hidden;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px;
            }}
            .table-header {{ 
                background: #667eea; color: white; padding: 20px;
                font-size: 18px; font-weight: bold;
            }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 15px; text-align: left; border-bottom: 1px solid #eee; }}
            th {{ background: #f8f9fa; font-weight: 600; }}
            .badge {{ 
                padding: 4px 8px; border-radius: 4px; font-size: 12px;
                font-weight: bold; text-transform: uppercase;
            }}
            .badge.hot {{ background: #ffe6e6; color: #e74c3c; }}
            .badge.warm {{ background: #fff3e0; color: #f39c12; }}
            .badge.qualified {{ background: #e3f2fd; color: #3498db; }}
            .badge.nurture {{ background: #f3e5f5; color: #9b59b6; }}
            .badge.unqualified {{ background: #f5f5f5; color: #666; }}
            .score {{ 
                font-weight: bold; padding: 4px 8px; border-radius: 4px;
                background: #f8f9fa; color: #333;
            }}
            .api-info {{ 
                background: #e8f5e9; border: 1px solid #c8e6c9;
                border-radius: 10px; padding: 20px; margin-top: 30px;
            }}
            .api-info h3 {{ color: #2e7d32; margin-top: 0; }}
            .api-info code {{ 
                background: #f5f5f5; padding: 2px 6px; border-radius: 4px;
                font-family: 'Monaco', 'Courier New', monospace;
            }}
            .refresh-btn {{
                background: #667eea; color: white; border: none; padding: 10px 20px;
                border-radius: 5px; cursor: pointer; margin-bottom: 20px;
            }}
            .refresh-btn:hover {{ background: #5a6fd8; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🤖 AI Lead Qualification System</h1>
            <p>Automatically capturing, qualifying, and managing leads using artificial intelligence</p>
        </div>
        
        <button class="refresh-btn" onclick="location.reload()">🔄 Refresh Dashboard</button>
        
        <div class="metrics">
            <div class="metric">
                <h3>Total Leads</h3>
                <p class="value total">{analytics['total_leads']}</p>
            </div>
            <div class="metric">
                <h3>Hot Leads 🔥</h3>
                <p class="value hot">{analytics['hot_leads']}</p>
            </div>
            <div class="metric">
                <h3>Warm Leads ⭐</h3>
                <p class="value warm">{analytics['warm_leads']}</p>
            </div>
            <div class="metric">
                <h3>Qualified Leads</h3>
                <p class="value qualified">{analytics['qualified_leads']}</p>
            </div>
            <div class="metric">
                <h3>Conversion Rate</h3>
                <p class="value conversion">{analytics['conversion_rate']}%</p>
           </div>
           <div class="metric">
               <h3>Avg Score</h3>
               <p class="value total">{analytics['avg_qualification_score']}</p>
           </div>
       </div>
       
       <div class="table-container">
           <div class="table-header">📊 Recent Leads</div>
           <table>
               <tr>
                   <th>Email</th>
                   <th>Company</th>
                   <th>Score</th>
                   <th>Stage</th>
                   <th>Created</th>
               </tr>
   """
   
    for lead in analytics['recent_leads']:
        created_date = lead['created_at'][:10] if lead['created_at'] else 'N/A'
        company = lead['company'] or 'N/A'
        stage = lead['qualification_stage']
        score = lead['qualification_score']
       
        html += f"""
               <tr>
                   <td>{lead['email']}</td>
                   <td>{company}</td>
                   <td><span class="score">{score}</span></td>
                   <td><span class="badge {stage.replace('_', ' ')}">{stage.replace('_', ' ').title()}</span></td>
                   <td>{created_date}</td>
               </tr>
       """
   
    html += f"""
           </table>
       </div>
       
       <div class="table-container">
           <div class="table-header">📈 Lead Sources</div>
           <table>
               <tr>
                   <th>Source</th>
                   <th>Count</th>
                   <th>Percentage</th>
               </tr>
   """
   
    for source in analytics['lead_sources']:
       percentage = round(source['count'] / analytics['total_leads'] * 100, 1) if analytics['total_leads'] > 0 else 0
       html += f"""
               <tr>
                   <td>{source['source'].title()}</td>
                   <td>{source['count']}</td>
                   <td>{percentage}%</td>
               </tr>
       """
   
    html += f"""
           </table>
       </div>
       
       <div class="api-info">
           <h3>🚀 API Endpoints for Integration</h3>
           <p><strong>Add New Lead:</strong> <code>POST /api/leads</code></p>
           <p><strong>Email Webhook:</strong> <code>POST /api/webhook/email</code></p>
           <p><strong>Get All Leads:</strong> <code>GET /api/leads</code></p>
           <p><strong>Send to CRM:</strong> <code>POST /api/leads/{{lead_id}}/send-to-crm</code></p>
           <p><strong>Analytics:</strong> <code>GET /api/analytics</code></p>
           <p><strong>Interactive API Docs:</strong> <a href="/docs" target="_blank">View Full API Documentation</a></p>
       </div>
       
       <div style="text-align: center; margin-top: 40px; color: #666;">
           <p>🤖 Your AI Lead Qualification System is running and ready!</p>
           <p><small>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
       </div>
       
       <script>
           // Auto-refresh every 5 minutes
           setTimeout(() => location.reload(), 300000);
       </script>
   </body>
   </html>
   """
   
    return html

# Lead capture form
@app.get("/capture", response_class=HTMLResponse)
async def lead_capture_form():
   """Simple lead capture form for testing"""
   
   return """
   <!DOCTYPE html>
   <html>
   <head>
       <title>🎯 Lead Capture Form</title>
       <style>
           body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
           .form-container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
           h1 { color: #333; text-align: center; }
           .form-group { margin-bottom: 20px; }
           label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
           input, textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }
           button { background: #667eea; color: white; padding: 12px 30px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; width: 100%; }
           button:hover { background: #5a6fd8; }
           .success { background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin-top: 20px; }
       </style>
   </head>
   <body>
       <div class="form-container">
           <h1>🎯 Get Started Today</h1>
           <p>Fill out this form and our AI will start qualifying you immediately!</p>
           
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
                   <label>Last Name</label>
                   <input type="text" name="last_name">
               </div>
               
               <div class="form-group">
                   <label>Company</label>
                   <input type="text" name="company">
               </div>
               
               <div class="form-group">
                   <label>Phone</label>
                   <input type="tel" name="phone">
               </div>
               
               <div class="form-group">
                   <label>Tell us about your biggest challenge:</label>
                   <textarea name="initial_message" rows="4" placeholder="What's the main problem you're trying to solve?"></textarea>
               </div>
               
               <button type="submit">🚀 Start My Qualification Process</button>
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
                   last_name: formData.get('last_name'),
                   company: formData.get('company'),
                   phone: formData.get('phone'),
                   initial_message: formData.get('initial_message'),
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
                       document.getElementById('result').innerHTML = `
                           <div class="success">
                               ✅ Success! Check your email - our AI assistant has sent you a personalized message to start the qualification process.
                               <br><br>
                               <strong>Lead ID:</strong> ${result.lead_id}
                           </div>
                       `;
                       e.target.reset();
                   } else {
                       throw new Error(result.detail);
                   }
               } catch (error) {
                   document.getElementById('result').innerHTML = `
                       <div style="background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; margin-top: 20px;">
                           ❌ Error: ${error.message}
                       </div>
                   `;
               }
           });
       </script>
   </body>
   </html>
   """

# Test endpoints
@app.post("/api/test/email-webhook")
async def test_email_webhook():
   """Test endpoint to simulate an email response"""
   
   test_data = EmailWebhook(
       from_email="test@example.com",
       subject="Re: Thanks for your interest!",
       text="Hi! We're a medium-sized company with about 50 employees. We're looking to implement a solution within the next 3 months and have a budget of around $50k. I'm the VP of Operations so I can make decisions on this. Our biggest challenge right now is our manual lead qualification process is taking too much time."
   )
   
   return await handle_email_webhook(test_data)

if __name__ == "__main__":
   print("🚀 Starting your AI Lead Qualification System...")
   print("🌐 Dashboard: http://localhost:8000")
   print("📝 Lead Capture: http://localhost:8000/capture")
   print("📚 API Docs: http://localhost:8000/docs")
   print("")
   print("✅ System ready! Your AI robot is now online!")
   
   import uvicorn
   uvicorn.run(app, host="0.0.0.0", port=8000)

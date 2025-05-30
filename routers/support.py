from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from datetime import datetime
from services.email_service import email_service
from services.auth_service import get_current_customer
from database import db_service
import uuid

router = APIRouter(prefix="/support", tags=["support"])

class SupportTicket(BaseModel):
    subject: str
    message: str
    priority: str = "normal"  # normal, high, urgent
    category: str = "general"  # general, technical, billing

@router.get("/", response_class=HTMLResponse)
async def support_page(api_key: str = None):
    """Support chat/ticket page"""
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>💬 Support - AI Lead Robot</title>
        <style>
            body {{ font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; background: #f5f7fa; }}
            .container {{ background: white; padding: 40px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .form-group {{ margin-bottom: 20px; }}
            label {{ display: block; margin-bottom: 5px; font-weight: bold; color: #555; }}
            input, select, textarea {{ width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; font-family: Arial; }}
            textarea {{ height: 120px; resize: vertical; }}
            .btn {{ background: #667eea; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }}
            .btn:hover {{ background: #5a6fd8; }}
            .success {{ background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .error {{ background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .faq {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .faq-item {{ margin: 15px 0; padding: 15px; background: white; border-radius: 5px; }}
            .chat-style {{ background: #e3f2fd; padding: 20px; border-radius: 15px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>💬 Need Help?</h1>
            <p>We're here to help! Send us a message and we'll get back to you within 24 hours.</p>
            
            <div class="chat-style">
                <h3>🤖 Quick Help</h3>
                <p><strong>Most common questions:</strong></p>
                <ul>
                    <li><strong>Setting up Zapier:</strong> <a href="/webhooks/setup?api_key={api_key or 'YOUR_API_KEY'}">Follow our step-by-step guide</a></li>
                    <li><strong>API Documentation:</strong> <a href="/dashboard?api_key={api_key or 'YOUR_API_KEY'}">View integration examples in your dashboard</a></li>
                    <li><strong>Billing Questions:</strong> Check your usage in the dashboard or contact us below</li>
                </ul>
            </div>
            
            <form id="supportForm">
                <div class="form-group">
                    <label>Your Email *</label>
                    <input type="email" name="email" required placeholder="your@email.com">
                </div>
                
                <div class="form-group">
                    <label>Subject *</label>
                    <input type="text" name="subject" required placeholder="How can we help you?">
                </div>
                
                <div class="form-group">
                    <label>Category</label>
                    <select name="category">
                        <option value="general">General Question</option>
                        <option value="technical">Technical Issue</option>
                        <option value="billing">Billing/Account</option>
                        <option value="integration">Zapier Integration</option>
                        <option value="feature">Feature Request</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Priority</label>
                    <select name="priority">
                        <option value="normal">Normal</option>
                        <option value="high">High</option>
                        <option value="urgent">Urgent (Account Down)</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Message *</label>
                    <textarea name="message" required placeholder="Please describe your question or issue in detail..."></textarea>
                </div>
                
                <button type="submit" class="btn">📤 Send Message</button>
            </form>
            
            <div id="result"></div>
            
            <div class="faq">
                <h3>📚 Frequently Asked Questions</h3>
                
                <div class="faq-item">
                    <strong>Q: How do I integrate with my CRM?</strong><br>
                    A: Use our Zapier integration to connect to any CRM including Salesforce, HubSpot, or Pipedrive. <a href="/webhooks/setup?api_key={api_key or 'YOUR_API_KEY'}">Setup guide here</a>.
                </div>
                
                <div class="faq-item">
                    <strong>Q: What's included in my plan?</strong><br>
                    A: Check your dashboard to see your current usage and limits. All plans include AI qualification and Zapier integration.
                </div>
                
                <div class="faq-item">
                    <strong>Q: How do I cancel my subscription?</strong><br>
                    A: Contact us using the form above and we'll help you cancel or adjust your plan.
                </div>
                
                <div class="faq-item">
                    <strong>Q: Can I upgrade/downgrade my plan?</strong><br>
                    A: Yes! Contact us and we'll help you switch plans. Changes take effect on your next billing cycle.
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 30px;">
                <p><strong>Need immediate help?</strong></p>
                <p>📧 Email: <a href="mailto:support@yourcompany.com">support@yourcompany.com</a></p>
                <p>⏰ Response Time: Within 24 hours (usually much faster!)</p>
            </div>
            
            <p style="text-align: center; margin-top: 20px;">
                <a href="/dashboard?api_key={api_key or 'YOUR_API_KEY'}" style="color: #667eea;">← Back to Dashboard</a>
            </p>
        </div>
        
        <script>
            document.getElementById('supportForm').addEventListener('submit', async (e) => {{
                e.preventDefault();
                
                const formData = new FormData(e.target);
                const data = {{
                    email: formData.get('email'),
                    subject: formData.get('subject'),
                    message: formData.get('message'),
                    category: formData.get('category'),
                    priority: formData.get('priority')
                }};
                
                document.getElementById('result').innerHTML = '<div style="color: #666;">📤 Sending your message...</div>';
                
                try {{
                    const response = await fetch('/support/ticket', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify(data)
                    }});
                    
                    const result = await response.json();
                    
                    if (response.ok) {{
                        document.getElementById('result').innerHTML = '<div class="success">✅ Message sent! We\\'ll get back to you within 24 hours. Ticket ID: ' + result.ticket_id + '</div>';
                        e.target.reset();
                    }} else {{
                        document.getElementById('result').innerHTML = '<div class="error">❌ Error sending message. Please try again or email us directly.</div>';
                    }}
                }} catch (error) {{
                    document.getElementById('result').innerHTML = '<div class="error">❌ Error sending message. Please email us at support@yourcompany.com</div>';
                }}
            }});
        </script>
    </body>
    </html>
    """

@router.post("/ticket")
async def create_support_ticket(ticket: SupportTicket):
    """Create a support ticket"""
    
    try:
        # Generate ticket ID
        ticket_id = f"TICKET-{str(uuid.uuid4())[:8].upper()}"
        
        # Save to database
        await db_service.execute_query('''
            INSERT INTO support_tickets (
                id, email, subject, message, category, priority, 
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ticket_id, ticket.email, ticket.subject, ticket.message,
            ticket.category, ticket.priority, 'open', datetime.now()
        ))
        
        # Send email notification to support team
        support_email = "support@yourcompany.com"  # Replace with your support email
        
        priority_emoji = {"normal": "📝", "high": "⚠️", "urgent": "🚨"}
        category_emoji = {"general": "💬", "technical": "🔧", "billing": "💳", "integration": "⚡", "feature": "💡"}
        
        subject = f"{priority_emoji.get(ticket.priority, '📝')} New Support Ticket: {ticket.subject}"
        
        content = f"""
        <div style="font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2>{priority_emoji.get(ticket.priority, '📝')} New Support Ticket</h2>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>Ticket ID:</strong> {ticket_id}</p>
                <p><strong>From:</strong> {ticket.email}</p>
                <p><strong>Category:</strong> {category_emoji.get(ticket.category, '💬')} {ticket.category.title()}</p>
                <p><strong>Priority:</strong> {ticket.priority.title()}</p>
                <p><strong>Subject:</strong> {ticket.subject}</p>
            </div>
            
            <div style="background: white; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                <h3>Message:</h3>
                <p>{ticket.message}</p>
            </div>
            
            <p style="margin-top: 30px; color: #666; font-size: 14px;">
                Reply to this email to respond to the customer.
            </p>
        </div>
        """
        
        # Send notification email
        await email_service.send_email(support_email, subject, content)
        
        return {
            "ticket_id": ticket_id,
            "status": "created",
            "message": "Support ticket created successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating ticket: {str(e)}")

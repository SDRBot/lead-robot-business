# At the top of routers/leads.py, add these imports:
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List
import uuid
from datetime import datetime

# Import your new services
from services.auth_service import get_current_customer
from services.webhook_service import zapier_service
from services.email_service import email_service
from database import db_service
from models import LeadInput

router = APIRouter(prefix="/api/leads", tags=["leads"])

# Update your existing create_lead function to use the new services
@router.post("/", response_model=dict)
async def create_lead(
    lead: LeadInput, 
    background_tasks: BackgroundTasks,
    customer: dict = Depends(get_current_customer)
):
    """Create lead with Zapier integration"""
    
    # Check usage limits
    if customer['leads_used_this_month'] >= customer['leads_limit']:
        raise HTTPException(status_code=429, detail="Monthly limit exceeded")
    
    # Create lead
    lead_id = str(uuid.uuid4())
    lead_data = lead.dict()
    lead_data['id'] = lead_id
    lead_data['customer_id'] = customer['id']
    lead_data['created_at'] = datetime.now().isoformat()
    
    # Save to database
    await db_service.execute_query('''
        INSERT INTO leads (
            id, customer_id, email, first_name, last_name, 
            company, phone, source, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        lead_id, customer['id'], lead.email, lead.first_name, 
        lead.last_name, lead.company, lead.phone, lead.source, 
        datetime.now(), datetime.now()
    ))
    
    # Update usage counter
    await db_service.execute_query(
        "UPDATE customers SET leads_used_this_month = leads_used_this_month + 1 WHERE id = ?",
        (customer['id'],)
    )
    
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

async def send_to_zapier_async(customer_id: str, lead_data: dict):
    """Background task to send to Zapier"""
    async with zapier_service:
        webhooks = await zapier_service.get_customer_webhooks(customer_id)
        for webhook in webhooks:
            await zapier_service.send_to_zapier(webhook['webhook_url'], lead_data)

async def send_welcome_email_async(email: str, first_name: str):
    """Background task for email"""
    if first_name:
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

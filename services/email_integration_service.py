# services/email_integration_service.py
import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
import asyncio

class EmailIntegrationService:
    """Manages customer email accounts and AI responses"""
    
    async def connect_email_account(self, customer_id: str, email_config: Dict):
        """Connect customer's email account (Gmail, Outlook, etc.)"""
        # Store encrypted email credentials
        await db_service.execute_query('''
            INSERT INTO email_accounts (
                id, customer_id, email_address, provider, 
                imap_host, smtp_host, access_token, refresh_token,
                ai_signature, ai_name, ai_role
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()), customer_id, email_config['email'],
            email_config['provider'], email_config['imap_host'],
            email_config['smtp_host'], email_config['access_token'],
            email_config['refresh_token'], email_config.get('signature'),
            email_config.get('ai_name', 'Alex'), email_config.get('ai_role', 'Sales Representative')
        ))
    
    async def fetch_new_emails(self, customer_id: str):
        """Fetch new emails from customer's inbox"""
        email_accounts = await db_service.execute_query(
            "SELECT * FROM email_accounts WHERE customer_id = ? AND active = TRUE",
            (customer_id,), fetch='all'
        )
        
        for account in email_accounts:
            # Connect to IMAP and fetch unread emails
            emails = await self._fetch_unread_emails(account)
            for email_data in emails:
                await self._process_incoming_email(customer_id, email_data)
    
    async def send_ai_response(self, conversation_id: str, response_text: str):
        """Send AI-generated response via customer's email"""
        conversation = await db_service.execute_query(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,), fetch='one'
        )
        
        if conversation:
            await self._send_email_via_customer_account(
                conversation['customer_id'],
                conversation['lead_email'],
                response_text,
                conversation['subject']
            )

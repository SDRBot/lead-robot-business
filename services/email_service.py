import asyncio
from typing import Optional
import logging
from config import settings

logger = logging.getLogger(__name__)

class EmailService:
    """Async email service using SendGrid"""
    
    def __init__(self):
        self.client = None
        if settings.sendgrid_api_key:
            try:
                from sendgrid import SendGridAPIClient
                self.client = SendGridAPIClient(api_key=settings.sendgrid_api_key)
                print("✅ SendGrid initialized")
            except ImportError:
                print("⚠️ SendGrid package not installed")
        else:
            print("⚠️ SendGrid API key not configured")
    
    async def send_email(self, to_email: str, subject: str, content: str) -> bool:
        """Send email asynchronously"""
        if not self.client:
            print(f"📧 Would send email to {to_email}: {subject}")
            return False
        
        try:
            from sendgrid.helpers.mail import Mail
            
            message = Mail(
                from_email=settings.from_email,
                to_emails=to_email,
                subject=subject,
                html_content=content
            )
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, self.client.send, message
            )
            
            logger.info(f"✅ Email sent to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Email error: {str(e)}")
            return False
    
    async def send_welcome_email(self, customer_email: str, plan: str, api_key: str) -> bool:
        """Send welcome email to new customers"""
        from config import PRICING_PLANS
        
        plan_info = PRICING_PLANS[plan]
        subject = "🎉 Welcome to AI Lead Robot - Your Account is Ready!"
        
        content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: white; padding: 40px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                <h1 style="color: #667eea; text-align: center;">🤖 Welcome to AI Lead Robot!</h1>
                
                <div style="background: #e8f5e9; padding: 20px; border-radius: 10px; margin: 20px 0;">
                    <h2 style="color: #155724; margin-top: 0;">🔥 Your 14-Day Free Trial is Active!</h2>
                    <p><strong>Plan:</strong> {plan_info['name']}</p>
                    <p><strong>Monthly Limit:</strong> {plan_info['leads_limit']} leads</p>
                    <p><strong>Price after trial:</strong> ${plan_info['price']}/month</p>
                </div>
                
                <h3>🔑 Your API Key:</h3>
                <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; font-family: monospace; word-break: break-all;">
                    {api_key}
                </div>
                
                <p style="text-align: center; margin-top: 30px;">
                    <a href="{settings.app_url}/dashboard?api_key={api_key}" 
                       style="background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px;">
                       🔓 Access Your Dashboard
                    </a>
                </p>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(customer_email, subject, content)

# Global instance
email_service = EmailService()

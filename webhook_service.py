import asyncio
import aiohttp
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ZapierWebhookService:
    """Service for Zapier webhook integrations (replaces HubSpot)"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            headers={'Content-Type': 'application/json'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def send_to_zapier(self, webhook_url: str, lead_data: Dict[str, Any], 
                           retry_count: int = 3) -> bool:
        """Send lead data to Zapier webhook with retry logic"""
        
        # Format data for Zapier
        zapier_payload = {
            "event": "lead_qualified",
            "timestamp": datetime.now().isoformat(),
            "lead": {
                "id": lead_data.get("id"),
                "email": lead_data.get("email"),
                "first_name": lead_data.get("first_name"),
                "last_name": lead_data.get("last_name"),
                "company": lead_data.get("company"),
                "phone": lead_data.get("phone"),
                "source": lead_data.get("source"),
                "qualification_score": lead_data.get("qualification_score", 0),
                "qualification_stage": lead_data.get("qualification_stage", "new"),
                "created_at": lead_data.get("created_at")
            }
        }
        
        for attempt in range(retry_count):
            try:
                async with self.session.post(webhook_url, json=zapier_payload) as response:
                    if response.status == 200:
                        logger.info(f"✅ Lead sent to Zapier: {lead_data.get('email')}")
                        return True
                    else:
                        logger.warning(f"Zapier webhook failed: {response.status}")
                        
            except Exception as e:
                logger.error(f"Zapier webhook error (attempt {attempt + 1}): {str(e)}")
                
            if attempt < retry_count - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return False
    
    async def get_customer_webhooks(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get Zapier webhook URLs for a customer"""
        from .database import db_service
        
        webhooks = await db_service.execute_query(
            "SELECT * FROM zapier_webhooks WHERE customer_id = ? AND active = TRUE",
            (customer_id,),
            fetch='all'
        )
        return webhooks or []
    
    async def save_webhook_config(self, customer_id: str, webhook_url: str, 
                                events: List[str] = None) -> str:
        """Save Zapier webhook configuration"""
        from .database import db_service
        
        webhook_id = str(uuid.uuid4())
        events = events or ["lead_qualified"]
        
        await db_service.execute_query('''
            INSERT INTO zapier_webhooks (
                id, customer_id, webhook_url, events, active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            webhook_id, customer_id, webhook_url, 
            json.dumps(events), True, datetime.now()
        ))
        
        return webhook_id

# Global instance
zapier_service = ZapierWebhookService()

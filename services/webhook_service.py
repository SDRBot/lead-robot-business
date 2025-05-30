import asyncio
import requests
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class ZapierWebhookService:
    """Service for Zapier webhook integrations using requests"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
    
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
        
        loop = asyncio.get_event_loop()
        
        def make_request():
            for attempt in range(retry_count):
                try:
                    response = requests.post(
                        webhook_url,
                        json=zapier_payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"✅ Lead sent to Zapier: {lead_data.get('email')}")
                        return True
                    else:
                        logger.warning(f"Zapier webhook failed: {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"Zapier webhook error (attempt {attempt + 1}): {str(e)}")
                    
                if attempt < retry_count - 1:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
            
            return False
        
        return await loop.run_in_executor(self.executor, make_request)
    
    async def get_customer_webhooks(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get Zapier webhook URLs for a customer"""
        from database import db_service
        
        webhooks = await db_service.execute_query(
            "SELECT * FROM zapier_webhooks WHERE customer_id = ? AND active = TRUE",
            (customer_id,),
            fetch='all'
        )
        return webhooks or []
    
    async def save_webhook_config(self, customer_id: str, webhook_url: str, 
                                events: List[str] = None) -> str:
        """Save Zapier webhook configuration"""
        from database import db_service
        
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

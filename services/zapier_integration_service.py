# services/zapier_integration_service.py
class ZapierIntegrationService:
    """Help customers set up their own Zapier integrations"""
    
    async def generate_zapier_webhook_endpoint(self, customer_id: str) -> str:
        """Generate unique webhook endpoint for customer's Zapier"""
        webhook_id = str(uuid.uuid4())
        webhook_url = f"{settings.app_url}/webhook/zapier/{customer_id}/{webhook_id}"
        
        await db_service.execute_query('''
            INSERT INTO customer_webhooks (
                id, customer_id, webhook_url, webhook_type, active
            ) VALUES (?, ?, ?, ?, ?)
        ''', (webhook_id, customer_id, webhook_url, 'zapier', True))
        
        return webhook_url
    
    async def create_zapier_template(self, customer_id: str) -> Dict:
        """Create Zapier template for easy setup"""
        webhook_url = await self.generate_zapier_webhook_endpoint(customer_id)
        
        return {
            "webhook_url": webhook_url,
            "template_name": "AI Sales Agent - Lead Scoring",
            "trigger": {
                "type": "webhook",
                "description": "When AI scores a lead as hot"
            },
            "sample_data": {
                "lead_email": "john@company.com",
                "lead_name": "John Smith",
                "company": "Acme Corp",
                "interest_score": 85,
                "conversation_summary": "Interested in demo, asked about pricing",
                "suggested_next_action": "Book discovery call",
                "ai_generated_response": "Thanks for your interest! I'd love to show you a quick demo..."
            },
            "suggested_actions": [
                "Create deal in CRM",
                "Send Slack notification",
                "Add to email sequence",
                "Book calendar meeting"
            ]
        }

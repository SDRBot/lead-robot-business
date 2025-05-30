import stripe
from typing import Dict, Any
from datetime import datetime
from config import settings
from database import db_service
import uuid

class StripeService:
    """Stripe payment service"""
    
    def __init__(self):
        if settings.stripe_secret_key:
            stripe.api_key = settings.stripe_secret_key
            print("✅ Stripe initialized")
        else:
            print("⚠️ Stripe secret key not configured")
    
    def create_checkout_session(self, plan: str, success_url: str, cancel_url: str):
        """Create Stripe checkout session with 14-day trial"""
        from config import PRICING_PLANS
        
        if plan not in PRICING_PLANS:
            raise ValueError(f"Plan '{plan}' not found")
        
        plan_info = PRICING_PLANS[plan]
        
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f"AI Lead Robot - {plan_info['name']}",
                            'description': f"{plan_info['description']} - {plan_info['leads_limit']} leads/month",
                        },
                        'unit_amount': plan_info['price'] * 100,
                        'recurring': {'interval': 'month'}
                    },
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={'plan': plan},
                subscription_data={
                    'trial_period_days': 14,
                },
            )
            
            return checkout_session.url
            
        except Exception as e:
            raise Exception(f"Error creating checkout: {str(e)}")
    
    async def handle_successful_payment(self, session_id: str) -> Dict[str, Any]:
        """Handle successful payment/trial signup"""
        
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=['customer', 'subscription']
        )
        
        customer_email = session.customer_details.email
        plan = session.metadata.get('plan')
        
        if not customer_email or not plan:
            raise ValueError("Missing customer email or plan in session")
        
        # Generate API key
        from services.auth_service import auth_service
        api_key = auth_service.generate_api_key()
        
        # Create customer in database
        from config import PRICING_PLANS
        customer_id = str(uuid.uuid4())
        plan_info = PRICING_PLANS[plan]
        
        await db_service.execute_query('''
            INSERT INTO customers (
                id, email, stripe_customer_id, stripe_subscription_id, 
                plan, api_key, leads_limit, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            customer_id, customer_email, str(session.customer),
            str(session.subscription), plan, api_key,
            plan_info['leads_limit'], 'active', datetime.now(), datetime.now()
        ))
        
        return {
            "customer_id": customer_id,
            "customer_email": customer_email,
            "plan": plan,
            "api_key": api_key,
            "subscription_id": str(session.subscription)
        }

# Global instance
stripe_service = StripeService()

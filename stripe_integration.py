# stripe_integration.py - Handle Stripe payments
import stripe
import os
from fastapi import HTTPException

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Your pricing plans (update these with your actual Stripe price IDs)
PRICING_PLANS = {
    "starter": {
        "name": "Starter Plan",
        "price": 99,
        "description": "500 leads per month",
        "stripe_price_id": "price_your_starter_price_id"  # You'll get this from Stripe
    },
    "professional": {
        "name": "Professional Plan", 
        "price": 299,
        "description": "2000 leads per month",
        "stripe_price_id": "price_your_pro_price_id"  # You'll get this from Stripe
    }
}

def create_checkout_session(plan_name: str, success_url: str, cancel_url: str):
    """Create a Stripe checkout session"""
    
    if plan_name not in PRICING_PLANS:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    plan = PRICING_PLANS[plan_name]
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',  # Change to 'gbp' if you want pounds
                    'product_data': {
                        'name': plan['name'],
                        'description': plan['description'],
                    },
                    'unit_amount': plan['price'] * 100,  # Stripe uses cents
                    'recurring': {'interval': 'month'}
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'plan': plan_name
            }
        )
        
        return checkout_session.url
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating checkout: {str(e)}")

def handle_successful_payment(session_id: str):
    """Handle successful payment and create customer account"""
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        
        customer_email = session.customer_details.email
        plan = session.metadata.plan
        
        return {
            "customer_email": customer_email,
            "plan": plan,
            "subscription_id": session.subscription,
            "customer_id": session.customer
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing payment: {str(e)}")

from pydantic import BaseSettings  # Change this line
from typing import Optional
import os

class Settings(BaseSettings):
    """Centralized configuration with validation"""
    
    # Database
    database_url: str = "sqlite:///leads.db"
    
    # Stripe
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    
    # Email  
    sendgrid_api_key: Optional[str] = None
    from_email: str = "hello@yourcompany.com"
    
    # OpenAI (optional)
    openai_api_key: Optional[str] = None
    
    # App settings
    app_url: str = "http://localhost:8000"
    environment: str = "development"
    debug: bool = True
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

# Pricing plans (moved from app.py)
PRICING_PLANS = {
    "starter": {
        "name": "Starter Plan",
        "price": 99,
        "leads_limit": 500,
        "description": "Perfect for small businesses",
        "features": [
            "500 leads per month",
            "AI-powered qualification", 
            "Email automation",
            "Basic analytics",
            "Email support"
        ]
    },
    "professional": {
        "name": "Professional Plan", 
        "price": 299,
        "leads_limit": 2000,
        "description": "Great for growing businesses",
        "features": [
            "2,000 leads per month",
            "Everything in Starter",
            "Zapier integrations",  # Updated from HubSpot
            "Advanced analytics",
            "Priority support",
            "API access"
        ]
    }
}

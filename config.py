from typing import Optional
import os

# Handle BaseSettings import for different pydantic versions
try:
    from pydantic_settings import BaseSettings
    print("✅ Using pydantic-settings")
except ImportError:
    try:
        from pydantic import BaseSettings
        print("✅ Using pydantic BaseSettings")
    except ImportError:
        # Fallback for when neither works
        print("⚠️ Creating BaseSettings fallback")
        class BaseSettings:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
            
            class Config:
                env_file = ".env"
                case_sensitive = False

class Settings(BaseSettings):
    """Centralized configuration with validation"""
    
    # Database
    database_url: str = "sqlite:///leads.db"
    
    # Stripe
    stripe_secret_key: Optional[str] = os.getenv("STRIPE_SECRET_KEY")
    stripe_webhook_secret: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    # Email  
    sendgrid_api_key: Optional[str] = os.getenv("SENDGRID_API_KEY")
    from_email: str = os.getenv("FROM_EMAIL", "hello@yourcompany.com")
    
    # OpenAI (optional)
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    
    # App settings
    app_url: str = os.getenv("APP_URL", "http://localhost:8000")
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # Security
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Initialize settings
try:
    settings = Settings()
    print("✅ Settings initialized successfully")
except Exception as e:
    print(f"⚠️ Settings initialization failed: {e}")
    # Create a simple fallback settings object
    class FallbackSettings:
        database_url = "sqlite:///leads.db"
        stripe_secret_key = os.getenv("STRIPE_SECRET_KEY")
        stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        from_email = os.getenv("FROM_EMAIL", "hello@yourcompany.com")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        app_url = os.getenv("APP_URL", "http://localhost:8000")
        environment = os.getenv("ENVIRONMENT", "development")
        debug = os.getenv("DEBUG", "true").lower() == "true"
        secret_key = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    
    settings = FallbackSettings()
    print("✅ Using fallback settings")

# Pricing plans configuration
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
            "Zapier integrations",
            "Advanced analytics",
            "Priority support",
            "API access"
        ]
    }
}

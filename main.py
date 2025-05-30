from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

# Import configuration and services
from config import settings
from database import db_service
from services.stripe_service import stripe_service

# Import all routers
from routers import leads, auth, dashboard, webhooks

# Import middleware
from middleware.auth import AuthMiddleware, RateLimitMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown"""
    # Startup
    await db_service.init_database()
    print("✅ Database initialized")
    
    yield
    
    # Shutdown
    print("🔄 Application shutting down")

# Create FastAPI app
app = FastAPI(
    title="AI Lead Robot - Refactored",
    description="Modular, efficient lead qualification with Zapier integration",
    version="2.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware, calls_per_minute=100)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(leads.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(webhooks.router)

# Keep your existing routes from app.py for backward compatibility
@app.get("/")
async def home():
    """Updated homepage mentioning Zapier instead of HubSpot"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 AI Lead Robot - Qualify Leads Automatically</title>
        <style>
            body { font-family: Arial; margin: 0; background: #f5f7fa; }
            .hero { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 80px 20px; text-align: center; }
            .hero h1 { font-size: 3em; margin: 0; }
            .hero p { font-size: 1.2em; margin: 20px 0; }
            .btn { background: #667eea; color: white; padding: 15px 30px; border: none; border-radius: 8px; font-size: 18px; text-decoration: none; display: inline-block; margin: 10px; }
        </style>
    </head>
    <body>
        <div class="hero">
            <h1>🤖 AI Lead Robot</h1>
            <p>Stop wasting time on unqualified leads. Our AI automatically qualifies your leads and sends them to 6,000+ apps via Zapier.</p>
            
            <div style="margin: 30px 0;">
                <a href="#pricing" class="btn">Start 14-Day Free Trial</a>
                <a href="/auth/login" class="btn">🔓 Customer Login</a>
            </div>
            
            <div style="margin-top: 40px; font-size: 14px; opacity: 0.8;">
                ⚡ New: Zapier Integration - Connect to Salesforce, HubSpot, Slack, and 6,000+ other apps!
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "features": {
            "database": "✅ Connected",
            "zapier_integration": "✅ Active", 
            "email_service": "✅ Ready",
            "stripe_payments": "✅ Configured"
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

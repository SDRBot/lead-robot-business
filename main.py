from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import your modular components
from config import settings
from services.database import db_service
from routers import leads, auth, dashboard, webhooks

# Keep your existing app.py for gradual migration
from app import app as legacy_app

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown"""
    # Startup
    await db_service.init_database()
    print("✅ Database initialized")
    
    yield
    
    # Shutdown
    print("🔄 Application shutting down")

# Create new modular app
app = FastAPI(
    title="AI Lead Robot - Refactored",
    description="Modular, efficient lead qualification with Zapier integration",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include modular routers
app.include_router(leads.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(webhooks.router)

# Mount legacy app for gradual migration
app.mount("/legacy", legacy_app)

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "database": "connected",
        "zapier_integration": "active"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

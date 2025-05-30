# main.py - Clean modular entry point
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os

# Import configuration and services
from config import settings
from database import db_service

# Import all routers
from routers import leads, auth, dashboard, webhooks

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
    title="AI Lead Robot - Modular",
    description="Efficient lead qualification with Zapier integration",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
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

# Your homepage and other essential routes
@app.get("/")
async def home():
    return {"message": "AI Lead Robot API", "version": "2.0.0", "docs": "/docs"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "2.0.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

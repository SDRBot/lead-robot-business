from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum

class AdminUser(BaseModel):
    username: str
    email: EmailStr
    role: str = "admin"
    active: bool = True

class AdminLogin(BaseModel):
    username: str
    password: str

class PromoCodeCreate(BaseModel):
    code: str
    trial_days: int = 30
    plan_override: Optional[str] = None
    max_uses: Optional[int] = None
    expires_at: Optional[datetime] = None
    description: Optional[str] = None

class CustomerUpdate(BaseModel):
    status: Optional[str] = None
    plan: Optional[str] = None
    leads_limit: Optional[int] = None
    notes: Optional[str] = None

class SystemStats(BaseModel):
    total_customers: int
    active_customers: int
    total_leads: int
    revenue_this_month: float
    promo_signups: int
    zapier_webhooks_sent: int

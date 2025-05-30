from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional, List
from datetime import datetime
from enum import Enum

class LeadInput(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    source: str = "api"
    initial_message: Optional[str] = None

class LeadResponse(BaseModel):
    id: str
    email: str
    first_name: Optional[str]
    company: Optional[str]
    qualification_score: int
    qualification_stage: str
    created_at: datetime

class ZapierWebhookConfig(BaseModel):
    webhook_url: HttpUrl
    events: List[str] = ["lead_qualified"]
    active: bool = True

class WebhookEvent(str, Enum):
    LEAD_CREATED = "lead_created"
    LEAD_QUALIFIED = "lead_qualified"
    LEAD_UPDATED = "lead_updated"
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
    
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class SetPasswordRequest(BaseModel):
    api_key: str
    password: str

class WebhookTestRequest(BaseModel):
    webhook_url: str

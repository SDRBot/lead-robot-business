# models.py - Corporate Models
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

class CorporateAccountType(str, Enum):
    STARTUP = "startup"          # 2-10 users
    BUSINESS = "business"        # 11-50 users  
    ENTERPRISE = "enterprise"    # 51+ users

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"     # Full access, billing, team management
    ADMIN = "admin"                 # Team management, no billing
    MANAGER = "manager"             # View team analytics, manage agents
    AGENT = "agent"                 # Own AI agent and conversations
    VIEWER = "viewer"               # Read-only access

class Territory(BaseModel):
    id: str
    name: str
    regions: List[str] = []
    industries: List[str] = []
    company_size_range: Optional[str] = None  # "1-50", "51-200", etc.

class CorporateAccount(BaseModel):
    company_name: str
    account_type: CorporateAccountType
    max_users: int
    billing_contact_email: EmailStr
    
    # Feature flags
    custom_branding: bool = True
    advanced_analytics: bool = True
    api_access: bool = True
    white_labeling: bool = False
    sso_enabled: bool = False
    
    # Settings
    territories: List[Territory] = []
    company_logo_url: Optional[str] = None
    primary_color: str = "#667eea"
    secondary_color: str = "#764ba2"
    
    @validator('max_users')
    def validate_max_users(cls, v, values):
        account_type = values.get('account_type')
        if account_type == CorporateAccountType.STARTUP and v > 10:
            raise ValueError("Startup accounts limited to 10 users")
        elif account_type == CorporateAccountType.BUSINESS and v > 50:
            raise ValueError("Business accounts limited to 50 users")
        return v

class TeamMember(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    department: Optional[str] = None
    
    # AI Agent Configuration
    ai_agent_name: str
    ai_agent_personality: Dict[str, Any] = {}
    
    # Access & Territories
    territories: List[str] = []  # Territory IDs they can access
    email_quota_monthly: int = 1000
    active: bool = True
    
    # Onboarding
    onboarded: bool = False
    invited_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None

class CorporateAnalytics(BaseModel):
    total_conversations: int
    total_leads_generated: int
    team_performance: List[Dict[str, Any]]
    territory_performance: List[Dict[str, Any]]
    conversion_rates: Dict[str, float]
    top_performing_agents: List[Dict[str, Any]]
    monthly_trends: Dict[str, List[float]]

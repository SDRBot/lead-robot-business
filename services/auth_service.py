import hashlib
import uuid
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer
from database import db_service

security = HTTPBearer()

class AuthService:
    """Authentication service with improved security"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password for storing"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its hash"""
        return hashlib.sha256(password.encode()).hexdigest() == hashed
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a new API key"""
        return f"sk_live_{str(uuid.uuid4()).replace('-', '')}"
    
    async def verify_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Verify API key and return customer info"""
        customer = await db_service.execute_query(
            "SELECT * FROM customers WHERE api_key = ? AND status = 'active'",
            (api_key,),
            fetch='one'
        )
        return customer
    
    async def authenticate_customer(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate customer with email and password"""
        customer = await db_service.execute_query(
            "SELECT * FROM customers WHERE email = ? AND status = 'active'",
            (email,),
            fetch='one'
        )
        
        if customer and customer.get('password_hash'):
            if self.verify_password(password, customer['password_hash']):
                return customer
        
        return None
    
    async def check_usage_limit(self, customer_id: str) -> bool:
        """Check if customer is within their usage limits"""
        customer = await db_service.execute_query(
            "SELECT leads_limit, leads_used_this_month FROM customers WHERE id = ?",
            (customer_id,),
            fetch='one'
        )
        
        if customer:
            return customer['leads_used_this_month'] < customer['leads_limit']
        return False

# Global instance
auth_service = AuthService()

# Dependency for routes
async def get_current_customer(credentials = Depends(security)):
    """Dependency to get current authenticated customer"""
    customer = await auth_service.verify_api_key(credentials.credentials)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return customer

import hashlib
import secrets
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from database import db_service
import uuid

class AdminService:
    """Admin service for managing the application"""
    
    # Default admin credentials (change these!)
    ADMIN_USERS = {
        "admin": {
            "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
            "email": "admin@yourcompany.com",
            "role": "superadmin"
        },
        "support": {
            "password_hash": hashlib.sha256("support123".encode()).hexdigest(), 
            "email": "support@yourcompany.com",
            "role": "support"
        }
    }
    
    @staticmethod
    def verify_admin(username: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify admin credentials"""
        if username in AdminService.ADMIN_USERS:
            user = AdminService.ADMIN_USERS[username]
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if password_hash == user["password_hash"]:
                return {
                    "username": username,
                    "email": user["email"],
                    "role": user["role"]
                }
        return None
    
    @staticmethod
    def generate_admin_token(username: str) -> str:
        """Generate admin session token"""
        return f"admin_{username}_{secrets.token_urlsafe(32)}"
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        
        # Customer stats
        total_customers = await db_service.execute_query(
            "SELECT COUNT(*) as count FROM customers",
            fetch='one'
        )
        
        active_customers = await db_service.execute_query(
            "SELECT COUNT(*) as count FROM customers WHERE status = 'active'",
            fetch='one'
        )
        
        # Lead stats
        total_leads = await db_service.execute_query(
            "SELECT COUNT(*) as count FROM leads",
            fetch='one'
        )
        
        leads_this_month = await db_service.execute_query(
            "SELECT COUNT(*) as count FROM leads WHERE created_at >= date('now', 'start of month')",
            fetch='one'
        )
        
        # Promo code usage
        promo_signups = await db_service.execute_query(
            "SELECT COUNT(*) as count FROM analytics WHERE event_type = 'promo_signup'",
            fetch='one'
        )
        
        # Recent signups (last 7 days)
        recent_signups = await db_service.execute_query(
            "SELECT COUNT(*) as count FROM customers WHERE created_at >= date('now', '-7 days')",
            fetch='one'
        )
        
        # Top plans
        plan_stats = await db_service.execute_query(
            "SELECT plan, COUNT(*) as count FROM customers GROUP BY plan ORDER BY count DESC",
            fetch='all'
        )
        
        return {
            "total_customers": total_customers['count'] if total_customers else 0,
            "active_customers": active_customers['count'] if active_customers else 0,
            "total_leads": total_leads['count'] if total_leads else 0,
            "leads_this_month": leads_this_month['count'] if leads_this_month else 0,
            "promo_signups": promo_signups['count'] if promo_signups else 0,
            "recent_signups": recent_signups['count'] if recent_signups else 0,
            "plan_distribution": plan_stats or [],
            "last_updated": datetime.now().isoformat()
        }
    
    async def get_all_customers(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all customers with pagination"""
        return await db_service.execute_query(
            "SELECT * FROM customers ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, skip),
            fetch='all'
        ) or []
    
    async def update_customer(self, customer_id: str, updates: Dict[str, Any]) -> bool:
        """Update customer information"""
        try:
            # Build dynamic update query
            set_clauses = []
            params = []
            
            for key, value in updates.items():
                if key in ['status', 'plan', 'leads_limit', 'notes']:
                    set_clauses.append(f"{key} = ?")
                    params.append(value)
            
            if not set_clauses:
                return False
            
            set_clauses.append("updated_at = ?")
            params.append(datetime.now())
            params.append(customer_id)
            
            query = f"UPDATE customers SET {', '.join(set_clauses)} WHERE id = ?"
            
            await db_service.execute_query(query, tuple(params))
            return True
            
        except Exception as e:
            print(f"❌ Error updating customer: {e}")
            return False
    
    async def create_promo_code(self, promo_data: Dict[str, Any]) -> str:
        """Create a new promo code"""
        promo_id = str(uuid.uuid4())
        
        await db_service.execute_query('''
            INSERT INTO promo_codes (
                id, code, trial_days, plan_override, max_uses, 
                expires_at, description, created_at, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            promo_id, promo_data['code'].upper(), promo_data['trial_days'],
            promo_data.get('plan_override'), promo_data.get('max_uses'),
            promo_data.get('expires_at'), promo_data.get('description'),
            datetime.now(), True
        ))
        
        return promo_id
    
    async def get_promo_codes(self) -> List[Dict[str, Any]]:
        """Get all promo codes with usage stats"""
        return await db_service.execute_query(
            "SELECT * FROM promo_codes ORDER BY created_at DESC",
            fetch='all'
        ) or []
    
    async def get_recent_activity(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent system activity"""
        return await db_service.execute_query(
            "SELECT * FROM analytics ORDER BY timestamp DESC LIMIT ?",
            (limit,),
            fetch='all'
        ) or []

# Global admin service
admin_service = AdminService()

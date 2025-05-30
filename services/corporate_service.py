# services/corporate_service.py
import json
import uuid
import secrets
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from database import db_service
from services.email_service import email_service
from services.auth_service import auth_service
from models import CorporateAccount, TeamMember, Territory, UserRole

class CorporateService:
    """Comprehensive corporate account management"""
    
    async def create_corporate_account(self, account_data: CorporateAccount, admin_email: str) -> str:
        """Create new corporate account with admin user"""
        
        corporate_id = str(uuid.uuid4())
        
        # Create corporate account
        await db_service.execute_query('''
            INSERT INTO corporate_accounts (
                id, company_name, account_type, max_users, billing_contact_email,
                custom_branding, advanced_analytics, api_access, white_labeling,
                sso_enabled, company_logo_url, primary_color, secondary_color,
                trial_ends_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            corporate_id, account_data.company_name, account_data.account_type.value,
            account_data.max_users, account_data.billing_contact_email,
            account_data.custom_branding, account_data.advanced_analytics,
            account_data.api_access, account_data.white_labeling, account_data.sso_enabled,
            account_data.company_logo_url, account_data.primary_color, 
            account_data.secondary_color, datetime.now() + timedelta(days=14)  # 14-day trial
        ))
        
        # Create default territories if provided
        for territory in account_data.territories:
            await self.create_territory(corporate_id, territory)
        
        # Create admin user
        admin_customer_id = await self._create_admin_customer(corporate_id, admin_email)
        
        # Send welcome email
        await self._send_corporate_welcome_email(corporate_id, admin_email)
        
        return corporate_id
    
    async def add_team_member(self, corporate_id: str, member_data: TeamMember, invited_by: str) -> str:
        """Add team member with invitation flow"""
        
        # Check if corporate account has capacity
        current_members = await self.get_member_count(corporate_id)
        corporate_account = await self.get_corporate_account(corporate_id)
        
        if current_members >= corporate_account['max_users']:
            raise ValueError(f"Account at capacity ({corporate_account['max_users']} users)")
        
        # Generate invite token
        invite_token = secrets.token_urlsafe(32)
        member_id = str(uuid.uuid4())
        
        # Create member record (pending activation)
        await db_service.execute_query('''
            INSERT INTO corporate_members (
                id, corporate_id, email, first_name, last_name, role,
                department, ai_agent_name, ai_agent_personality, territories,
                email_quota_monthly, invite_token, invited_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            member_id, corporate_id, member_data.email, member_data.first_name,
            member_data.last_name, member_data.role.value, member_data.department,
            member_data.ai_agent_name, json.dumps(member_data.ai_agent_personality),
            json.dumps(member_data.territories), member_data.email_quota_monthly,
            invite_token, datetime.now()
        ))
        
        # Send invitation email
        await self._send_team_invitation(corporate_id, member_data, invite_token, invited_by)
        
        return member_id
    
    async def accept_team_invitation(self, invite_token: str, password: str) -> Dict[str, Any]:
        """Accept team invitation and create customer account"""
        
        # Find pending member
        member = await db_service.execute_query(
            "SELECT * FROM corporate_members WHERE invite_token = ? AND customer_id IS NULL",
            (invite_token,), fetch='one'
        )
        
        if not member:
            raise ValueError("Invalid or expired invitation")
        
        # Create customer account
        api_key = auth_service.generate_api_key()
        customer_id = str(uuid.uuid4())
        password_hash = auth_service.hash_password(password)
        
        await db_service.execute_query('''
            INSERT INTO customers (
                id, email, plan, api_key, leads_limit, status,
                password_hash, corporate_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            customer_id, member['email'], 'corporate', member['email_quota_monthly'],
            'active', password_hash, member['corporate_id']
        ))
        
        # Update member record
        await db_service.execute_query('''
            UPDATE corporate_members 
            SET customer_id = ?, onboarded = TRUE, joined_at = ?, invite_token = NULL
            WHERE id = ?
        ''', (customer_id, datetime.now(), member['id']))
        
        return {
            "customer_id": customer_id,
            "api_key": api_key,
            "member_id": member['id'],
            "corporate_id": member['corporate_id']
        }
    
    async def get_team_analytics(self, corporate_id: str, date_range: int = 30) -> Dict[str, Any]:
        """Comprehensive team analytics"""
        
        start_date = datetime.now() - timedelta(days=date_range)
        
        # Team performance metrics
        team_metrics = await db_service.execute_query('''
            SELECT 
                cm.id, cm.first_name, cm.last_name, cm.ai_agent_name,
                cm.email_sent_this_month,
                COUNT(DISTINCT c.id) as total_conversations,
                AVG(c.interest_score) as avg_interest_score,
                COUNT(CASE WHEN c.interest_score >= 70 THEN 1 END) as hot_leads
            FROM corporate_members cm
            LEFT JOIN customers cust ON cm.customer_id = cust.id
            LEFT JOIN conversations c ON cust.id = c.customer_id AND c.created_at >= ?
            WHERE cm.corporate_id = ? AND cm.active = TRUE
            GROUP BY cm.id
        ''', (start_date, corporate_id), fetch='all')
        
        # Territory performance
        territory_metrics = await db_service.execute_query('''
            SELECT 
                ct.name as territory_name,
                COUNT(DISTINCT c.id) as conversations,
                AVG(c.interest_score) as avg_score,
                COUNT(CASE WHEN c.interest_score >= 70 THEN 1 END) as hot_leads
            FROM corporate_territories ct
            LEFT JOIN corporate_members cm ON JSON_EXTRACT(cm.territories, '$') LIKE '%' || ct.id || '%'
            LEFT JOIN customers cust ON cm.customer_id = cust.id
            LEFT JOIN conversations c ON cust.id = c.customer_id AND c.created_at >= ?
            WHERE ct.corporate_id = ?
            GROUP BY ct.id, ct.name
        ''', (start_date, corporate_id), fetch='all')
        
        # Overall stats
        overall_stats = await db_service.execute_query('''
            SELECT 
                COUNT(DISTINCT cm.id) as total_active_members,
                SUM(cm.email_sent_this_month) as total_emails_sent,
                COUNT(DISTINCT c.id) as total_conversations,
                AVG(c.interest_score) as overall_avg_score,
                COUNT(CASE WHEN c.interest_score >= 70 THEN 1 END) as total_hot_leads
            FROM corporate_members cm
            LEFT JOIN customers cust ON cm.customer_id = cust.id
            LEFT JOIN conversations c ON cust.id = c.customer_id AND c.created_at >= ?
            WHERE cm.corporate_id = ? AND cm.active = TRUE
        ''', (start_date, corporate_id), fetch='one')
        
        # Monthly trends
        monthly_trends = await db_service.execute_query('''
            SELECT 
                DATE(c.created_at) as date,
                COUNT(*) as conversations,
                AVG(c.interest_score) as avg_score
            FROM conversations c
            JOIN customers cust ON c.customer_id = cust.id
            JOIN corporate_members cm ON cust.id = cm.customer_id
            WHERE cm.corporate_id = ? AND c.created_at >= ?
            GROUP BY DATE(c.created_at)
            ORDER BY date
        ''', (corporate_id, start_date), fetch='all')
        
        return {
            "team_performance": team_metrics or [],
            "territory_performance": territory_metrics or [],
            "overall_stats": overall_stats or {},
            "monthly_trends": monthly_trends or [],
            "date_range_days": date_range,
            "generated_at": datetime.now().isoformat()
        }
    
    async def create_territory(self, corporate_id: str, territory: Territory) -> str:
        """Create new territory"""
        territory_id = str(uuid.uuid4())
        
        await db_service.execute_query('''
            INSERT INTO corporate_territories (
                id, corporate_id, name, regions, industries, company_size_range
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            territory_id, corporate_id, territory.name,
            json.dumps(territory.regions), json.dumps(territory.industries),
            territory.company_size_range
        ))
        
        return territory_id
    
    async def assign_member_to_territory(self, member_id: str, territory_ids: List[str]):
        """Assign team member to territories"""
        await db_service.execute_query(
            "UPDATE corporate_members SET territories = ? WHERE id = ?",
            (json.dumps(territory_ids), member_id)
        )
    
    async def get_corporate_dashboard_data(self, corporate_id: str) -> Dict[str, Any]:
        """Get all data needed for corporate dashboard"""
        
        analytics = await self.get_team_analytics(corporate_id)
        members = await self.get_team_members(corporate_id)
        territories = await self.get_territories(corporate_id)
        recent_activity = await self.get_recent_activity(corporate_id, limit=20)
        
        return {
            "analytics": analytics,
            "team_members": members,
            "territories": territories,
            "recent_activity": recent_activity,
            "account_info": await self.get_corporate_account(corporate_id)
        }
    
    async def update_member_permissions(self, member_id: str, new_role: UserRole, territories: List[str]):
        """Update team member role and territory access"""
        await db_service.execute_query('''
            UPDATE corporate_members 
            SET role = ?, territories = ?, updated_at = ?
            WHERE id = ?
        ''', (new_role.value, json.dumps(territories), datetime.now(), member_id))
    
    async def deactivate_member(self, member_id: str):
        """Deactivate team member (soft delete)"""
        await db_service.execute_query(
            "UPDATE corporate_members SET active = FALSE, updated_at = ? WHERE id = ?",
            (datetime.now(), member_id)
        )
        
        # Also deactivate their customer account
        member = await db_service.execute_query(
            "SELECT customer_id FROM corporate_members WHERE id = ?",
            (member_id,), fetch='one'
        )
        
        if member and member['customer_id']:
            await db_service.execute_query(
                "UPDATE customers SET status = 'inactive' WHERE id = ?",
                (member['customer_id'],)
            )
    
    # Helper methods
    async def get_corporate_account(self, corporate_id: str) -> Optional[Dict[str, Any]]:
        """Get corporate account details"""
        return await db_service.execute_query(
            "SELECT * FROM corporate_accounts WHERE id = ?",
            (corporate_id,), fetch='one'
        )
    
    async def get_team_members(self, corporate_id: str) -> List[Dict[str, Any]]:
        """Get all team members"""
        return await db_service.execute_query(
            "SELECT * FROM corporate_members WHERE corporate_id = ? ORDER BY created_at",
            (corporate_id,), fetch='all'
        ) or []
    
    async def get_territories(self, corporate_id: str) -> List[Dict[str, Any]]:
        """Get all territories"""
        return await db_service.execute_query(
            "SELECT * FROM corporate_territories WHERE corporate_id = ?",
            (corporate_id,), fetch='all'
        ) or []
    
    async def get_member_count(self, corporate_id: str) -> int:
        """Get active member count"""
        result = await db_service.execute_query(
            "SELECT COUNT(*) as count FROM corporate_members WHERE corporate_id = ? AND active = TRUE",
            (corporate_id,), fetch='one'
        )
        return result['count'] if result else 0
    
    async def get_recent_activity(self, corporate_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent team activity"""
        return await db_service.execute_query('''
            SELECT 
                'conversation' as activity_type,
                c.id,
                c.lead_name,
                c.interest_score,
                cm.first_name || ' ' || cm.last_name as agent_name,
                c.created_at
            FROM conversations c
            JOIN customers cust ON c.customer_id = cust.id
            JOIN corporate_members cm ON cust.id = cm.customer_id
            WHERE cm.corporate_id = ?
            UNION ALL
            SELECT 
                'member_joined' as activity_type,
                cm.id,
                cm.first_name || ' ' || cm.last_name as lead_name,
                NULL as interest_score,
                'System' as agent_name,
                cm.joined_at as created_at
            FROM corporate_members cm
            WHERE cm.corporate_id = ? AND cm.joined_at IS NOT NULL
            ORDER BY created_at DESC
            LIMIT ?
        ''', (corporate_id, corporate_id, limit), fetch='all') or []
    
    # Email methods
    async def _send_corporate_welcome_email(self, corporate_id: str, admin_email: str):
        """Send welcome email to corporate admin"""
        corporate = await self.get_corporate_account(corporate_id)
        
        subject = f"🎉 Welcome to AI Lead Robot Corporate - {corporate['company_name']}"
        content = f"""
        <div style="font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: {corporate['primary_color']};">Welcome to AI Lead Robot Corporate!</h1>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3>🏢 Account Details</h3>
                <p><strong>Company:</strong> {corporate['company_name']}</p>
                <p><strong>Account Type:</strong> {corporate['account_type'].title()}</p>
                <p><strong>Max Team Members:</strong> {corporate['max_users']}</p>
                <p><strong>Trial Ends:</strong> {corporate['trial_ends_at'][:10]}</p>
            </div>
            
            <h3>🚀 Next Steps:</h3>
            <ol>
                <li>Set up your company branding</li>
                <li>Create territories for your team</li>
                <li>Invite team members</li>
                <li>Configure AI agents for each member</li>
            </ol>
            
            <p style="text-align: center; margin: 30px 0;">
                <a href="{settings.app_url}/corporate/dashboard/{corporate_id}" 
                   style="background: {corporate['primary_color']}; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px;">
                   🏢 Access Corporate Dashboard
                </a>
            </p>
        </div>
        """
        
        await email_service.send_email(admin_email, subject, content)
    
    async def _send_team_invitation(self, corporate_id: str, member_data: TeamMember, invite_token: str, invited_by: str):
        """Send team invitation email"""
        corporate = await self.get_corporate_account(corporate_id)
        
        subject = f"🤝 Join {corporate['company_name']} on AI Lead Robot"
        
        content = f"""
        <div style="font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: {corporate['primary_color']};">You've been invited to join {corporate['company_name']}!</h1>
            
            <p>Hi {member_data.first_name},</p>
            <p>{invited_by} has invited you to join their team on AI Lead Robot.</p>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3>👤 Your Role</h3>
                <p><strong>Role:</strong> {member_data.role.value.replace('_', ' ').title()}</p>
                <p><strong>AI Agent Name:</strong> {member_data.ai_agent_name}</p>
                <p><strong>Monthly Email Quota:</strong> {member_data.email_quota_monthly:,}</p>
                {f"<p><strong>Department:</strong> {member_data.department}</p>" if member_data.department else ""}
            </div>
            
            <p style="text-align: center; margin: 30px 0;">
                <a href="{settings.app_url}/corporate/accept-invite/{invite_token}" 
                   style="background: {corporate['primary_color']}; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px;">
                   🚀 Accept Invitation
                </a>
            </p>
            
            <p style="color: #666; font-size: 14px;">
                This invitation will expire in 7 days.
            </p>
        </div>
        """
        
        await email_service.send_email(member_data.email, subject, content)
    
    async def _create_admin_customer(self, corporate_id: str, admin_email: str) -> str:
        """Create admin customer account"""
        api_key = auth_service.generate_api_key()
        customer_id = str(uuid.uuid4())
        
        await db_service.execute_query('''
            INSERT INTO customers (
                id, email, plan, api_key, leads_limit, status, corporate_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (customer_id, admin_email, 'corporate', 10000, 'active', corporate_id))
        
        # Create admin member record
        await db_service.execute_query('''
            INSERT INTO corporate_members (
                id, corporate_id, customer_id, email, first_name, last_name,
                role, ai_agent_name, onboarded, joined_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()), corporate_id, customer_id, admin_email,
            "Admin", "User", UserRole.SUPER_ADMIN.value, "AdminBot",
            True, datetime.now()
        ))
        
        return customer_id

# Global instance
corporate_service = CorporateService()

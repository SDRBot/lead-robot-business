from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from services.auth_service import get_current_customer
from database import db_service
from config import PRICING_PLANS

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/", response_class=HTMLResponse)
async def dashboard(api_key: str = None, request: Request = None, customer: dict = Depends(get_current_customer)):
    """Customer dashboard"""
    
    # Get customer stats
    total_leads = await db_service.execute_query(
        "SELECT COUNT(*) as count FROM leads WHERE customer_id = ?",
        (customer['id'],),
        fetch='one'
    )
    
    qualified_leads = await db_service.execute_query(
        "SELECT COUNT(*) as count FROM leads WHERE customer_id = ? AND qualification_stage IN ('hot_lead', 'warm_lead')",
        (customer['id'],),
        fetch='one'
    )
    
    recent_leads = await db_service.execute_query(
        "SELECT * FROM leads WHERE customer_id = ? ORDER BY created_at DESC LIMIT 10",
        (customer['id'],),
        fetch='all'
    )
    
    plan_info = PRICING_PLANS[customer['plan']]
    usage_percent = (customer['leads_used_this_month'] / customer['leads_limit']) * 100
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>📊 Dashboard - AI Lead Robot</title>
        <style>
            body {{ font-family: Arial; margin: 0; padding: 20px; background: #f5f7fa; max-width: 1200px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 30px; }}
            .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
            .metric {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }}
            .metric h3 {{ margin: 0 0 10px 0; color: #666; font-size: 14px; }}
            .metric .value {{ font-size: 32px; font-weight: bold; margin: 0; }}
            .usage-bar {{ background: #e9ecef; height: 20px; border-radius: 10px; overflow: hidden; margin: 10px 0; }}
            .usage-fill {{ background: linear-gradient(90deg, #28a745, #ffc107, #dc3545); height: 100%; width: {min(usage_percent, 100)}%; }}
            table {{ width: 100%; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); border-collapse: collapse; }}
            th, td {{ padding: 15px; text-align: left; border-bottom: 1px solid #eee; }}
            th {{ background: #f8f9fa; font-weight: bold; }}
            .btn {{ background: #667eea; color: white; padding: 10px 20px; border: none; border-radius: 5px; text-decoration: none; display: inline-block; margin: 5px; }}
            .btn:hover {{ background: #5a6fd8; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 AI Lead Robot Dashboard</h1>
            <p>Welcome back! Here's how your lead qualification is performing.</p>
            <p><strong>Plan:</strong> {plan_info['name']} | <strong>Email:</strong> {customer['email']}</p>
        </div>
        
        <div class="metrics">
            <div class="metric">
                <h3>Total Leads</h3>
                <div class="value" style="color: #2ecc71;">{total_leads['count'] if total_leads else 0}</div>
            </div>
            <div class="metric">
                <h3>Qualified Leads</h3>
                <div class="value" style="color: #e74c3c;">{qualified_leads['count'] if qualified_leads else 0}</div>
            </div>
            <div class="metric">
                <h3>Conversion Rate</h3>
                <div class="value" style="color: #3498db;">{round((qualified_leads['count']/max(total_leads['count'],1))*100, 1) if total_leads and qualified_leads else 0}%</div>
            </div>
            <div class="metric">
                <h3>Monthly Usage</h3>
                <div class="value" style="color: #9b59b6;">{customer['leads_used_this_month']}/{customer['leads_limit']}</div>
                <div class="usage-bar"><div class="usage-fill"></div></div>
            </div>
        </div>
        
        <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px;">
            <h3>🔗 Quick Actions</h3>
            <a href="/api/leads/test?api_key={customer['api_key']}" class="btn">🧪 Test Lead Capture</a>
            <a href="/webhooks/setup?api_key={customer['api_key']}" class="btn">⚡ Setup Zapier</a>
            <a href="/support?api_key={customer['api_key']}" class="btn">💬 Get Support</a>
        </div>
        
        <h2>📋 Recent Leads</h2>
        <table>
            <tr>
                <th>Email</th>
                <th>Name</th>
                <th>Company</th>
                <th>Score</th>
                <th>Stage</th>
                <th>Created</th>
            </tr>
    """
    
    for lead in (recent_leads or []):
        created_date = lead['created_at'][:16] if lead.get('created_at') else 'N/A'
        
        html += f"""
            <tr>
                <td>{lead.get('email', 'N/A')}</td>
                <td>{lead.get('first_name', 'N/A')}</td>
                <td>{lead.get('company', 'N/A')}</td>
                <td>{lead.get('qualification_score', 0)}</td>
                <td>{lead.get('qualification_stage', 'new').replace('_', ' ').title()}</td>
                <td>{created_date}</td>
            </tr>
        """
    
    html += """
        </table>
        
        <div style="margin-top: 40px; text-align: center; color: #666;">
            <p>🤖 Your AI Lead Robot is working 24/7 to qualify your leads!</p>
            <p><a href="mailto:support@yourcompany.com">Need help? Contact Support</a></p>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(html)

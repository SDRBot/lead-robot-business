# routers/corporate.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from services.corporate_service import corporate_service
from services.auth_service import get_current_customer
from models import TeamMember, Territory, UserRole

router = APIRouter(prefix="/corporate", tags=["corporate"])

@router.get("/dashboard/{corporate_id}", response_class=HTMLResponse)
async def corporate_dashboard(
    corporate_id: str,
    customer: dict = Depends(get_current_customer)
):
    """Corporate dashboard with team management"""
    
    # Verify access
    member = await db_service.execute_query(
        "SELECT * FROM corporate_members WHERE customer_id = ? AND corporate_id = ?",
        (customer['id'], corporate_id), fetch='one'
    )
    
    if not member or member['role'] not in ['super_admin', 'admin', 'manager']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    dashboard_data = await corporate_service.get_corporate_dashboard_data(corporate_id)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🏢 Corporate Dashboard - {dashboard_data['account_info']['company_name']}</title>
        <style>
            :root {{
                --primary-color: {dashboard_data['account_info']['primary_color']};
                --secondary-color: {dashboard_data['account_info']['secondary_color']};
            }}
            body {{ font-family: Arial; margin: 0; background: #f5f7fa; }}
            .header {{ background: linear-gradient(135deg, var(--primary-color), var(--secondary-color)); color: white; padding: 30px; }}
            .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
            .dashboard-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin: 30px 0; }}
            .card {{ background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
            .stat-card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: var(--primary-color); }}
            .team-member {{ display: flex; justify-content: space-between; align-items: center; padding: 15px; border-bottom: 1px solid #eee; }}
            .member-info {{ display: flex; align-items: center; gap: 15px; }}
            .member-avatar {{ width: 40px; height: 40px; border-radius: 50%; background: var(--primary-color); display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; }}
            .member-stats {{ font-size: 0.9em; color: #666; }}
            .role-badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }}
            .role-super_admin {{ background: #dc3545; color: white; }}
            .role-admin {{ background: #fd7e14; color: white; }}
            .role-manager {{ background: #20c997; color: white; }}
            .role-agent {{ background: #0d6efd; color: white; }}
            .role-viewer {{ background: #6c757d; color: white; }}
            .btn {{ background: var(--primary-color); color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; }}
            .btn-secondary {{ background: #6c757d; }}
            .btn-success {{ background: #198754; }}
            .btn-danger {{ background: #dc3545; }}
            .territory-list {{ display: grid; gap: 15px; }}
            .territory-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid var(--primary-color); }}
            .activity-feed {{ max-height: 400px; overflow-y: auto; }}
            .activity-item {{ display: flex; align-items

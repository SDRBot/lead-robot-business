from fastapi import APIRouter, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from services.admin_service import admin_service
from models import AdminLogin, PromoCodeCreate, CustomerUpdate
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer()

# In-memory admin sessions (use Redis in production)
admin_sessions = {}

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin authentication"""
    token = credentials.credentials
    if token in admin_sessions:
        return admin_sessions[token]
    raise HTTPException(status_code=401, detail="Invalid admin token")

@router.get("/", response_class=HTMLResponse)
async def admin_login_page():
    """Admin login page"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🔐 Admin Login - AI Lead Robot</title>
        <style>
            body { font-family: Arial; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin: 0; padding: 0; min-height: 100vh; display: flex; justify-content: center; align-items: center; }
            .login-container { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); max-width: 400px; width: 100%; }
            h1 { text-align: center; color: #333; margin-bottom: 30px; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
            input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
            .btn { background: #667eea; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; width: 100%; font-size: 16px; }
            .btn:hover { background: #5a6fd8; }
            .error { background: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px; margin: 10px 0; }
            .warning { background: #fff3cd; color: #856404; padding: 15px; border-radius: 5px; margin: 20px 0; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h1>🔐 Admin Panel</h1>
            
            <div class="warning">
                <strong>⚠️ Default Credentials:</strong><br>
                Username: <code>admin</code> | Password: <code>admin123</code><br>
                Username: <code>support</code> | Password: <code>support123</code><br>
                <em>Change these in production!</em>
            </div>
            
            <form id="loginForm">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" name="username" required>
                </div>
                
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" required>
                </div>
                
                <button type="submit" class="btn">🔓 Login to Admin Panel</button>
            </form>
            
            <div id="message"></div>
        </div>
        
        <script>
            document.getElementById('loginForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData(e.target);
                const data = {
                    username: formData.get('username'),
                    password: formData.get('password')
                };
                
                try {
                    const response = await fetch('/admin/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        localStorage.setItem('admin_token', result.token);
                        window.location.href = '/admin/dashboard';
                    } else {
                        document.getElementById('message').innerHTML = '<div class="error">❌ ' + result.detail + '</div>';
                    }
                } catch (error) {
                    document.getElementById('message').innerHTML = '<div class="error">❌ Login failed</div>';
                }
            });
        </script>
    </body>
    </html>
    """

@router.post("/login")
async def admin_login(login: AdminLogin):
    """Admin login endpoint"""
    
    admin_user = admin_service.verify_admin(login.username, login.password)
    if not admin_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Generate session token
    token = admin_service.generate_admin_token(login.username)
    admin_sessions[token] = admin_user
    
    return {
        "token": token,
        "user": admin_user,
        "message": "Login successful"
    }

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard():
    """Admin dashboard - main view"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>📊 Admin Dashboard - AI Lead Robot</title>
        <style>
            body {{ font-family: Arial; margin: 0; background: #f5f7fa; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }}
            .stat-card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #667eea; }}
            .nav {{ background: white; padding: 15px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .nav a {{ margin: 0 15px; color: #667eea; text-decoration: none; font-weight: bold; }}
            .nav a:hover {{ color: #5a6fd8; }}
            .table {{ width: 100%; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }}
            .table th, .table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
            .table th {{ background: #f8f9fa; font-weight: bold; }}
            .btn {{ background: #667eea; color: white; padding: 8px 16px; border: none; border-radius: 5px; text-decoration: none; font-size: 14px; }}
            .btn-danger {{ background: #dc3545; }}
            .btn-success {{ background: #28a745; }}
            #loadingSpinner {{ text-align: center; padding: 40px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="container">
                <h1>📊 Admin Dashboard</h1>
                <p>AI Lead Robot Management Panel</p>
                <button onclick="logout()" style="background: rgba(255,255,255,0.2); color: white; border: none; padding: 8px 16px; border-radius: 5px; cursor: pointer; float: right;">🚪 Logout</button>
            </div>
        </div>
        
        <div class="container">
            <div class="nav">
                <a href="#" onclick="showStats()">📊 Statistics</a>
                <a href="#" onclick="showCustomers()">👥 Customers</a>
                <a href="#" onclick="showPromoCodes()">🎁 Promo Codes</a>
                <a href="#" onclick="showActivity()">📈 Activity</a>
                <a href="#" onclick="showSupport()">🎫 Support Tickets</a>
            </div>
            
            <div id="content">
                <div id="loadingSpinner">🔄 Loading dashboard...</div>
            </div>
        </div>
        
        <script>
            const adminToken = localStorage.getItem('admin_token');
            if (!adminToken) {{ window.location.href = '/admin/'; }}
            
            function logout() {{
                localStorage.removeItem('admin_token');
                window.location.href = '/admin/';
            }}
            
            async function apiCall(endpoint) {{
                const response = await fetch(endpoint, {{
                    headers: {{ 'Authorization': 'Bearer ' + adminToken }}
                }});
                return response.json();
            }}
            
            async function showStats() {{
                document.getElementById('content').innerHTML = '<div id="loadingSpinner">🔄 Loading statistics...</div>';
                
                try {{
                    const stats = await apiCall('/admin/api/stats');
                    
                    document.getElementById('content').innerHTML = `
                        <h2>📊 System Statistics</h2>
                        <div class="stats-grid">
                            <div class="stat-card">
                                <div class="stat-number">${{stats.total_customers}}</div>
                                <div>Total Customers</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-number">${{stats.active_customers}}</div>
                                <div>Active Customers</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-number">${{stats.total_leads}}</div>
                                <div>Total Leads</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-number">${{stats.leads_this_month}}</div>
                                <div>Leads This Month</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-number">${{stats.promo_signups}}</div>
                                <div>Promo Signups</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-number">${{stats.recent_signups}}</div>
                                <div>Signups (7 days)</div>
                            </div>
                        </div>
                        
                        <h3>📈 Plan Distribution</h3>
                        <table class="table">
                            <tr><th>Plan</th><th>Customers</th></tr>
                            ${{stats.plan_distribution.map(p => `<tr><td>${{p.plan}}</td><td>${{p.count}}</td></tr>`).join('')}}
                        </table>
                    `;
                }} catch (error) {{
                    document.getElementById('content').innerHTML = '<div style="color: red;">❌ Error loading statistics</div>';
                }}
            }}
            
            async function showCustomers() {{
                document.getElementById('content').innerHTML = '<div id="loadingSpinner">🔄 Loading customers...</div>';
                
                try {{
                    const customers = await apiCall('/admin/api/customers');
                    
                    let customerRows = customers.map(c => `
                        <tr>
                            <td>${{c.email}}</td>
                            <td>${{c.plan}}</td>
                            <td>${{c.status}}</td>
                            <td>${{c.leads_used_this_month}}/${{c.leads_limit}}</td>
                            <td>${{new Date(c.created_at).toLocaleDateString()}}</td>
                            <td>
                                <button class="btn btn-danger" onclick="updateCustomerStatus('${{c.id}}', 'suspended')">Suspend</button>
                                <button class="btn btn-success" onclick="updateCustomerStatus('${{c.id}}', 'active')">Activate</button>
                            </td>
                        </tr>
                    `).join('');
                    
                    document.getElementById('content').innerHTML = `
                        <h2>👥 Customer Management</h2>
                        <table class="table">
                            <tr>
                                <th>Email</th>
                                <th>Plan</th>
                                <th>Status</th>
                                <th>Usage</th>
                                <th>Created</th>
                                <th>Actions</th>
                            </tr>
                            ${{customerRows}}
                        </table>
                    `;
                }} catch (error) {{
                    document.getElementById('content').innerHTML = '<div style="color: red;">❌ Error loading customers</div>';
                }}
            }}
            
            async function updateCustomerStatus(customerId, status) {{
                try {{
                    await fetch(`/admin/api/customers/${{customerId}}`, {{
                        method: 'PUT',
                        headers: {{ 
                            'Authorization': 'Bearer ' + adminToken,
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify({{ status: status }})
                    }});
                    
                    showCustomers(); // Refresh the list
                    alert(`✅ Customer status updated to ${{status}}`);
                }} catch (error) {{
                    alert('❌ Error updating customer');
                }}
            }}
            
            // Load stats by default
            showStats();
        </script>
    </body>
    </html>
    """

@router.get("/api/stats")
async def get_admin_stats(admin: dict = Depends(get_current_admin)):
    """Get system statistics for admin dashboard"""
    return await admin_service.get_system_stats()

@router.get("/api/customers")
async def get_admin_customers(admin: dict = Depends(get_current_admin), skip: int = 0, limit: int = 100):
    """Get all customers for admin management"""
    return await admin_service.get_all_customers(skip, limit)

@router.put("/api/customers/{customer_id}")
async def update_customer_admin(
    customer_id: str, 
    update: CustomerUpdate,
    admin: dict = Depends(get_current_admin)
):
    """Update customer information"""
    success = await admin_service.update_customer(customer_id, update.dict(exclude_unset=True))
    if success:
        return {"message": "Customer updated successfully"}
    else:
        raise HTTPException(status_code=400, detail="Failed to update customer")

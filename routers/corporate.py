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
            .activity-item {{ display: flex; align-items: center; gap: 15px; padding: 12px; border-bottom: 1px solid #eee; }}
            .activity-icon {{ width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; }}
            .activity-conversation {{ background: #e3f2fd; color: #1976d2; }}
            .activity-member {{ background: #e8f5e9; color: #2e7d32; }}
            .activity-territory {{ background: #fff3e0; color: #f57c00; }}
            .chart-container {{ height: 300px; margin: 20px 0; }}
            .nav-tabs {{ display: flex; border-bottom: 2px solid #eee; margin-bottom: 20px; }}
            .nav-tab {{ padding: 12px 24px; cursor: pointer; border-bottom: 2px solid transparent; }}
            .nav-tab.active {{ border-bottom-color: var(--primary-color); color: var(--primary-color); font-weight: bold; }}
            .tab-content {{ display: none; }}
            .tab-content.active {{ display: block; }}
       </style>
   </head>
   <body>
       <div class="header">
           <div class="container">
               <h1>🏢 {dashboard_data['account_info']['company_name']} Dashboard</h1>
               <p>Corporate AI Sales Team Management</p>
               <div style="float: right;">
                   <span class="role-badge role-{member['role']}">{member['role'].replace('_', ' ').title()}</span>
                   <button onclick="showSettings()" class="btn" style="margin-left: 15px;">⚙️ Settings</button>
               </div>
           </div>
       </div>
       
       <div class="container">
           <!-- Key Metrics -->
           <div class="stats-grid">
               <div class="stat-card">
                   <div class="stat-number">{dashboard_data['analytics']['overall_stats'].get('total_active_members', 0)}</div>
                   <div>Active Team Members</div>
               </div>
               <div class="stat-card">
                   <div class="stat-number">{dashboard_data['analytics']['overall_stats'].get('total_conversations', 0)}</div>
                   <div>Total Conversations</div>
               </div>
               <div class="stat-card">
                   <div class="stat-number">{dashboard_data['analytics']['overall_stats'].get('total_hot_leads', 0)}</div>
                   <div>Hot Leads (70+ Score)</div>
               </div>
               <div class="stat-card">
                   <div class="stat-number">{dashboard_data['analytics']['overall_stats'].get('total_emails_sent', 0)}</div>
                   <div>Emails Sent This Month</div>
               </div>
               <div class="stat-card">
                   <div class="stat-number">{round(dashboard_data['analytics']['overall_stats'].get('overall_avg_score', 0), 1)}</div>
                   <div>Average Interest Score</div>
               </div>
           </div>
           
           <!-- Navigation Tabs -->
           <div class="nav-tabs">
               <div class="nav-tab active" onclick="showTab('team')">👥 Team Management</div>
               <div class="nav-tab" onclick="showTab('analytics')">📊 Analytics</div>
               <div class="nav-tab" onclick="showTab('territories')">🗺️ Territories</div>
               <div class="nav-tab" onclick="showTab('activity')">📈 Activity Feed</div>
           </div>
           
           <!-- Team Management Tab -->
           <div id="team-tab" class="tab-content active">
               <div class="dashboard-grid">
                   <div class="card">
                       <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                           <h3>👥 Team Members ({len(dashboard_data['team_members'])})</h3>
                           <button onclick="showInviteMember()" class="btn">➕ Invite Member</button>
                       </div>
                       
                       <div class="team-list">
   """
   
   for member in dashboard_data['team_members']:
       performance = next((p for p in dashboard_data['analytics']['team_performance'] if p['id'] == member['id']), {})
       initials = f"{member['first_name'][0]}{member['last_name'][0]}" if member['first_name'] and member['last_name'] else "?"
       
       html += f"""
                           <div class="team-member">
                               <div class="member-info">
                                   <div class="member-avatar">{initials}</div>
                                   <div>
                                       <div style="font-weight: bold;">{member['first_name']} {member['last_name']}</div>
                                       <div style="color: #666; font-size: 0.9em;">🤖 {member['ai_agent_name']}</div>
                                       <div class="member-stats">
                                           {performance.get('total_conversations', 0)} conversations • 
                                           {performance.get('hot_leads', 0)} hot leads • 
                                           Score: {round(performance.get('avg_interest_score', 0), 1)}
                                       </div>
                                   </div>
                               </div>
                               <div style="text-align: right;">
                                   <div class="role-badge role-{member['role']}">{member['role'].replace('_', ' ').title()}</div>
                                   <div style="margin-top: 8px;">
                                       <button onclick="editMember('{member['id']}')" class="btn btn-secondary" style="padding: 5px 10px; font-size: 0.8em;">✏️ Edit</button>
                                       {"<button onclick=\"deactivateMember('{}')\" class=\"btn btn-danger\" style=\"padding: 5px 10px; font-size: 0.8em; margin-left: 5px;\">🚫 Deactivate</button>".format(member['id']) if member['role'] != 'super_admin' else ""}
                                   </div>
                               </div>
                           </div>
       """
   
   html += f"""
                       </div>
                   </div>
                   
                   <div class="card">
                       <h3>📊 Team Performance Rankings</h3>
                       <div class="performance-rankings">
   """
   
   # Sort team performance by hot leads
   sorted_performance = sorted(
       dashboard_data['analytics']['team_performance'], 
       key=lambda x: x.get('hot_leads', 0), 
       reverse=True
   )
   
   for i, perf in enumerate(sorted_performance[:10]):  # Top 10
       rank_emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
       
       html += f"""
                           <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; border-bottom: 1px solid #eee;">
                               <div>
                                   <span style="font-weight: bold;">{rank_emoji} {perf['first_name']} {perf['last_name']}</span>
                                   <div style="font-size: 0.9em; color: #666;">🤖 {perf['ai_agent_name']}</div>
                               </div>
                               <div style="text-align: right;">
                                   <div style="font-weight: bold; color: var(--primary-color);">{perf.get('hot_leads', 0)} Hot Leads</div>
                                   <div style="font-size: 0.9em; color: #666;">{perf.get('total_conversations', 0)} conversations</div>
                               </div>
                           </div>
       """
   
   html += f"""
                       </div>
                   </div>
               </div>
           </div>
           
           <!-- Analytics Tab -->
           <div id="analytics-tab" class="tab-content">
               <div class="dashboard-grid">
                   <div class="card">
                       <h3>📈 Performance Trends</h3>
                       <canvas id="trendsChart" class="chart-container"></canvas>
                   </div>
                   
                   <div class="card">
                       <h3>🎯 Territory Performance</h3>
                       <div class="territory-performance">
   """
   
   for territory in dashboard_data['analytics']['territory_performance']:
       html += f"""
                           <div class="territory-card">
                               <div style="display: flex; justify-content: space-between; align-items: center;">
                                   <div>
                                       <h4 style="margin: 0;">{territory['territory_name']}</h4>
                                       <div style="color: #666; font-size: 0.9em;">{territory.get('conversations', 0)} conversations</div>
                                   </div>
                                   <div style="text-align: right;">
                                       <div style="font-size: 1.2em; font-weight: bold; color: var(--primary-color);">{territory.get('hot_leads', 0)} Hot Leads</div>
                                       <div style="color: #666;">Avg Score: {round(territory.get('avg_score', 0), 1)}</div>
                                   </div>
                               </div>
                           </div>
       """
   
   html += f"""
                       </div>
                   </div>
               </div>
               
               <div class="card">
                   <h3>📊 Detailed Team Analytics</h3>
                   <div style="overflow-x: auto;">
                       <table style="width: 100%; border-collapse: collapse;">
                           <thead>
                               <tr style="background: #f8f9fa;">
                                   <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6;">Team Member</th>
                                   <th style="padding: 12px; text-align: center; border-bottom: 2px solid #dee2e6;">Conversations</th>
                                   <th style="padding: 12px; text-align: center; border-bottom: 2px solid #dee2e6;">Hot Leads</th>
                                   <th style="padding: 12px; text-align: center; border-bottom: 2px solid #dee2e6;">Avg Score</th>
                                   <th style="padding: 12px; text-align: center; border-bottom: 2px solid #dee2e6;">Emails Sent</th>
                                   <th style="padding: 12px; text-align: center; border-bottom: 2px solid #dee2e6;">Conversion Rate</th>
                               </tr>
                           </thead>
                           <tbody>
   """
   
   for perf in dashboard_data['analytics']['team_performance']:
       conversion_rate = (perf.get('hot_leads', 0) / max(perf.get('total_conversations', 1), 1)) * 100
       
       html += f"""
                               <tr>
                                   <td style="padding: 12px; border-bottom: 1px solid #dee2e6;">
                                       <div>
                                           <strong>{perf['first_name']} {perf['last_name']}</strong>
                                           <div style="font-size: 0.9em; color: #666;">🤖 {perf['ai_agent_name']}</div>
                                       </div>
                                   </td>
                                   <td style="padding: 12px; text-align: center; border-bottom: 1px solid #dee2e6;">{perf.get('total_conversations', 0)}</td>
                                   <td style="padding: 12px; text-align: center; border-bottom: 1px solid #dee2e6; color: var(--primary-color); font-weight: bold;">{perf.get('hot_leads', 0)}</td>
                                   <td style="padding: 12px; text-align: center; border-bottom: 1px solid #dee2e6;">{round(perf.get('avg_interest_score', 0), 1)}</td>
                                   <td style="padding: 12px; text-align: center; border-bottom: 1px solid #dee2e6;">{perf.get('email_sent_this_month', 0)}</td>
                                   <td style="padding: 12px; text-align: center; border-bottom: 1px solid #dee2e6;">{round(conversion_rate, 1)}%</td>
                               </tr>
       """
   
   html += f"""
                           </tbody>
                       </table>
                   </div>
               </div>
           </div>
           
           <!-- Territories Tab -->
           <div id="territories-tab" class="tab-content">
               <div class="card">
                   <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                       <h3>🗺️ Sales Territories ({len(dashboard_data['territories'])})</h3>
                       <button onclick="showCreateTerritory()" class="btn">➕ Create Territory</button>
                   </div>
                   
                   <div class="territory-list">
   """
   
   for territory in dashboard_data['territories']:
       regions = json.loads(territory.get('regions', '[]')) if territory.get('regions') else []
       industries = json.loads(territory.get('industries', '[]')) if territory.get('industries') else []
       
       html += f"""
                       <div class="territory-card">
                           <div style="display: flex; justify-content: space-between; align-items: start;">
                               <div style="flex: 1;">
                                   <h4 style="margin: 0 0 10px 0;">{territory['name']}</h4>
                                   
                                   {f"<div><strong>Regions:</strong> {', '.join(regions)}</div>" if regions else ""}
                                   {f"<div><strong>Industries:</strong> {', '.join(industries)}</div>" if industries else ""}
                                   {f"<div><strong>Company Size:</strong> {territory['company_size_range']}</div>" if territory.get('company_size_range') else ""}
                                   
                                   <div style="margin-top: 10px; font-size: 0.9em; color: #666;">
                                       <strong>Assigned Agents:</strong>
       """
       
       # Find members assigned to this territory
       assigned_members = [
           m for m in dashboard_data['team_members'] 
           if territory['id'] in json.loads(m.get('territories', '[]'))
       ]
       
       if assigned_members:
           member_names = [f"{m['first_name']} {m['last_name']}" for m in assigned_members]
           html += ", ".join(member_names)
       else:
           html += "None assigned"
       
       html += f"""
                                   </div>
                               </div>
                               <div>
                                   <button onclick="editTerritory('{territory['id']}')" class="btn btn-secondary" style="padding: 5px 10px; font-size: 0.8em;">✏️ Edit</button>
                               </div>
                           </div>
                       </div>
       """
   
   html += f"""
                   </div>
               </div>
           </div>
           
           <!-- Activity Feed Tab -->
           <div id="activity-tab" class="tab-content">
               <div class="card">
                   <h3>📈 Recent Activity</h3>
                   <div class="activity-feed">
   """
   
   for activity in dashboard_data['recent_activity']:
       if activity['activity_type'] == 'conversation':
           icon = "💬"
           icon_class = "activity-conversation"
           description = f"New conversation with {activity['lead_name']} (Score: {activity.get('interest_score', 'N/A')})"
       elif activity['activity_type'] == 'member_joined':
           icon = "👤"
           icon_class = "activity-member"
           description = f"{activity['lead_name']} joined the team"
       else:
           icon = "📋"
           icon_class = "activity-territory"
           description = activity.get('description', 'System activity')
       
       created_time = datetime.fromisoformat(activity['created_at']).strftime('%H:%M')
       created_date = datetime.fromisoformat(activity['created_at']).strftime('%b %d')
       
       html += f"""
                       <div class="activity-item">
                           <div class="activity-icon {icon_class}">{icon}</div>
                           <div style="flex: 1;">
                               <div style="font-weight: bold;">{description}</div>
                               <div style="font-size: 0.9em; color: #666;">by {activity['agent_name']} • {created_date} at {created_time}</div>
                           </div>
                       </div>
       """
   
   html += f"""
                   </div>
               </div>
           </div>
       </div>
       
       <!-- Modals -->
       <div id="inviteMemberModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000;">
           <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; padding: 30px; border-radius: 15px; max-width: 500px; width: 90%;">
               <h3>➕ Invite Team Member</h3>
               
               <form id="inviteMemberForm">
                   <div style="margin-bottom: 15px;">
                       <label style="display: block; margin-bottom: 5px; font-weight: bold;">Email Address</label>
                       <input type="email" name="email" required style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box;">
                   </div>
                   
                   <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                       <div>
                           <label style="display: block; margin-bottom: 5px; font-weight: bold;">First Name</label>
                           <input type="text" name="first_name" required style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box;">
                       </div>
                       <div>
                           <label style="display: block; margin-bottom: 5px; font-weight: bold;">Last Name</label>
                           <input type="text" name="last_name" required style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box;">
                       </div>
                   </div>
                   
                   <div style="margin-bottom: 15px;">
                       <label style="display: block; margin-bottom: 5px; font-weight: bold;">Role</label>
                       <select name="role" required style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                           <option value="agent">Agent - Can manage own AI and conversations</option>
                           <option value="manager">Manager - Can view team analytics</option>
                           <option value="admin">Admin - Can manage team members</option>
                       </select>
                   </div>
                   
                   <div style="margin-bottom: 15px;">
                       <label style="display: block; margin-bottom: 5px; font-weight: bold;">AI Agent Name</label>
                       <input type="text" name="ai_agent_name" required placeholder="e.g. Sarah, Alex, Jordan" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box;">
                   </div>
                   
                   <div style="margin-bottom: 15px;">
                       <label style="display: block; margin-bottom: 5px; font-weight: bold;">Department (Optional)</label>
                       <input type="text" name="department" placeholder="e.g. Sales, Marketing" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box;">
                   </div>
                   
                   <div style="margin-bottom: 15px;">
                       <label style="display: block; margin-bottom: 5px; font-weight: bold;">Monthly Email Quota</label>
                       <select name="email_quota" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                           <option value="500">500 emails/month</option>
                           <option value="1000" selected>1,000 emails/month</option>
                           <option value="2500">2,500 emails/month</option>
                           <option value="5000">5,000 emails/month</option>
                       </select>
                   </div>
                   
                   <div style="text-align: right; margin-top: 20px;">
                       <button type="button" onclick="hideInviteMember()" class="btn btn-secondary" style="margin-right: 10px;">Cancel</button>
                       <button type="submit" class="btn">📤 Send Invitation</button>
                   </div>
               </form>
           </div>
       </div>
       
       <script>
           // Tab switching
           function showTab(tabName) {{
               // Hide all tabs
               document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
               document.querySelectorAll('.nav-tab').forEach(tab => tab.classList.remove('active'));
               
               // Show selected tab
               document.getElementById(tabName + '-tab').classList.add('active');
               event.target.classList.add('active');
           }}
           
           // Team member management
           function showInviteMember() {{
               document.getElementById('inviteMemberModal').style.display = 'block';
           }}
           
           function hideInviteMember() {{
               document.getElementById('inviteMemberModal').style.display = 'none';
           }}
           
           // Form submission
           document.getElementById('inviteMemberForm').addEventListener('submit', async (e) => {{
               e.preventDefault();
               
               const formData = new FormData(e.target);
               const memberData = {{
                   email: formData.get('email'),
                   first_name: formData.get('first_name'),
                   last_name: formData.get('last_name'),
                   role: formData.get('role'),
                   ai_agent_name: formData.get('ai_agent_name'),
                   department: formData.get('department'),
                   email_quota_monthly: parseInt(formData.get('email_quota'))
               }};
               
               try {{
                   const response = await fetch('/corporate/{corporate_id}/invite', {{
                       method: 'POST',
                       headers: {{ 
                           'Content-Type': 'application/json',
                           'Authorization': 'Bearer ' + localStorage.getItem('api_key') || '{customer["api_key"]}'
                       }},
                       body: JSON.stringify(memberData)
                   }});
                   
                   if (response.ok) {{
                       alert('✅ Invitation sent successfully!');
                       hideInviteMember();
                       location.reload();
                   }} else {{
                       const error = await response.json();
                       alert('❌ Error: ' + error.detail);
                   }}
               }} catch (error) {{
                   alert('❌ Error sending invitation');
               }}
           }});
           
           // Member management functions
           function editMember(memberId) {{
               // Implementation for editing member
               window.location.href = `/corporate/{corporate_id}/member/${{memberId}}/edit`;
           }}
           
           function deactivateMember(memberId) {{
               if (confirm('Are you sure you want to deactivate this team member?')) {{
                   fetch(`/corporate/{corporate_id}/member/${{memberId}}/deactivate`, {{
                       method: 'POST',
                       headers: {{ 'Authorization': 'Bearer ' + (localStorage.getItem('api_key') || '{customer["api_key"]}') }}
                   }}).then(() => location.reload());
               }}
           }}
           
           // Settings
           function showSettings() {{
               window.location.href = '/corporate/{corporate_id}/settings';
           }}
           
           // Territory management
           function showCreateTerritory() {{
               window.location.href = '/corporate/{corporate_id}/territories/create';
           }}
           
           function editTerritory(territoryId) {{
               window.location.href = `/corporate/{corporate_id}/territories/${{territoryId}}/edit`;
           }}
           
           // Auto-refresh dashboard every 2 minutes
           setInterval(() => {{
               location.reload();
           }}, 120000);
       </script>
   </body>
   </html>
   """
   
   return HTMLResponse(html)

@router.post("/dashboard/{corporate_id}/invite")
async def invite_team_member(
   corporate_id: str,
   member_data: TeamMember,
   customer: dict = Depends(get_current_customer)
):
   """Invite new team member"""
   
   # Verify admin access
   member = await db_service.execute_query(
       "SELECT * FROM corporate_members WHERE customer_id = ? AND corporate_id = ?",
       (customer['id'], corporate_id), fetch='one'
   )
   
   if not member or member['role'] not in ['super_admin', 'admin']:
       raise HTTPException(status_code=403, detail="Admin access required")
   
   try:
       member_id = await corporate_service.add_team_member(
           corporate_id, 
           member_data, 
           f"{member['first_name']} {member['last_name']}"
       )
       
       return {"member_id": member_id, "message": "Invitation sent successfully"}
       
   except ValueError as e:
       raise HTTPException(status_code=400, detail=str(e))

@router.get("/accept-invite/{invite_token}", response_class=HTMLResponse)
async def accept_invitation_page(invite_token: str):
   """Team invitation acceptance page"""
   
   # Verify invite token
   member = await db_service.execute_query(
       "SELECT * FROM corporate_members WHERE invite_token = ? AND customer_id IS NULL",
       (invite_token,), fetch='one'
   )
   
   if not member:
       return HTMLResponse("""
       <div style="text-align: center; font-family: Arial; margin: 100px;">
           <h1>❌ Invalid Invitation</h1>
           <p>This invitation link is invalid or has already been used.</p>
           <a href="/">← Back to Home</a>
       </div>
       """, status_code=400)
   
   corporate = await corporate_service.get_corporate_account(member['corporate_id'])
   
   return f"""
   <!DOCTYPE html>
   <html>
   <head>
       <title>🤝 Join {corporate['company_name']} - AI Lead Robot</title>
       <style>
           body {{ font-family: Arial; background: linear-gradient(135deg, {corporate['primary_color']}, {corporate['secondary_color']}); margin: 0; padding: 0; min-height: 100vh; display: flex; justify-content: center; align-items: center; }}
           .container {{ background: white; padding: 40px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); max-width: 500px; width: 90%; }}
           h1 {{ text-align: center; color: {corporate['primary_color']}; }}
           .company-info {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
           .form-group {{ margin-bottom: 20px; }}
           label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
           input {{ width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }}
           .btn {{ background: {corporate['primary_color']}; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; width: 100%; font-size: 16px; }}
           .btn:hover {{ opacity: 0.9; }}
           .message {{ padding: 15px; border-radius: 8px; margin: 20px 0; }}
           .success {{ background: #d4edda; color: #155724; }}
           .error {{ background: #f8d7da; color: #721c24; }}
       </style>
   </head>
   <body>
       <div class="container">
           <h1>🤝 Join {corporate['company_name']}</h1>
           
           <div class="company-info">
               <h3>👤 Your Role Details</h3>
               <p><strong>Name:</strong> {member['first_name']} {member['last_name']}</p>
               <p><strong>Role:</strong> {member['role'].replace('_', ' ').title()}</p>
               <p><strong>AI Agent:</strong> {member['ai_agent_name']}</p>
               <p><strong>Email Quota:</strong> {member['email_quota_monthly']:,}/month</p>
               {f"<p><strong>Department:</strong> {member['department']}</p>" if member.get('department') else ""}
           </div>
           
           <form id="acceptForm">
               <div class="form-group">
                   <label>Create Password</label>
                   <input type="password" name="password" required minlength="8" placeholder="At least 8 characters">
               </div>
               
               <div class="form-group">
                   <label>Confirm Password</label>
                   <input type="password" name="confirm_password" required placeholder="Enter password again">
               </div>
               
               <button type="submit" class="btn">🚀 Join Team</button>
           </form>
           
           <div id="message"></div>
       </div>
       
       <script>
           document.getElementById('acceptForm').addEventListener('submit', async (e) => {{
               e.preventDefault();
               
               const formData = new FormData(e.target);
               const password = formData.get('password');
               const confirmPassword = formData.get('confirm_password');
               
               if (password !== confirmPassword) {{
                   document.getElementById('message').innerHTML = '<div class="message error">❌ Passwords do not match.</div>';
                   return;
               }}
               
               try {{
                   const response = await fetch('/corporate/accept-invite', {{
                       method: 'POST',
                       headers: {{ 'Content-Type': 'application/json' }},
                       body: JSON.stringify({{ 
                           invite_token: '{invite_token}',
                           password: password 
                       }})
                   }});
                   
                   const result = await response.json();
                   
                   if (response.ok) {{
                       document.getElementById('message').innerHTML = '<div class="message success">✅ Welcome to the team! Redirecting to your dashboard...</div>';
                       
                       // Store API key and redirect
                       localStorage.setItem('api_key', result.api_key);
                       setTimeout(() => {{
                           window.location.href = `/corporate/dashboard/${{result.corporate_id}}`;
                       }}, 2000);
                   }} else {{
                       document.getElementById('message').innerHTML = '<div class="message error">❌ ' + result.detail + '</div>';
                   }}
               }} catch (error) {{
                   document.getElementById('message').innerHTML = '<div class="message error">❌ Error joining team. Please try again.</div>';
               }}
           }});
       </script>
   </body>
   </html>
   """

@router.post("/accept-invite")
async def accept_invitation(request: Request):
   """Process team invitation acceptance"""
   
   try:
       body = await request.json()
       invite_token = body.get('invite_token')
       password = body.get('password')
       
       if not invite_token or not password:
           raise HTTPException(status_code=400, detail="Invite token and password required")
       
       result = await corporate_service.accept_team_invitation(invite_token, password)
       
       return {
           "success": True,
           "customer_id": result["customer_id"],
           "api_key": result["api_key"],
           "member_id": result["member_id"],
           "corporate_id": result["corporate_id"],
           "message": "Successfully joined the team!"
       }
       
   except ValueError as e:
       raise HTTPException(status_code=400, detail=str(e))
   except Exception as e:
       raise HTTPException(status_code=500, detail=f"Error processing invitation: {str(e)}")

@router.get("/settings/{corporate_id}", response_class=HTMLResponse)
async def corporate_settings(
   corporate_id: str,
   customer: dict = Depends(get_current_customer)
):
   """Corporate account settings page"""
   
   # Verify super admin access
   member = await db_service.execute_query(
       "SELECT * FROM corporate_members WHERE customer_id = ? AND corporate_id = ?",
       (customer['id'], corporate_id), fetch='one'
   )
   
   if not member or member['role'] != 'super_admin':
       raise HTTPException(status_code=403, detail="Super admin access required")
   
   corporate = await corporate_service.get_corporate_account(corporate_id)
   
   return f"""
   <!DOCTYPE html>
   <html>
   <head>
       <title>⚙️ Corporate Settings - {corporate['company_name']}</title>
       <style>
           body {{ font-family: Arial; margin: 0; background: #f5f7fa; }}
           .header {{ background: linear-gradient(135deg, {corporate['primary_color']}, {corporate['secondary_color']}); color: white; padding: 30px; }}
           .container {{ max-width: 1000px; margin: 0 auto; padding: 20px; }}
           .settings-grid {{ display: grid; gap: 30px; margin: 30px 0; }}
           .card {{ background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
           .form-group {{ margin-bottom: 20px; }}
           label {{ display: block; margin-bottom: 5px; font-weight: bold; color: #555; }}
           input, select, textarea {{ width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }}
           .btn {{ background: {corporate['primary_color']}; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; }}
           .btn:hover {{ opacity: 0.9; }}
           .btn-danger {{ background: #dc3545; }}
           .color-picker {{ display: flex; align-items: center; gap: 10px; }}
           .color-preview {{ width: 40px; height: 40px; border-radius: 8px; border: 2px solid #ddd; }}
           .feature-toggle {{ display: flex; justify-content: space-between; align-items: center; padding: 15px; border: 1px solid #ddd; border-radius: 8px; margin: 10px 0; }}
           .toggle-switch {{ position: relative; width: 60px; height: 30px; background: #ccc; border-radius: 15px; cursor: pointer; }}
           .toggle-switch.active {{ background: {corporate['primary_color']}; }}
           .toggle-slider {{ position: absolute; top: 3px; left: 3px; width: 24px; height: 24px; background: white; border-radius: 50%; transition: 0.3s; }}
           .toggle-switch.active .toggle-slider {{ transform: translateX(30px); }}
           .billing-info {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
           .usage-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
           .usage-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
           .usage-number {{ font-size: 2em; font-weight: bold; color: {corporate['primary_color']}; }}
       </style>
   </head>
   <body>
       <div class="header">
           <div class="container">
               <h1>⚙️ Corporate Settings</h1>
               <p>Manage your {corporate['company_name']} account</p>
               <a href="/corporate/dashboard/{corporate_id}" style="color: white; text-decoration: none;">← Back to Dashboard</a>
           </div>
       </div>
       
       <div class="container">
           <div class="settings-grid">
               <!-- Company Information -->
               <div class="card">
                   <h3>🏢 Company Information</h3>
                   
                   <form id="companyInfoForm">
                       <div class="form-group">
                           <label>Company Name</label>
                           <input type="text" name="company_name" value="{corporate['company_name']}" required>
                       </div>
                       
                       <div class="form-group">
                           <label>Billing Contact Email</label>
                           <input type="email" name="billing_email" value="{corporate['billing_contact_email']}" required>
                       </div>
                       
                       <div class="form-group">
                           <label>Company Logo URL (Optional)</label>
                           <input type="url" name="logo_url" value="{corporate.get('company_logo_url', '')}" placeholder="https://example.com/logo.png">
                       </div>
                       
                       <button type="submit" class="btn">💾 Update Company Info</button>
                   </form>
               </div>
               
               <!-- Branding -->
               <div class="card">
                   <h3>🎨 Branding & Appearance</h3>
                   
                   <form id="brandingForm">
                       <div class="form-group">
                           <label>Primary Color</label>
                           <div class="color-picker">
                               <input type="color" name="primary_color" value="{corporate['primary_color']}" onchange="updateColorPreview('primary', this.value)">
                               <div class="color-preview" id="primaryPreview" style="background: {corporate['primary_color']};"></div>
                               <input type="text" value="{corporate['primary_color']}" readonly style="width: 100px;">
                           </div>
                       </div>
                       
                       <div class="form-group">
                           <label>Secondary Color</label>
                           <div class="color-picker">
                               <input type="color" name="secondary_color" value="{corporate['secondary_color']}" onchange="updateColorPreview('secondary', this.value)">
                               <div class="color-preview" id="secondaryPreview" style="background: {corporate['secondary_color']};"></div>
                               <input type="text" value="{corporate['secondary_color']}" readonly style="width: 100px;">
                           </div>
                       </div>
                       
                       <button type="submit" class="btn">🎨 Update Branding</button>
                   </form>
               </div>
               
               <!-- Features & Permissions -->
               <div class="card">
                   <h3>⚡ Features & Permissions</h3>
                   
                   <div class="feature-toggle">
                       <div>
                           <strong>Custom Branding</strong>
                           <div style="color: #666; font-size: 0.9em;">Allow custom colors and logos</div>
                       </div>
                       <div class="toggle-switch {'active' if corporate['custom_branding'] else ''}" onclick="toggleFeature('custom_branding', this)">
                           <div class="toggle-slider"></div>
                       </div>
                   </div>
                   
                   <div class="feature-toggle">
                       <div>
                           <strong>Advanced Analytics</strong>
                           <div style="color: #666; font-size: 0.9em;">Detailed team performance metrics</div>
                       </div>
                       <div class="toggle-switch {'active' if corporate['advanced_analytics'] else ''}" onclick="toggleFeature('advanced_analytics', this)">
                           <div class="toggle-slider"></div>
                       </div>
                   </div>
                   
                   <div class="feature-toggle">
                       <div>
                           <strong>API Access</strong>
                           <div style="color: #666; font-size: 0.9em;">Programmatic access to platform</div>
                       </div>
                       <div class="toggle-switch {'active' if corporate['api_access'] else ''}" onclick="toggleFeature('api_access', this)">
                           <div class="toggle-slider"></div>
                       </div>
                   </div>
                   
                   <div class="feature-toggle">
                       <div>
                           <strong>White Labeling</strong>
                           <div style="color: #666; font-size: 0.9em;">Remove AI Lead Robot branding</div>
                       </div>
                       <div class="toggle-switch {'active' if corporate['white_labeling'] else ''}" onclick="toggleFeature('white_labeling', this)">
                           <div class="toggle-slider"></div>
                       </div>
                   </div>
                   
                   <div class="feature-toggle">
                       <div>
                           <strong>Single Sign-On (SSO)</strong>
                           <div style="color: #666; font-size: 0.9em;">Enterprise SSO integration</div>
                       </div>
                       <div class="toggle-switch {'active' if corporate['sso_enabled'] else ''}" onclick="toggleFeature('sso_enabled', this)">
                           <div class="toggle-slider"></div>
                       </div>
                   </div>
               </div>
               
               <!-- Account Usage -->
               <div class="card">
                   <h3>📊 Account Usage</h3>
                   
                   <div class="usage-stats">
                       <div class="usage-card">
                           <div class="usage-number">{await corporate_service.get_member_count(corporate_id)}</div>
                           <div>Team Members</div>
                           <div style="font-size: 0.8em; color: #666;">of {corporate['max_users']} max</div>
                       </div>
                       
                       <div class="usage-card">
                           <div class="usage-number">{corporate['account_type'].title()}</div>
                           <div>Account Type</div>
                           <div style="font-size: 0.8em; color: #666;">Plan level</div>
                       </div>
                       
                       <div class="usage-card">
                           <div class="usage-number">{"Active" if corporate['status'] == 'active' else corporate['status'].title()}</div>
                           <div>Status</div>
                           <div style="font-size: 0.8em; color: #666;">Account status</div>
                       </div>
                   </div>
                   
                   <div class="billing-info">
                       <h4>💳 Billing Information</h4>
                       <p><strong>Account Type:</strong> {corporate['account_type'].title()}</p>
                       <p><strong>Max Users:</strong> {corporate['max_users']}</p>
                       {f"<p><strong>Trial Ends:</strong> {corporate['trial_ends_at'][:10] if corporate.get('trial_ends_at') else 'N/A'}</p>" if corporate.get('trial_ends_at') else ""}
                       
                       <button onclick="manageBilling()" class="btn">💳 Manage Billing</button>
                       <button onclick="upgradeAccount()" class="btn" style="margin-left: 10px;">⬆️ Upgrade Account</button>
                   </div>
               </div>
               
               <!-- Team Management -->
               <div class="card">
                   <h3>👥 Team Management</h3>
                   
                   <div class="form-group">
                       <label>Default Email Quota for New Members</label>
                       <select id="defaultQuota">
                           <option value="500">500 emails/month</option>
                           <option value="1000" selected>1,000 emails/month</option>
                           <option value="2500">2,500 emails/month</option>
                           <option value="5000">5,000 emails/month</option>
                       </select>
                   </div>
                   
                   <div class="form-group">
                       <label>Default AI Agent Personality</label>
                       <select id="defaultPersonality">
                           <option value="professional">Professional & Formal</option>
                           <option value="friendly" selected>Friendly & Approachable</option>
                           <option value="consultative">Consultative & Advisory</option>
                           <option value="direct">Direct & Concise</option>
                       </select>
                   </div>
                   
                   <button onclick="saveTeamDefaults()" class="btn">💾 Save Team Defaults</button>
               </div>
               
               <!-- Danger Zone -->
               <div class="card" style="border-left: 4px solid #dc3545;">
                   <h3 style="color: #dc3545;">⚠️ Danger Zone</h3>
                   
                   <div style="background: #f8d7da; padding: 15px; border-radius: 8px; margin: 15px 0;">
                       <strong>Export Data</strong>
                       <p style="margin: 5px 0;">Download all your corporate data before making major changes.</p>
                       <button onclick="exportData()" class="btn btn-secondary">📥 Export All Data</button>
                   </div>
                   
                   <div style="background: #f8d7da; padding: 15px; border-radius: 8px; margin: 15px 0;">
                       <strong>Cancel Subscription</strong>
                       <p style="margin: 5px 0;">This will deactivate your account and all team members.</p>
                       <button onclick="cancelSubscription()" class="btn btn-danger">❌ Cancel Subscription</button>
                   </div>
               </div>
           </div>
       </div>
       
       <script>
           // Color preview updates
           function updateColorPreview(type, color) {{
               document.getElementById(type + 'Preview').style.background = color;
               event.target.nextElementSibling.nextElementSibling.value = color;
           }}
           
           // Feature toggles
           function toggleFeature(feature, element) {{
               element.classList.toggle('active');
               const enabled = element.classList.contains('active');
               
               // Update feature in backend
               fetch('/corporate/{corporate_id}/settings/features', {{
                   method: 'POST',
                   headers: {{ 
                       'Content-Type': 'application/json',
                       'Authorization': 'Bearer ' + (localStorage.getItem('api_key') || '{customer["api_key"]}')
                   }},
                   body: JSON.stringify({{ feature: feature, enabled: enabled }})
               }});
           }}
           
           // Form submissions
           document.getElementById('companyInfoForm').addEventListener('submit', async (e) => {{
               e.preventDefault();
               
               const formData = new FormData(e.target);
               const data = {{
                   company_name: formData.get('company_name'),
                   billing_contact_email: formData.get('billing_email'),
                   company_logo_url: formData.get('logo_url')
               }};
               
               try {{
                   const response = await fetch('/corporate/{corporate_id}/settings/company', {{
                       method: 'POST',
                       headers: {{ 
                           'Content-Type': 'application/json',
                           'Authorization': 'Bearer ' + (localStorage.getItem('api_key') || '{customer["api_key"]}')
                       }},
                       body: JSON.stringify(data)
                   }});
                   
                   if (response.ok) {{
                       alert('✅ Company information updated!');
                   }} else {{
                       alert('❌ Error updating company information');
                   }}
               }} catch (error) {{
                   alert('❌ Error updating company information');
               }}
           }});
           
           document.getElementById('brandingForm').addEventListener('submit', async (e) => {{
               e.preventDefault();
               
               const formData = new FormData(e.target);
               const data = {{
                   primary_color: formData.get('primary_color'),
                   secondary_color: formData.get('secondary_color')
               }};
               
               try {{
                   const response = await fetch('/corporate/{corporate_id}/settings/branding', {{
                       method: 'POST',
                       headers: {{ 
                           'Content-Type': 'application/json',
                           'Authorization': 'Bearer ' + (localStorage.getItem('api_key') || '{customer["api_key"]}')
                       }},
                       body: JSON.stringify(data)
                   }});
                   
                   if (response.ok) {{
                       alert('✅ Branding updated! Refresh the page to see changes.');
                   }} else {{
                       alert('❌ Error updating branding');
                   }}
               }} catch (error) {{
                   alert('❌ Error updating branding');
               }}
           }});
           
           // Team defaults
           function saveTeamDefaults() {{
               const quota = document.getElementById('defaultQuota').value;
               const personality = document.getElementById('defaultPersonality').value;
               
               fetch('/corporate/{corporate_id}/settings/team-defaults', {{
                   method: 'POST',
                   headers: {{ 
                       'Content-Type': 'application/json',
                       'Authorization': 'Bearer ' + (localStorage.getItem('api_key') || '{customer["api_key"]}')
                   }},
                   body: JSON.stringify({{ 
                       default_quota: parseInt(quota),
                       default_personality: personality
                   }})
               }}).then(() => alert('✅ Team defaults saved!'));
           }}
           
           // Danger zone functions
           function exportData() {{
               window.open('/corporate/{corporate_id}/export', '_blank');
           }}
           
           function manageBilling() {{
               window.open('https://billing.stripe.com/p/login/...', '_blank'); // Replace with your Stripe billing portal
           }}
           
           function upgradeAccount() {{
               window.location.href = '/corporate/{corporate_id}/upgrade';
           }}
           
           function cancelSubscription() {{
               if (confirm('⚠️ Are you sure you want to cancel your subscription? This will deactivate your entire team.')) {{
                   if (confirm('This action cannot be undone. All team members will lose access immediately.')) {{
                       fetch('/corporate/{corporate_id}/cancel', {{
                           method: 'POST',
                           headers: {{ 'Authorization': 'Bearer ' + (localStorage.getItem('api_key') || '{customer["api_key"]}') }}
                       }}).then(() => {{
                           alert('Subscription cancelled. Redirecting...');
                           window.location.href = '/';
                       }});
                   }}
               }}
           }}
       </script>
   </body>
   </html>
   """

# Add the remaining API endpoints for settings updates
@router.post("/settings/{corporate_id}/company")
async def update_company_info(
   corporate_id: str,
   request: Request,
   customer: dict = Depends(get_current_customer)
):
   """Update company information"""
   
   # Verify super admin access
   member = await db_service.execute_query(
       "SELECT * FROM corporate_members WHERE customer_id = ? AND corporate_id = ?",
       (customer['id'], corporate_id), fetch='one'
   )
   
   if not member or member['role'] != 'super_admin':
       raise HTTPException(status_code=403, detail="Super admin access required")
   
   body = await request.json()
   
   await db_service.execute_query('''
       UPDATE corporate_accounts 
       SET company_name = ?, billing_contact_email = ?, company_logo_url = ?, updated_at = ?
       WHERE id = ?
   ''', (
       body['company_name'], body['billing_contact_email'], 
       body.get('company_logo_url'), datetime.now(), corporate_id
   ))
   
   return {"message": "Company information updated successfully"}

@router.post("/settings/{corporate_id}/branding")
async def update_branding(
   corporate_id: str,
   request: Request,
   customer: dict = Depends(get_current_customer)
):
   """Update branding colors"""
   
   # Verify admin access
   member = await db_service.execute_query(
       "SELECT * FROM corporate_members WHERE customer_id = ? AND corporate_id = ?",
       (customer['id'], corporate_id), fetch='one'
   )
   
   if not member or member['role'] not in ['super_admin', 'admin']:
       raise HTTPException(status_code=403, detail="Admin access required")
   
   body = await request.json()
   
   await db_service.execute_query('''
       UPDATE corporate_accounts 
       SET primary_color = ?, secondary_color = ?, updated_at = ?
       WHERE id = ?
   ''', (body['primary_color'], body['secondary_color'], datetime.now(), corporate_id))
   
   return {"message": "Branding updated successfully"}

@router.post("/settings/{corporate_id}/features")
async def update_features(
   corporate_id: str,
   request: Request,
   customer: dict = Depends(get_current_customer)
):
   """Update feature toggles"""
   
   # Verify super admin access
   member = await db_service.execute_query(
       "SELECT * FROM corporate_members WHERE customer_id = ? AND corporate_id = ?",
       (customer['id'], corporate_id), fetch='one'
   )
   
   if not member or member['role'] != 'super_admin':
       raise HTTPException(status_code=403, detail="Super admin access required")
   
   body = await request.json()
   feature = body['feature']
   enabled = body['enabled']
   
   # Validate feature name
   valid_features = ['custom_branding', 'advanced_analytics', 'api_access', 'white_labeling', 'sso_enabled']
   if feature not in valid_features:
       raise HTTPException(status_code=400, detail="Invalid feature")
   
   await db_service.execute_query(f'''
       UPDATE corporate_accounts 
       SET {feature} = ?, updated_at = ?
       WHERE id = ?
   ''', (enabled, datetime.now(), corporate_id))
   
   return {"message": f"Feature {feature} {'enabled' if enabled else 'disabled'}"}

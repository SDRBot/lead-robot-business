# routers/conversations.py
@router.get("/conversations", response_class=HTMLResponse)
async def conversations_dashboard(customer: dict = Depends(get_current_customer)):
    """Real-time conversation tracking dashboard"""
    
    conversations = await db_service.execute_query(
        "SELECT * FROM conversations WHERE customer_id = ? ORDER BY last_activity DESC",
        (customer['id'],), fetch='all'
    )
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>💬 Conversations - AI Sales Agent</title>
        <style>
            .conversation-list {{ display: grid; gap: 20px; }}
            .conversation-card {{ background: white; padding: 20px; border-radius: 10px; border-left: 4px solid #667eea; }}
            .high-score {{ border-left-color: #28a745; }}
            .medium-score {{ border-left-color: #ffc107; }}
            .low-score {{ border-left-color: #dc3545; }}
            .conversation-actions {{ margin-top: 15px; }}
            .ai-response {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>💬 Active Conversations</h1>
            
            <div class="stats-bar">
                <div class="stat">
                    <span class="number">{len([c for c in conversations if c['interest_score'] >= 70])}</span>
                    <span class="label">Hot Leads</span>
                </div>
                <div class="stat">
                    <span class="number">{len([c for c in conversations if c['status'] == 'awaiting_response'])}</span>
                    <span class="label">Awaiting Response</span>
                </div>
                <div class="stat">
                    <span class="number">{len([c for c in conversations if c['last_activity'] > datetime.now() - timedelta(hours=24)])}</span>
                    <span class="label">Active Today</span>
                </div>
            </div>
            
            <div class="conversation-list">
    """
    
    for conv in conversations:
        score_class = 'high-score' if conv['interest_score'] >= 70 else 'medium-score' if conv['interest_score'] >= 40 else 'low-score'
        
        html += f"""
                <div class="conversation-card {score_class}">
                    <div class="conversation-header">
                        <h3>{conv['lead_name']} - {conv['company']}</h3>
                        <div class="score-badge">Interest Score: {conv['interest_score']}/100</div>
                    </div>
                    
                    <div class="last-message">
                        <strong>Last message:</strong> {conv['last_message'][:100]}...
                    </div>
                    
                    <div class="ai-response">
                        <h4>🤖 AI Suggested Response:</h4>
                        <p>{conv['suggested_response']}</p>
                        
                        <div class="conversation-actions">
                            <button onclick="sendAIResponse('{conv['id']}')" class="btn btn-primary">✅ Send AI Response</button>
                            <button onclick="editResponse('{conv['id']}')" class="btn btn-secondary">✏️ Edit Response</button>
                            <button onclick="viewFullConversation('{conv['id']}')" class="btn">👁️ View Full Thread</button>
                        </div>
                    </div>
                </div>
        """
    
    html += """
            </div>
        </div>
        
        <script>
            // Real-time updates
            setInterval(async () => {
                const response = await fetch('/api/conversations/updates');
                const updates = await response.json();
                updateConversationCards(updates);
            }, 30000); // Check every 30 seconds
            
            async function sendAIResponse(conversationId) {
                // Send the AI-generated response
                const response = await fetch(`/api/conversations/${conversationId}/send-response`, {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + getApiKey() }
                });
                
                if (response.ok) {
                    alert('✅ Response sent!');
                    location.reload();
                }
            }
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(html)

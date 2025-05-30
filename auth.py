from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from services.auth_service import auth_service, get_current_customer
from services.email_service import email_service
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["authentication"])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class SetPasswordRequest(BaseModel):
    api_key: str
    password: str

@router.post("/login")
async def login(request: LoginRequest):
    """Login with email and password"""
    
    customer = await auth_service.authenticate_customer(
        request.email, 
        request.password
    )
    
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    return {"api_key": customer["api_key"]}

@router.post("/set-password")
async def set_password(request: SetPasswordRequest):
    """Set password for customer"""
    
    # Verify API key first
    customer = await auth_service.verify_api_key(request.api_key)
    if not customer:
        raise HTTPException(status_code=404, detail="Invalid API key")
    
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    # Hash and update password
    password_hash = auth_service.hash_password(request.password)
    
    from database import db_service
    await db_service.execute_query(
        "UPDATE customers SET password_hash = ?, updated_at = ? WHERE api_key = ?",
        (password_hash, datetime.now(), request.api_key)
    )
    
    return {"message": "Password set successfully"}

@router.get("/login", response_class=HTMLResponse)
async def login_page():
    """Login page"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🔐 Login - AI Lead Robot</title>
        <style>
            body { font-family: Arial; background: #f5f7fa; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
            .container { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); max-width: 400px; }
            h1 { text-align: center; color: #333; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
            .btn { background: #667eea; color: white; padding: 12px; border: none; border-radius: 5px; cursor: pointer; width: 100%; }
            .btn:hover { background: #5a6fd8; }
            .message { padding: 15px; border-radius: 8px; margin: 20px 0; }
            .success { background: #d4edda; color: #155724; }
            .error { background: #f8d7da; color: #721c24; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 AI Lead Robot</h1>
            <h2 style="text-align: center; color: #666;">Login to Your Account</h2>
            
            <form id="loginForm">
                <div class="form-group">
                    <label>Email Address</label>
                    <input type="email" name="email" required placeholder="your@email.com">
                </div>
                
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" required placeholder="Your password">
                </div>
                
                <button type="submit" class="btn">🔓 Login to Dashboard</button>
            </form>
            
            <div id="message"></div>
            
            <div style="text-align: center; margin-top: 20px;">
                <a href="/" style="color: #667eea;">← Back to Home</a>
            </div>
        </div>
        
        <script>
            document.getElementById('loginForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData(e.target);
                const data = {
                    email: formData.get('email'),
                    password: formData.get('password')
                };
                
                try {
                    const response = await fetch('/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        document.getElementById('message').innerHTML = '<div class="success">✅ Login successful! Redirecting...</div>';
                        setTimeout(() => {
                            window.location.href = '/dashboard?api_key=' + result.api_key;
                        }, 1000);
                    } else {
                        document.getElementById('message').innerHTML = '<div class="error">❌ ' + result.detail + '</div>';
                    }
                } catch (error) {
                    document.getElementById('message').innerHTML = '<div class="error">❌ Login failed. Please try again.</div>';
                }
            });
        </script>
    </body>
    </html>
    """

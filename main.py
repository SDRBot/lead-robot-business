# main.py - Main entry point for Render
from app import app
from website import app as website_app

# Combine both apps
app.mount("/business", website_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

"""
Flask-based test to check if the issue is with FastAPI/Mangum
"""
from flask import Flask

# Create Flask app (WSGI-native)
app = Flask(__name__)

@app.route('/')
def hello():
    return {
        "message": "Flask test working on Vercel!",
        "status": "success",
        "framework": "Flask"
    }

@app.route('/health')
def health():
    return {"status": "healthy", "framework": "Flask"}

# Flask is WSGI-native, no need for Mangum
# Vercel should detect 'app' automatically

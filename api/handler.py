import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the FastAPI app directly
from index import app

# Export for Vercel - no wrapper needed
# Vercel will handle the ASGI/WSGI conversion automatically
def handler(request):
    """Simple request handler for Vercel"""
    return app

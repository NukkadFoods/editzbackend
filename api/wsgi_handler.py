"""
WSGI-compatible handler for Vercel deployment
Converts FastAPI (ASGI) to WSGI for Vercel compatibility
"""
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import our FastAPI app
from index import fastapi_app
from mangum import Mangum

# Create WSGI-compatible handler using Mangum
# This is what Vercel expects - a WSGI application object
application = Mangum(fastapi_app)

# Alternative names that Vercel might look for
app = application  # Vercel often looks for 'app'
handler = application  # Some configurations look for 'handler'

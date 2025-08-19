"""
Simple WSGI handler for Vercel compatibility
This bypasses the ASGI detection issue
"""
import json
import base64
from urllib.parse import parse_qs, urlparse
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import our FastAPI app
from index import app
from mangum import Mangum

# Create Mangum handler
mangum_handler = Mangum(app)

def handler(event, context):
    """
    Simple handler function that Vercel expects
    """
    try:
        return mangum_handler(event, context)
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Handler error: {str(e)}"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

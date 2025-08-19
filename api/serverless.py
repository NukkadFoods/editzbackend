"""
Serverless entry point for Vercel deployment
This file creates a minimal handler that wraps our FastAPI application
"""

def create_app():
    """Factory function to create the FastAPI app"""
    from .index import app
    return app

def create_handler():
    """Factory function to create the Mangum handler"""
    from mangum import Mangum
    app = create_app()
    return Mangum(app)

# Create the handler using factory pattern to avoid variable exposure
handler = create_handler()

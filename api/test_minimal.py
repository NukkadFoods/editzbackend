"""
Minimal test handler to debug Vercel deployment
"""
from mangum import Mangum
from fastapi import FastAPI

# Create a minimal FastAPI app
test_app = FastAPI()

@test_app.get("/")
def read_root():
    return {"message": "Hello from Vercel!", "status": "working"}

@test_app.get("/health")
def health_check():
    return {"status": "healthy", "service": "PDF Editor Backend"}

# Create WSGI handler
app = Mangum(test_app)

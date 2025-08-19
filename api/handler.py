from mangum import Mangum
from .index import app

# Simple wrapper for Vercel
handler = Mangum(app)

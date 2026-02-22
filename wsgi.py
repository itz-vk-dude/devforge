"""
WSGI entry point for production deployment.
Usage: gunicorn wsgi:app --workers 4 --bind 0.0.0.0:8000
"""
from dotenv import load_dotenv
load_dotenv()

from app import app
import database as db

db.init_db()

if __name__ == "__main__":
    app.run()

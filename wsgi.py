"""
WSGI entry point for Flask app - compatible with Gunicorn, Railway, Heroku.
Uses the factory pattern from crm/__init__.py
"""
import os
from crm import create_app, db

# Create the Flask application
app = create_app()

# Context for database operations
if __name__ != "__main__":
    # Ensure app context is active for Gunicorn
    with app.app_context():
        db.create_all()

if __name__ == "__main__":
    # Local development only
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

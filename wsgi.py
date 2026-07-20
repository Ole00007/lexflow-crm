"""
WSGI entry point for Flask app - compatible with Gunicorn, Railway, Heroku.
Uses the factory pattern from crm/__init__.py
Handles database initialization and migrations on startup.
"""
import os
import sys
from crm import create_app, db
from flask_migrate import upgrade

# Create the Flask application
app = create_app()

# Initialize database and run migrations on startup (Railway/production)
def init_database():
    """Initialize database with migrations."""
    with app.app_context():
        try:
            # Run migrations
            upgrade()
            print("✓ Database migrations completed successfully")
        except Exception as e:
            print(f"⚠ Migration error: {e}", file=sys.stderr)
            # If migrations fail, try to create tables directly
            try:
                db.create_all()
                print("✓ Tables created directly (fallback)")
            except Exception as e2:
                print(f"✗ Failed to initialize database: {e2}", file=sys.stderr)
                raise

# Run init on startup (not in test mode)
if "pytest" not in sys.modules and "gunicorn" in sys.modules or os.environ.get("RAILWAY_ENVIRONMENT_NAME"):
    init_database()

if __name__ == "__main__":
    # Local development only
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

"""
WSGI entry point for Flask app - compatible with Gunicorn, Railway, Heroku.
Uses the factory pattern from crm/__init__.py
"""
import os
import sys
import logging

# Basic logging to stderr for debugging
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Python {sys.version}")
logger.info(f"DATABASE_URL: {os.environ.get('DATABASE_URL', 'NOT SET')[:50]}")

try:
    from crm import create_app
    app = create_app()
    logger.info("✓ App initialized successfully")
except Exception as e:
    logger.error(f"✗ Failed to create app: {e}", exc_info=True)
    # Re-raise so Gunicorn sees the error in logs
    raise

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

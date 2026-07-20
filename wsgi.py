"""
WSGI entry point for Flask app - compatible with Gunicorn, Railway, Heroku.
Uses the factory pattern from crm/__init__.py
"""
import os
import sys
import logging

# Set up logging early
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

logger.info(f"Starting WSGI initialization...")
logger.info(f"Python: {sys.version}")
logger.info(f"CWD: {os.getcwd()}")
logger.info(f"DATABASE_URL set: {bool(os.environ.get('DATABASE_URL'))}")

try:
    logger.info("Importing Flask app factory...")
    from crm import create_app, db
    from flask import request
    logger.info("✓ crm module imported")
    
    logger.info("Creating Flask app...")
    app = create_app()
    logger.info(f"✓ App created: {app.name}")
    logger.info(f"  Config SQLALCHEMY_DATABASE_URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    
    # Simple startup handler
    @app.before_request
    def log_request():
        logger.debug(f"{request.method} {request.path}")
    
    logger.info("✓ WSGI app ready")
    
except Exception as e:
    logger.error(f"✗ Failed to initialize WSGI: {e}", exc_info=True)
    raise

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask app on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)

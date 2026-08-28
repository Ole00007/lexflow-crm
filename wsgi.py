"""WSGI entry point for Flask app.
Uses the factory pattern from crm/__init__.py
Auto-runs migrations on startup.
"""
import os
import sys
import logging

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Python {sys.version}")

try:
    from crm import create_app, db
    from flask_migrate import upgrade as flask_upgrade
    from alembic.config import Config
    from alembic import command

    app = create_app()

    with app.app_context():
        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "migrations", "alembic.ini"))
        alembic_cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "migrations"))
        try:
            # Stamp to base to clear old migration history
            command.stamp(alembic_cfg, "base")
            # Run all migrations up to head
            command.upgrade(alembic_cfg, "head")
            logger.info("✓ Migrations applied successfully")
        except Exception as me:
            # Fallback: create tables directly matching models
            logger.warning(f"Migration failed, using db.create_all(): {me}")
            db.create_all()
            logger.info("✓ Tables created via db.create_all()")

    logger.info("✓ App initialized successfully")
except Exception as e:
    logger.error(f"✗ Failed to create app: {e}", exc_info=True)
    raise

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
"""WSGI entry point — auto-migrates DB on startup."""
import os, sys, logging
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"Python {sys.version}")

try:
    from crm import create_app
    app = create_app()

    with app.app_context():
        from crm.extensions import db
        # Check if workspace table exists — if not, old schema -> recreate
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if 'workspaces' not in inspector.get_table_names():
            logger.info("Old schema detected — recreating all tables...")
            db.drop_all()
            db.create_all()
            logger.info("✓ Tables recreated with new schema")
        else:
            # Check if workspace_id column exists on cases
            cols = [c['name'] for c in inspector.get_columns('cases')]
            if 'workspace_id' not in cols:
                logger.info("Missing workspace_id — recreating tables...")
                db.drop_all()
                db.create_all()
                logger.info("✓ Tables recreated with new schema")
            else:
                logger.info("✓ Schema is current")

    logger.info("✓ App initialized successfully")
except Exception as e:
    logger.error(f"✗ Failed: {e}", exc_info=True)
    raise

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
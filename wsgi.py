"""WSGI entry point — uses create_app() from crm package."""
import os, sys, logging
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from crm import create_app
    app = create_app()
    logger.info("✓ App initialized")
except Exception as e:
    logger.error(f"✗ Failed: {e}", exc_info=True)
    raise

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
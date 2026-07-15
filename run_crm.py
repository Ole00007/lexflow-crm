# CRM ENTRY POINT - use this file to run the CRM app.
# DO NOT use app.py for CRM work. app.py runs the legacy intake app only.

import os
from crm import create_app

app = create_app()

if __name__ == "__main__":
    # For Railway deployment: listen on $PORT environment variable
    # Default to 5001 for local development
    port = int(os.environ.get("PORT", 5001))
    host = os.environ.get("HOST", "0.0.0.0")
    debug = os.environ.get("FLASK_ENV") == "development"
    
    app.run(host=host, port=port, debug=debug)

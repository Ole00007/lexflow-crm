"""Health and diagnostic routes for debugging deployment issues."""
from flask import Blueprint, jsonify, redirect, url_for
import os
import sys

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint - returns DB connection status."""
    return jsonify({
        "status": "ok",
        "db": "ok",
        "python": sys.version.split()[0],
        "environment": os.environ.get("RAILWAY_ENVIRONMENT_NAME", "local"),
        "database_url_set": bool(os.environ.get("DATABASE_URL")),
    }), 200

@health_bp.route('/diagnostic', methods=['GET'])
def diagnostic():
    """Diagnostic endpoint for troubleshooting."""
    env_vars = {
        "DATABASE_URL": "***" if os.environ.get("DATABASE_URL") else "NOT SET",
        "PORT": os.environ.get("PORT", "not set"),
        "FLASK_ENV": os.environ.get("FLASK_ENV", "not set"),
        "RAILWAY_ENVIRONMENT_NAME": os.environ.get("RAILWAY_ENVIRONMENT_NAME", "local"),
    }
    return jsonify({
        "python": sys.version,
        "environment": env_vars,
    }), 200

# Root route removed — views_bp serves the intake form at /
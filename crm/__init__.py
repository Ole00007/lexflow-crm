from flask import Flask, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from pathlib import Path
from .config import Config
from .extensions import db, migrate, jwt, cors, limiter

def create_app():
    app = Flask(__name__,
                template_folder=str(Path(__file__).resolve().parent.parent / "templates"),
                static_folder=str(Path(__file__).resolve().parent.parent / "static"))
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", ["*"])}})
    limiter.init_app(app)

    # Allow both /api/contacts and /api/contacts/ (no 308 redirects)
    app.url_map.strict_slashes = False

    # API Blueprints
    from .routes.health import health_bp
    from .routes.contacts import contacts_bp
    from .routes.cases import cases_bp
    from .routes.auth import auth_bp
    from .routes.tasks import tasks_bp
    from .routes.deadlines import deadlines_bp
    from .routes.admin import admin_bp
    from .routes.webhooks import webhooks_bp
    from .routes.notes import notes_bp
    from .routes.activity import activity_bp
    from .routes.calendar import calendar_bp
    from .routes.notifications import notifications_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(cases_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(deadlines_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(activity_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(notifications_bp)

    # View Blueprint (serves Jinja2 templates from /dashboard, /kanban, /, etc.)
    from .routes.views import views_bp
    app.register_blueprint(views_bp)

    # Security headers middleware
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https:"
        return response

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad request"}), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(409)
    def conflict(error):
        return jsonify({"error": "Conflict"}), 409

    @app.errorhandler(500)
    def server_error(error):
        return jsonify({"error": "Internal server error"}), 500

    # Schema refresh on first request (detects old Railway DB schema)
    @app.before_request
    def _ensure_schema():
        """Ensure DB schema matches models. Runs once per worker."""
        if not getattr(app, '_schema_checked', False):
            from .extensions import db as _db
            from sqlalchemy import inspect, text
            inspector = inspect(_db.engine)
            tables = inspector.get_table_names()
            if tables:
                cols = [c['name'] for c in inspector.get_columns('cases')]
                if 'workspace_id' not in cols:
                    import logging
                    logging.getLogger(__name__).info("Old schema — recreating tables with CASCADE...")
                    # Use CASCADE to drop dependent objects
                    with _db.engine.connect() as conn:
                        conn.execute(text("DROP SCHEMA public CASCADE"))
                        conn.execute(text("CREATE SCHEMA public"))
                        conn.commit()
                    _db.create_all()
                    logging.getLogger(__name__).info("✓ Tables recreated")
            app._schema_checked = True

    return app
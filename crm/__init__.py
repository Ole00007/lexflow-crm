from flask import Flask, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from pathlib import Path
import os
from .config import Config
from .extensions import db, migrate, jwt, cors, limiter


def _seed_default_users():
    """Seed admin user and workspace for fresh DB (idempotent)."""
    from .models.workspace import Workspace
    from .models.user import User
    # If user exists but workspace FK is stale, update it
    user = User.query.filter_by(email="olesya00007@yahoo.com").first()
    if user:
        # Check if their workspace exists
        ws = Workspace.query.get(user.workspace_id)
        if not ws:
            # Workspace was deleted — create a new one and reassign
            ws = Workspace(slug="lexflow", name="LexFlow Default", description="Default workspace", is_active=True)
            db.session.add(ws)
            db.session.flush()
            user.workspace_id = ws.id
            db.session.commit()
        return
    # Reuse existing workspace (migration may have seeded slug 'lexflow' already)
    ws = Workspace.query.filter_by(slug="lexflow").first()
    if not ws:
        ws = Workspace(slug="lexflow", name="LexFlow Default", description="Default workspace", is_active=True)
        db.session.add(ws)
        db.session.flush()
    user = User(email="olesya00007@yahoo.com", role="superadmin", workspace_id=ws.id)
    user.set_password("Test12345!")
    db.session.add(user)
    db.session.commit()


def _ensure_test_users():
    """Idempotently ensure multi-tenant test users exist (runs on every boot)."""
    from .models.workspace import Workspace
    from .models.user import User
    ws = Workspace.query.filter_by(slug="lexflow").first()
    if not ws:
        ws = Workspace.query.first()
    # Gmail test user (Ole's multi-tenant test login)
    gmail_user = User.query.filter_by(email="olesya00007@gmail.com").first()
    if not gmail_user:
        gmail_user = User(email="olesya00007@gmail.com", role="superadmin", workspace_id=ws.id if ws else None)
        gmail_user.set_password("Test1")
        db.session.add(gmail_user)
    db.session.commit()


def _ensure_workspace_users():
    """Idempotently create/update the full workspace account roster.

    Runs on every boot. Creates missing users; updates a user's password ONLY
    when it still matches a known default (i.e. the customer hasn't changed it
    yet via the change-credentials feature). Never touches a password that the
    user already changed.
    """
    from .models.workspace import Workspace
    from .models.user import User

    # (email, password, role, workspace_slug, known_previous_defaults)
    roster = [
        ("superadmin@lexflow.it", "lexflow0826", "superadmin", "lexflow", ["Test12345!"]),
        ("olesya00007@yahoo.com", "crm0826", "superadmin", "lexflow", ["Test12345!"]),
        ("alegra_007@proton.me", "avibe0826", "admin", "avibeagency", []),
        ("ms.okuneva@internet.ru", "pagliano0826", "admin", "pagliano", []),
        ("olesya00007@google.com", "Romanelli0826", "admin", "romanelli-studio", []),
        ("preview@romanelli.test", "Romanelli0826", "admin", "romanelli-studio", []),
        ("ferro@lexflow.it", "ferro0826", "admin", "tommasoferro", []),
    ]

    for email, password, role, slug, old_defaults in roster:
        ws = Workspace.query.filter_by(slug=slug).first()
        if not ws:
            ws = Workspace.query.first()
        user = User.query.filter_by(email=email).first()
        if user:
            # Only reset password if it's still a known default (not yet changed by the user)
            if old_defaults and user.check_password(old_defaults[0]):
                user.set_password(password)
                user.role = role
                if ws:
                    user.workspace_id = ws.id
        else:
            user = User(email=email, role=role, workspace_id=ws.id if ws else None)
            user.set_password(password)
            db.session.add(user)
    db.session.commit()

    # Romanelli sub-workspaces (2 for test; 3rd later) — children of romanelli-studio
    parent_ws = Workspace.query.filter_by(slug="romanelli-studio").first()
    if parent_ws:
        subs = [
            ("romanelli-cl1", "Romanelli Client 1", "cl1@romanelli.test", "cl10826"),
            ("romanelli-cl2", "Romanelli Client 2", "cl2@romanelli.test", "cl20826"),
        ]
        for slug, name, email, pw in subs:
            sub = Workspace.query.filter_by(slug=slug).first()
            if not sub:
                sub = Workspace(parent_workspace_id=parent_ws.id, slug=slug, name=name,
                                description=f"Sub-workspace under {parent_ws.name}", is_active=True)
                db.session.add(sub)
                db.session.flush()
            sub_user = User.query.filter_by(email=email).first()
            if not sub_user:
                sub_user = User(email=email, role="admin", workspace_id=sub.id)
                sub_user.set_password(pw)
                db.session.add(sub_user)
    db.session.commit()


def _seed_code_prefixes():
    """Idempotently set each workspace's per-tenant case-ID prefix (R, P, A, F, L…).
    Only fills workspaces that don't have a code_prefix yet — never overwrites."""
    from .models.workspace import Workspace
    default_prefixes = {
        "lexflow": "L", "avibeagency": "A", "pagliano": "P",
        "romanelli-studio": "R", "romanelli-audit": "RA", "romanelli-cl1": "R1",
        "romanelli-cl2": "R2", "tommasoferro": "F",
    }
    changed = False
    for ws in Workspace.query.filter_by(is_active=True).all():
        if not ws.code_prefix and ws.slug in default_prefixes:
            ws.code_prefix = default_prefixes[ws.slug]
            changed = True
    if changed:
        db.session.commit()


def _next_case_no(workspace_id, code_prefix=None):
    """Compute the next per-workspace case display number, e.g. R-01, R-02…
    New cases only. Returns e.g. 'R-07'. Falls back to the legacy #id scheme
    if no prefix is set (frontend shows display_id)."""
    from .models.case import Case
    from .models.workspace import Workspace
    if not code_prefix:
        ws = Workspace.query.get(workspace_id)
        code_prefix = ws.code_prefix if ws else None
    if not code_prefix:
        return None
    # count existing numbered cases in this workspace to compute the next seq
    count = Case.query.filter(
        Case.workspace_id == workspace_id,
        Case.is_deleted == False,
        Case.case_no.isnot(None),
    ).count()
    return f"{code_prefix}-{count + 1:02d}"


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

    # Inject current user (and their workspace) into every template
    @app.context_processor
    def inject_current_user():
        from .models.user import User
        user = None
        try:
            uid = get_jwt_identity()
            if uid:
                user = User.query.filter_by(id=int(uid), is_deleted=False).first()
        except Exception:
            user = None

        # Per-workspace public site (the client's own website / landing page)
        site_map = {
            "pagliano": os.environ.get("PAGLIANO_SITE_URL", "https://verdant-crumble-021449.netlify.app"),
            "romanelli-studio": os.environ.get("ROMANELLI_SITE_URL", "https://romanelli-studio.olesya00007.workers.dev"),
            "romanelli-audit": os.environ.get("ROMANELLI_AUDIT_SITE_URL", "https://romanelli-studio.olesya00007.workers.dev"),
            "tommasoferro": os.environ.get("FERRO_SITE_URL", "#"),
            "avibeagency": os.environ.get("AVIBE_SITE_URL", "#"),
        }
        # Per-workspace favicon (matches each tenant's landing-page favicon)
        favicon_map = {
            "romanelli-studio": "/static/favicons/romanelli.svg",
            "romanelli-audit": "/static/favicons/romanelli.svg",
        }
        # Per-tenant 'Secure Workspace' heading label (what the user sees on top)
        secure_label_map = {
            "lexflow": "LexFlow Secure Workspace",
            "avibeagency": "Avibe Agency Secure Workspace",
            "pagliano": "Avv.Pagl Secure Workspace",
            "romanelli-studio": "Romanelli-Studio Secure Workspace",
            "romanelli-audit": "Romanelli Audit Secure Workspace",
            "romanelli-cl1": "Romanelli Client 1 Secure Workspace",
            "romanelli-cl2": "Romanelli Client 2 Secure Workspace",
            "tommasoferro": "Ferro-Studio Secure Workspace",
        }
        main_site_url = "#"
        favicon_url = None
        secure_label = None
        if user and user.workspace:
            main_site_url = site_map.get(user.workspace.slug, "#")
            favicon_url = favicon_map.get(user.workspace.slug)
            secure_label = secure_label_map.get(
                user.workspace.slug,
                f"{user.workspace.name} Secure Workspace",
            )

        return {
            "current_user": user,
            "main_site_url": main_site_url,
            "favicon_url": favicon_url,
            "secure_label": secure_label,
            "is_superadmin": bool(user and user.role == "superadmin"),
        }

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
    from .routes.saved_views import saved_views_bp
    from .routes.attachments import attachments_bp

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
    app.register_blueprint(saved_views_bp)
    app.register_blueprint(attachments_bp)

    # Google Calendar OAuth
    from .routes.google_oauth_routes import google_oauth_bp
    app.register_blueprint(google_oauth_bp)

    # View Blueprint
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
            from sqlalchemy import inspect, text
            from .models.user import User
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            if tables:
                cols = [c['name'] for c in inspector.get_columns('cases')]
                if 'workspace_id' not in cols:
                    import logging
                    log = logging.getLogger(__name__)
                    log.info("Old schema — recreating tables with CASCADE...")
                    with db.engine.connect() as conn:
                        conn.execute(text("DROP SCHEMA public CASCADE"))
                        conn.execute(text("CREATE SCHEMA public"))
                        conn.commit()
                    db.create_all()
                    log.info("✓ Tables recreated")
            # Ensure the new workspaces.parent_workspace_id column exists
            # (prod DBs predate this column; db.create_all() only creates missing
            # tables, not columns — so we add it explicitly if missing).
            import logging
            log = logging.getLogger(__name__)
            try:
                ws_cols = [c['name'] for c in inspector.get_columns('workspaces')]
                if 'parent_workspace_id' not in ws_cols:
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE workspaces ADD COLUMN parent_workspace_id INTEGER"))
                        conn.commit()
                    log.info("✓ Added workspaces.parent_workspace_id")
            except Exception as e:
                log.warning(f"ensure parent_workspace_id skipped: {e}")

            # Ensure the new cases.case_no and workspaces.code_prefix columns exist
            # (additive — same pattern as parent_workspace_id above).
            try:
                case_cols = [c['name'] for c in inspector.get_columns('cases')]
                if 'case_no' not in case_cols:
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE cases ADD COLUMN case_no VARCHAR(20)"))
                        conn.commit()
                    log.info("✓ Added cases.case_no")
            except Exception as e:
                log.warning(f"ensure case_no skipped: {e}")
            try:
                ws_cols2 = [c['name'] for c in inspector.get_columns('workspaces')]
                if 'code_prefix' not in ws_cols2:
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE workspaces ADD COLUMN code_prefix VARCHAR(5)"))
                        conn.commit()
                    log.info("✓ Added workspaces.code_prefix")
            except Exception as e:
                log.warning(f"ensure code_prefix skipped: {e}")

            # Seed per-tenant code_prefix for case IDs (additive; only fills blank)
            _seed_code_prefixes()

            # Always ensure at least one user exists
            if not User.query.first():
                _seed_default_users()
                logging.getLogger(__name__).info("✓ Default user seeded")

            # Ensure test/multi-tenant users exist on every boot (idempotent)
            _ensure_workspace_users()
            # Create any missing tables (e.g. new models added after prod was first
            # deployed). db.create_all() is checkfirst+additive — it only creates
            # tables that don't exist and never alters/drops existing data.
            db.create_all()

            # Heal out-of-range task dates (e.g. a task whose duedate has year
            # 92026). These crash GET /api/tasks with "year XXXX is out of range"
            # during result conversion. Reset the bad date to NULL so the list
            # renders. Runs on boot, idempotent, additive.
            try:
                from sqlalchemy import text as _text
                with db.engine.connect() as conn:
                    conn.execute(_text(
                        "UPDATE tasks SET duedate = NULL "
                        "WHERE duedate IS NOT NULL "
                        "AND (EXTRACT(YEAR FROM duedate) < 1900 "
                        "     OR EXTRACT(YEAR FROM duedate) > 2100)"
                    ))
                    conn.commit()
            except Exception as e:
                logging.getLogger(__name__).warning(f"heal task dates skipped: {e}")

            app._schema_checked = True

    return app
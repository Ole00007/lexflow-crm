"""LexFlow CRM test suite — pytest + Flask test client.

Run:  python -m pytest tests/ -v
No running server required. Uses an isolated SQLite test database.
"""
import os
import sys
import tempfile

# Point at a throwaway DB BEFORE importing the app
_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.name}"
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("RATELIMIT_STORAGE_URL", "memory://")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from crm import create_app
from crm.extensions import db


@pytest.fixture(scope="session")
def app():
    application = create_app()
    application.config["TESTING"] = True
    with application.app_context():
        db.create_all()
    return application


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(scope="function")
def superadmin_headers(client):
    """Login as the seeded superadmin and return auth headers."""
    resp = client.post("/api/auth/login", json={
        "email": "olesya00007@yahoo.com",
        "password": "Test12345!",
    })
    if resp.status_code == 200:
        token = resp.get_json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return {}

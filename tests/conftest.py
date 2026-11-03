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
# Seed passwords required by the app (A2 fix — no hardcoded creds)
os.environ.setdefault("SEED_OLEYA00007YAHOO_PASSWORD", "Test12345!")
os.environ.setdefault("SEED_OLEYA00007GMAIL_PASSWORD", "Test1")
os.environ.setdefault("SEED_SUPERADMINLEXFLOW_PASSWORD", "lexflow0826")
os.environ.setdefault("SEED_ALEGRA007PROTON_PASSWORD", "avibe0826")
os.environ.setdefault("SEED_MSOKUNEVAINTERNET_PASSWORD", "pagliano0826")
os.environ.setdefault("SEED_OLEYA00007GOOGLE_PASSWORD", "Romanelli0826")
os.environ.setdefault("SEED_PREVIEWROMANELLI_PASSWORD", "Romanelli0826")
os.environ.setdefault("SEED_FERROLEXFLOW_PASSWORD", "ferro0826")
os.environ.setdefault("SEED_AVIBELEXFLOW_PASSWORD", "Avibe@12345")
os.environ.setdefault("SEED_PAGLIANOLEXFLOW_PASSWORD", "Pag@12345")
os.environ.setdefault("SEED_ROMANELLILEXFLOW_PASSWORD", "Rom@12345")
os.environ.setdefault("SEED_AUDITLEXFLOW_PASSWORD", "Audit@12345")
os.environ.setdefault("SEED_CL1ROMANELLI_PASSWORD", "cl10826")
os.environ.setdefault("SEED_CL2ROMANELLI_PASSWORD", "cl20826")

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


# Test files that cannot share the pytest process:
#  - SCRIPT_TESTS: plain scripts (column-0 `sys.exit(`): run as scripts in a subprocess.
#  - ENV_TESTS: pytest files that set DATABASE_URL at import level (pollutes every other test): run with pytest in a subprocess.
# Both are executed by test_plain_scripts.py and never collected in-process.
import pathlib as _pl
_files = sorted(_pl.Path(__file__).parent.glob('test_*.py'))
def _lines(f):
    return f.read_text(errors='ignore').splitlines()
def _is_script(f):
    ls = _lines(f)
    return any(l.startswith('sys.exit(') for l in ls) or any(l.strip().startswith('sys.exit(') and not l.startswith('    sys.exit(main')
                                                              and 'def ' not in l for l in ls if l.startswith('    sys.exit(0)') or l.startswith('    sys.exit(1)')) \
        or not any(l.startswith(('def test_', 'async def test_')) or l.startswith('    def test_') for l in ls)
SCRIPT_TESTS = [f.name for f in _files if f.name != 'test_plain_scripts.py' and _is_script(f)]
ENV_TESTS = [f.name for f in _files if f.name not in SCRIPT_TESTS and f.name != 'test_plain_scripts.py'
             and any(l.startswith(('os.environ.update(DATABASE_URL', "os.environ.setdefault('DATABASE_URL'", 'os.environ["DATABASE_URL"]', "os.environ['DATABASE_URL']")) for l in _lines(f))]
collect_ignore = sorted({'test_gantt_dependencies.py', 'test_context_notes.py', 'test_gantt_team.py', 'test_notify.py',
                         'test_deadline_calendar_isolation.py'} | set(SCRIPT_TESTS) | set(ENV_TESTS))

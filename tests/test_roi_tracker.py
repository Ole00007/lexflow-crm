"""PART C + PART D tests — ROI calculator embedding and in-app progress tracker.

PART C (embed): /roi-calculator?embed=1 must relax framing ONLY for that page
while the calculator flag is on, expressing the allow-list via CSP
`frame-ancestors` (env ROI_EMBED_ORIGINS, default lexflow-site.pages.dev) and
REMOVING the global X-Frame-Options: DENY for that response so the two do not
conflict. The rest of the app keeps its DENY protection.

PART D (tracker): GET/PUT /api/roi/progress behind ROI_TRACKER_ENABLED (default
OFF -> 404). Tenant-scoped via the caller's JWT: a normal user sees only their
own rows; a user in ANOTHER workspace sees nothing of the first's rows.
Validation: month 'YYYY-MM', 0<=hours<=744, matters>=0, note<=200.
"""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TPL = BASE / "templates" / "roi_calculator.html"


# ── helpers ─────────────────────────────────────────────────────────────
def _login(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"login {email} failed: {resp.status_code} {resp.get_data(as_text=True)[:200]}"
    return {"Authorization": "Bearer " + resp.get_json()["access_token"]}


# ── PART C: embedding & frame policy ────────────────────────────────────
def _calc_enabled_ctx():
    os.environ["ROI_CALCULATOR_ENABLED"] = "true"


def _calc_disabled_ctx():
    os.environ["ROI_CALCULATOR_ENABLED"] = "false"


def test_embed_header_present_with_embed_and_flag_on(client):
    _calc_enabled_ctx()
    r = client.get("/roi-calculator?embed=1")
    assert r.status_code == 200
    csp = r.headers.get("Content-Security-Policy", "")
    assert "frame-ancestors https://lexflow-site.pages.dev" in csp, csp
    # body-of-page CSP preserved (script-src still restricts; XSS posture kept)
    assert "script-src 'self'" in csp, csp
    assert "default-src 'self'" in csp, csp
    # X-Frame-Options must be absent so it cannot conflict with frame-ancestors
    assert "X-Frame-Options" not in r.headers, r.headers.get("X-Frame-Options")


def test_embed_header_absent_without_embed_param(client):
    _calc_enabled_ctx()
    r = client.get("/roi-calculator")
    assert r.status_code == 200
    csp = r.headers.get("Content-Security-Policy", "")
    assert "frame-ancestors" not in csp, csp
    # the app-wide baseline protection is kept
    assert r.headers.get("X-Frame-Options") == "DENY"


def test_embed_header_absent_when_flag_off(client):
    _calc_disabled_ctx()
    r = client.get("/roi-calculator?embed=1")
    # the route 404s when the flag is off, and the embed header must NOT be set
    assert r.status_code == 404
    csp = r.headers.get("Content-Security-Policy", "")
    assert csp is None or "frame-ancestors" not in csp
    assert r.headers.get("X-Frame-Options") == "DENY"


def test_embed_accepts_custom_origins(client):
    _calc_enabled_ctx()
    os.environ["ROI_EMBED_ORIGINS"] = "https://site.example.org, https://other.example.com"
    try:
        r = client.get("/roi-calculator?embed=1")
        assert r.status_code == 200
        csp = r.headers.get("Content-Security-Policy", "")
        assert "frame-ancestors https://site.example.org https://other.example.com" in csp, csp
    finally:
        os.environ.pop("ROI_EMBED_ORIGINS", None)


def test_rest_of_app_keeps_deny(client):
    _calc_enabled_ctx()
    r = client.get("/login")
    assert r.status_code == 200
    assert r.headers.get("X-Frame-Options") == "DENY"
    csp = r.headers.get("Content-Security-Policy", "")
    assert "frame-ancestors" not in csp


def test_embed_mode_marks_page_and_keeps_no_external_refs():
    """The template supports embed mode: body carries data-embed and the embed
    height-postMessage script is present, but the page still references no
    external assets (same rule as PART B)."""
    assert TPL.exists()
    src = TPL.read_text(encoding="utf-8")
    assert 'data-embed="1"' in src
    assert "lf-roi-height" in src
    assert "postMessage" in src
    # still zero external http(s) refs
    import re
    ext = re.findall(r'https?://', src)
    assert ext == [], f"external refs found: {ext}"


# ── PART D: tracker API ─────────────────────────────────────────────────
def _tracker_enabled():
    os.environ["ROI_TRACKER_ENABLED"] = "true"


def _tracker_disabled():
    os.environ.pop("ROI_TRACKER_ENABLED", None)


def test_tracker_404_when_flag_off(client):
    _tracker_disabled()
    h = _login(client, "olesya00007@yahoo.com", "Test12345!")
    r = client.get("/api/roi/progress", headers=h)
    assert r.status_code == 404
    r2 = client.put("/api/roi/progress", headers=h, json={
        "month": "2026-10", "hours_saved_actual": 10, "matters_handled": 5
    })
    assert r2.status_code == 404


def test_tracker_requires_auth(client):
    _tracker_enabled()
    r = client.get("/api/roi/progress")
    assert r.status_code in (401, 403)


def test_tracker_put_validation_errors(client):
    _tracker_enabled()
    h = _login(client, "olesya00007@yahoo.com", "Test12345!")
    # bad month
    r = client.put("/api/roi/progress", headers=h, json={
        "month": "10-2026", "hours_saved_actual": 10, "matters_handled": 5
    })
    assert r.status_code == 400
    assert "month" in str([d for d in r.get_json()["details"]])
    # hours out of range
    r = client.put("/api/roi/progress", headers=h, json={
        "month": "2026-10", "hours_saved_actual": 9999, "matters_handled": 5
    })
    assert r.status_code == 400
    # negative matters
    r = client.put("/api/roi/progress", headers=h, json={
        "month": "2026-10", "hours_saved_actual": 10, "matters_handled": -3
    })
    assert r.status_code == 400
    # note too long
    r = client.put("/api/roi/progress", headers=h, json={
        "month": "2026-10", "hours_saved_actual": 10, "matters_handled": 5,
        "note": "x" * 201
    })
    assert r.status_code == 400
    # bad value types
    r = client.put("/api/roi/progress", headers=h, json={
        "month": "2026-10", "hours_saved_actual": "abc", "matters_handled": 5
    })
    assert r.status_code == 400


def test_tracker_put_then_get_own_row(client):
    _tracker_enabled()
    h = _login(client, "olesya00007@yahoo.com", "Test12345!")
    r = client.put("/api/roi/progress", headers=h, json={
        "month": "2026-10", "hours_saved_actual": 12.5, "matters_handled": 7,
        "note": "ottimo mese"
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    row = r.get_json()["row"]
    assert row["month"] == "2026-10"
    assert row["hours_saved_actual"] == 12.5
    assert row["matters_handled"] == 7
    # upsert same month => update, not duplicate
    r = client.put("/api/roi/progress", headers=h, json={
        "month": "2026-10", "hours_saved_actual": 20, "matters_handled": 9
    })
    assert r.status_code == 200
    g = client.get("/api/roi/progress", headers=h)
    rows = [x for x in g.get_json()["rows"] if x["month"] == "2026-10"]
    assert len(rows) == 1
    assert rows[0]["hours_saved_actual"] == 20


def _create_ws(client, super_h, slug, email):
    """Create an isolated workspace + admin via the superadmin API."""
    r = client.post("/api/admin/workspaces", headers=super_h, json={
        "name": slug, "slug": slug, "client_email": email,
    })
    if r.status_code == 409:
        return  # slug already exists from a prior run in the same session DB
    assert r.status_code == 201, f"create ws {slug} failed: {r.status_code} {r.get_data(as_text=True)[:300]}"


def test_tracker_tenant_isolation(client):
    """A user in one workspace never sees another workspace's rows (including
    admins scoped to their own workspace only)."""
    import uuid
    slug_a = "roi_iso_a_" + uuid.uuid4().hex[:8]
    slug_b = "roi_iso_b_" + uuid.uuid4().hex[:8]
    email_a = "roi_a_" + uuid.uuid4().hex[:8] + "@test.local"
    email_b = "roi_b_" + uuid.uuid4().hex[:8] + "@test.local"

    _tracker_enabled()
    hs = _login(client, "olesya00007@yahoo.com", "Test12345!")
    _create_ws(client, hs, slug_a, email_a)
    _create_ws(client, hs, slug_b, email_b)

    # The create-workspace API creates the admin user; we set its password via
    # the reset-password endpoint so we can log in as it for assertions.
    from crm.extensions import db
    from crm.models.user import User as U
    from crm.models.roi_progress import RoiProgress as RP
    with client.application.app_context():
        (ua,) = U.query.filter_by(email=email_a, is_deleted=False).all()
        (ub,) = U.query.filter_by(email=email_b, is_deleted=False).all()
        assert ua.workspace_id != ub.workspace_id, "test workspaces must not share a workspace"
        ua_ws, ua_id, ub_ws, ub_id = ua.workspace_id, ua.id, ub.workspace_id, ub.id

        # A records a self-reported progress row in workspace A.
        db.session.add(RP(workspace_id=ua_ws, user_id=ua_id,
                          month="2026-10", hours_saved_actual=30, matters_handled=11))
        db.session.commit()

        # Log in as B (we reset its password via DB so we can log in).
        ub.set_password("b-test-pw-12345")
        db.session.commit()
    hb = _login(client, email_b, "b-test-pw-12345")

    g = client.get("/api/roi/progress", headers=hb)
    assert g.status_code == 200
    rows = g.get_json()["rows"]
    # B (admin, scoped to workspace B) must NOT see A's row
    assert all(row["workspace_id"] != ua_ws for row in rows)
    assert all(row["user_id"] != ua_id for row in rows)

    # record B's own row and confirm B sees only B's row (B is admin => workspace scope)
    r = client.put("/api/roi/progress", headers=hb, json={
        "month": "2026-10", "hours_saved_actual": 4, "matters_handled": 1
    })
    assert r.status_code == 200
    g = client.get("/api/roi/progress", headers=hb)
    rows = g.get_json()["rows"]
    assert all(row["workspace_id"] == ub_ws for row in rows)
    assert len(rows) == 1, f"B sees: {rows}"


def test_tracker_superadmin_sees_all(client):
    _tracker_enabled()
    h = _login(client, "olesya00007@yahoo.com", "Test12345!")
    client.put("/api/roi/progress", headers=h, json={
        "month": "2026-11", "hours_saved_actual": 5, "matters_handled": 2
    })
    g = client.get("/api/roi/progress", headers=h)
    data = g.get_json()
    assert data["scope"] == "all"
    assert any(r["hours_saved_actual"] == 5 for r in data["rows"])


# ── PART D: tracker UI wiring ───────────────────────────────────────────
def test_tracker_ui_gated_in_template():
    """The tracker UI and its JS/CSS are served only when the flag is on; the
    template wires the tracker module but adds no external assets."""
    src = TPL.read_text(encoding="utf-8")
    assert "roi_tracker_enabled and not embed" in src
    assert "roi_progress.js" in src
    assert "roi_progress.css" in src
    # honest self-reported wording in both languages
    assert "auto-dichiarat" in src or "self-reported" in src
    assert "self-reported" in src

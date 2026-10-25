"""WS-C notification buttons — plain-script test suite (no pytest).

Run:
    /Users/olesiarasing/.hermes/profiles/backend-dev/cache/scratch/gv/bin/python \
        tests/test_notify.py

Pattern: throwaway SQLite, create_app, test_client, PASS/FAIL lines, final
'RESULT: ALL PASS'. The notify blueprint is registered IN THIS HARNESS because
crm/__init__.py is a shared file owned by backend-dev (see hand-off report); the
registration snippet there is identical to what we do below.

No network: the Telegram HTTP sender is monkeypatched. No real secrets: the
token value is a throwaway literal, referenced only inside this test DB.
"""
import io
import os
import sys
import tempfile
import logging

# ── Env BEFORE importing the app ─────────────────────────────────────────────
_TMP_DB = tempfile.NamedTemporaryFile(suffix="_notify.db", delete=False)
_TMP_DB.close()
os.environ["DATABASE_URL"] = "sqlite:///%s" % _TMP_DB.name
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("RATELIMIT_STORAGE_URL", "memory://")
# Seed passwords (throwaway DB only)
os.environ.setdefault("SEED_OLEYA00007YAHOO_PASSWORD", "Test12345!")
os.environ.setdefault("SEED_MSOKUNEVAINTERNET_PASSWORD", "pagliano0826")
os.environ.setdefault("SEED_CL1ROMANELLI_PASSWORD", "cl10826")
os.environ.setdefault("SEED_OLEYA00007GOOGLE_PASSWORD", "Romanelli0826")
# Feature flag + bot config
os.environ["NOTIFY_BUTTONS_ENABLED"] = "1"
os.environ["LEXFLOW_TELEGRAM_BOT"] = "LexFlowBot"
# Throwaway, NON-real token literal used only to exercise the code path.
_FAKE_TOKEN = "123456:THROWAWAY_FAKE_TOKEN_abc"
os.environ["LEXFLOW_TELEGRAM_BOT_TOKEN"] = _FAKE_TOKEN

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crm import create_app
from crm.extensions import db
from crm.routes.notify import notify_bp
from crm.services import notify_links
from crm.models.task import Task
from crm.models.firm_team import FirmTeamMember
from crm.models.notify_consent import NotifyConsent
from crm.models.workspace import Workspace

app = create_app()
if 'notify' not in app.blueprints:      # registered by crm/__init__ once integrated
    app.register_blueprint(notify_bp)
app.config["TESTING"] = True
with app.app_context():
    db.create_all()

client = app.test_client()

# ── Tiny assert harness ──────────────────────────────────────────────────────
_PASS = 0
_FAIL = 0


def check(name, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print("PASS: %s" % name)
    else:
        _FAIL += 1
        print("FAIL: %s" % name)


def login(email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        return None
    return {"Authorization": "Bearer %s" % r.get_json()["access_token"]}


def make_task(headers, title="Send the notice", status="pending"):
    c = client.post(
        "/api/contacts",
        json={"full_name": "Giulia Verdi Confidential", "email": "g_%d@test.local" % id(object()), "status": "lead"},
        headers=headers,
    )
    assert c.status_code in (200, 201), c.get_json()
    cid = c.get_json()["id"]
    cs = client.post(
        "/api/cases",
        json={"contactid": cid, "title": "Matter X", "status": "Intake", "priority": "Medium"},
        headers=headers,
    )
    assert cs.status_code in (200, 201), cs.get_json()
    case_id = cs.get_json()["id"]
    t = client.post(
        "/api/tasks/",
        json={"title": title, "caseid": case_id, "status": status, "priority": "Medium",
              "startdate": "2026-10-14", "duedate": "2026-10-25"},
        headers=headers,
    )
    assert t.status_code in (200, 201), t.get_json()
    return t.get_json()["id"]


# ── 1. Pure link-building / sanitising (no app, no network) ──────────────────
with app.app_context():
    # normalize_phone
    check("phone valid +39 -> digits", notify_links.normalize_phone("+39 333 1234567") == "393331234567")
    check("phone injection '+39 333; DROP' rejected", notify_links.normalize_phone("+39 333; DROP") is None)
    check("phone 00-prefix stripped", notify_links.normalize_phone("0039 333 1234567") == "393331234567")
    check("phone too short rejected", notify_links.normalize_phone("12345") is None)
    check("phone too long rejected", notify_links.normalize_phone("1" * 16) is None)
    check("phone None -> None", notify_links.normalize_phone(None) is None)

    # sanitize_text: newlines/control chars collapsed, unicode kept
    s = notify_links.sanitize_text("Depo\nsit\t\u00e8 \ud83d\ude00".encode("utf-16", "surrogatepass").decode("utf-16"))
    check("sanitize removes newlines", "\n" not in s and "\t" not in s)
    check("sanitize keeps unicode", "\u00e8" in s)

    # Stub task for pure builders
    class _Case:
        def display_id(self):
            return "L-07"

    class _Task:
        id = 42
        title = "Send\nthe <notice>"
        duedate = None
        case = _Case()

    t = _Task()
    txt = notify_links.build_message_text(t)
    check("message has matter no", "L-07" in txt)
    check("message has title", "the <notice>" in txt or "Send the <notice>" in txt)
    check("message has no newline", "\n" not in txt)

    dl = notify_links.telegram_deeplink(t)
    check("telegram deeplink uses bot+start", dl == "https://t.me/LexFlowBot?start=task42")
    share = notify_links.telegram_share_link(t)
    check("telegram share link form", share.startswith("https://t.me/share/url?") and "text=" in share)

    wa = notify_links.whatsapp_link("+39 333 1234567", t)
    check("wa.me normalised number", wa.startswith("https://wa.me/393331234567?text="))
    wa_generic = notify_links.whatsapp_link(None, t)
    check("wa.me generic (no number)", wa_generic.startswith("https://wa.me/?text="))
    wa_bad = notify_links.whatsapp_link("+39 333; DROP", t)
    check("wa.me bad phone -> generic", wa_bad.startswith("https://wa.me/?text="))

    # whatsapp stub raises NotImplemented
    raised = False
    try:
        notify_links.send_whatsapp_message("x", "y")
    except NotImplementedError:
        raised = True
    check("whatsapp real send raises NotImplementedError", raised)

# ── 2. Auth + flag gating ────────────────────────────────────────────────────
sa = login("olesya00007@yahoo.com", "Test12345!")
check("superadmin login works", sa is not None)

task_id = make_task(sa)

# flag ON: unauthenticated -> 401
r = client.get("/api/notify/task/%d/links" % task_id)
check("links requires auth (401)", r.status_code == 401)

# flag OFF -> 404 even for superadmin
os.environ["NOTIFY_BUTTONS_ENABLED"] = "false"
r = client.get("/api/notify/task/%d/links" % task_id, headers=sa)
check("flag off -> 404 (links)", r.status_code == 404)
r = client.post("/api/notify/task/%d/send" % task_id, headers=sa, json={"channel": "telegram", "member_id": 1})
check("flag off -> 404 (send)", r.status_code == 404)
os.environ["NOTIFY_BUTTONS_ENABLED"] = "1"

# ── 3. GET links payload + recipients ────────────────────────────────────────
# seed a firm team member in the task's (lexflow) workspace
with app.app_context():
    tsk = db.session.get(Task, task_id)
    ws_id = tsk.workspace_id
    m = FirmTeamMember(workspace_id=ws_id, name="Avv. Mario", role="avvocato",
                       email=None, phone="+39 06 123 4567", is_active=True)
    m2 = FirmTeamMember(workspace_id=ws_id, name="No Phone Clerk", role="office",
                        email=None, phone=None, is_active=True)
    db.session.add(m)
    db.session.add(m2)
    db.session.commit()
    member_id = m.id
    member2_id = m2.id

r = client.get("/api/notify/task/%d/links" % task_id, headers=sa)
j = r.get_json()
check("links 200", r.status_code == 200)
check("links telegram.share present", bool(j["telegram"]["share"]))
check("links telegram.deeplink present", bool(j["telegram"]["deeplink"]))
check("links whatsapp.link present", bool(j["whatsapp"]["link"]))
rec_by_id = {x["member_id"]: x for x in j["recipients"]}
check("recipient with phone has whatsapp channel", "whatsapp" in rec_by_id[member_id]["channels"])
check("recipient without phone has no whatsapp channel", "whatsapp" not in rec_by_id[member2_id]["channels"])
check("recipient telegram channel always present", "telegram" in rec_by_id[member_id]["channels"])
check("recipient consent defaults false", rec_by_id[member_id]["consented"]["telegram"] is False)

# no PII leak: client full name must NOT be in any generated text/link
blob = (j["telegram"]["share"] + j["whatsapp"]["link"]).lower()
check("no client name in links (PII)", "giulia" not in blob and "verdi" not in blob)
with app.app_context():
    tsk = db.session.get(Task, task_id)
    mtxt = notify_links.build_message_text(tsk)
    check("message text no client name (PII)", "Giulia" not in mtxt and "Verdi" not in mtxt)

# ── 4. Tenant isolation: admin of another workspace -> 404 ───────────────────
# Build a genuinely separate workspace + admin (the seeded roster collapses
# unknown slugs onto the first workspace, so we create our own here).
with app.app_context():
    from crm.models.user import User
    other_ws = Workspace(slug="ws-other-notify", name="Other Firm", is_active=True)
    db.session.add(other_ws)
    db.session.flush()
    ou = User(email="otheradmin@notify.local", role="admin", workspace_id=other_ws.id)
    ou.set_password("Other12345!")
    db.session.add(ou)
    # a sub-workspace under the task's firm (lexflow) with a sub-tenant admin
    tsk = db.session.get(Task, task_id)
    sub_ws = Workspace(slug="ws-sub-notify", name="Client Sub",
                       parent_workspace_id=tsk.workspace_id, is_active=True)
    db.session.add(sub_ws)
    db.session.flush()
    su = User(email="subadmin@notify.local", role="admin", workspace_id=sub_ws.id)
    su.set_password("Sub12345!")
    db.session.add(su)
    db.session.commit()

other = login("otheradmin@notify.local", "Other12345!")
check("other-workspace admin login works", other is not None)
r = client.get("/api/notify/task/%d/links" % task_id, headers=other)
check("tenant isolation: other admin GET links -> 404", r.status_code == 404)
r = client.post("/api/notify/task/%d/send" % task_id, headers=other,
                json={"channel": "telegram", "member_id": member_id})
check("tenant isolation: other admin send -> 404", r.status_code == 404)

# ── 5. Send: consent required (403) ──────────────────────────────────────────
r = client.post("/api/notify/task/%d/send" % task_id, headers=sa,
                json={"channel": "telegram", "member_id": member_id})
check("send without consent -> 403", r.status_code == 403)

# ── 6. WhatsApp real send -> 501 ─────────────────────────────────────────────
r = client.post("/api/notify/task/%d/send" % task_id, headers=sa,
                json={"channel": "whatsapp", "member_id": member_id})
check("whatsapp real send -> 501", r.status_code == 501)

# ── 7. PUT consent (admin/superadmin) persists; sub-tenant admin forbidden ───
r = client.put("/api/notify/consent", headers=sa,
               json={"member_id": member_id, "channel": "telegram", "granted": True,
                     "telegram_chat_id": "99900111"})
check("consent PUT 200", r.status_code == 200)
check("consent PUT persisted granted", r.get_json()["granted"] is True)
check("consent PUT hides raw chat id", "telegram_chat_id" not in r.get_json() and r.get_json()["has_target"] is True)

# sub-tenant admin (client sub-workspace) must be forbidden (read-only on firm team)
subadmin = login("subadmin@notify.local", "Sub12345!")
if subadmin:
    r = client.put("/api/notify/consent", headers=subadmin,
                   json={"member_id": member_id, "channel": "telegram", "granted": True})
    check("sub-tenant admin consent PUT -> 403", r.status_code == 403)
else:
    check("sub-tenant admin login (prereq)", False)

# ── 8. Send with consent calls injected sender; token never logged ───────────
_sent = {}


def _fake_post(url, json_body, timeout=10):
    _sent["url"] = url
    _sent["body"] = json_body

    class _Resp:
        status_code = 200

        def json(self):
            return {"ok": True}

    return _Resp()


# capture logs to assert the token is never logged
log_buf = io.StringIO()
handler = logging.StreamHandler(log_buf)
handler.setLevel(logging.DEBUG)
root = logging.getLogger()
root.addHandler(handler)
old_level = root.level
root.setLevel(logging.DEBUG)

_orig_post = notify_links.http_post
notify_links.http_post = _fake_post
try:
    r = client.post("/api/notify/task/%d/send" % task_id, headers=sa,
                    json={"channel": "telegram", "member_id": member_id})
finally:
    notify_links.http_post = _orig_post
    root.removeHandler(handler)
    root.setLevel(old_level)

check("send with consent -> 200", r.status_code == 200)
check("injected sender was called", "url" in _sent)
check("send url targets sendMessage", _sent.get("url", "").endswith("/sendMessage"))
check("send url carries token", _FAKE_TOKEN in _sent.get("url", ""))
check("send body has chat_id", _sent.get("body", {}).get("chat_id") == "99900111")
check("send body has text", bool(_sent.get("body", {}).get("text")))
check("send body text no newline", "\n" not in _sent.get("body", {}).get("text", ""))
logged = log_buf.getvalue()
check("token NEVER appears in logs", _FAKE_TOKEN not in logged)

# ── 9. Send without token configured -> 501 ──────────────────────────────────
_saved_token = os.environ.pop("LEXFLOW_TELEGRAM_BOT_TOKEN", None)
r = client.post("/api/notify/task/%d/send" % task_id, headers=sa,
                json={"channel": "telegram", "member_id": member_id})
check("send without token configured -> 501", r.status_code == 501)
if _saved_token is not None:
    os.environ["LEXFLOW_TELEGRAM_BOT_TOKEN"] = _saved_token

# ── Result ───────────────────────────────────────────────────────────────────
print("\n%d passed, %d failed" % (_PASS, _FAIL))
if _FAIL == 0:
    print("RESULT: ALL PASS")
    sys.exit(0)
else:
    print("RESULT: FAIL")
    sys.exit(1)

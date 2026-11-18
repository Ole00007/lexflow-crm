"""Golden demo smoke — Mindmap + Elisa, against a running local server.

Usage:
  python scripts/demo_smoke.py --base http://127.0.0.1:5057 \
      --email olesya00007@yahoo.com --password 'Test12345!'

Exit 0 = every check passed. Prints a checklist so the same script can be run
5 minutes before the meeting.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.request


class Check:
    def __init__(self):
        self.failures = []

    def __call__(self, name, ok, detail=""):
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))
        if not ok:
            self.failures.append(name)


def _req(base, path, method="GET", token=None, body=None, agent=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    if agent:
        req.add_header("X-Agent-Name", agent)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5057")
    ap.add_argument("--email", default="olesya00007@yahoo.com")
    ap.add_argument("--password", default="Test12345!")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    check = Check()

    code, _ = _req(base, "/health")
    check("health 200", code == 200, f"status={code}")

    code, auth = _req(base, "/api/auth/login", "POST", body={"email": a.email, "password": a.password})
    check("login", code == 200 and bool((auth or {}).get("access_token")), f"status={code}")
    if code != 200:
        return 1
    token = auth["access_token"]

    # --- Elisa: propose -> approve -> single use ---------------------------------
    due = (dt.date.today() + dt.timedelta(days=3)).isoformat()
    code, chat = _req(base, "/api/agent/chat", "POST", token,
                      {"message": f"Create task Demo smoke for matter Rasing separazione due {due}"})
    action = (chat or {}).get("pending_action") or {}
    check("elisa proposes a gated action", code == 200 and action.get("tool") == "create_task",
          f"status={code} body={str(chat)[:160]}")
    if action.get("id"):
        code, _ = _req(base, f"/api/agent/chat/actions/{action['id']}/approve", "POST", token)
        check("approval executes", code == 200, f"status={code}")
        code, body = _req(base, f"/api/agent/chat/actions/{action['id']}/approve", "POST", token)
        check("second approval refused (409)", code == 409, f"status={code} body={body}")

    # --- Mindmap provenance ------------------------------------------------------
    code, tasks = _req(base, "/api/tasks", "GET", token)
    items = tasks if isinstance(tasks, list) else (tasks or {}).get("items", [])
    target_id = items[0]["id"] if items else 1

    code, note = _req(base, "/api/notes/", "POST", token,
                      {"target_type": "task", "target_id": target_id,
                       "content": "Demo smoke human note", "source": "agent"})
    check("human note created", code == 201, f"status={code} body={str(note)[:120]}")
    check("client cannot forge agent provenance", (note or {}).get("source") == "human",
          f"source={(note or {}).get('source')}")
    check("author is visible", bool((note or {}).get("author_name") or (note or {}).get("author_email")))

    code, agent_notes = _req(base, "/api/notes/?source=agent", "GET", token)
    check("agent filter returns only promoted notes",
          code == 200 and isinstance(agent_notes, list) and all(n.get("source") == "agent" for n in agent_notes))

    code, _ = _req(base, "/api/notes/?source=robot", "GET", token)
    check("invalid source rejected (400)", code == 400, f"status={code}")

    # --- Draft sandbox (present once B1 server merges) ---------------------------
    code, drafts = _req(base, "/api/agent/drafts?status=proposed", "GET", token)
    if code == 404:
        print("SKIP  draft endpoints not merged yet")
    else:
        check("draft tray lists", code == 200, f"status={code}")
        if isinstance(drafts, list) and drafts:
            d = drafts[0]
            code, promoted = _req(base, f"/api/agent/drafts/{d['id']}/accept", "POST", token)
            check("accept promotes to notes", code == 200, f"status={code}")
            if code == 200:
                n = (promoted or {}).get("note") or {}
                check("promoted note keeps agent provenance",
                      n.get("source") == "agent" and str(n.get("source_ref")) == str(d["id"]))
            code, body = _req(base, f"/api/agent/drafts/{d['id']}/accept", "POST", token)
            check("double accept refused (409)", code == 409, f"status={code} body={body}")
        else:
            print("SKIP  no proposed drafts seeded")

    print()
    if check.failures:
        print(f"RESULT: FAIL ({len(check.failures)}): {', '.join(check.failures)}")
        return 1
    print("RESULT: PASS — every check green")
    return 0


if __name__ == "__main__":
    sys.exit(main())

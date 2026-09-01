"""Google Calendar → LexFlow sync (one-way import, ws7 LexFlow ONLY).

Pulls events from a configured Google Calendar and upserts them into the
calendar_events table scoped to the LexFlow workspace (id of slug 'lexflow').
This is deliberately isolated from every other workspace (Romanelli etc.):
we write workspace_id = lexflow_ws.id only, and skip any event that already
exists (matched by google_event_id).

AUTH NOTE: a Google API key (GOOGLE_CALENDAR_API_KEY) can only read calendars
the user has made public (or events shared 'publicly'). For a private calendar
you need OAuth 2.0 (client_secret.json + refresh token). The sync will report
its real result; if Google returns 401/403 it means the calendar isn't readable
with the key and we tell you exactly that.

Env vars:
  GOOGLE_CALENDAR_API_KEY  — API key (set in Railway, never committed)
  GOOGLE_CALENDAR_ID       — the calendar to read (e.g. the owner's email).
                             If empty, sync is skipped with a clear log line.
  GOOGLE_CALENDAR_MAX      — max events per sync (default 200).
"""
import os
import logging
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

from .extensions import db
from .models.calendar_event import CalendarEvent
from .models.workspace import Workspace

log = logging.getLogger(__name__)

API_BASE = "https://www.googleapis.com/calendar/v3/calendars"


def _lexflow_workspace():
    """The single target workspace for this sync — slug 'lexflow' (ws7 in prod).
    Never fall back to a hardcoded id; resolve by slug so it's correct in any
    environment."""
    return Workspace.query.filter_by(slug="lexflow", is_active=True).first()


def _fetch_google_events(api_key, calendar_id, max_results):
    """Call the Calendar API v3 list endpoint. Returns (events, error).

    calendar_id is an email-like id (e.g. user@gmail.com). Google expects the
    raw '@' in the path segment — URL-encoding it to %40 can yield a 404, so we
    deliberately do NOT quote the calendar_id here."""
    time_min = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = (f"{API_BASE}/{calendar_id}/events"
           f"?key={api_key}&maxResults={max_results}"
           f"&orderBy=startTime&singleEvents=true"
           f"&timeMin={time_min}")
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data.get("items", []), None
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:400]
        return None, f"Google API HTTP {e.code}: {body}"
    except Exception as e:  # noqa: BLE001
        return None, f"Google API error: {e}"


def _parse_dt(value):
    """Google returns dateTime (tz-aware) or date (all-day). Convert to naive UTC
    datetime matching how the rest of the CRM stores datetimes."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, AttributeError):
        return None


def _event_type_mapping(summary):
    """Best-effort legal event_type from the summary text."""
    s = (summary or "").lower()
    if any(k in s for k in ("udienza", "hearing", "audience", "udienza")):
        return "hearing"
    if any(k in s for k in ("termine", "scadenza", "deadline", "filing")):
        return "filing_deadline"
    if any(k in s for k in ("riunione", "meeting", "call", "consulenza")):
        return "meeting"
    if any(k in s for k in ("deposizione", "deposition", "testimone")):
        return "deposition"
    if any(k in s for k in ("promemoria", "reminder")):
        return "reminder"
    return "hearing"


def sync_google_to_lexflow():
    """Run one sync pass. Returns a dict summary for the caller/logs."""
    lex = _lexflow_workspace()
    if not lex:
        log.warning("google-cal-sync: no 'lexflow' workspace — skipping")
        return {"ok": False, "error": "no lexflow workspace"}

    api_key = os.environ.get("GOOGLE_CALENDAR_API_KEY", "").strip()
    calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "").strip()
    if not api_key:
        return {"ok": False, "error": "GOOGLE_CALENDAR_API_KEY not set"}
    if not calendar_id:
        return {"ok": False, "error": "GOOGLE_CALENDAR_ID not set — calendar skipped"}

    max_results = int(os.environ.get("GOOGLE_CALENDAR_MAX", "200"))
    items, err = _fetch_google_events(api_key, calendar_id, max_results)
    if err:
        log.warning("google-cal-sync: %s", err)
        return {"ok": False, "error": err}

    created = skipped = existing = 0
    for ev in items:
        gid = ev.get("id")
        summary = ev.get("summary") or "(untitled)"
        start = ev.get("start") or {}
        end = ev.get("end") or {}
        start_dt = _parse_dt(start.get("dateTime") or start.get("date"))
        end_dt = _parse_dt(end.get("dateTime") or end.get("date"))
        if not start_dt:
            skipped += 1
            continue

        # Dedupe by google_event_id
        dup = CalendarEvent.query.filter_by(
            workspace_id=lex.id, notes=f"gcal:{gid}").first()
        if dup:
            existing += 1
            continue

        ev_row = CalendarEvent(
            workspace_id=lex.id,
            title=summary[:255],
            description=ev.get("description") or "",
            event_type=_event_type_mapping(summary),
            location=(ev.get("location") or "")[:255] or None,
            start_datetime=start_dt,
            end_datetime=end_dt,
            is_all_day=bool(start.get("date")),
            status="scheduled",
            notes=f"gcal:{gid}",
        )
        db.session.add(ev_row)
        created += 1

    db.session.commit()
    log.info("google-cal-sync: created=%d existing=%d skipped=%d (ws=%s)",
             created, existing, skipped, lex.slug)
    return {"ok": True, "created": created, "existing": existing, "skipped": skipped,
            "workspace": lex.slug}


def push_lexflow_to_google():
    """Push (write) LexFlow workspace calendar events back to Google Calendar.

    REQUIRED: OAuth 2.0 credentials — an API key cannot create/modify events on
    a (private) Google Calendar. Needs:
      - GOOGLE_CALENDAR_CLIENT_ID / GOOGLE_CALENDAR_CLIENT_SECRET (OAuth app)
      - GOOGLE_CALENDAR_REFRESH_TOKEN (owner authorized once)
      - GOOGLE_CALENDAR_ID (target calendar)
    Until configured, returns a clear "needs OAuth" result and does nothing.
    Events imported from Google (notes 'gcal:<id>') are skipped to avoid an
    echo loop; existing LexFlow events without a google id are inserted.
    """
    lex = _lexflow_workspace()
    if not lex:
        return {"ok": False, "error": "no lexflow workspace"}

    client_id = os.environ.get("GOOGLE_CALENDAR_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("GOOGLE_CALENDAR_REFRESH_TOKEN", "").strip()
    calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "").strip()
    if not (client_id and client_secret and refresh_token and calendar_id):
        return {
            "ok": False,
            "error": ("push needs OAuth (GOOGLE_CALENDAR_CLIENT_ID / CLIENT_SECRET / "
                      "REFRESH_TOKEN / GOOGLE_CALENDAR_ID not configured). An API key "
                      "cannot write a private Google Calendar — set up the 2FA-safe "
                      "OAuth flow to enable push."),
        }

    # 1) refresh access token
    access, err = _oauth_access_token(client_id, client_secret, refresh_token)
    if err:
        return {"ok": False, "error": err}

    events = CalendarEvent.query.filter_by(
        workspace_id=lex.id, is_deleted=False).all()
    inserted = updated = skipped = 0
    for ev in events:
        if ev.notes and ev.notes.startswith("gcal:"):
            skipped += 1  # came from Google — don't echo back
            continue
        payload = _event_payload(ev)
        if not payload:
            skipped += 1
            continue
        if ev.notes and ev.notes.startswith("gcalpush:"):
            gid = ev.notes[len("gcalpush:"):]
            err = _gcal_request("PUT", calendar_id, gid, payload, access)
            if err:
                return {"ok": False, "error": f"update {gid}: {err}"}
            updated += 1
        else:
            gid, err = _gcal_insert(calendar_id, payload, access)
            if err:
                return {"ok": False, "error": f"insert {ev.title}: {err}"}
            ev.notes = f"gcalpush:{gid}"
            db.session.commit()
            inserted += 1

    return {"ok": True, "inserted": inserted, "updated": updated,
            "skipped": skipped, "workspace": lex.slug}


def _oauth_access_token(client_id, client_secret, refresh_token):
    """Exchange the refresh token for a short-lived access token."""
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            tok = json.loads(resp.read().decode()).get("access_token")
        if not tok:
            return None, "OAuth: no access_token in response"
        return tok, None
    except urllib.error.HTTPError as e:
        return None, f"OAuth token error HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e:  # noqa: BLE001
        return None, f"OAuth token error: {e}"


def _event_payload(ev):
    """Build a Google Calendar event resource from a LexFlow event."""
    if not ev.start_datetime:
        return None
    if ev.is_all_day:
        start = {"date": ev.start_datetime.strftime("%Y-%m-%d")}
        end = {"date": (ev.end_datetime or ev.start_datetime).strftime("%Y-%m-%d")}
    else:
        start = {"dateTime": ev.start_datetime.isoformat()}
        end = {"dateTime": (ev.end_datetime or ev.start_datetime).isoformat()}
    return {
        "summary": ev.title,
        "description": ev.description or "",
        "location": ev.location or "",
        "start": start,
        "end": end,
    }


def _gcal_insert(calendar_id, payload, access):
    url = (f"{API_BASE}/{urllib.request.quote(calendar_id, safe='')}/events")
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + access,
                 "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode()).get("id"), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def _gcal_request(method, calendar_id, event_id, payload, access):
    url = (f"{API_BASE}/{urllib.request.quote(calendar_id, safe='')}/events/"
           f"{urllib.request.quote(event_id, safe='')}")
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + access,
                 "Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
        return None
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e:  # noqa: BLE001
        return str(e)

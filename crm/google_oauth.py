"""Google Calendar OAuth 2.0 flow (LexFlow owner's calendar).

Provides:
  - build_auth_url()        -> the Google consent URL (owner clicks it, logs in,
                               approves; no passwords stored by us).
  - handle_oauth_callback() -> exchange the one-time code for a refresh token
                               and store it in the DB.
  - get_access_token()      -> refresh-token -> short-lived access token.
  - oauth_calendar_request() -> authenticated Google Calendar API call.

Client id/secret come from env (set in Railway, never committed):
  GOOGLE_CALENDAR_CLIENT_ID / GOOGLE_CALENDAR_CLIENT_SECRET
Redirect URI must be registered in the Google Cloud Console OAuth client:
  {PUBLIC_BASE_URL}/api/auth/google-calendar/callback
  (PUBLIC_BASE_URL defaults to https://web-production-031a6.up.railway.app)
"""
import os
import logging
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

from .extensions import db
from .models.google_token import GoogleCalendarToken

log = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://www.googleapis.com/calendar/v3/calendars"
SCOPE = "https://www.googleapis.com/auth/calendar"  # read + write (bidirectional)


def _client_id():
    return os.environ.get("GOOGLE_CALENDAR_CLIENT_ID", "").strip()


def _client_secret():
    return os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET", "").strip()


def public_base_url():
    """The externally reachable base of this app (for the redirect URI)."""
    return os.environ.get(
        "PUBLIC_BASE_URL", "https://web-production-031a6.up.railway.app"
    ).rstrip("/")


def redirect_uri():
    return f"{public_base_url()}/api/auth/google-calendar/callback"


def build_auth_url(state=""):
    """Return the Google consent URL for the owner to authorize."""
    params = {
        "client_id": _client_id(),
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",   # needed to receive a refresh token
        "prompt": "consent",        # force consent so a refresh token is issued
        "include_granted_scopes": "true",
    }
    if state:
        params["state"] = state
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def handle_oauth_callback(code):
    """Exchange an authorization code for a refresh token; store it in the DB.

    Returns (ok, detail) — detail is the stored token record on success or an
    error message on failure.
    """
    client_id = _client_id()
    client_secret = _client_secret()
    if not (client_id and client_secret):
        return False, "GOOGLE_CALENDAR_CLIENT_ID / CLIENT_SECRET not configured"

    data = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri(),
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            tok = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return False, f"Token exchange HTTP {e.code}: {e.read().decode()[:400]}"
    except Exception as e:  # noqa: BLE001
        return False, f"Token exchange error: {e}"

    refresh = tok.get("refresh_token")
    if not refresh:
        return False, "No refresh_token in response (check access_type=offline & prompt=consent)"

    row = GoogleCalendarToken.query.filter_by(scope_key="lexflow").first()
    if row:
        row.refresh_token = refresh
    else:
        row = GoogleCalendarToken(scope_key="lexflow", refresh_token=refresh)
        db.session.add(row)
    db.session.commit()
    log.info("google-oauth: refresh token stored")
    return True, row


def get_refresh_token():
    row = GoogleCalendarToken.query.filter_by(scope_key="lexflow").first()
    return row.refresh_token if row else None


def get_access_token():
    """Return (access_token, error). Exchanges the stored refresh token for a
    short-lived access token via Google."""
    refresh = get_refresh_token()
    client_id = _client_id()
    client_secret = _client_secret()
    if not refresh:
        return None, "No refresh token — run the Google Calendar OAuth flow first"
    if not (client_id and client_secret):
        return None, "GOOGLE_CALENDAR_CLIENT_ID / CLIENT_SECRET not configured"

    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            tok = json.loads(resp.read().decode())
        access = tok.get("access_token")
        if not access:
            return None, "No access_token in response"
        return access, None
    except urllib.error.HTTPError as e:
        return None, f"OAuth token HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e:  # noqa: BLE001
        return None, f"OAuth token error: {e}"


def oauth_calendar_request(method, calendar_id, path_suffix="", payload=None):
    """Authenticated call to the Google Calendar API using OAuth.

    path_suffix: e.g. "" (list), "/<event_id>" (get/put/delete). For list,
    extra_query may be appended via path_suffix like "?maxResults=100".
    Returns (data_dict_or_bytes, error).
    """
    access, err = get_access_token()
    if err:
        return None, err
    calendar_id_q = urllib.parse.quote(calendar_id, safe="@")
    url = f"{API_BASE}/{calendar_id_q}/events{path_suffix}"
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=body,
        headers={"Authorization": "Bearer " + access,
                 "Content-Type": "application/json"},
        method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw.decode()) if raw else {}, None
    except urllib.error.HTTPError as e:
        return None, f"Google API HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e:  # noqa: BLE001
        return None, f"Google API error: {e}"

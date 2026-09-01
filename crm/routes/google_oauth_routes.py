"""Google Calendar OAuth routes: /api/auth/google-calendar (start) + callback."""
import logging
import secrets

from flask import Blueprint, jsonify, redirect, request
from flask_jwt_extended import jwt_required

from ..google_oauth import build_auth_url, handle_oauth_callback, redirect_uri
from ..models.google_token import GoogleCalendarToken

log = logging.getLogger(__name__)

google_oauth_bp = Blueprint('google_oauth', __name__, url_prefix='/api/auth')


@google_oauth_bp.get('/google-calendar')
@jwt_required()
def google_calendar_start():
    """Start the OAuth flow: return the Google consent URL.
    Called from the CRM (logged-in user) to begin connecting the LexFlow owner's
    calendar. The owner then opens the URL in a browser, approves, and is
    redirected back to /api/auth/google-calendar/callback.
    """
    state = secrets.token_urlsafe(16)
    return jsonify({
        'auth_url': build_auth_url(state=state),
        'redirect_uri': redirect_uri(),
        'state': state,
    }), 200


@google_oauth_bp.get('/google-calendar/callback')
def google_calendar_callback():
    """OAuth callback: exchange the one-time code for a refresh token.
    This is a public route (Google redirects the user's browser here with ?code=).
    On success we show a simple confirmation page; the refresh token is stored
    in the DB and the sync becomes operational.
    """
    code = request.args.get('code')
    error = request.args.get('error')
    if error:
        return f"<h3>Google Calendar authorization failed</h3><p>{error}</p>", 400
    if not code:
        return "<h3>Missing authorization code</h3>", 400

    ok, detail = handle_oauth_callback(code)
    if not ok:
        log.warning("google-oauth callback failed: %s", detail)
        return f"<h3>Google Calendar authorization failed</h3><p>{detail}</p>", 400

    return ("<html><body style='font-family:sans-serif;text-align:center;padding:60px'>"
            "<h2>✅ Google Calendar connected</h2>"
            "<p>LexFlow can now read and sync events to your calendar.</p>"
            "<p><a href='/admin/panel' style='color:#1a73e8'>← Back to the admin panel</a></p>"
            "</body></html>"), 200


@google_oauth_bp.get('/google-calendar/status')
@jwt_required()
def google_calendar_status():
    """Return whether the OAuth refresh token is stored (connected)."""
    row = GoogleCalendarToken.query.filter_by(scope_key='lexflow').first()
    return jsonify({
        'connected': bool(row and row.refresh_token),
        'redirect_uri': redirect_uri(),
    }), 200

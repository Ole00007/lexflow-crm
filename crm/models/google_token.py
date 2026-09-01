from ..extensions import db
from datetime import datetime


class GoogleCalendarToken(db.Model):
    """Stores the OAuth refresh token for the LexFlow Google Calendar sync.

    We store the refresh token in the DB (not an env var) so the OAuth callback
    can save it server-side without needing a manual env edit. This DB lives on
    the private Railway Postgres. The access token is short-lived and fetched
    on demand; we only persist the long-lived refresh token.
    """
    __tablename__ = "google_calendar_tokens"

    id = db.Column(db.Integer, primary_key=True)
    # Only one row is ever used (the LexFlow owner's calendar); key kept for clarity.
    scope_key = db.Column(db.String(50), nullable=False, default="lexflow", unique=True)
    refresh_token = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "scope_key": self.scope_key,
            "has_refresh_token": bool(self.refresh_token),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

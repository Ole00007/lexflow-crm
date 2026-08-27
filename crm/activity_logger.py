"""
Activity logging helpers — called by model hooks and routes to auto-log timeline events.
"""
from flask import current_app
from .extensions import db
from .models.activity import ActivityLog
from .workspace import get_current_workspace_id


def log_activity(actor_id, target_type, target_id, action, summary, details=None):
    """Create an activity log entry. Safe to call from anywhere if db is available."""
    try:
        entry = ActivityLog(
            workspace_id=get_current_workspace_id() or 1,
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            action=action,
            summary=summary,
            details=details,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        current_app.logger.warning(f"Failed to log activity: {e}")
        db.session.rollback()
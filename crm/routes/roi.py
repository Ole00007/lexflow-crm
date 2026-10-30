"""
ROI progress tracker blueprint (PART D).

Flag: ROI_TRACKER_ENABLED (default OFF). When OFF any /api/roi/progress call
returns 404 so production behaviour is unchanged until it is turned on.
Tenant-scoped via the caller's JWT — no trust in client-supplied ids.

Endpoints:
  GET /api/roi/progress          -> rows the caller may see:
                                   - normal user -> only their OWN rows
                                   - admin       -> whole workspace total
                                   - superadmin  -> all rows (no filter)
  PUT /api/roi/progress          -> upsert the caller's OWN row for a month
                                   (create or update; never someone else's).

Validation: month 'YYYY-MM', 0 <= hours_saved_actual <= 744, matters_handled
>= 0, note <= 200 chars. All self-reported — the UI says so honestly.
"""
import os
import re

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..extensions import db
from ..models.user import User
from ..models.roi_progress import RoiProgress
from ..workspace import get_visible_workspace_ids

roi_bp = Blueprint("roi", __name__, url_prefix="/api/roi")

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _enabled():
    return os.environ.get("ROI_TRACKER_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


def _current_user():
    uid = get_jwt_identity()
    if not uid:
        return None
    return User.query.filter_by(id=int(uid), is_deleted=False).first()


def _validate(payload):
    """Return (errors_list). payload may be partial (PUT only needs month + at
    least one value). Raises nothing — returns a list of human-readable issues."""
    errors = []

    month = (payload.get("month") or "").strip()
    if not MONTH_RE.match(month):
        errors.append("month must be 'YYYY-MM'")

    hrs = payload.get("hours_saved_actual")
    if hrs is not None and hrs != "":
        try:
            hrs = float(hrs)
            if hrs < 0 or hrs > 744:
                errors.append("hours_saved_actual must be between 0 and 744 (hours in a month)")
        except (TypeError, ValueError):
            errors.append("hours_saved_actual must be a number")
    else:
        hrs = 0.0

    matters = payload.get("matters_handled")
    if matters is not None and matters != "":
        try:
            matters = int(matters)
            if matters < 0:
                errors.append("matters_handled must be >= 0")
        except (TypeError, ValueError):
            errors.append("matters_handled must be an integer")
    else:
        matters = 0

    note = payload.get("note")
    if note is not None and len(note) > 200:
        errors.append("note must be 200 characters or fewer")

    return errors


@roi_bp.get("/progress")
@jwt_required()
def get_progress():
    if not _enabled():
        return jsonify({"error": "Not found"}), 404
    user = _current_user()
    if not user:
        return jsonify({"error": "Not found"}), 401

    rows = RoiProgress.query
    if user.role != "superadmin":
        ws_ids = get_visible_workspace_ids()
        if not ws_ids:
            return jsonify({"rows": [], "scope": "none"}), 200
        rows = rows.filter(RoiProgress.workspace_id.in_(ws_ids))
        if user.role != "admin":
            # normal user: own rows only
            rows = rows.filter(RoiProgress.user_id == user.id)
            scope = "own"
        else:
            scope = "workspace"
    else:
        scope = "all"

    rows = rows.order_by(RoiProgress.month.desc()).all()
    return jsonify({"rows": [r.to_dict() for r in rows], "scope": scope}), 200


@roi_bp.put("/progress")
@jwt_required()
def put_progress():
    if not _enabled():
        return jsonify({"error": "Not found"}), 404
    user = _current_user()
    if not user:
        return jsonify({"error": "Not found"}), 401

    payload = request.get_json(silent=True) or {}
    errors = _validate(payload)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    month = (payload.get("month") or "").strip()
    hours = payload.get("hours_saved_actual")
    hours = float(hours) if hours not in (None, "") else 0.0
    matters = payload.get("matters_handled")
    matters = int(matters) if matters not in (None, "") else 0
    note = payload.get("note")
    note = (str(note).strip() or None)
    if note is not None:
        note = note[:200]

    ws_id = user.workspace_id
    if not ws_id:
        return jsonify({"error": "Not found"}), 401

    row = RoiProgress.query.filter_by(
        workspace_id=ws_id, user_id=user.id, month=month
    ).first()
    if row is None:
        row = RoiProgress(workspace_id=ws_id, user_id=user.id, month=month)
        db.session.add(row)
    row.hours_saved_actual = hours
    row.matters_handled = matters
    row.note = note
    db.session.commit()
    return jsonify({"row": row.to_dict(), "scope": "own"}), 200

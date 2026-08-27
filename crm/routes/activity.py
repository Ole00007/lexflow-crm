from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from ..extensions import db, limiter
from ..models.activity import ActivityLog
from ..workspace import get_current_workspace_id

activity_bp = Blueprint('activity', __name__, url_prefix='/api/activity')
VALID_TARGET_TYPES = {"case", "contact", "task"}

def _filtered_query():
    q = ActivityLog.query.order_by(ActivityLog.created_at.desc())
    wid = get_current_workspace_id()
    if wid is not None:
        q = q.filter_by(workspace_id=wid)
    return q

@activity_bp.get('/')
@jwt_required(optional=True)
@limiter.limit("60 per minute")
def get_activity():
    target_type = request.args.get("target_type")
    target_id = request.args.get("target_id", type=int)
    limit = request.args.get("limit", 50, type=int)
    query = _filtered_query()
    if target_type:
        if target_type not in VALID_TARGET_TYPES:
            return jsonify({"error": "Invalid target_type"}), 400
        query = query.filter_by(target_type=target_type)
    if target_id:
        query = query.filter_by(target_id=target_id)
    entries = query.limit(min(limit, 200)).all()
    return jsonify([e.to_dict() for e in entries]), 200
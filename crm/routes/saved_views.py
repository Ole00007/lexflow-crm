from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db, limiter
from ..models.view import View
from ..workspace import get_current_workspace_id

saved_views_bp = Blueprint('saved_views', __name__, url_prefix='/api/views')

VALID_OBJECT_TYPES = {"case", "contact", "task"}


def _filtered_query():
    """Base query scoped to the current user + workspace (multi-tenant isolation)."""
    q = View.query.order_by(View.created_at.desc())
    wid = get_current_workspace_id()
    if wid is not None:
        q = q.filter_by(workspace_id=wid)
    return q


@saved_views_bp.get('/')
@jwt_required()
@limiter.limit("60 per minute")
def list_views():
    """List the current user's saved views for the active workspace."""
    current_user = int(get_jwt_identity())
    query = _filtered_query().filter_by(created_by=current_user)
    object_type = request.args.get("object_type")
    if object_type:
        object_type = object_type.lower()
        if object_type not in VALID_OBJECT_TYPES:
            return jsonify({"error": "Invalid object_type"}), 400
        query = query.filter_by(object_type=object_type)
    return jsonify([v.to_dict() for v in query.all()]), 200


@saved_views_bp.post('/')
@jwt_required()
@limiter.limit("30 per minute")
def create_view():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    name = (data.get("name") or "").strip()
    object_type = (data.get("object_type") or "").lower()
    if not name:
        return jsonify({"error": "name is required"}), 400
    if object_type not in VALID_OBJECT_TYPES:
        return jsonify({"error": "Invalid object_type"}), 400

    current_user = int(get_jwt_identity())
    view = View(
        workspace_id=get_current_workspace_id() or 1,
        name=name,
        object_type=object_type,
        filters_json=data.get("filters"),
        sort_json=data.get("sort"),
        visible_columns_json=data.get("visible_columns"),
        created_by=current_user,
        is_default=bool(data.get("is_default", False)),
    )
    if view.is_default:
        _clear_default(view.workspace_id, current_user, object_type, exclude_id=None)
    db.session.add(view)
    db.session.commit()
    return jsonify(view.to_dict()), 201


@saved_views_bp.get('/<int:view_id>')
@jwt_required()
def get_view(view_id):
    view = _filtered_query().filter_by(id=view_id).first()
    if not view:
        return jsonify({"error": "View not found"}), 404
    current_user = int(get_jwt_identity())
    if view.created_by != current_user:
        return jsonify({"error": "Only the owner can access this view"}), 403
    return jsonify(view.to_dict()), 200


@saved_views_bp.put('/<int:view_id>')
@jwt_required()
def update_view(view_id):
    view = _filtered_query().filter_by(id=view_id).first()
    if not view:
        return jsonify({"error": "View not found"}), 404
    current_user = int(get_jwt_identity())
    if view.created_by != current_user:
        return jsonify({"error": "Only the owner can edit this view"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name cannot be empty"}), 400
        view.name = name
    if "object_type" in data:
        object_type = (data.get("object_type") or "").lower()
        if object_type not in VALID_OBJECT_TYPES:
            return jsonify({"error": "Invalid object_type"}), 400
        view.object_type = object_type
    if "filters" in data:
        view.filters_json = data.get("filters")
    if "sort" in data:
        view.sort_json = data.get("sort")
    if "visible_columns" in data:
        view.visible_columns_json = data.get("visible_columns")
    if "is_default" in data:
        new_default = bool(data.get("is_default"))
        if new_default and not view.is_default:
            _clear_default(view.workspace_id, current_user, view.object_type, exclude_id=view.id)
        view.is_default = new_default

    db.session.commit()
    return jsonify(view.to_dict()), 200


@saved_views_bp.delete('/<int:view_id>')
@jwt_required()
def delete_view(view_id):
    view = _filtered_query().filter_by(id=view_id).first()
    if not view:
        return jsonify({"error": "View not found"}), 404
    current_user = int(get_jwt_identity())
    if view.created_by != current_user:
        return jsonify({"error": "Only the owner can delete this view"}), 403
    db.session.delete(view)
    db.session.commit()
    return jsonify({"deleted": True}), 200


def _clear_default(workspace_id, user_id, object_type, exclude_id):
    """Ensure only one default view per (user, workspace, object_type)."""
    query = View.query.filter_by(
        created_by=user_id,
        object_type=object_type,
        is_default=True,
    )
    if workspace_id is not None:
        query = query.filter_by(workspace_id=workspace_id)
    if exclude_id is not None:
        query = query.filter(View.id != exclude_id)
    for v in query.all():
        v.is_default = False

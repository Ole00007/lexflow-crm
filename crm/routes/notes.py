from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db, limiter
from ..models.note import Note
from ..activity_logger import log_activity
from ..workspace import get_current_workspace_id
from ..models.case import Case
from ..models.contact import Contact
from ..models.task import Task

notes_bp = Blueprint('notes', __name__, url_prefix='/api/notes')
VALID_TARGET_TYPES = {"case", "contact", "task"}

def _resolve_target(target_type, target_id):
    model_map = {"case": Case, "contact": Contact, "task": Task}
    model_cls = model_map.get(target_type)
    if not model_cls: return None
    return model_cls.query.filter_by(id=target_id, is_deleted=False).first()

def _filtered_query():
    q = Note.query.order_by(Note.created_at.desc())
    wid = get_current_workspace_id()
    if wid is not None:
        q = q.filter_by(workspace_id=wid)
    return q

@notes_bp.get('/')
@jwt_required()
@limiter.limit("60 per minute")
def get_notes():
    target_type = request.args.get("target_type")
    target_id = request.args.get("target_id", type=int)
    query = _filtered_query()
    if target_type and target_id:
        if target_type not in VALID_TARGET_TYPES:
            return jsonify({"error": f"Invalid target_type"}), 400
        query = query.filter_by(target_type=target_type, target_id=target_id)
    return jsonify([n.to_dict() for n in query.all()]), 200

@notes_bp.post('/')
@jwt_required()
@limiter.limit("30 per minute")
def create_note():
    data = request.get_json()
    if not data: return jsonify({"error": "No data provided"}), 400
    target_type = data.get("target_type", "").lower()
    target_id = data.get("target_id")
    content = data.get("content", "").strip()
    if target_type not in VALID_TARGET_TYPES:
        return jsonify({"error": f"Invalid target_type"}), 400
    if not target_id: return jsonify({"error": "target_id is required"}), 400
    if not content: return jsonify({"error": "content is required"}), 400
    target = _resolve_target(target_type, target_id)
    if not target: return jsonify({"error": f"{target_type.capitalize()} not found"}), 404
    author_id = int(get_jwt_identity())
    note = Note(workspace_id=get_current_workspace_id() or 1, author_id=author_id, target_type=target_type, target_id=target_id, content=content)
    db.session.add(note)
    db.session.commit()
    log_activity(author_id, target_type, target_id, "note_added", f"Note added to {target_type}")
    return jsonify(note.to_dict()), 201

@notes_bp.put('/<int:note_id>')
@jwt_required()
def update_note(note_id):
    note = _filtered_query().filter_by(id=note_id).first()
    if not note: return jsonify({"error": "Note not found"}), 404
    current_user = int(get_jwt_identity())
    if note.author_id != current_user: return jsonify({"error": "Only the author can edit this note"}), 403
    data = request.get_json()
    if not data or "content" not in data: return jsonify({"error": "content is required"}), 400
    note.content = data["content"].strip()
    db.session.commit()
    return jsonify(note.to_dict()), 200

@notes_bp.delete('/<int:note_id>')
@jwt_required()
def delete_note(note_id):
    note = _filtered_query().filter_by(id=note_id).first()
    if not note: return jsonify({"error": "Note not found"}), 404
    current_user = int(get_jwt_identity())
    if note.author_id != current_user: return jsonify({"error": "Only the author can delete this note"}), 403
    db.session.delete(note)
    db.session.commit()
    return jsonify({"deleted": True}), 200
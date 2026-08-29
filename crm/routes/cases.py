from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models.case import Case
from ..models.contact import Contact
from ..activity_logger import log_activity
from ..workspace import get_current_workspace_id, workspace_filter
from datetime import date, datetime

cases_bp = Blueprint("cases", __name__, url_prefix="/api/cases")

def _get_actor_id():
    try:
        uid = get_jwt_identity()
        return int(uid) if uid else None
    except Exception:
        return None

def _filtered_query():
    # superadmin sees all workspaces (workspace_filter bypasses for superadmin)
    return workspace_filter(Case.query.filter_by(is_deleted=False), Case)

@cases_bp.get('')
@jwt_required(optional=True)
def get_cases():
    query = _filtered_query()
    # Kanban fetches per-column: /api/cases?status=Intake etc.
    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)
    cases = query.order_by(Case.id.desc()).all()
    return jsonify([c.to_dict() for c in cases]), 200

@cases_bp.get('/<int:case_id>')
@jwt_required(optional=True)
def get_case(case_id):
    case = _filtered_query().filter_by(id=case_id).first()
    if not case:
        return jsonify({"error": "Case not found"}), 404
    return jsonify(case.to_dict()), 200

@cases_bp.post('')
@jwt_required()
def create_case():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    if not data.get("contactid"):
        return jsonify({"error": "contactid is required"}), 400
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    wid = get_current_workspace_id()

    contact = Contact.query.filter_by(id=data.get("contactid"), is_deleted=False).first()
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    case = Case(
        workspace_id=wid or 1,
        contactid=data.get("contactid"),
        ownerid=data.get("ownerid"),
        title=data.get("title"),
        casetype=data.get("casetype"),
        status=data.get("status", "Intake"),
        priority=data.get("priority", "Medium"),
        openedat=date.fromisoformat(data["openedat"]) if data.get("openedat") else date.today(),
        duedate=date.fromisoformat(data["duedate"]) if data.get("duedate") else None,
        assignedto=data.get("assignedto"),
    )
    db.session.add(case)
    db.session.commit()

    actor_id = _get_actor_id()
    log_activity(actor_id, "case", case.id, "created", f"Case '{case.title}' created")

    return jsonify(case.to_dict()), 201

@cases_bp.put('/<int:case_id>')
@jwt_required()
def update_case(case_id):
    case = _filtered_query().filter_by(id=case_id).first()
    if not case:
        return jsonify({"error": "Case not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    changes = []
    if "title" in data:
        case.title = data["title"]; changes.append("title")
    if "casetype" in data:
        case.casetype = data["casetype"]; changes.append("casetype")
    if "status" in data:
        old_status = case.status; case.status = data["status"]
        changes.append(f"status: {old_status} -> {data['status']}")
    if "priority" in data:
        case.priority = data["priority"]; changes.append(f"priority: {data['priority']}")
    if "openedat" in data:
        case.openedat = date.fromisoformat(data["openedat"]) if isinstance(data["openedat"], str) else data["openedat"]
        changes.append("openedat")
    if "duedate" in data:
        case.duedate = date.fromisoformat(data["duedate"]) if isinstance(data["duedate"], str) else data["duedate"]
        changes.append("duedate")
    if "assignedto" in data:
        case.assignedto = data["assignedto"]; changes.append("assignedto")
    if "contactid" in data:
        case.contactid = data["contactid"]; changes.append("contactid")

    if changes:
        actor_id = _get_actor_id()
        log_activity(actor_id, "case", case.id, "updated", f"Case '{case.title}' updated", details="; ".join(changes))

    db.session.commit()
    return jsonify(case.to_dict()), 200

@cases_bp.delete('/<int:case_id>')
def delete_case(case_id):
    case = _filtered_query().filter_by(id=case_id).first()
    if not case:
        return jsonify({"error": "Case not found"}), 404
    if case.is_deleted:
        return jsonify({"deleted": False, "message": "Case already deleted"}), 200

    case.is_deleted = True
    case.deleted_at = datetime.utcnow()
    db.session.commit()

    actor_id = _get_actor_id()
    log_activity(actor_id, "case", case.id, "deleted", f"Case '{case.title}' deleted")

    return jsonify({"deleted": True}), 200
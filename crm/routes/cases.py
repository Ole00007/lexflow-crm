from flask import Blueprint, jsonify, request
from ..extensions import db
from ..models.case import Case
from ..models.contact import Contact
from datetime import date, datetime

cases_bp = Blueprint("cases", __name__)

@cases_bp.get("/cases")
def get_cases():
    # Filter out deleted cases
    cases = Case.query.filter_by(is_deleted=False).order_by(Case.id.desc()).all()
    return jsonify([c.to_dict() for c in cases]), 200

@cases_bp.get("/cases/<int:case_id>")
def get_case(case_id):
    case = Case.query.filter_by(id=case_id, is_deleted=False).first()
    if not case:
        return jsonify({"error": "Case not found"}), 404
    return jsonify(case.to_dict()), 200

@cases_bp.post("/cases")
def create_case():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    if not data.get("contactid"):
        return jsonify({"error": "contactid is required"}), 400
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    contact = Contact.query.filter_by(id=data.get("contactid"), is_deleted=False).first()
    if not contact:
        return jsonify({"error": "contact not found"}), 404

    case = Case(
        contactid=data.get("contactid"),
        ownerid=data.get("ownerid"),
        title=data.get("title"),
        casetype=data.get("casetype"),
        status=data.get("status", "Intake"),
        priority=data.get("priority", "Medium"),
        openedat=date.fromisoformat(data["openedat"]) if data.get("openedat") else date.today(),
        duedate=date.fromisoformat(data["duedate"]) if data.get("duedate") else None,
        assignedto=data.get("assignedto")
    )
    db.session.add(case)
    db.session.commit()
    return jsonify(case.to_dict()), 201

@cases_bp.put("/cases/<int:case_id>")
def update_case(case_id):
    case = Case.query.filter_by(id=case_id, is_deleted=False).first()
    if not case:
        return jsonify({"error": "Case not found"}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Update case fields
    if "title" in data:
        case.title = data["title"]
    if "casetype" in data:
        case.casetype = data["casetype"]
    if "status" in data:
        case.status = data["status"]
    if "priority" in data:
        case.priority = data["priority"]
    if "duedate" in data:
        case.duedate = date.fromisoformat(data["duedate"]) if data["duedate"] else None
    if "assignedto" in data:
        case.assignedto = data["assignedto"]
    
    db.session.commit()
    return jsonify(case.to_dict()), 200

@cases_bp.delete("/cases/<int:case_id>")
def delete_case(case_id):
    case = Case.query.filter_by(id=case_id, is_deleted=False).first()
    if not case:
        return jsonify({"error": "Case not found"}), 404
    
    # Soft delete
    case.is_deleted = True
    case.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"deleted": True}), 200

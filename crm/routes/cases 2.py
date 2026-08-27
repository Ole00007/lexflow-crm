from flask import Blueprint, jsonify, request
from ..extensions import db, limiter
from ..models.case import Case
from ..models.contact import Contact
from ..validators import validate_string, validate_date, validate_enum, validate_integer
from datetime import date, datetime

cases_bp = Blueprint("cases", __name__, url_prefix="/api")

VALID_STATUS = ["Intake", "Active", "Closed", "On Hold"]
VALID_PRIORITY = ["Low", "Medium", "High", "Critical"]

@cases_bp.get("/cases")
@limiter.limit("60 per minute")
def get_cases():
    """Get all active cases"""
    cases = Case.query.filter_by(is_deleted=False).order_by(Case.id.desc()).all()
    return jsonify([c.to_dict() for c in cases]), 200

@cases_bp.get("/cases/<int:case_id>")
@limiter.limit("60 per minute")
def get_case(case_id):
    """Get case by ID"""
    case = Case.query.filter_by(id=case_id, is_deleted=False).first()
    if not case:
        return jsonify({"error": "Case not found"}), 404
    return jsonify(case.to_dict()), 200

@cases_bp.post("/cases")
@limiter.limit("30 per minute")
def create_case():
    """Create a new case"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    
    # Validate contactid
    is_valid, msg = validate_integer(data.get("contactid"), "contactid", required=True)
    if not is_valid:
        return jsonify({"error": msg}), 400
    
    # Validate title
    is_valid, title = validate_string(data.get("title"), "title", min_length=3, max_length=255, required=True)
    if not is_valid:
        return jsonify({"error": title}), 400
    
    # Verify contact exists
    contact = Contact.query.filter_by(id=data.get("contactid"), is_deleted=False).first()
    if not contact:
        return jsonify({"error": "Contact not found"}), 404
    
    # Validate optional casetype
    casetype = None
    if data.get("casetype"):
        is_valid, ct_val = validate_string(data.get("casetype"), "casetype", min_length=1, max_length=100, required=False)
        if not is_valid:
            return jsonify({"error": ct_val}), 400
        casetype = ct_val
    
    # Validate status
    status = data.get("status", "Intake")
    is_valid, status_val = validate_enum(status, "status", VALID_STATUS, required=False)
    if not is_valid:
        return jsonify({"error": status_val}), 400
    
    # Validate priority
    priority = data.get("priority", "Medium")
    is_valid, priority_val = validate_enum(priority, "priority", VALID_PRIORITY, required=False)
    if not is_valid:
        return jsonify({"error": priority_val}), 400
    
    # Validate dates
    is_valid, openedat = validate_date(data.get("openedat"), "openedat", required=False)
    if not is_valid:
        return jsonify({"error": openedat}), 400
    if not openedat:
        openedat = date.today()
    
    is_valid, duedate = validate_date(data.get("duedate"), "duedate", required=False)
    if not is_valid:
        return jsonify({"error": duedate}), 400
    
    # Validate assignedto if provided
    assignedto = None
    if data.get("assignedto"):
        is_valid, at_val = validate_integer(data.get("assignedto"), "assignedto", required=False)
        if not is_valid:
            return jsonify({"error": at_val}), 400
        assignedto = at_val
    
    case = Case(
        contactid=data.get("contactid"),
        ownerid=data.get("ownerid"),
        title=title,
        casetype=casetype,
        status=status_val,
        priority=priority_val,
        openedat=openedat,
        duedate=duedate,
        assignedto=assignedto
    )
    db.session.add(case)
    db.session.commit()
    return jsonify(case.to_dict()), 201

@cases_bp.put("/cases/<int:case_id>")
@limiter.limit("30 per minute")
def update_case(case_id):
    """Update case"""
    case = Case.query.filter_by(id=case_id, is_deleted=False).first()
    if not case:
        return jsonify({"error": "Case not found"}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    
    # Update title with validation
    if "title" in data:
        if data["title"] is not None:
            is_valid, title = validate_string(data["title"], "title", min_length=3, max_length=255, required=True)
            if not is_valid:
                return jsonify({"error": title}), 400
            case.title = title
    
    # Update casetype with validation
    if "casetype" in data:
        if data["casetype"] is not None:
            is_valid, ct_val = validate_string(data["casetype"], "casetype", min_length=1, max_length=100, required=False)
            if not is_valid:
                return jsonify({"error": ct_val}), 400
            case.casetype = ct_val
    
    # Update status with validation
    if "status" in data:
        is_valid, status_val = validate_enum(data["status"], "status", VALID_STATUS, required=False)
        if not is_valid:
            return jsonify({"error": status_val}), 400
        case.status = status_val
    
    # Update priority with validation
    if "priority" in data:
        is_valid, priority_val = validate_enum(data["priority"], "priority", VALID_PRIORITY, required=False)
        if not is_valid:
            return jsonify({"error": priority_val}), 400
        case.priority = priority_val
    
    # Update duedate with validation
    if "duedate" in data:
        is_valid, duedate = validate_date(data["duedate"], "duedate", required=False)
        if not is_valid:
            return jsonify({"error": duedate}), 400
        case.duedate = duedate
    
    # Update assignedto with validation
    if "assignedto" in data:
        if data["assignedto"] is not None:
            is_valid, at_val = validate_integer(data["assignedto"], "assignedto", required=False)
            if not is_valid:
                return jsonify({"error": at_val}), 400
            case.assignedto = at_val
        else:
            case.assignedto = None
    
    db.session.commit()
    return jsonify(case.to_dict()), 200

@cases_bp.delete("/cases/<int:case_id>")
@limiter.limit("30 per minute")
def delete_case(case_id):
    """Soft delete case"""
    case = Case.query.filter_by(id=case_id, is_deleted=False).first()
    if not case:
        return jsonify({"error": "Case not found"}), 404
    
    # Soft delete
    case.is_deleted = True
    case.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"deleted": True}), 200


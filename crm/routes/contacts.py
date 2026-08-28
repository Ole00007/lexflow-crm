from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models.contact import Contact
from ..models.user import User
from ..activity_logger import log_activity
from ..workspace import get_current_workspace_id
from datetime import datetime

contacts_bp = Blueprint('contacts', __name__, url_prefix='/api/contacts')

def _get_actor_id():
    try:
        uid = get_jwt_identity()
        return int(uid) if uid else None
    except Exception:
        return None

def _filtered_query():
    q = Contact.query.filter_by(is_deleted=False)
    try:
        uid = get_jwt_identity()
        if uid:
            user = db.session.get(User, int(uid))
            if user and user.workspace_id:
                q = q.filter_by(workspace_id=user.workspace_id)
    except Exception:
        pass
    return q

@contacts_bp.get('')
@jwt_required(optional=True)
def get_contacts():
    contacts = _filtered_query().order_by(Contact.id.desc()).all()
    return jsonify([c.to_dict() for c in contacts]), 200

@contacts_bp.get('/<int:contact_id>')
@jwt_required(optional=True)
def get_contact(contact_id):
    contact = _filtered_query().filter_by(id=contact_id).first()
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404
    return jsonify(contact.to_dict()), 200

@contacts_bp.post('')
@jwt_required()
def create_contact():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    if not data.get('full_name'):
        return jsonify({'error': 'full_name is required'}), 400

    wid = get_current_workspace_id()
    if wid is None:
        return jsonify({'error': 'Authentication required to create contacts'}), 401

    contact = Contact(
        workspace_id=wid,
        ownerid=data.get('ownerid'),
        fullname=data.get('full_name'),
        email=data.get('email'),
        phone=data.get('phone'),
        company=data.get('company'),
        status=data.get('status', 'lead'),
        notes=data.get('notes'),
    )
    db.session.add(contact)
    db.session.commit()

    actor_id = _get_actor_id()
    log_activity(actor_id, "contact", contact.id, "created", f"Contact '{contact.fullname}' created")

    return jsonify(contact.to_dict()), 201

@contacts_bp.put('/<int:contact_id>')
@jwt_required()
def update_contact(contact_id):
    contact = _filtered_query().filter_by(id=contact_id).first()
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    changes = []
    for field, attr in [('full_name', 'fullname'), ('email', 'email'), ('phone', 'phone'),
                         ('company', 'company'), ('status', 'status'), ('notes', 'notes')]:
        if field in data:
            setattr(contact, attr, data[field])
            changes.append(f"{field}")

    if changes:
        actor_id = _get_actor_id()
        log_activity(actor_id, "contact", contact.id, "updated", f"Contact '{contact.fullname}' updated: {', '.join(changes)}")

    db.session.commit()
    return jsonify(contact.to_dict()), 200

@contacts_bp.delete('/<int:contact_id>')
@jwt_required()
def delete_contact(contact_id):
    contact = _filtered_query().filter_by(id=contact_id).first()
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404
    if contact.is_deleted:
        return jsonify({'deleted': False, 'message': 'Contact already deleted'}), 200

    contact.is_deleted = True
    contact.deleted_at = datetime.utcnow()
    db.session.commit()

    actor_id = _get_actor_id()
    log_activity(actor_id, "contact", contact.id, "deleted", f"Contact '{contact.fullname}' deleted")

    return jsonify({'deleted': True}), 200
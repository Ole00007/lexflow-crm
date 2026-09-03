from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models.contact import Contact, VALID_LIFECYCLE_STAGES
from ..models.user import User
from ..activity_logger import log_activity
from ..workspace import get_current_workspace_id, workspace_filter
from datetime import datetime
import json

contacts_bp = Blueprint('contacts', __name__, url_prefix='/api/contacts')

def _get_actor_id():
    try:
        uid = get_jwt_identity()
        return int(uid) if uid else None
    except Exception:
        return None

def _filtered_query():
    # superadmin sees all workspaces (workspace_filter bypasses for superadmin)
    return workspace_filter(Contact.query.filter_by(is_deleted=False), Contact)

@contacts_bp.get('')
@jwt_required(optional=True)
def get_contacts():
    contacts = _filtered_query().order_by(Contact.id.desc()).all()
    out = []
    for c in contacts:
        d = c.to_dict()
        d['suggested_status'] = _suggest_contact_status(c)
        out.append(d)
    return jsonify(out), 200


def _suggest_contact_status(contact):
    """Suggested contact status — a HINT only. Staff always makes the final call.
    - has an open (non-Closed) case  -> 'active'
    - all cases Closed / none open    -> 'passive'
    - no cases at all                 -> 'lead'
    """
    from ..models.case import Case
    try:
        open_cases = Case.query.filter_by(contactid=contact.id, is_deleted=False) \
            .filter(Case.status != 'Closed').count()
        total_cases = Case.query.filter_by(contactid=contact.id, is_deleted=False).count()
        if open_cases and open_cases > 0:
            return 'active'
        if total_cases and total_cases > 0:
            return 'passive'
        return 'lead'
    except Exception:
        return 'lead'

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
        lifecycle_stage=data.get('lifecycle_stage') or 'lead',
    )
    if contact.lifecycle_stage not in VALID_LIFECYCLE_STAGES:
        return jsonify({'error': f"lifecycle_stage must be one of: {', '.join(VALID_LIFECYCLE_STAGES)}"}), 400
    if 'tags' in data and data['tags'] is not None:
        tags = data['tags']
        if isinstance(tags, list):
            contact.tags = json.dumps(tags)
        elif isinstance(tags, str):
            contact.tags = tags
    if 'updated_at' in data and data['updated_at']:
        try:
            contact.updated_at = datetime.fromisoformat(str(data['updated_at']).replace('Z', ''))
        except ValueError:
            pass
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

    if 'lifecycle_stage' in data:
        ls = (data.get('lifecycle_stage') or 'lead').strip()
        if ls not in VALID_LIFECYCLE_STAGES:
            return jsonify({'error': f"lifecycle_stage must be one of: {', '.join(VALID_LIFECYCLE_STAGES)}"}), 400
        contact.lifecycle_stage = ls
        changes.append("lifecycle_stage")
    if 'tags' in data:
        tags = data['tags']
        if isinstance(tags, list):
            contact.tags = json.dumps(tags)
        elif isinstance(tags, str):
            contact.tags = tags
        changes.append("tags")
    if changes:
        contact.updated_at = datetime.utcnow()
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
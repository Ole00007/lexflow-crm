from flask import Blueprint, jsonify, request
from ..extensions import db
from ..models.contact import Contact

contacts_bp = Blueprint('contacts', __name__)

@contacts_bp.get('/contacts')
def get_contacts():
    contacts = Contact.query.order_by(Contact.id.desc()).all()
    return jsonify([c.to_dict() for c in contacts]), 200

@contacts_bp.post('/contacts')
def create_contact():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    if not data.get('full_name'):
        return jsonify({'error': 'full_name is required'}), 400

    contact = Contact(
        ownerid=data.get('ownerid'),
        fullname=data.get('full_name'),
        email=data.get('email'),
        phone=data.get('phone'),
        company=data.get('company'),
        status=data.get('status', 'lead'),
        notes=data.get('notes')
    )
    db.session.add(contact)
    db.session.commit()
    return jsonify(contact.to_dict()), 201

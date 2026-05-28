from flask import Blueprint, jsonify
from ..models.contact import Contact

contacts_bp = Blueprint("contacts", __name__)

@contacts_bp.get("/contacts")
def get_contacts():
    contacts = Contact.query.order_by(Contact.id.desc()).all()
    return jsonify([contact.to_dict() for contact in contacts]), 200

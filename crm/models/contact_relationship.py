from ..extensions import db
from datetime import datetime

class ContactRelationship(db.Model):
    __tablename__ = "contact_relationships"

    id = db.Column(db.Integer, primary_key=True)
    contact_id_a = db.Column(db.Integer, db.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    contact_id_b = db.Column(db.Integer, db.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    relationship_type = db.Column(db.String(100), nullable=False)  # e.g., "spouse", "partner", "employee", "client", "opposing_counsel"
    notes = db.Column(db.Text, nullable=True)
    createdat = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updatedat = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    contact_a = db.relationship("Contact", foreign_keys=[contact_id_a], backref=db.backref("relationships_as_a", lazy=True, cascade="all, delete-orphan"))
    contact_b = db.relationship("Contact", foreign_keys=[contact_id_b], backref=db.backref("relationships_as_b", lazy=True, cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            "id": self.id,
            "contact_id_a": self.contact_id_a,
            "contact_id_b": self.contact_id_b,
            "relationship_type": self.relationship_type,
            "notes": self.notes,
            "createdat": self.createdat.isoformat() if self.createdat else None,
            "updatedat": self.updatedat.isoformat() if self.updatedat else None,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None
        }

from ..extensions import db
from datetime import datetime
import json

VALID_LIFECYCLE_STAGES = ('lead', 'prospect', 'client', 'churned')


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=True)
    ownerid = db.Column(db.Integer, nullable=True)
    fullname = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    company = db.Column(db.String(255), nullable=True)
    source = db.Column(db.String(20), nullable=False, default="manual")  # manual, intake, booking, web, import
    status = db.Column(db.String(50), nullable=True, default="lead")
    notes = db.Column(db.Text, nullable=True)
    gdpr_consent = db.Column(db.Boolean, nullable=False, default=False)
    gdpr_consent_ts = db.Column(db.DateTime, nullable=True)
    lifecycle_stage = db.Column(db.String(20), nullable=True, default='lead')
    tags = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    workspace = db.relationship("Workspace", backref=db.backref("contacts", lazy=True))

    def _parse_tags(self):
        if not self.tags:
            return []
        try:
            parsed = json.loads(self.tags)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "ownerid": self.ownerid,
            "fullname": self.fullname,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "source": self.source,
            "status": self.status,
            "notes": self.notes,
            "gdpr_consent": self.gdpr_consent,
            "gdpr_consent_ts": self.gdpr_consent_ts.isoformat() if self.gdpr_consent_ts else None,
            "lifecycle_stage": self.lifecycle_stage,
            "tags": self._parse_tags(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
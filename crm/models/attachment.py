from ..extensions import db


class Attachment(db.Model):
    """Files (allegati) attached to CRM records via polymorphic target_type + target_id."""
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), unique=True, nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    target_type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    workspace = db.relationship("Workspace", backref=db.backref("attachments", lazy=True))
    uploader = db.relationship("User", backref=db.backref("attachments", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "filename": self.filename,
            "stored_name": self.stored_name,
            "filepath": self.filepath,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "uploaded_by": self.uploaded_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

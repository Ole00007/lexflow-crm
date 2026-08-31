from ..extensions import db
from datetime import datetime

class Workspace(db.Model):
    """Multi-tenant workspace — isolates data per client.

    Sub-workspaces (parent_workspace_id set) are child spaces under a client
    workspace, e.g. 3 client sub-spaces inside romanelli-studio. A parent
    admin sees their own + sub-workspace data; a sub-workspace admin sees
    only their own.
    """
    __tablename__ = "workspaces"

    id = db.Column(db.Integer, primary_key=True)
    parent_workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    code_prefix = db.Column(db.String(5), nullable=True)  # per-tenant case-ID prefix, e.g. R / P / A / F
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    parent = db.relationship("Workspace", remote_side=[id], backref=db.backref("sub_workspaces", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "parent_workspace_id": self.parent_workspace_id,
            "name": self.name,
            "slug": self.slug,
            "code_prefix": self.code_prefix,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
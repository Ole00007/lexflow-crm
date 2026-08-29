from ..extensions import db
from datetime import datetime


class View(db.Model):
    """A user's saved list/filter configuration (Viste salvate).

    Stores the persisted state of a CRM list view: the object type it applies
    to (case/contact/task), the applied filters, sorting and visible columns,
    plus a flag to mark it as the user's default view.
    """
    __tablename__ = "views"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    object_type = db.Column(db.String(50), nullable=False)
    filters_json = db.Column(db.JSON, nullable=True)
    sort_json = db.Column(db.JSON, nullable=True)
    visible_columns_json = db.Column(db.JSON, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("'0'"))
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    creator = db.relationship("User", backref=db.backref("views", lazy=True))
    workspace = db.relationship("Workspace", backref=db.backref("views", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "object_type": self.object_type,
            "filters": self.filters_json,
            "sort": self.sort_json,
            "visible_columns": self.visible_columns_json,
            "created_by": self.created_by,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

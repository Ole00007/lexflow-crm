from ..extensions import db
from datetime import datetime

class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False)
    caseid = db.Column(db.Integer, db.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    userid = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default="pending")
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    duedate = db.Column(db.Date, nullable=True)
    createdat = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updatedat = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    case = db.relationship("Case", backref=db.backref("tasks", lazy=True, passive_deletes=True))
    user = db.relationship("User", backref=db.backref("tasks", lazy=True, passive_deletes=True))
    workspace = db.relationship("Workspace", backref=db.backref("tasks", lazy=True))

    def to_dict(self):
        def _iso(v):
            try:
                return v.isoformat() if v else None
            except Exception:
                return None
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "caseid": self.caseid,
            "userid": self.userid,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "duedate": _iso(self.duedate),
            "createdat": _iso(self.createdat),
            "updatedat": _iso(self.updatedat),
            "is_deleted": self.is_deleted,
            "deleted_at": _iso(self.deleted_at),
        }
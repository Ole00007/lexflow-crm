from ..extensions import db
from datetime import datetime

class ActivityLog(db.Model):
    """Auto-logged activity timeline for case/contact/task changes."""
    __tablename__ = "activity_log"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    target_type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(50), nullable=False)
    summary = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    actor = db.relationship("User", backref=db.backref("activities", lazy=True))
    workspace = db.relationship("Workspace", backref=db.backref("activity_log", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "actor_id": self.actor_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "action": self.action,
            "summary": self.summary,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
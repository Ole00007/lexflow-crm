from datetime import datetime

from ..extensions import db


class AgentPolicy(db.Model):
    """Per-workspace switch for event-driven draft generation. require_review is always true."""
    __tablename__ = "agent_policies"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True)
    event_key = db.Column(db.String(64), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    require_review = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    max_per_day = db.Column(db.Integer, nullable=False, default=3, server_default="3")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("workspace_id", "event_key", name="uq_agent_policy_ws_event"),)

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "event_key": self.event_key,
            "enabled": bool(self.enabled),
            "require_review": True,
            "max_per_day": self.max_per_day,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

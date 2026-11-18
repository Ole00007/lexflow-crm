from datetime import datetime

from ..extensions import db


class AgentDelegation(db.Model):
    """A human granting a named agent the right to propose drafts (scoped, expiring, revocable)."""
    __tablename__ = "agent_delegations"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    to_agent = db.Column(db.String(64), nullable=False)
    scope = db.Column(db.Text, nullable=True)  # JSON: {"target_types":[..],"target_ids":[..]} or "*"
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def is_active(self, now=None):
        now = now or datetime.utcnow()
        return self.revoked_at is None and self.expires_at > now

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "from_user_id": self.from_user_id,
            "to_agent": self.to_agent,
            "scope": self.scope,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

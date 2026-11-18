from datetime import datetime, timedelta

from ..extensions import db

DRAFT_TTL_DAYS = 7


def _iso(value):
    """ISO-8601 with an explicit UTC marker.

    DB timestamps are naive UTC; browsers parse a naive string as LOCAL time, so
    every rendered time was one hour off in CET. Append 'Z' when no offset.
    """
    if not value:
        return None
    return value.isoformat() + ('' if value.tzinfo is not None else 'Z')


class AgentDraft(db.Model):
    """Agent-proposed text. Agents write ONLY here; a human accept promotes it to `notes`."""
    __tablename__ = "agent_drafts"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True)
    target_type = db.Column(db.String(50), nullable=False)  # workspace | task | case | contact
    target_id = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    origin = db.Column(db.String(20), nullable=False)  # human_request | superior_agent | event_rule
    requested_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_by_agent = db.Column(db.String(64), nullable=True)
    evidence = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="proposed")  # draft|proposed|accepted|rejected|expired
    policy_id = db.Column(db.Integer, db.ForeignKey("agent_policies.id"), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.utcnow() + timedelta(days=DRAFT_TTL_DAYS))
    decided_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at = db.Column(db.DateTime, nullable=True)
    note_id = db.Column(db.Integer, db.ForeignKey("notes.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.Index("ix_agent_drafts_target", "workspace_id", "target_type", "target_id"),)

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "content": self.content,
            "origin": self.origin,
            "requested_by": self.requested_by,
            "requested_by_agent": self.requested_by_agent,
            "evidence": self.evidence,
            "status": self.status,
            "expires_at": _iso(self.expires_at),
            "created_at": _iso(self.created_at),
            "note_id": self.note_id,
        }

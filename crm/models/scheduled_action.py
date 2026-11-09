from ..extensions import db

# Lifecycle: pending -> processing -> done | failed | suppressed ; pending -> cancelled
STATES = ("pending", "processing", "done", "failed", "suppressed", "cancelled")


class ScheduledAction(db.Model):
    """Event-driven delay engine row (T-009). One row = one action due at `due_at`.

    Extensible for the T-013/T-018 AI decision layer: `kind` selects the handler,
    `source` records who enqueued it ('rule' | 'ai' | 'manual'), `payload` is free
    JSON for handler args, so new kinds need no schema change.
    `suppression_key` groups actions that must be cancelled together
    (e.g. "contact:5:drip" when the contact replies).
    """

    __tablename__ = "scheduled_actions"
    __table_args__ = (db.Index("ix_scheduled_actions_state_due", "state", "due_at"),)

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True)
    kind = db.Column(db.String(64), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True, index=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    channel = db.Column(db.String(20), nullable=True)      # 'email' | 'whatsapp' | ... (for should_notify)
    notif_type = db.Column(db.String(32), nullable=True)   # 'transactional' | 'marketing'
    due_at = db.Column(db.DateTime, nullable=False)
    state = db.Column(db.String(16), nullable=False, default="pending")
    attempts = db.Column(db.Integer, nullable=False, default=0)
    max_attempts = db.Column(db.Integer, nullable=False, default=3)
    suppression_key = db.Column(db.String(128), nullable=True, index=True)
    source = db.Column(db.String(16), nullable=False, default="rule")
    payload = db.Column(db.Text, nullable=True)
    last_error = db.Column(db.Text, nullable=True)
    locked_at = db.Column(db.DateTime, nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

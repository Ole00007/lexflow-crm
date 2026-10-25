from ..extensions import db


class NotifyConsent(db.Model):
    """Per-recipient opt-in for outbound notifications (GDPR consent record).

    A real send is allowed ONLY when a matching row has granted=True for the
    (member, channel) pair. Stores who granted it, when, and on which channel.

    `telegram_chat_id` is the delivery target captured out of band when the team
    member starts the LexFlow Telegram bot (the deep-link flow). Without it a real
    Telegram send cannot be addressed, so the send path returns an error rather
    than guessing. It is never echoed back raw by to_dict() (PII minimisation).
    """

    __tablename__ = "notify_consents"
    __table_args__ = (
        db.UniqueConstraint("member_id", "channel", name="uq_notify_consent_member_channel"),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(
        db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True
    )
    member_id = db.Column(
        db.Integer,
        db.ForeignKey("firm_team_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel = db.Column(db.String(20), nullable=False)  # 'telegram' | 'whatsapp'
    granted = db.Column(db.Boolean, nullable=False, default=False)
    telegram_chat_id = db.Column(db.String(64), nullable=True)
    consented_by = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )
    consented_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "member_id": self.member_id,
            "channel": self.channel,
            "granted": self.granted,
            "has_target": bool(self.telegram_chat_id),  # never leak the raw chat id
            "consented_by": self.consented_by,
            "consented_at": self.consented_at.isoformat() if self.consented_at else None,
        }

from ..extensions import db
from datetime import datetime

class Event(db.Model):
    """Events from chatbot interactions and external integrations."""
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False)
    caseid = db.Column(db.Integer, db.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_type = db.Column(db.String(50), nullable=False, default="note")
    event_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    case = db.relationship("Case", backref=db.backref("events", lazy=True, passive_deletes=True))
    workspace = db.relationship("Workspace", backref=db.backref("events", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "caseid": self.caseid,
            "title": self.title,
            "description": self.description,
            "event_type": self.event_type,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
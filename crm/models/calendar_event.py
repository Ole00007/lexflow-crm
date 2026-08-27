from ..extensions import db
from datetime import datetime

class CalendarEvent(db.Model):
    """Legal calendar events — hearings, court dates, filing deadlines, meetings."""
    __tablename__ = "calendar_events"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False)
    caseid = db.Column(db.Integer, db.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True)
    contactid = db.Column(db.Integer, db.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    ownerid = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Legal-specific fields
    event_type = db.Column(db.String(50), nullable=False, default="hearing")

    location = db.Column(db.String(255), nullable=True)
    court_name = db.Column(db.String(255), nullable=True)
    judge_name = db.Column(db.String(255), nullable=True)

    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=True)
    is_all_day = db.Column(db.Boolean, nullable=False, default=False)

    status = db.Column(db.String(50), nullable=False, default="scheduled")

    notes = db.Column(db.Text, nullable=True)

    createdat = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updatedat = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    workspace = db.relationship("Workspace", backref=db.backref("calendar_events", lazy=True))
    case = db.relationship("Case", backref=db.backref("calendar_events", lazy=True, passive_deletes=True))
    contact = db.relationship("Contact", backref=db.backref("calendar_events", lazy=True))
    owner = db.relationship("User", backref=db.backref("calendar_events", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "caseid": self.caseid,
            "contactid": self.contactid,
            "ownerid": self.ownerid,
            "title": self.title,
            "description": self.description,
            "event_type": self.event_type,
            "location": self.location,
            "court_name": self.court_name,
            "judge_name": self.judge_name,
            "start_datetime": self.start_datetime.isoformat() if self.start_datetime else None,
            "end_datetime": self.end_datetime.isoformat() if self.end_datetime else None,
            "is_all_day": self.is_all_day,
            "status": self.status,
            "notes": self.notes,
            "createdat": self.createdat.isoformat() if self.createdat else None,
            "updatedat": self.updatedat.isoformat() if self.updatedat else None,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }
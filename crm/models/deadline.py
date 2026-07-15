from ..extensions import db
from datetime import datetime

class Deadline(db.Model):
    __tablename__ = "deadlines"

    id = db.Column(db.Integer, primary_key=True)
    caseid = db.Column(db.Integer, db.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    deadline_date = db.Column(db.Date, nullable=False)
    deadline_type = db.Column(db.String(50), nullable=False)  # e.g., "filing", "response", "hearing", "discovery"
    status = db.Column(db.String(50), nullable=False, default="pending")  # pending, completed, missed, waived
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    createdat = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updatedat = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    case = db.relationship("Case", backref=db.backref("deadlines", lazy=True, passive_deletes=True))

    def to_dict(self):
        return {
            "id": self.id,
            "caseid": self.caseid,
            "title": self.title,
            "description": self.description,
            "deadline_date": self.deadline_date.isoformat() if self.deadline_date else None,
            "deadline_type": self.deadline_type,
            "status": self.status,
            "priority": self.priority,
            "createdat": self.createdat.isoformat() if self.createdat else None,
            "updatedat": self.updatedat.isoformat() if self.updatedat else None,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None
        }

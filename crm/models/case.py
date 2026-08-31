from ..extensions import db
from datetime import date

class Case(db.Model):
    __tablename__ = "cases"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False)
    contactid = db.Column(db.Integer, db.ForeignKey("contacts.id", ondelete="RESTRICT"), nullable=False)
    ownerid = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(255), nullable=False)
    casetype = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), nullable=False, default="Intake")
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    openedat = db.Column(db.Date, nullable=False, default=date.today)
    duedate = db.Column(db.Date, nullable=True)
    assignedto = db.Column(db.Integer, nullable=True)
    case_no = db.Column(db.String(20), nullable=True)  # per-workspace display ID, e.g. R-01 (NEW cases only)
    createdat = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updatedat = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    contact = db.relationship("Contact", backref=db.backref("cases", lazy=True, passive_deletes=True))
    workspace = db.relationship("Workspace", backref=db.backref("cases", lazy=True))

    def display_id(self):
        """Human-facing case ID: per-workspace code (R-01) for new cases,
        or legacy internal id (e.g. #6) for pre-existing ones."""
        return self.case_no or f"#{self.id}"

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "contactid": self.contactid,
            "ownerid": self.ownerid,
            "title": self.title,
            "casetype": self.casetype,
            "status": self.status,
            "priority": self.priority,
            "openedat": self.openedat.isoformat() if self.openedat else None,
            "duedate": self.duedate.isoformat() if self.duedate else None,
            "assignedto": self.assignedto,
            "case_no": self.case_no,
            "display_id": self.display_id(),
            "createdat": self.createdat.isoformat() if self.createdat else None,
            "updatedat": self.updatedat.isoformat() if self.updatedat else None,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }
"""ROI progress tracker (PART D).

A logged-in user records their ACTUAL results each month so the ROI calculator
becomes a tracking tool: hours actually saved and matters actually handled are
SELF-REPORTED (honest wording — never the product claiming them). No PII is
stored beyond the user id (we deliberately do NOT copy email or name here).
"""
from ..extensions import db


class RoiProgress(db.Model):
    """One row per (workspace, user, month). Values are self-reported.

    Display rules:
      - normal user      -> sees only their OWN rows
      - admin            -> sees the workspace total (all staff rows)
      - superadmin       -> sees every row across all workspaces
    """

    __tablename__ = "roi_progress"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(
        db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    month = db.Column(db.String(7), nullable=False)  # 'YYYY-MM'
    hours_saved_actual = db.Column(db.Float, nullable=False, default=0.0)
    matters_handled = db.Column(db.Integer, nullable=False, default=0)
    note = db.Column(db.String(200), nullable=True)
    created_at = db.Column(
        db.DateTime, server_default=db.func.now(), nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint(
            "workspace_id", "user_id", "month", name="uq_roi_progress_ws_user_month"
        ),
    )

    workspace = db.relationship("Workspace", backref=db.backref("roi_progress", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "month": self.month,
            "hours_saved_actual": round(self.hours_saved_actual or 0, 2),
            "matters_handled": self.matters_handled or 0,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

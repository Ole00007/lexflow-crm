from ..extensions import db
from datetime import datetime


class FirmTeamMember(db.Model):
    """A member of a law firm's team shown to that firm's clients.

    The member belongs to the FIRM's workspace (e.g. romanelli-studio).
    Client sub-workspaces (romanelli-cl1..clN) see these members READ-ONLY
    (their lawyer, assistant, office phone) — never other tenants' data.
    Only the firm's admin (parent workspace) or superadmin can manage them.

    RULE (2026-09-03): a client sees ONLY the team of their own parent firm.
    This applies generically to any workspace with parent_workspace_id.
    """

    __tablename__ = "firm_team_members"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(
        db.Integer, db.ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(50), nullable=False, default="avvocato"
    )  # avvocato | assistente | office
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    workspace = db.relationship("Workspace", backref=db.backref("firm_team", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "role": self.role,
            "email": self.email,
            "phone": self.phone,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

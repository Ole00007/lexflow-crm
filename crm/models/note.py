from ..extensions import db
from datetime import datetime


def _iso(value):
    """ISO-8601 with an explicit UTC marker (DB values are naive UTC).

    Without the 'Z', a browser parses the string as local time and every note
    renders one hour off in CET.
    """
    if not value:
        return None
    return value.isoformat() + ('' if value.tzinfo is not None else 'Z')

class Note(db.Model):
    """Notes attached to any CRM record via polymorphic target_type + target_id."""
    __tablename__ = "notes"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    target_type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    # Provenance: who/what produced this note. 'human' is the only value this
    # table accepts from a person; 'agent' is set by the draft-promotion path
    # (human accepts an agent draft), with source_ref pointing at the draft.
    # See docs: agent drafts live in their own table and can never write here.
    source = db.Column(db.String(16), nullable=False, default="human", server_default="human")
    source_ref = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    author = db.relationship("User", backref=db.backref("notes", lazy=True))
    workspace = db.relationship("Workspace", backref=db.backref("notes", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "author_id": self.author_id,
            "author_email": self.author.email if self.author else None,
            "author_name": (self.author.full_name if self.author and getattr(self.author, "full_name", None) else (self.author.email if self.author else None)),
            "target_type": self.target_type,
            "target_id": self.target_id,
            "content": self.content,
            "source": self.source or "human",
            "source_ref": self.source_ref,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }
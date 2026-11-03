"""Matter-stage checklist (WS-K, feat/wave2-checklist).

THE KEY FEATURE: for every matter the system knows the CURRENT STAGE, which
document/action is MISSING next, who owns it and when it is due — and exposes
that as an API an agent (or a human) can act on.

MatterChecklistItem is one concrete step on a matter: a required document, an
action, or a deadline. Items are instantiated from a DATA template
(crm/services/checklist_templates.py) — stages are NOT a table. Each item is
tenant-scoped (workspace_id NOT NULL) exactly like TaskAssignee / TaskFlag, and
carries a global `position` assigned in template order so stages stay ordered
without a separate stage-order column.
"""
from ..extensions import db

# status lifecycle. 'done' and 'not_applicable' are the RESOLVED states (they
# count as finished for progress and never appear as "next missing").
ITEM_STATUSES = ('todo', 'in_progress', 'done', 'blocked', 'not_applicable')
RESOLVED_STATUSES = ('done', 'not_applicable')
# an item is one of these kinds (mirrors the template data)
ITEM_KINDS = ('document', 'action', 'deadline')

# owner_role reuses the Gantt roles — single source of truth is TASK_ROLES.
from .task_assignee import TASK_ROLES  # noqa: E402  (re-exported for callers)


class MatterChecklistItem(db.Model):
    __tablename__ = 'matter_checklist_items'
    __table_args__ = (
        db.UniqueConstraint('caseid', 'stage_key', 'position', name='uq_checklist_case_stage_pos'),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    caseid = db.Column(db.Integer, db.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False, index=True)
    stage_key = db.Column(db.String(60), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    label = db.Column(db.String(200), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default='action')      # document | action | deadline
    required_doc = db.Column(db.String(200), nullable=True)                # Italian doc name when kind == document
    status = db.Column(db.String(20), nullable=False, default='todo')      # see ITEM_STATUSES
    blocked_reason = db.Column(db.String(300), nullable=True)
    owner_role = db.Column(db.String(30), nullable=True)                   # one of TASK_ROLES
    due_date = db.Column(db.Date, nullable=True)
    vault_ref = db.Column(db.String(255), nullable=True)                   # vault-relative (superadmin only; validated)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id', ondelete='SET NULL'), nullable=True)  # optional Gantt/Calendar link
    completed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)

    case = db.relationship('Case', backref=db.backref('checklist_items', lazy=True, passive_deletes=True))
    task = db.relationship('Task')

    @property
    def is_resolved(self):
        return self.status in RESOLVED_STATUSES

    def to_dict(self, is_superadmin=False):
        role_label, role_color = (None, None)
        if self.owner_role and self.owner_role in TASK_ROLES:
            role_label, role_color = TASK_ROLES[self.owner_role]
        d = {
            'id': self.id,
            'caseid': self.caseid,
            'stage_key': self.stage_key,
            'position': self.position,
            'label': self.label,
            'kind': self.kind,
            'required_doc': self.required_doc,
            'status': self.status,
            'blocked_reason': self.blocked_reason,
            'owner_role': self.owner_role,
            'owner_role_label': role_label,
            'owner_role_color': role_color,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'task_id': self.task_id,
            'completed_by': self.completed_by,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
        # the vault reference is NOT a tenant resource — only the superadmin sees it,
        # exactly like the Gantt vault link.
        if is_superadmin:
            d['vault_ref'] = self.vault_ref
            d['vault_docs_api'] = ('/api/gantt/tasks/%d/docs' % self.task_id) if self.task_id else None
        return d

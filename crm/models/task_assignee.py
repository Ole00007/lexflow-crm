"""Task team roles + lawyer flags for the Gantt (WS-A, feat/gantt-team-roles).

TaskAssignee  — who is responsible for a task in which ROLE. The person comes
                from the firm Team directory (FirmTeamMember), never free text.
TaskFlag      — an explicit "needs the lawyer" flag raised by a human or an agent;
                an open flag is the hand-off point for human approval.
"""
from ..extensions import db

# role key -> (label, colour used by the UI). Colours are a UI contract: the
# Gantt CSS has one class per key (.role-<key>), keep both in sync.
TASK_ROLES = {
    'case_owner':      ('Case owner',      '#F5B942'),   # amber
    'docs_supply':     ('Docs supply',     '#38D6D0'),   # cyan
    'legal_assistant': ('Legal assistant', '#B78CFF'),   # violet
    'lawyer_review':   ('Lawyer review',   '#FF6F91'),   # rose
}


class TaskAssignee(db.Model):
    __tablename__ = 'task_assignees'
    __table_args__ = (db.UniqueConstraint('task_id', 'team_member_id', 'role', name='uq_task_assignee_role'),)

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False, index=True)
    team_member_id = db.Column(db.Integer, db.ForeignKey('firm_team_members.id'), nullable=False, index=True)
    role = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    task = db.relationship('Task', backref=db.backref('assignees', lazy=True, passive_deletes=True))
    member = db.relationship('FirmTeamMember')

    def to_dict(self):
        label, color = TASK_ROLES.get(self.role, (self.role, '#9AA7BD'))
        return {
            'member_id': self.team_member_id,
            'name': self.member.name if self.member else None,
            'role': self.role,
            'role_label': label,
            'color': color,
            'email': self.member.email if self.member else None,
            'phone': self.member.phone if self.member else None,
        }


class TaskFlag(db.Model):
    __tablename__ = 'task_flags'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False, index=True)
    raised_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    raised_by_agent = db.Column(db.String(80), nullable=True)      # e.g. 'lexflow-agent' when raised by software
    target_member_id = db.Column(db.Integer, db.ForeignKey('firm_team_members.id'), nullable=True)
    reason = db.Column(db.String(500), nullable=False, default='')
    status = db.Column(db.String(20), nullable=False, default='open')   # open | resolved
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id, 'task_id': self.task_id, 'status': self.status, 'reason': self.reason,
            'target_member_id': self.target_member_id, 'raised_by_agent': self.raised_by_agent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

from __future__ import annotations

import json
from datetime import datetime

from ..extensions import db
def redact_sensitive(value):
    from ..agent.guard import redact_sensitive as _r
    return _r(value)



class AgentRun(db.Model):
    __tablename__ = 'agent_runs'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    run_id = db.Column(db.String(36), nullable=False, unique=True, index=True)
    goal = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(32), nullable=False, default='running')
    final_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'user_id': self.user_id,
            'run_id': self.run_id,
            'goal': self.goal,
            'status': self.status,
            'final_text': self.final_text,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class AgentAudit(db.Model):
    __tablename__ = 'agent_audit'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    run_id = db.Column(db.String(36), nullable=False, index=True)
    step_no = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(16), nullable=False)
    tool = db.Column(db.String(64), nullable=True)
    args_json = db.Column(db.Text, nullable=True)
    result_summary = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    def to_dict(self):
        args = None
        if self.args_json:
            try:
                args = json.loads(self.args_json)
            except Exception:
                args = {'raw': self.args_json[:500]}
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'user_id': self.user_id,
            'run_id': self.run_id,
            'step_no': self.step_no,
            'kind': self.kind,
            'tool': self.tool,
            'args': redact_sensitive(args) if args is not None else None,
            'result_summary': self.result_summary,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class AgentPendingAction(db.Model):
    __tablename__ = 'agent_pending_actions'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    run_id = db.Column(db.String(36), nullable=False, index=True)
    tool = db.Column(db.String(64), nullable=False)
    args_json = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(16), nullable=False, default='pending')
    decided_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    decided_at = db.Column(db.DateTime, nullable=True)
    result_summary = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    def args(self):
        try:
            return json.loads(self.args_json)
        except Exception:
            return {}

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'user_id': self.user_id,
            'run_id': self.run_id,
            'tool': self.tool,
            'args': redact_sensitive(self.args()),
            'status': self.status,
            'decided_by': self.decided_by,
            'decided_at': self.decided_at.isoformat() if self.decided_at else None,
            'result_summary': self.result_summary,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

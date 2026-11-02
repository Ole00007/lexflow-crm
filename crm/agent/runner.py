from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..extensions import db
from ..models.agent_audit import AgentAudit, AgentPendingAction, AgentRun
from .brain import RuleBrain
from .guard import (
    AgentGuardError,
    MAX_STEPS,
    MAX_TOOL_CALLS,
    ensure_agent_enabled,
    redact_sensitive,
    serialize_args,
    summarize_data,
    tool_requires_approval,
    validate_tool_call,
)
from .tools import AgentTools


class AgentRuntimeError(RuntimeError):
    pass


def approval_ttl() -> timedelta:
    """How long a proposed write stays approvable (env LEXFLOW_AGENT_APPROVAL_TTL_MIN, default 15)."""
    try:
        return timedelta(minutes=max(1, int(os.environ.get('LEXFLOW_AGENT_APPROVAL_TTL_MIN', '15'))))
    except ValueError:
        return timedelta(minutes=15)


def payload_hash(run_id: str, user_id: int, workspace_id: int, tool: str, args_json: str) -> str:
    """Binds an approval to the exact content that was shown to the user."""
    raw = '\x1f'.join([str(run_id), str(user_id), str(workspace_id), str(tool), args_json])
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


@dataclass
class AgentOutcome:
    run: AgentRun
    payload: Dict[str, Any]
    status_code: int


def _current_step(audits: List[AgentAudit]) -> int:
    return len(audits)


class AgentRunner:
    def __init__(self, *, user, token: str, brain=None):
        self.user = user
        self.token = token
        self.brain = brain or RuleBrain()
        self.tools = AgentTools(token)

    def _audit(self, *, run: AgentRun, kind: str, step_no: int, status: str,
               tool: Optional[str] = None, args: Optional[Dict[str, Any]] = None,
               result: Any = None) -> AgentAudit:
        row = AgentAudit(
            workspace_id=run.workspace_id,
            user_id=run.user_id,
            run_id=run.run_id,
            step_no=step_no,
            kind=kind,
            tool=tool,
            args_json=serialize_args(args or {}) if args is not None else None,
            result_summary=summarize_data(result) if result is not None else None,
            status=status,
        )
        db.session.add(row)
        db.session.flush()
        return row

    def _result_data(self, wrapped: Dict[str, Any]) -> Any:
        if isinstance(wrapped, dict) and 'untrusted_data' in wrapped:
            return wrapped['untrusted_data']
        return wrapped

    def run_goal(self, goal: str) -> AgentOutcome:
        ensure_agent_enabled()
        run = AgentRun(
            workspace_id=self.user.workspace_id,
            user_id=self.user.id,
            run_id=str(uuid.uuid4()),
            goal=goal[:500],
            status='running',
        )
        db.session.add(run)
        db.session.flush()

        history: List[Dict[str, Any]] = []
        tool_calls = 0
        step_no = 0

        try:
            while True:
                if step_no >= MAX_STEPS:
                    raise AgentRuntimeError('step limit exceeded')
                step = self.brain.next_step(goal, history)
                if 'final' in step:
                    text = str(step['final'])
                    self._audit(run=run, kind='final', step_no=step_no + 1, status='completed', result=text)
                    run.final_text = text
                    run.status = 'completed'
                    db.session.commit()
                    return AgentOutcome(run=run, payload=self._payload(run), status_code=200)

                tool = step.get('tool')
                args = validate_tool_call(tool, step.get('args') or {})
                tool_calls += 1
                if tool_calls > MAX_TOOL_CALLS:
                    raise AgentRuntimeError('tool call limit exceeded')

                if tool_requires_approval(tool):
                    args_json = serialize_args(args)
                    pending = AgentPendingAction(
                        workspace_id=run.workspace_id,
                        user_id=run.user_id,
                        run_id=run.run_id,
                        tool=tool,
                        args_json=args_json,
                        status='pending',
                        payload_hash=payload_hash(run.run_id, run.user_id, run.workspace_id, tool, args_json),
                        expires_at=datetime.utcnow() + approval_ttl(),
                    )
                    db.session.add(pending)
                    self._audit(run=run, kind='approval', step_no=step_no + 1, status='pending', tool=tool, args=args,
                                result={'pending_action_id': None})
                    run.status = 'pending_approval'
                    db.session.commit()
                    return AgentOutcome(run=run, payload=self._payload(run, pending_action=pending), status_code=200)

                result = self.tools.execute(tool, args)
                result_data = self._result_data(result)
                if isinstance(result_data, dict) and int(result_data.get('status_code') or 200) >= 400:
                    self._audit(run=run, kind='error', step_no=step_no + 1, status='error', tool=tool, args=args,
                                result=result_data)
                    run.status = 'error'
                    run.final_text = summarize_data(result_data)
                    db.session.commit()
                    return AgentOutcome(run=run, payload=self._payload(run), status_code=400)

                self._audit(run=run, kind='tool_call', step_no=step_no + 1, status='executed', tool=tool, args=args,
                            result=result_data)
                history.append({'tool': tool, 'args': args, 'result': result})
                step_no += 1
        except AgentGuardError as exc:
            self._audit(run=run, kind='error', step_no=step_no + 1, status='error', result=str(exc))
            run.status = 'error'
            run.final_text = str(exc)
            db.session.commit()
            return AgentOutcome(run=run, payload={'error': str(exc), 'run': self._payload(run)['run']}, status_code=400)
        except AgentRuntimeError as exc:
            self._audit(run=run, kind='error', step_no=step_no + 1, status='error', result=str(exc))
            run.status = 'error'
            run.final_text = str(exc)
            db.session.commit()
            return AgentOutcome(run=run, payload={'error': str(exc), 'run': self._payload(run)['run']}, status_code=400)

    def _payload(self, run: AgentRun, pending_action: Optional[AgentPendingAction] = None) -> Dict[str, Any]:
        audits = AgentAudit.query.filter_by(run_id=run.run_id).order_by(AgentAudit.id.asc()).all()
        pending = AgentPendingAction.query.filter_by(run_id=run.run_id).order_by(AgentPendingAction.id.asc()).all()
        return {
            'run': run.to_dict(),
            'steps': [row.to_dict() for row in audits],
            'pending_actions': [row.to_dict() for row in pending],
            'pending_action': pending_action.to_dict() if pending_action else None,
        }

    def resolve_action(self, action_id: int, *, approve: bool, actor_user) -> AgentOutcome:
        ensure_agent_enabled()
        action = AgentPendingAction.query.filter_by(id=action_id).first()
        if not action:
            raise AgentRuntimeError('pending action not found')
        run = AgentRun.query.filter_by(run_id=action.run_id).first()
        if not run:
            raise AgentRuntimeError('run not found')
        if actor_user.role != 'superadmin' and actor_user.id != run.user_id:
            raise AgentRuntimeError('approval requires the run owner or a superadmin')
        if actor_user.role != 'superadmin' and getattr(actor_user, 'workspace_id', None) != action.workspace_id:
            raise AgentRuntimeError('approval requires the run owner or a superadmin')
        if action.status != 'pending':
            raise AgentRuntimeError('action already resolved')
        if approve:
            # Bound to the exact content the user was shown: a changed row is refused, never executed.
            if action.payload_hash and action.payload_hash != payload_hash(
                    action.run_id, action.user_id, action.workspace_id, action.tool, action.args_json):
                action.status = 'failed'
                action.result_summary = 'payload changed after proposal - refused'
                run.status = 'error'
                db.session.commit()
                raise AgentRuntimeError('proposal was modified after it was shown - refused')
            if action.expires_at and datetime.utcnow() > action.expires_at:
                action.status = 'expired'
                action.decided_by = actor_user.id
                action.decided_at = datetime.utcnow()
                run.status = 'expired'
                db.session.commit()
                raise AgentRuntimeError('proposal expired - ask Elisa again')
            # Atomic claim: two concurrent confirms cannot both execute (single-use).
            claimed = AgentPendingAction.query.filter_by(id=action.id, status='pending').update(
                {'status': 'approving'}, synchronize_session=False)
            db.session.commit()
            if claimed != 1:
                raise AgentRuntimeError('action already resolved')
            db.session.refresh(action)

        step_no = AgentAudit.query.filter_by(run_id=run.run_id).count() + 1
        if not approve:
            action.status = 'rejected'
            action.decided_by = actor_user.id
            action.decided_at = datetime.utcnow()
            run.status = 'rejected'
            self._audit(run=run, kind='approval', step_no=step_no, status='rejected', tool=action.tool,
                        args=json.loads(action.args_json), result='rejected')
            db.session.commit()
            return AgentOutcome(run=run, payload=self._payload(run), status_code=200)

        args = json.loads(action.args_json)
        result = self.tools.execute(action.tool, args)
        result_data = self._result_data(result)
        if isinstance(result_data, dict) and int(result_data.get('status_code') or 200) >= 400:
            action.status = 'failed'
            action.decided_by = actor_user.id
            action.decided_at = datetime.utcnow()
            self._audit(run=run, kind='error', step_no=step_no, status='error', tool=action.tool, args=args,
                        result=result_data)
            run.status = 'error'
            run.final_text = summarize_data(result_data)
            db.session.commit()
            return AgentOutcome(run=run, payload={'error': summarize_data(result_data), **self._payload(run)}, status_code=400)

        action.status = 'executed'
        action.decided_by = actor_user.id
        action.decided_at = datetime.utcnow()
        action.result_summary = summarize_data(result_data)
        self._audit(run=run, kind='approval', step_no=step_no, status='approved', tool=action.tool, args=args,
                    result=result_data)
        self._audit(run=run, kind='tool_call', step_no=step_no + 1, status='executed', tool=action.tool, args=args,
                    result=result_data)
        run.status = 'completed'
        run.final_text = summarize_data(result_data)
        db.session.commit()
        return AgentOutcome(run=run, payload=self._payload(run), status_code=200)

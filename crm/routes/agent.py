from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_limiter.util import get_remote_address

from ..extensions import limiter, db
from ..models.agent_audit import AgentAudit, AgentPendingAction, AgentRun
from ..models.user import User
from ..workspace import workspace_filter
from ..agent.brain import HttpLLMBrain, RuleBrain
from ..agent.guard import ensure_agent_enabled
from ..agent.runner import AgentRunner, AgentRuntimeError


agent_bp = Blueprint('agent', __name__)


def _current_user():
    try:
        uid = get_jwt_identity()
        if uid:
            return User.query.filter_by(id=int(uid), is_deleted=False).first()
    except Exception:
        return None
    return None


def _require_superadmin(user):
    if not user or user.role != 'superadmin':
        return jsonify({'error': 'Superadmin access required for LexFlow Agent'}), 403
    return None


def _brain():
    url = (request.headers.get('X-Lexflow-Agent-LLM-Url') or '').strip()
    if url:
        return HttpLLMBrain(url=url)
    return RuleBrain()


@agent_bp.get('/agent')
@jwt_required(optional=True)
def agent_page():
    ensure_agent_enabled()
    user = _current_user()
    if user and user.role != 'superadmin':
        return jsonify({'error': 'Superadmin access required for LexFlow Agent'}), 403
    return render_template('agent.html')


@agent_bp.post('/api/agent/runs')
@jwt_required(optional=True)
@limiter.limit('10 per minute', key_func=get_remote_address)
def create_run():
    ensure_agent_enabled()
    user = _current_user()
    blocked = _require_superadmin(user)
    if blocked:
        return blocked
    body = request.get_json(silent=True) or {}
    goal = str(body.get('goal') or '').strip()
    if not goal:
        return jsonify({'error': 'goal is required'}), 400
    if len(goal) > 500:
        return jsonify({'error': 'goal must be 500 characters or fewer'}), 400
    token = request.headers.get('Authorization') or ''
    runner = AgentRunner(user=user, token=token, brain=_brain())
    outcome = runner.run_goal(goal)
    return jsonify(outcome.payload), outcome.status_code


@agent_bp.get('/api/agent/runs/<int:run_id>')
@jwt_required(optional=True)
def get_run(run_id):
    ensure_agent_enabled()
    user = _current_user()
    blocked = _require_superadmin(user)
    if blocked:
        return blocked
    run = AgentRun.query.filter_by(id=run_id).first()
    if not run:
        return jsonify({'error': 'Not found'}), 404
    audits = AgentAudit.query.filter_by(run_id=run.run_id).order_by(AgentAudit.id.asc()).all()
    pending = AgentPendingAction.query.filter_by(run_id=run.run_id).order_by(AgentPendingAction.id.asc()).all()
    return jsonify({'run': run.to_dict(), 'steps': [a.to_dict() for a in audits], 'pending_actions': [p.to_dict() for p in pending]}), 200


@agent_bp.get('/api/agent/runs')
@jwt_required(optional=True)
def list_runs():
    ensure_agent_enabled()
    user = _current_user()
    blocked = _require_superadmin(user)
    if blocked:
        return blocked
    page = max(1, request.args.get('page', 1, type=int) or 1)
    per_page = min(50, max(1, request.args.get('per_page', 20, type=int) or 20))
    query = workspace_filter(AgentRun.query, AgentRun).filter_by(user_id=user.id).order_by(AgentRun.id.desc())
    total = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({'items': [r.to_dict() for r in rows], 'page': page, 'per_page': per_page, 'total': total, 'has_more': total > page * per_page}), 200


@agent_bp.post('/api/agent/actions/<int:action_id>/approve')
@jwt_required(optional=True)
def approve_action(action_id):
    ensure_agent_enabled()
    user = _current_user()
    blocked = _require_superadmin(user)
    if blocked:
        return blocked
    runner = AgentRunner(user=user, token=request.headers.get('Authorization') or '', brain=_brain())
    try:
        outcome = runner.resolve_action(action_id, approve=True, actor_user=user)
    except AgentRuntimeError as exc:
        text = str(exc)
        status = 404 if 'not found' in text else 409 if 'already resolved' in text else 403
        return jsonify({'error': text}), status
    return jsonify(outcome.payload), outcome.status_code


@agent_bp.post('/api/agent/actions/<int:action_id>/reject')
@jwt_required(optional=True)
def reject_action(action_id):
    ensure_agent_enabled()
    user = _current_user()
    blocked = _require_superadmin(user)
    if blocked:
        return blocked
    runner = AgentRunner(user=user, token=request.headers.get('Authorization') or '', brain=_brain())
    try:
        outcome = runner.resolve_action(action_id, approve=False, actor_user=user)
    except AgentRuntimeError as exc:
        text = str(exc)
        status = 404 if 'not found' in text else 409 if 'already resolved' in text else 403
        return jsonify({'error': text}), status
    return jsonify(outcome.payload), outcome.status_code

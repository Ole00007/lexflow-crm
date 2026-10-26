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


def _chat_brain():
    # Never trust a client-supplied LLM URL (SSRF): chat uses the server env or the offline rule brain.
    import os
    # The LLM URL/key/model also power model-written summaries/drafts (crm/agent/llm.py). LLM *routing* of the chat
    # is a separate opt-in so enabling summaries never changes the deterministic, approval-gated rule brain.
    if (os.environ.get('LEXFLOW_AGENT_LLM_URL') or '').strip() and \
            (os.environ.get('LEXFLOW_AGENT_LLM_ROUTING') or '').strip().lower() in ('1', 'true', 'yes', 'on'):
        return HttpLLMBrain()
    return RuleBrain()


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


# ---------------------------------------------------------------------------
# Elisa in-app chat (floating bubble). Any authenticated workspace user may chat;
# every write still stops at a human approval and runs with the caller's own JWT.
# ---------------------------------------------------------------------------
def _require_user(user):
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    return None


def describe_action(tool, args):
    args = args or {}
    if tool == 'create_task':
        bits = [f"Create task “{args.get('title')}” on matter #{args.get('caseid')}"]
        if args.get('duedate'):
            bits.append(f"due {args['duedate']}")
        if args.get('priority'):
            bits.append(f"priority {args['priority']}")
        return ', '.join(bits)
    if tool == 'create_calendar_event':
        when = str(args.get('start_datetime', ''))[:16].replace('T', ' ')
        note = ' — the client linked to the matter may be notified by email' if args.get('caseid') else ''
        return f"Add to agenda: “{args.get('title')}” ({args.get('event_type', 'meeting')}) on {when}{note}"
    if tool == 'update_task_status':
        return f"Set task #{args.get('task_id')} to “{args.get('status')}”"
    if tool == 'flag_lawyer':
        return f"Flag the lawyer on task #{args.get('task_id')}: {args.get('reason')}"
    if tool == 'draft_notification':
        return f"Draft notification “{args.get('subject')}”"
    return f"{tool} {args}"


def _chat_payload(payload):
    run = payload.get('run') or {}
    pending = payload.get('pending_action')
    action = None
    if pending:
        action = dict(pending)
        action['description'] = describe_action(pending.get('tool'), pending.get('args'))
        reply = 'I can do this for you — please confirm:'
    else:
        reply = run.get('final_text') or 'Done.'
    is_draft = (not action) and str(reply).startswith(('BOZZA', 'DRAFT'))
    return {'reply': reply, 'status': run.get('status'), 'run_id': run.get('run_id'), 'pending_action': action, 'draft': is_draft}


@agent_bp.post('/api/agent/chat')
@jwt_required(optional=True)
@limiter.limit('30 per minute', key_func=get_remote_address)
def chat():
    ensure_agent_enabled()
    user = _current_user()
    blocked = _require_user(user)
    if blocked:
        return blocked
    body = request.get_json(silent=True) or {}
    message = str(body.get('message') or '').strip()
    if not message:
        return jsonify({'error': 'message is required'}), 400
    if len(message) > 500:
        return jsonify({'error': 'message must be 500 characters or fewer'}), 400
    runner = AgentRunner(user=user, token=request.headers.get('Authorization') or '', brain=_chat_brain())
    outcome = runner.run_goal(message)
    out = _chat_payload(outcome.payload)
    return jsonify(out), (200 if outcome.status_code < 500 else outcome.status_code)


def _resolve(action_id, approve):
    ensure_agent_enabled()
    user = _current_user()
    blocked = _require_user(user)
    if blocked:
        return blocked
    runner = AgentRunner(user=user, token=request.headers.get('Authorization') or '', brain=_chat_brain())
    try:
        outcome = runner.resolve_action(action_id, approve=approve, actor_user=user)
    except AgentRuntimeError as exc:
        text = str(exc)
        status = 404 if 'not found' in text else 409 if 'already resolved' in text else 403
        return jsonify({'error': text}), status
    if outcome.status_code >= 400:
        return jsonify({'reply': 'That did not work: ' + str((outcome.payload or {}).get('error', 'error')), 'status': 'error'}), outcome.status_code
    run = outcome.payload.get('run') or {}
    reply = 'Done — it is in your workspace.' if approve else 'Okay, I did not do it.'
    return jsonify({'reply': reply, 'status': run.get('status'), 'run_id': run.get('run_id'), 'result': run.get('final_text') if approve else None}), 200


@agent_bp.post('/api/agent/chat/actions/<int:action_id>/approve')
@jwt_required(optional=True)
def chat_approve(action_id):
    return _resolve(action_id, True)


@agent_bp.post('/api/agent/chat/actions/<int:action_id>/reject')
@jwt_required(optional=True)
def chat_reject(action_id):
    return _resolve(action_id, False)

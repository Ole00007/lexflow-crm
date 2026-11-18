"""Agent draft sandbox (Mindmap B1, server half). Contract: docs/Mindmap_Drafts_API_Contract.md.

Agents write ONLY to agent_drafts. The single bridge into `notes` is a human
accepting a draft (accept_draft below), which inserts source='agent' rows.
"""
import json
import re
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db, limiter
from ..models.activity import ActivityLog
from ..models.agent_delegation import AgentDelegation
from ..models.agent_draft import AgentDraft, DRAFT_TTL_DAYS
from ..models.agent_policy import AgentPolicy
from ..models.note import Note
from ..models.user import User
from ..workspace import get_visible_workspace_ids, workspace_filter

agent_drafts_bp = Blueprint('agent_drafts', __name__, url_prefix='/api/agent')

TARGET_TYPES = {'workspace', 'task', 'case', 'contact'}
ORIGINS = {'human_request', 'superior_agent', 'event_rule'}
STATUSES = {'draft', 'proposed', 'accepted', 'rejected', 'expired'}
EVENT_KEYS = {'lead_stalled', 'quote_sent', 'deadline_missed', 'task_overdue', 'custom'}
KILL_SWITCH_KEY = '__kill_switch__'  # internal row; enabled=True means kill switch ENGAGED
DEFAULT_MAX_PER_DAY = 3
AGENT_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')


def _now():
    return datetime.utcnow()


def _user():
    return db.session.get(User, int(get_jwt_identity()))


def _is_super(user):
    return bool(user and user.role == 'superadmin')


def _can_see_workspace(workspace_id):
    ids = get_visible_workspace_ids()
    return ids is None or workspace_id in ids


def _err(msg, code):
    return jsonify({'error': msg}), code


# ── Drafts ─────────────────────────────────────────────────────────────

@agent_drafts_bp.get('/drafts')
@jwt_required()
def list_drafts():
    q = workspace_filter(AgentDraft.query, AgentDraft)
    status = (request.args.get('status') or '').strip().lower()
    if status:
        if status not in STATUSES:
            return _err('Invalid status', 400)
        q = q.filter(AgentDraft.status == status)
        if status == 'proposed':
            q = q.filter(AgentDraft.expires_at > _now())  # lapsed drafts never show in the tray
    target_type = (request.args.get('target_type') or '').strip().lower()
    if target_type:
        if target_type not in TARGET_TYPES:
            return _err('Invalid target_type', 400)
        q = q.filter(AgentDraft.target_type == target_type)
    target_id = request.args.get('target_id', type=int)
    if target_id is not None:
        q = q.filter(AgentDraft.target_id == target_id)
    return jsonify([d.to_dict() for d in q.order_by(AgentDraft.created_at.desc(), AgentDraft.id.desc()).all()]), 200


def _load_for_decision(draft_id):
    """Return (draft, user, error_response). 404 missing, 403 wrong tenant/user."""
    user = _user()
    draft = db.session.get(AgentDraft, draft_id)
    if not draft:
        return None, user, _err('Draft not found', 404)
    if not user or not _can_see_workspace(draft.workspace_id):
        return None, user, _err('Forbidden', 403)
    if not _is_super(user) and draft.requested_by is not None and draft.requested_by != user.id:
        return None, user, _err('Not your draft', 403)
    return draft, user, None


def _conflict_response(draft_id):
    """Explain why the atomic UPDATE matched nothing: 410 if lapsed, else 409."""
    db.session.rollback()
    row = db.session.get(AgentDraft, draft_id)
    db.session.refresh(row)
    if row.status == 'expired' or (row.status == 'proposed' and row.expires_at <= _now()):
        if row.status == 'proposed':  # record the lapse; row stays for audit
            AgentDraft.query.filter(AgentDraft.id == draft_id, AgentDraft.status == 'proposed') \
                .update({'status': 'expired', 'updated_at': _now()}, synchronize_session=False)
            db.session.commit()
        return _err('Draft expired', 410)
    return _err(f'Draft already resolved ({row.status})', 409)


def _claim(draft, user, new_status):
    """Atomic single-use transition proposed -> new_status. True only for the single winner."""
    now = _now()
    n = AgentDraft.query.filter(
        AgentDraft.id == draft.id,
        AgentDraft.status == 'proposed',
        AgentDraft.expires_at > now,
    ).update(
        {'status': new_status, 'decided_by': user.id, 'decided_at': now, 'updated_at': now},
        synchronize_session=False,
    )
    return n == 1


@agent_drafts_bp.post('/drafts/<int:draft_id>/accept')
@jwt_required()
@limiter.limit('30 per minute')
def accept_draft(draft_id):
    draft, user, error = _load_for_decision(draft_id)
    if error:
        return error
    if not _claim(draft, user, 'accepted'):
        return _conflict_response(draft_id)
    # Same transaction as the claim: promotion + audit commit together or not at all.
    try:
        note = Note(
            workspace_id=draft.workspace_id,
            author_id=draft.requested_by,
            target_type=draft.target_type,
            target_id=draft.target_id,
            content=draft.content,
            source='agent',
            source_ref=str(draft.id),
        )
        db.session.add(note)
        db.session.flush()
        AgentDraft.query.filter(AgentDraft.id == draft.id).update({'note_id': note.id}, synchronize_session=False)
        db.session.add(ActivityLog(
            workspace_id=draft.workspace_id,
            actor_id=user.id,
            target_type=draft.target_type,
            target_id=draft.target_id,
            action='agent_draft_promoted',
            summary=f'Agent draft #{draft.id} accepted and promoted to note #{note.id}',
            details=json.dumps({'draft_id': draft.id, 'note_id': note.id,
                                'agent': draft.requested_by_agent, 'origin': draft.origin}),
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    db.session.refresh(draft)
    return jsonify({'draft': draft.to_dict(), 'note': note.to_dict()}), 200


@agent_drafts_bp.post('/drafts/<int:draft_id>/reject')
@jwt_required()
@limiter.limit('30 per minute')
def reject_draft(draft_id):
    draft, user, error = _load_for_decision(draft_id)
    if error:
        return error
    if not _claim(draft, user, 'rejected'):
        return _conflict_response(draft_id)
    db.session.add(ActivityLog(
        workspace_id=draft.workspace_id, actor_id=user.id,
        target_type=draft.target_type, target_id=draft.target_id,
        action='agent_draft_rejected', summary=f'Agent draft #{draft.id} rejected',
        details=json.dumps({'draft_id': draft.id, 'agent': draft.requested_by_agent}),
    ))
    db.session.commit()
    db.session.refresh(draft)
    return jsonify({'draft': draft.to_dict()}), 200


# ── Internal/agent creation path ──────────────────────────────────────

def _scope_allows(delegation, target_type, target_id):
    raw = delegation.scope
    if raw is None or raw == '' or raw == '*':
        return True
    try:
        scope = json.loads(raw)
    except (TypeError, ValueError):
        return False
    if scope == '*':
        return True
    if not isinstance(scope, dict):
        return False
    types = scope.get('target_types')
    ids = scope.get('target_ids')
    if types is not None and target_type not in types:
        return False
    if ids is not None and target_id not in ids:
        return False
    return True


def _target_in_workspace(target_type, target_id, workspace_id):
    if target_type == 'workspace':
        return target_id == workspace_id
    from ..models.case import Case
    from ..models.contact import Contact
    from ..models.task import Task
    cls = {'task': Task, 'case': Case, 'contact': Contact}[target_type]
    q = cls.query.filter_by(id=target_id)
    if hasattr(cls, 'is_deleted'):
        q = q.filter_by(is_deleted=False)
    row = q.first()
    return bool(row) and getattr(row, 'workspace_id', workspace_id) == workspace_id


def _kill_switch_engaged(workspace_id):
    row = AgentPolicy.query.filter_by(workspace_id=workspace_id, event_key=KILL_SWITCH_KEY).first()
    return bool(row and row.enabled)


@agent_drafts_bp.post('/drafts')
@jwt_required()
@limiter.limit('60 per minute')
def create_draft():
    # Service-identity gate: agents only. Browsers send Origin / Sec-Fetch-* on
    # fetch(); a header-less client must still name itself via X-Agent-Name.
    agent = (request.headers.get('X-Agent-Name') or '').strip().lower()
    if not agent or not AGENT_NAME_RE.match(agent):
        return _err('X-Agent-Name service identity required', 403)
    if request.headers.get('Origin') or request.headers.get('Sec-Fetch-Mode') or request.headers.get('Sec-Fetch-Site'):
        return _err('Browser-origin calls are not allowed on this endpoint', 403)

    user = _user()
    if not user or not user.workspace_id:
        return _err('Forbidden', 403)
    ws_id = user.workspace_id

    data = request.get_json(silent=True) or {}
    target_type = str(data.get('target_type') or '').lower()
    target_id = data.get('target_id')
    content = str(data.get('content') or '').strip()
    origin = str(data.get('origin') or 'human_request').lower()
    evidence = data.get('evidence')
    if target_type not in TARGET_TYPES:
        return _err('Invalid target_type', 400)
    if not isinstance(target_id, int) or isinstance(target_id, bool):
        return _err('target_id is required', 400)
    if not content:
        return _err('content is required', 400)
    if origin not in ORIGINS:
        return _err('Invalid origin', 400)
    if not _target_in_workspace(target_type, target_id, ws_id):
        return _err('Target not found', 404)

    now = _now()
    policy = None
    requested_by = None
    event_key = str(data.get('event_key') or 'custom').lower()
    if origin == 'event_rule':
        if event_key not in EVENT_KEYS:
            return _err('Invalid event_key', 400)
        if _kill_switch_engaged(ws_id):
            return _err('Kill switch engaged: event_rule generation is off', 403)
        policy = AgentPolicy.query.filter_by(workspace_id=ws_id, event_key=event_key).first()
        if not policy or not policy.enabled:
            return _err('No enabled policy for this event', 403)
    else:
        delegations = AgentDelegation.query.filter_by(workspace_id=ws_id, to_agent=agent).all()
        match = next((d for d in delegations if d.is_active(now) and _scope_allows(d, target_type, target_id)), None)
        if not match:
            return _err('No active delegation for this agent and target', 403)
        requested_by = match.from_user_id
        cap_policy = AgentPolicy.query.filter_by(workspace_id=ws_id, event_key=event_key).first()
        policy = cap_policy if cap_policy and cap_policy.event_key != KILL_SWITCH_KEY else None

    cap = (policy.max_per_day if policy else None) or DEFAULT_MAX_PER_DAY
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today = AgentDraft.query.filter(
        AgentDraft.workspace_id == ws_id,
        AgentDraft.target_type == target_type,
        AgentDraft.target_id == target_id,
        AgentDraft.created_at >= day_start,
    ).count()
    if today >= cap:
        return _err('Daily draft cap reached for this target', 429)

    draft = AgentDraft(
        workspace_id=ws_id, target_type=target_type, target_id=target_id, content=content,
        origin=origin, requested_by=requested_by, requested_by_agent=agent,
        evidence=(str(evidence) if evidence else None), status='proposed',
        policy_id=policy.id if (policy and origin == 'event_rule') else None,
        expires_at=now + timedelta(days=DRAFT_TTL_DAYS), created_at=now, updated_at=now,
    )
    db.session.add(draft)
    db.session.commit()
    return jsonify(draft.to_dict()), 201


# ── Policies ──────────────────────────────────────────────────────────

@agent_drafts_bp.get('/policies')
@jwt_required()
def list_policies():
    user = _user()
    ws_id = user.workspace_id if user else None
    rows = AgentPolicy.query.filter(AgentPolicy.workspace_id == ws_id,
                                    AgentPolicy.event_key != KILL_SWITCH_KEY).order_by(AgentPolicy.event_key).all()
    return jsonify([p.to_dict() for p in rows]), 200


@agent_drafts_bp.put('/policies/<event_key>')
@jwt_required()
def upsert_policy(event_key):
    user = _user()
    if not _is_super(user):
        return _err('Superadmin only', 403)
    event_key = event_key.lower()
    if event_key not in EVENT_KEYS:
        return _err('Invalid event_key', 400)
    data = request.get_json(silent=True) or {}
    policy = AgentPolicy.query.filter_by(workspace_id=user.workspace_id, event_key=event_key).first()
    if not policy:
        policy = AgentPolicy(workspace_id=user.workspace_id, event_key=event_key)
        db.session.add(policy)
    if 'enabled' in data:
        if not isinstance(data['enabled'], bool):
            return _err('enabled must be boolean', 400)
        policy.enabled = data['enabled']
    elif policy.enabled is None:
        policy.enabled = False
    if 'max_per_day' in data:
        mpd = data['max_per_day']
        if not isinstance(mpd, int) or isinstance(mpd, bool) or not 1 <= mpd <= 50:
            return _err('max_per_day must be an integer 1..50', 400)
        policy.max_per_day = mpd
    elif policy.max_per_day is None:
        policy.max_per_day = DEFAULT_MAX_PER_DAY
    policy.require_review = True  # invariant: never configurable
    db.session.commit()
    return jsonify(policy.to_dict()), 200


@agent_drafts_bp.post('/policies/kill-switch')
@jwt_required()
def kill_switch():
    """Body {enabled: bool} = whether event_rule generation is ENABLED.
    enabled=false engages the kill switch (all event_rule generation stops at once);
    enabled=true releases it (policies keep their own enabled flags)."""
    user = _user()
    if not _is_super(user):
        return _err('Superadmin only', 403)
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get('enabled'), bool):
        return _err('enabled (boolean) is required', 400)
    engaged = not data['enabled']
    row = AgentPolicy.query.filter_by(workspace_id=user.workspace_id, event_key=KILL_SWITCH_KEY).first()
    if not row:
        row = AgentPolicy(workspace_id=user.workspace_id, event_key=KILL_SWITCH_KEY, max_per_day=0)
        db.session.add(row)
    row.enabled = engaged
    row.require_review = True
    db.session.add(ActivityLog(
        workspace_id=user.workspace_id, actor_id=user.id, target_type='workspace', target_id=user.workspace_id,
        action='agent_kill_switch', summary=f'Agent kill switch {"ENGAGED" if engaged else "released"}',
    ))
    db.session.commit()
    return jsonify({'kill_switch': engaged, 'event_rule_generation_enabled': not engaged}), 200


# ── Delegations ───────────────────────────────────────────────────────

@agent_drafts_bp.get('/delegations')
@jwt_required()
def list_delegations():
    q = workspace_filter(AgentDelegation.query, AgentDelegation)
    return jsonify([d.to_dict() for d in q.order_by(AgentDelegation.id.desc()).all()]), 200


@agent_drafts_bp.post('/delegations')
@jwt_required()
def create_delegation():
    user = _user()
    data = request.get_json(silent=True) or {}
    to_agent = str(data.get('to_agent') or '').strip().lower()
    if not AGENT_NAME_RE.match(to_agent):
        return _err('to_agent is required', 400)
    ttl = data.get('ttl_hours', 24)
    if not isinstance(ttl, (int, float)) or isinstance(ttl, bool) or not 0 < ttl <= 24 * 30:
        return _err('ttl_hours must be 1..720', 400)
    scope = data.get('scope', '*')
    if scope != '*' and not isinstance(scope, dict):
        return _err('scope must be "*" or an object', 400)
    from_user_id = user.id
    if _is_super(user) and data.get('from_user_id'):
        from_user_id = int(data['from_user_id'])
    elif data.get('from_user_id') not in (None, user.id):
        return _err('Only the granting user may create a delegation', 403)
    d = AgentDelegation(
        workspace_id=user.workspace_id, from_user_id=from_user_id, to_agent=to_agent,
        scope=json.dumps(scope), expires_at=_now() + timedelta(hours=ttl),
    )
    db.session.add(d)
    db.session.commit()
    return jsonify(d.to_dict()), 201


@agent_drafts_bp.delete('/delegations/<int:delegation_id>')
@jwt_required()
def revoke_delegation(delegation_id):
    user = _user()
    d = db.session.get(AgentDelegation, delegation_id)
    if not d:
        return _err('Delegation not found', 404)
    if not _can_see_workspace(d.workspace_id) or not (_is_super(user) or d.from_user_id == user.id):
        return _err('Forbidden', 403)
    if d.revoked_at is None:
        d.revoked_at = _now()
        db.session.commit()
    return jsonify(d.to_dict()), 200

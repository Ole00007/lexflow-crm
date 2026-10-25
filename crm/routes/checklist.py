"""Matter-stage checklist — THE KEY FEATURE (WS-K, feat/wave2-checklist).

For every matter the system knows the CURRENT STAGE, which document/action is
MISSING next, who owns it and when it is due — and exposes that as an API an
agent (or a human) can act on.

Everything here is:
  * behind the MATTER_CHECKLIST_ENABLED kill-switch — flag OFF => every route
    404s (checked in a before_request BEFORE auth, so the feature is invisible),
  * tenant-scoped through workspace_filter / the case's workspace,
  * JWT protected (writes gated by role: status = any visible user; owner/due =
    admin; vault_ref = superadmin, exactly like the Gantt).

Routes
  GET   /api/checklist/templates
  POST  /api/cases/<id>/checklist/init        {template[, force]}   admin
  GET   /api/cases/<id>/checklist
  PATCH /api/checklist/items/<id>             {status, blocked_reason, owner_role, due_date, vault_ref}
  POST  /api/checklist/items/<id>/materialize
  GET   /api/checklist/next-actions?limit=20                        the AGENT endpoint
  GET   /cases/<id>/checklist                 (HTML page shell)
"""
import os
from datetime import datetime, date

from flask import Blueprint, jsonify, request, render_template, abort
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..extensions import db
from ..models.user import User
from ..models.case import Case
from ..models.task import Task
from ..models.matter_checklist import (
    MatterChecklistItem, ITEM_STATUSES, RESOLVED_STATUSES, ITEM_KINDS,
)
from ..models.task_assignee import TASK_ROLES
from ..workspace import workspace_filter
from ..services import checklist_templates as tpl
# vault_ref validation is SHARED with the Gantt — import, never copy (brief rule).
from ..routes.task_team import _safe_ref, _vault_root

checklist_bp = Blueprint('checklist', __name__)

_ON = ('1', 'true', 'yes', 'on')
MAX_BLOCKED_REASON = 300
MAX_NEXT_ACTIONS = 100
UNFINISHED = tuple(s for s in ITEM_STATUSES if s not in RESOLVED_STATUSES)  # todo,in_progress,blocked
MISSING_STATUSES = ('todo', 'blocked')  # what counts as "next missing"


def flag_on():
    """The MATTER_CHECKLIST_ENABLED kill-switch. A query param can NEVER force it on."""
    return os.environ.get('MATTER_CHECKLIST_ENABLED', 'false').strip().lower() in _ON


@checklist_bp.before_request
def _kill_switch():
    """Flag OFF => the whole feature does not exist (404 for ALL routes, pre-auth)."""
    if not flag_on():
        abort(404)


# ── helpers ──────────────────────────────────────────────────────────────────
def _user():
    try:
        return User.query.filter_by(id=int(get_jwt_identity()), is_deleted=False).first()
    except Exception:
        return None


def _is_admin(user):
    return bool(user and user.role in ('admin', 'superadmin'))


def _is_super(user):
    return bool(user and user.role == 'superadmin')


def _visible_case(case_id):
    return workspace_filter(Case.query.filter_by(id=case_id, is_deleted=False), Case).first()


def _visible_item(item_id):
    return workspace_filter(
        MatterChecklistItem.query.filter_by(id=item_id, is_deleted=False),
        MatterChecklistItem,
    ).first()


def _live_items(case_id):
    return (MatterChecklistItem.query
            .filter_by(caseid=case_id, is_deleted=False)
            .order_by(MatterChecklistItem.position.asc())
            .all())


def _parse_due(value):
    """Return (ok, date_or_None). value may be None/'' (clear) or an ISO date."""
    if value in (None, ''):
        return True, None
    if not isinstance(value, str) or len(value) > 10:
        return False, None
    try:
        return True, date.fromisoformat(value)
    except ValueError:
        return False, None


def _days_in_stage(item):
    """Approximation: days since the item was created (we do not track a per-stage
    clock). Used only to rank the agent's next-actions feed (older first)."""
    try:
        created = item.created_at.date() if item.created_at else date.today()
    except Exception:
        created = date.today()
    return max(0, (date.today() - created).days)


def _days_overdue(due):
    if not due:
        return 0
    return max(0, (date.today() - due).days)


def _checklist_state(items):
    """Compute grouped stages + current_stage + progress + next_missing from a
    flat, position-ordered item list.

    current_stage = first stage (in position order) that still has an UNFINISHED
                    item (todo/in_progress/blocked); not_applicable & done count
                    as resolved.
    next_missing  = first todo/blocked item in the current stage (by position).
    progress      = resolved / total, as an int percent.
    """
    stages = []           # ordered list of {key, name, items, state}
    stage_index = {}
    for it in items:
        if it.stage_key not in stage_index:
            stage_index[it.stage_key] = len(stages)
            stages.append({'key': it.stage_key, 'name': tpl.stage_name(it.stage_key),
                           'items': [], 'state': 'upcoming'})
        stages[stage_index[it.stage_key]]['items'].append(it)

    total = len(items)
    resolved = sum(1 for it in items if it.status in RESOLVED_STATUSES)
    progress = int(round(resolved * 100.0 / total)) if total else 0

    current_stage = None
    for st in stages:
        if any(it.status in UNFINISHED for it in st['items']):
            current_stage = st['key']
            break

    # mark stage states: done (all resolved) / current / upcoming
    seen_current = False
    for st in stages:
        if st['key'] == current_stage:
            st['state'] = 'current'
            seen_current = True
        elif not seen_current and all(it.status in RESOLVED_STATUSES for it in st['items']):
            st['state'] = 'done'
        elif all(it.status in RESOLVED_STATUSES for it in st['items']):
            st['state'] = 'done'
        else:
            st['state'] = 'upcoming'

    next_missing = None
    if current_stage is not None:
        cur = next(s for s in stages if s['key'] == current_stage)
        for it in cur['items']:  # already position-ordered
            if it.status in MISSING_STATUSES:
                next_missing = it
                break

    return stages, current_stage, progress, resolved, total, next_missing


# ── endpoints ─────────────────────────────────────────────────────────────────
@checklist_bp.get('/api/checklist/templates')
@jwt_required()
def api_templates():
    if not _user():
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({'templates': tpl.list_templates(),
                    'disclaimer': tpl.TEMPLATE_DISCLAIMER}), 200


@checklist_bp.post('/api/cases/<int:case_id>/checklist/init')
@jwt_required()
def api_init(case_id):
    user = _user()
    if not _is_admin(user):
        return jsonify({'error': 'Unauthorized - admin access required'}), 403
    case = _visible_case(case_id)
    if not case:
        return jsonify({'error': 'Not found'}), 404
    body = request.get_json(silent=True) or {}
    template_key = body.get('template')
    if not tpl.get_template(template_key):
        return jsonify({'error': 'unknown template', 'allowed': list(tpl.TEMPLATES)}), 400
    force = bool(body.get('force'))

    existing = _live_items(case_id)
    if existing and not force:
        return jsonify({'error': 'checklist already initialised',
                        'count': len(existing)}), 409
    if existing and force:
        # re-initialise: HARD-delete existing live items, then recreate. The
        # unique constraint (caseid, stage_key, position) ignores is_deleted, so
        # a soft-delete would collide with the fresh rows — remove them outright.
        (MatterChecklistItem.query
         .filter_by(caseid=case_id, is_deleted=False)
         .delete(synchronize_session=False))
        db.session.flush()

    created = 0
    for pos, stage_key, item in tpl.iter_template_items(template_key):
        db.session.add(MatterChecklistItem(
            workspace_id=case.workspace_id, caseid=case.id,
            stage_key=stage_key, position=pos,
            label=item['label'][:200], kind=item['kind'],
            required_doc=(item.get('required_doc') or None),
            owner_role=item.get('owner_role'), status='todo'))
        created += 1
    db.session.commit()
    return jsonify({'case_id': case.id, 'template': template_key,
                    'created': created, 'forced': force and bool(existing)}), 201


@checklist_bp.get('/api/cases/<int:case_id>/checklist')
@jwt_required()
def api_get_checklist(case_id):
    user = _user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    case = _visible_case(case_id)
    if not case:
        return jsonify({'error': 'Not found'}), 404
    items = _live_items(case_id)
    stages, current_stage, progress, resolved, total, next_missing = _checklist_state(items)
    is_super = _is_super(user)
    return jsonify({
        'case_id': case.id,
        'case_no': case.display_id(),
        'disclaimer': tpl.TEMPLATE_DISCLAIMER,
        'current_stage': current_stage,
        'progress': progress,
        'counts': {'total': total, 'resolved': resolved},
        'next_missing': next_missing.to_dict(is_superadmin=is_super) if next_missing else None,
        'stages': [{
            'key': st['key'], 'name': st['name'], 'state': st['state'],
            'items': [it.to_dict(is_superadmin=is_super) for it in st['items']],
        } for st in stages],
    }), 200


@checklist_bp.patch('/api/checklist/items/<int:item_id>')
@jwt_required()
def api_patch_item(item_id):
    user = _user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    item = _visible_item(item_id)
    if not item:
        return jsonify({'error': 'Not found'}), 404
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({'error': 'invalid body'}), 400

    # ── permission pre-checks (reject before any mutation) ──
    admin_fields = ('owner_role', 'due_date')
    if any(f in body for f in admin_fields) and not _is_admin(user):
        return jsonify({'error': 'Unauthorized - admin access required to set owner/due'}), 403
    if 'vault_ref' in body and not _is_super(user):
        return jsonify({'error': 'Unauthorized - superadmin access required to set vault_ref'}), 403

    # ── validate all inputs up front (never 500) ──
    if 'status' in body:
        if body['status'] not in ITEM_STATUSES:
            return jsonify({'error': 'invalid status', 'allowed': list(ITEM_STATUSES)}), 400
    if 'owner_role' in body and body['owner_role'] is not None:
        if body['owner_role'] not in TASK_ROLES:
            return jsonify({'error': 'invalid owner_role', 'allowed': list(TASK_ROLES)}), 400
    if 'blocked_reason' in body:
        br = body['blocked_reason']
        if br is not None and (not isinstance(br, str) or len(br) > MAX_BLOCKED_REASON):
            return jsonify({'error': 'blocked_reason too long (max %d)' % MAX_BLOCKED_REASON}), 400
    due_val = None
    if 'due_date' in body:
        ok, due_val = _parse_due(body['due_date'])
        if not ok:
            return jsonify({'error': 'invalid due_date (expected YYYY-MM-DD)'}), 400
    clean_ref = None
    if 'vault_ref' in body:
        ref = body['vault_ref']
        if ref in (None, ''):
            clean_ref = None
        else:
            clean_ref = _safe_ref(ref, _vault_root())
            if not clean_ref:
                return jsonify({'error': 'invalid vault_ref'}), 400

    # ── apply ──
    if 'status' in body:
        new_status = body['status']
        if new_status == 'done' and item.status != 'done':
            item.completed_by = user.id
            item.completed_at = datetime.utcnow()
        elif new_status != 'done':
            item.completed_by = None
            item.completed_at = None
        item.status = new_status
    if 'blocked_reason' in body:
        item.blocked_reason = (body['blocked_reason'] or None)
    if 'owner_role' in body:
        item.owner_role = body['owner_role']  # already validated (None or valid role)
    if 'due_date' in body:
        item.due_date = due_val
    if 'vault_ref' in body:
        item.vault_ref = clean_ref

    db.session.commit()
    return jsonify(item.to_dict(is_superadmin=_is_super(user))), 200


@checklist_bp.post('/api/checklist/items/<int:item_id>/materialize')
@jwt_required()
def api_materialize(item_id):
    """Create (or link) a Task so the item shows on the Gantt and Calendar.
    Idempotent: if the item already links a live task, return it unchanged."""
    user = _user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    item = _visible_item(item_id)
    if not item:
        return jsonify({'error': 'Not found'}), 404

    if item.task_id:
        existing = Task.query.filter_by(id=item.task_id, is_deleted=False).first()
        if existing:
            return jsonify({'item_id': item.id, 'task_id': existing.id, 'created': False}), 200

    title = ('[%s] %s' % (tpl.stage_name(item.stage_key), item.label))[:255]
    task = Task(workspace_id=item.workspace_id, caseid=item.caseid, userid=user.id,
                title=title, status='pending', priority='Medium',
                duedate=item.due_date, startdate=None)
    db.session.add(task)
    db.session.flush()
    item.task_id = task.id
    db.session.commit()
    return jsonify({'item_id': item.id, 'task_id': task.id, 'created': True}), 201


@checklist_bp.get('/api/checklist/next-actions')
@jwt_required()
def api_next_actions():
    """THE AGENT ENDPOINT: the next missing item per visible matter, sorted by
    due_date asc (nulls last), then days-in-stage desc. Carries NO client names,
    emails or free text beyond the item label (and the lawyer-flag reason)."""
    user = _user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    limit = request.args.get('limit', default=20, type=int)
    if not limit or limit < 1:
        limit = 20
    limit = min(limit, MAX_NEXT_ACTIONS)
    is_super = _is_super(user)

    rows = (workspace_filter(
        MatterChecklistItem.query.filter(
            MatterChecklistItem.is_deleted == False,  # noqa: E712
            MatterChecklistItem.status.in_(MISSING_STATUSES),
        ), MatterChecklistItem)
        .order_by(MatterChecklistItem.caseid.asc(), MatterChecklistItem.position.asc())
        .all())

    # one entry per matter: the lowest-position missing item
    first_by_case = {}
    for it in rows:
        if it.caseid not in first_by_case:
            first_by_case[it.caseid] = it

    case_ids = list(first_by_case.keys())
    cases = {c.id: c for c in Case.query.filter(Case.id.in_(case_ids)).all()} if case_ids else {}

    entries = []
    for cid, it in first_by_case.items():
        c = cases.get(cid)
        entry = {
            'case_id': cid,
            'case_no': (c.display_id() if c else None),
            'stage': tpl.stage_name(it.stage_key),
            'stage_key': it.stage_key,
            'label': it.label,
            'kind': it.kind,
            'owner_role': it.owner_role,
            'due_date': it.due_date.isoformat() if it.due_date else None,
            'days_overdue': _days_overdue(it.due_date),
            'days_in_stage': _days_in_stage(it),
            'blocked_reason': it.blocked_reason,
            'item_id': it.id,
        }
        if is_super:
            entry['vault_docs_api'] = ('/api/gantt/tasks/%d/docs' % it.task_id) if it.task_id else None
        entries.append(entry)

    # due_date asc nulls last, then days-in-stage desc
    entries.sort(key=lambda e: (e['due_date'] is None, e['due_date'] or '', -e['days_in_stage']))
    return jsonify({'count': len(entries[:limit]), 'actions': entries[:limit]}), 200


# ── HTML page shell ───────────────────────────────────────────────────────────
@checklist_bp.get('/cases/<int:case_id>/checklist')
@jwt_required(optional=True)
def checklist_page(case_id):
    """Page shell. Like the Gantt page, the JWT lives in localStorage so all
    authorization happens on the JSON endpoints; this only renders the shell.
    The kill-switch 404 is already enforced in before_request."""
    return render_template('checklist.html', case_id=case_id, checklist_enabled=True)

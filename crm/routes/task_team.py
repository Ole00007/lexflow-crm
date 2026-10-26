"""Task team roles, vault docs link and lawyer flags for the Gantt (WS-A).

Everything here is tenant-scoped through workspace_filter, JWT protected, and the
write endpoints are admin/superadmin only. The vault (Ole's Obsidian) is NOT a
tenant resource: vault links/doc listings are superadmin only.

Endpoints (all under /api/gantt):
  GET  /tasks/<id>/docs              superadmin  list documents in the task's vault_ref folder
  PUT  /tasks/<id>/assignees         admin       replace [{member_id, role}] (members from the firm Team)
  PUT  /tasks/<id>/vault-ref         superadmin  set the vault-relative folder (validated)
  POST /tasks/<id>/flag-lawyer       any visible user (human or agent) — raises an open flag
  GET  /tasks/<id>/flags             list flags for the task
  POST /flags/<id>/resolve           admin
"""
import os
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..extensions import db
from ..models.task import Task
from ..models.user import User
from ..models.firm_team import FirmTeamMember
from ..models.task_assignee import TaskAssignee, TaskFlag, TASK_ROLES
from ..workspace import workspace_filter

task_team_bp = Blueprint('task_team', __name__, url_prefix='/api/gantt')

MAX_DOCS = 100
_HIDDEN_PREFIX = '.'


# ── helpers ────────────────────────────────────────────────────────────────
def _user():
    try:
        return User.query.filter_by(id=int(get_jwt_identity()), is_deleted=False).first()
    except Exception:
        return None


def _vault_root():
    v = os.environ.get('LEXFLOW_VAULT_DIR', '').strip()
    return os.path.realpath(v) if v and os.path.isdir(v) else None


def _safe_ref(ref, root):
    """Validate a vault-relative reference. Returns the clean relative path or None."""
    if not ref or not isinstance(ref, str) or len(ref) > 255:
        return None
    ref = ref.replace('\\', '/').strip()
    if ref.startswith('/'):
        return None            # absolute paths are never valid vault references
    ref = ref.strip('/')
    if not ref or ref.startswith('.') or '\x00' in ref:
        return None
    parts = ref.split('/')
    if any(p in ('', '.', '..') or p.startswith(_HIDDEN_PREFIX) for p in parts):
        return None
    if root:
        real = os.path.realpath(os.path.join(root, ref))
        if not (real == root or real.startswith(root + os.sep)):
            return None
    return ref


def _obsidian_url(root, rel):
    return 'obsidian://open?vault=%s&file=%s' % (quote(os.path.basename(root), safe=''), quote(rel, safe=''))


def _visible_task(task_id):
    return workspace_filter(Task.query.filter_by(id=task_id, is_deleted=False), Task).first()


def _fill_inferred_responsible(tasks, out):
    """Every task shows WHO is responsible: when no explicit team is assigned, fall back to the task's own
    assignee (tasks.userid), else the matter's owner / assigned lawyer. Marked inferred=True (UI may soften it)."""
    from ..models.user import User
    from ..models.case import Case
    missing = [t for t in tasks if t.id in out and not out[t.id]['team']]
    if not missing:
        return
    case_ids = {t.caseid for t in missing if t.caseid}
    cases = {c.id: c for c in Case.query.filter(Case.id.in_(case_ids)).all()} if case_ids else {}
    uids = {t.userid for t in missing if t.userid}
    for c in cases.values():
        uids |= {x for x in (c.ownerid, c.assignedto) if x}
    users = {u.id: u for u in User.query.filter(User.id.in_(uids)).all()} if uids else {}
    label, color = TASK_ROLES['case_owner']

    def entry(u):
        local = (u.email or '').split('@')[0].replace('.', ' ').replace('_', ' ').strip()
        return {'member_id': None, 'user_id': u.id, 'name': local.title() or u.email, 'role': 'case_owner',
                'role_label': label, 'color': color, 'email': None, 'phone': None, 'inferred': True}
    for t in missing:
        uid = t.userid
        if not uid and t.caseid in cases:
            uid = cases[t.caseid].assignedto or cases[t.caseid].ownerid
        if uid and uid in users:
            out[t.id]['team'].append(entry(users[uid]))


def team_payload(tasks, user):
    """Per-task extras for GET /api/gantt/tasks: {task_id: {team, vault, open_flags}}."""
    ids = [t.id for t in tasks]
    out = {t.id: {'team': [], 'vault': None, 'open_flags': 0} for t in tasks}
    if not ids:
        return out
    for a in TaskAssignee.query.filter(TaskAssignee.task_id.in_(ids)).all():
        if a.task_id in out and a.member is not None:
            out[a.task_id]['team'].append(a.to_dict())
    for f in TaskFlag.query.filter(TaskFlag.task_id.in_(ids), TaskFlag.status == 'open').all():
        out[f.task_id]['open_flags'] += 1
    _fill_inferred_responsible(tasks, out)
    order = list(TASK_ROLES)
    for v in out.values():
        v['team'].sort(key=lambda m: order.index(m['role']) if m['role'] in order else 99)
    if user is not None and user.role == 'superadmin':
        root = _vault_root()
        for t in tasks:
            ref = getattr(t, 'vault_ref', None)
            if ref and root and _safe_ref(ref, root):
                out[t.id]['vault'] = {
                    'ref': ref,
                    'obsidian_url': _obsidian_url(root, ref),
                    'docs_api': '/api/gantt/tasks/%d/docs' % t.id,
                }
    return out


# ── endpoints ──────────────────────────────────────────────────────────────
@task_team_bp.get('/tasks/<int:task_id>/docs')
@jwt_required()
def task_docs(task_id):
    user = _user()
    if not user or user.role != 'superadmin':
        return jsonify({'error': 'Unauthorized - superadmin access required'}), 403
    task = _visible_task(task_id)
    if not task:
        return jsonify({'error': 'Not found'}), 404
    root = _vault_root()
    ref = _safe_ref(getattr(task, 'vault_ref', None), root) if root else None
    if not root or not ref:
        return jsonify({'task_id': task_id, 'ref': None, 'docs': [], 'source': 'unconfigured'}), 200
    base = os.path.realpath(os.path.join(root, ref))
    docs = []
    if os.path.isfile(base):
        candidates = [base]
    elif os.path.isdir(base):
        candidates = []
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if not d.startswith(_HIDDEN_PREFIX)]
            for fn in sorted(filenames):
                if not fn.startswith(_HIDDEN_PREFIX):
                    candidates.append(os.path.join(dirpath, fn))
            if len(candidates) >= MAX_DOCS * 2:
                break
    else:
        candidates = []
    for p in candidates:
        real = os.path.realpath(p)
        if not (real == root or real.startswith(root + os.sep)) or not os.path.isfile(real):
            continue  # symlink escaping the vault / not a regular file
        rel = os.path.relpath(real, root).replace(os.sep, '/')
        st = os.stat(real)
        docs.append({'name': os.path.basename(real), 'path_rel': rel, 'size': st.st_size,
                     'modified': datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds'),
                     'obsidian_url': _obsidian_url(root, rel)})
        if len(docs) >= MAX_DOCS:
            break
    return jsonify({'task_id': task_id, 'ref': ref, 'docs': docs, 'source': 'obsidian'}), 200


@task_team_bp.put('/tasks/<int:task_id>/vault-ref')
@jwt_required()
def set_vault_ref(task_id):
    user = _user()
    if not user or user.role != 'superadmin':
        return jsonify({'error': 'Unauthorized - superadmin access required'}), 403
    task = _visible_task(task_id)
    if not task:
        return jsonify({'error': 'Not found'}), 404
    ref = (request.get_json(silent=True) or {}).get('vault_ref')
    if ref in (None, ''):
        task.vault_ref = None
    else:
        clean = _safe_ref(ref, _vault_root())
        if not clean:
            return jsonify({'error': 'Invalid vault_ref'}), 400
        task.vault_ref = clean
    db.session.commit()
    return jsonify({'task_id': task.id, 'vault_ref': task.vault_ref}), 200


@task_team_bp.put('/tasks/<int:task_id>/assignees')
@jwt_required()
def set_assignees(task_id):
    user = _user()
    if not user or user.role not in ('admin', 'superadmin'):
        return jsonify({'error': 'Unauthorized - admin access required'}), 403
    task = _visible_task(task_id)
    if not task:
        return jsonify({'error': 'Not found'}), 404
    body = request.get_json(silent=True)
    items = body.get('assignees') if isinstance(body, dict) else None
    if not isinstance(items, list) or len(items) > 12:
        return jsonify({'error': 'assignees must be a list (max 12)'}), 400
    clean, seen = [], set()
    for it in items:
        if not isinstance(it, dict) or it.get('role') not in TASK_ROLES:
            return jsonify({'error': 'invalid role', 'allowed': list(TASK_ROLES)}), 400
        try:
            mid = int(it.get('member_id'))
        except (TypeError, ValueError):
            return jsonify({'error': 'invalid member_id'}), 400
        member = FirmTeamMember.query.filter_by(id=mid, is_active=True).first()
        # the member must belong to the task's workspace OR to its parent firm (client sub-workspaces)
        ws = task.workspace
        allowed_ws = {task.workspace_id}
        if ws is not None and getattr(ws, 'parent_workspace_id', None):
            allowed_ws.add(ws.parent_workspace_id)
        if member is None or member.workspace_id not in allowed_ws:
            return jsonify({'error': 'member not in this workspace team'}), 400
        key = (mid, it['role'])
        if key not in seen:
            seen.add(key)
            clean.append(key)
    TaskAssignee.query.filter_by(task_id=task.id).delete()
    for mid, role in clean:
        db.session.add(TaskAssignee(workspace_id=task.workspace_id, task_id=task.id, team_member_id=mid, role=role))
    db.session.commit()
    rows = TaskAssignee.query.filter_by(task_id=task.id).all()
    return jsonify({'task_id': task.id, 'team': [r.to_dict() for r in rows]}), 200


@task_team_bp.post('/tasks/<int:task_id>/flag-lawyer')
@jwt_required()
def flag_lawyer(task_id):
    user = _user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    task = _visible_task(task_id)
    if not task:
        return jsonify({'error': 'Not found'}), 404
    body = request.get_json(silent=True) or {}
    reason = str(body.get('reason') or '').strip()[:500]
    # the lawyer to flag: explicit lawyer_review > case_owner of the task
    target = None
    for role in ('lawyer_review', 'case_owner'):
        a = TaskAssignee.query.filter_by(task_id=task.id, role=role).first()
        if a:
            target = a.team_member_id
            break
    agent = (request.headers.get('X-Agent-Name') or '').strip()[:80] or None
    flag = TaskFlag(workspace_id=task.workspace_id, task_id=task.id, raised_by_user_id=user.id,
                    raised_by_agent=agent, target_member_id=target, reason=reason, status='open')
    db.session.add(flag)
    db.session.commit()
    return jsonify(flag.to_dict()), 201


@task_team_bp.get('/tasks/<int:task_id>/flags')
@jwt_required()
def list_flags(task_id):
    if not _user():
        return jsonify({'error': 'Unauthorized'}), 401
    task = _visible_task(task_id)
    if not task:
        return jsonify({'error': 'Not found'}), 404
    rows = TaskFlag.query.filter_by(task_id=task.id).order_by(TaskFlag.id.desc()).limit(50).all()
    return jsonify([r.to_dict() for r in rows]), 200


@task_team_bp.post('/flags/<int:flag_id>/resolve')
@jwt_required()
def resolve_flag(flag_id):
    user = _user()
    if not user or user.role not in ('admin', 'superadmin'):
        return jsonify({'error': 'Unauthorized - admin access required'}), 403
    flag = workspace_filter(TaskFlag.query.filter_by(id=flag_id), TaskFlag).first()
    if not flag:
        return jsonify({'error': 'Not found'}), 404
    flag.status = 'resolved'
    flag.resolved_at = datetime.utcnow()
    db.session.commit()
    return jsonify(flag.to_dict()), 200

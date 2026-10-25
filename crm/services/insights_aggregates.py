"""Insights aggregates (WS-D) — Harvey-style usage/progress analytics.

AGGREGATES ONLY. This module never returns client names, task titles, emails,
phone numbers or any free text. It returns counts and derived metrics scoped to
the caller's visible workspaces (workspace_filter / get_visible_workspace_ids).

Small-cell suppression: counts 1-2 inside a breakdown are returned as-is for a
non-superadmin (it is their own data) but never mix tenants — every query is
workspace-scoped, so a breakdown can never contain another tenant's rows.
"""
import logging
from datetime import date, timedelta

from sqlalchemy import func

from ..extensions import db
from ..models.case import Case
from ..models.task import Task
from ..models.task_assignee import TaskAssignee, TaskFlag, TASK_ROLES
from ..models.firm_team import FirmTeamMember
from ..workspace import workspace_filter, get_visible_workspace_ids

logger = logging.getLogger(__name__)

# role key -> colour (mirrors crm/models/task_assignee.py TASK_ROLES + gantt.css)
ROLE_COLORS = {k: v[1] for k, v in TASK_ROLES.items()}

# deadline-health buckets (open tasks)
HEALTH_OVERDUE = 'overdue'
HEALTH_DUE_7 = 'due_7'
HEALTH_DUE_30 = 'due_30'
HEALTH_LATER = 'later'
HEALTH_NONE = 'no_date'

VALID_RANGES = (30, 90, 365)


def _visible_ids():
    """Return the visible workspace id list (None = superadmin sees all)."""
    return get_visible_workspace_ids()


def _scoped(query, model):
    return workspace_filter(query, model)


def _week_start(d):
    """Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


def _initials(name):
    """'Elena Romanelli' -> 'E.R.' ; 'Elisa' -> 'E.' ; None -> '?'."""
    if not name:
        return '?'
    parts = [p for p in name.replace('.', ' ').split() if p]
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][0].upper() + '.'
    return parts[0][0].upper() + '.' + parts[-1][0].upper() + '.'


def _kpis(ws_ids, today, start):
    """KPI cards: open matters, tasks done in range, overdue, due ≤7d, avg days open→first done."""
    # open matters (not soft-deleted, status != Closed)
    q = _scoped(Case.query.filter(Case.is_deleted == False), Case)
    if ws_ids is not None:
        q = q.filter(Case.workspace_id.in_(ws_ids))
    open_matters = q.filter(Case.status != 'Closed').count()

    # tasks done in range (status == 'done' and updatedat within range)
    q = _scoped(Task.query.filter(Task.is_deleted == False), Task)
    if ws_ids is not None:
        q = q.filter(Task.workspace_id.in_(ws_ids))
    tasks_done = q.filter(Task.status == 'done', Task.updatedat >= start).count()

    # overdue open tasks (duedate < today, status != done)
    q = _scoped(Task.query.filter(Task.is_deleted == False), Task)
    if ws_ids is not None:
        q = q.filter(Task.workspace_id.in_(ws_ids))
    overdue = q.filter(Task.status != 'done', Task.duedate.isnot(None), Task.duedate < today).count()

    # due in next 7 days (open)
    q = _scoped(Task.query.filter(Task.is_deleted == False), Task)
    if ws_ids is not None:
        q = q.filter(Task.workspace_id.in_(ws_ids))
    due_7 = q.filter(Task.status != 'done', Task.duedate.isnot(None),
                     Task.duedate >= today, Task.duedate <= today + timedelta(days=7)).count()

    # avg days matter-open -> first task done (only matters with ≥1 done task)
    q = _scoped(Task.query.filter(Task.is_deleted == False), Task)
    if ws_ids is not None:
        q = q.filter(Task.workspace_id.in_(ws_ids))
    done_tasks = q.filter(Task.status == 'done').all()
    first_done = {}
    for t in done_tasks:
        if t.updatedat is None or t.case is None or t.case.openedat is None:
            continue
        key = t.caseid
        if key not in first_done or t.updatedat < first_done[key][0]:
            first_done[key] = (t.updatedat, t.case.openedat)
    if first_done:
        total = 0.0
        for upd, opened in first_done.values():
            total += (upd.date() - opened).days
        avg_days = round(total / len(first_done), 1)
    else:
        avg_days = None

    return {
        'open_matters': open_matters,
        'tasks_done': tasks_done,
        'overdue_tasks': overdue,
        'due_next_7': due_7,
        'avg_days_open_to_first_done': avg_days,
    }


def _activity(ws_ids, today, start, range_days):
    """Weekly series: matters opened, tasks completed, tasks created."""
    weeks = {}
    cur = _week_start(start)
    end = _week_start(today) + timedelta(days=7)
    while cur < end:
        weeks[cur.isoformat()] = {'matters_opened': 0, 'tasks_completed': 0, 'tasks_created': 0}
        cur += timedelta(days=7)

    # matters opened (openedat within range)
    q = _scoped(Case.query.filter(Case.is_deleted == False), Case)
    if ws_ids is not None:
        q = q.filter(Case.workspace_id.in_(ws_ids))
    for c in q.filter(Case.openedat >= start).all():
        if c.openedat:
            wk = _week_start(c.openedat).isoformat()
            if wk in weeks:
                weeks[wk]['matters_opened'] += 1

    # tasks completed (updatedat within range, status done)
    q = _scoped(Task.query.filter(Task.is_deleted == False), Task)
    if ws_ids is not None:
        q = q.filter(Task.workspace_id.in_(ws_ids))
    for t in q.filter(Task.status == 'done', Task.updatedat >= start).all():
        if t.updatedat:
            wk = _week_start(t.updatedat.date()).isoformat()
            if wk in weeks:
                weeks[wk]['tasks_completed'] += 1

    # tasks created (createdat within range)
    q = _scoped(Task.query.filter(Task.is_deleted == False), Task)
    if ws_ids is not None:
        q = q.filter(Task.workspace_id.in_(ws_ids))
    for t in q.filter(Task.createdat >= start).all():
        if t.createdat:
            wk = _week_start(t.createdat.date()).isoformat()
            if wk in weeks:
                weeks[wk]['tasks_created'] += 1

    return [{'week': k, **v} for k, v in sorted(weeks.items())]


def _matters_by_status(ws_ids):
    """Counts of matters by Case.status."""
    q = _scoped(Case.query.filter(Case.is_deleted == False), Case)
    if ws_ids is not None:
        q = q.filter(Case.workspace_id.in_(ws_ids))
    rows = q.with_entities(Case.status, func.count(Case.id)).group_by(Case.status).all()
    return [{'status': s or 'Unknown', 'count': n} for s, n in rows]


def _deadline_health(ws_ids, today):
    """Open tasks bucketed by deadline health."""
    q = _scoped(Task.query.filter(Task.is_deleted == False), Task)
    if ws_ids is not None:
        q = q.filter(Task.workspace_id.in_(ws_ids))
    open_tasks = q.filter(Task.status != 'done').all()
    buckets = {HEALTH_OVERDUE: 0, HEALTH_DUE_7: 0, HEALTH_DUE_30: 0, HEALTH_LATER: 0, HEALTH_NONE: 0}
    for t in open_tasks:
        if t.duedate is None:
            buckets[HEALTH_NONE] += 1
        elif t.duedate < today:
            buckets[HEALTH_OVERDUE] += 1
        elif t.duedate <= today + timedelta(days=7):
            buckets[HEALTH_DUE_7] += 1
        elif t.duedate <= today + timedelta(days=30):
            buckets[HEALTH_DUE_30] += 1
        else:
            buckets[HEALTH_LATER] += 1
    return buckets


def _workload_by_role(ws_ids):
    """Open tasks per role and per team member (staff only, initials + count)."""
    q = _scoped(TaskAssignee.query, TaskAssignee)
    if ws_ids is not None:
        q = q.filter(TaskAssignee.workspace_id.in_(ws_ids))
    q = q.join(Task, TaskAssignee.task_id == Task.id).filter(
        Task.is_deleted == False, Task.status != 'done')
    rows = q.with_entities(TaskAssignee.role, func.count(TaskAssignee.id)).group_by(TaskAssignee.role).all()
    by_role = {r: 0 for r in TASK_ROLES}
    for role, n in rows:
        if role in by_role:
            by_role[role] = n

    # per member: staff only (FirmTeamMember), never clients. Count open tasks.
    q = _scoped(TaskAssignee.query, TaskAssignee)
    if ws_ids is not None:
        q = q.filter(TaskAssignee.workspace_id.in_(ws_ids))
    q = q.join(Task, TaskAssignee.task_id == Task.id).filter(
        Task.is_deleted == False, Task.status != 'done')
    member_rows = q.with_entities(TaskAssignee.team_member_id, func.count(TaskAssignee.id)).group_by(TaskAssignee.team_member_id).all()
    members = {m.id: m for m in FirmTeamMember.query.all()}
    per_member = []
    for mid, n in member_rows:
        m = members.get(mid)
        if not m:
            continue
        per_member.append({'initials': _initials(m.name), 'count': n})
    per_member.sort(key=lambda x: (-x['count'], x['initials']))

    return {
        'by_role': [{'role': k, 'label': TASK_ROLES[k][0], 'color': ROLE_COLORS[k], 'count': v}
                    for k, v in by_role.items()],
        'by_member': per_member,
    }


def _flags(ws_ids, today, start):
    """Open lawyer flags, resolved this range, median hours-to-resolve."""
    q = _scoped(TaskFlag.query, TaskFlag)
    if ws_ids is not None:
        q = q.filter(TaskFlag.workspace_id.in_(ws_ids))
    open_flags = q.filter(TaskFlag.status == 'open').count()

    q = _scoped(TaskFlag.query, TaskFlag)
    if ws_ids is not None:
        q = q.filter(TaskFlag.workspace_id.in_(ws_ids))
    resolved = q.filter(TaskFlag.status == 'resolved', TaskFlag.resolved_at >= start).all()
    resolved_count = len(resolved)

    hours = []
    for f in resolved:
        if f.created_at and f.resolved_at:
            delta = (f.resolved_at - f.created_at).total_seconds() / 3600.0
            if delta >= 0:
                hours.append(delta)
    median = None
    if hours:
        hours.sort()
        n = len(hours)
        median = round(hours[n // 2] if n % 2 else (hours[n // 2 - 1] + hours[n // 2]) / 2.0, 1)

    return {'open': open_flags, 'resolved_in_range': resolved_count, 'median_hours_to_resolve': median}


def build_summary(range_days):
    """Build the full /api/insights/summary payload for the current user.

    range_days must be one of VALID_RANGES (validated by the route).
    """
    today = date.today()
    start = today - timedelta(days=range_days - 1)
    ws_ids = _visible_ids()

    # previous equal-length window (for KPI deltas) — aggregates only
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=range_days - 1)
    kpis_prev = _kpis(ws_ids, prev_end, prev_start)

    return {
        'range': range_days,
        'generated_at': today.isoformat(),
        'kpis': _kpis(ws_ids, today, start),
        'kpis_previous': kpis_prev,
        'activity': _activity(ws_ids, today, start, range_days),
        'matters_by_status': _matters_by_status(ws_ids),
        'deadline_health': _deadline_health(ws_ids, today),
        'workload_by_role': _workload_by_role(ws_ids),
        'flags': _flags(ws_ids, today, start),
    }

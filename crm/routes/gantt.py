"""Gantt C — read-only staff timeline endpoint.

GET /api/gantt/tasks — returns a JSON array of task objects for the
Frappe Gantt chart. Workspace-scoped, JWT-protected, and filtered
per the approved P3 authorization rule.

Response whitelist (exact — no extra keys):
  id, name, start, end, progress, dependencies, custom_class
"""
import logging
from datetime import date

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_

from ..extensions import db
from ..models.task import Task
from ..models.case import Case
from ..models.user import User
from ..workspace import workspace_filter

logger = logging.getLogger(__name__)

gantt_bp = Blueprint('gantt', __name__, url_prefix='/api/gantt')

# Status → (progress, custom_class) — approved map (docs/gantt_bar_semantics.md)
_STATUS_MAP = {
    'pending':     (0,   'gantt-status-pending'),
    'in_progress': (50,  'gantt-status-in-progress'),
    'done':        (100, 'gantt-status-done'),
}
_UNKNOWN_STATUS = (0, 'gantt-status-unknown')


@gantt_bp.get('/tasks')
@jwt_required()
def get_gantt_tasks():
    """Return tasks for the read-only Gantt chart.

    Authorization (P3 approved rule):
      - workspace-scoped via workspace_filter
      - admin/superadmin → all tasks in visible workspaces
      - staff → own tasks + tasks on cases they own/are assigned to
    """
    uid = int(get_jwt_identity())
    user = db.session.get(User, uid)
    if not user:
        return jsonify([]), 200

    # Base query: workspace-scoped, not soft-deleted
    query = workspace_filter(Task.query.filter_by(is_deleted=False), Task)

    # P3 authorization: non-admins see only their own tasks + case-owned tasks
    if user.role not in ('admin', 'superadmin'):
        query = query.join(Case, Task.caseid == Case.id).filter(
            or_(
                Task.userid == uid,
                Case.ownerid == uid,
                Case.assignedto == uid,
            )
        )

    tasks = query.all()
    # ids that can legally be referenced as a dependency (visible + dated + valid)
    visible_ids = {t.id for t in tasks if t.startdate and t.duedate and t.duedate >= t.startdate}

    today = date.today()
    result = []
    dropped_missing_dates = 0
    dropped_end_before_start = 0

    for task in tasks:
        # start = startdate (new P2 field); end = duedate
        start = task.startdate
        end = task.duedate

        # Exclusion: missing start or end
        if start is None or end is None:
            dropped_missing_dates += 1
            continue

        # Exclusion: end < start (non-sensitive warning — task id only)
        if end < start:
            dropped_end_before_start += 1
            logger.warning("Gantt: task %d dropped (end < start)", task.id)
            continue

        # Status → progress + custom_class
        progress, custom_class = _STATUS_MAP.get(task.status, _UNKNOWN_STATUS)

        # Overdue modifier: end < today AND progress < 100
        if end < today and progress < 100:
            custom_class = custom_class + ' gantt-status-overdue'

        # Dependencies: only ids that are themselves in this response (no leak of
        # hidden/other-workspace tasks, no dangling arrows), never self-reference.
        deps = []
        for part in (task.depends_on or '').split(','):
            part = part.strip()
            if part.isascii() and part.isdigit() and int(part) in visible_ids and int(part) != task.id and part not in deps:
                deps.append(part)

        result.append({
            'id': task.id,
            'name': task.title,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'progress': progress,
            'dependencies': ','.join(deps),
            'custom_class': custom_class,
        })

    if dropped_missing_dates or dropped_end_before_start:
        logger.info(
            "Gantt: dropped %d missing-date, %d end-before-start (workspace user %d)",
            dropped_missing_dates, dropped_end_before_start, uid,
        )

    return jsonify(result), 200

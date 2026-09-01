from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, date
from ..extensions import db
from ..models.task import Task
from ..models.case import Case
from ..models.user import User
from ..workspace import get_current_workspace_id, workspace_filter
from ..activity_logger import log_activity

tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')

def _safe_date(value):
    """Parse a date string strictly (YYYY-MM-DD). Returns a date or None.
    Prevents malformed values (e.g. year 92026) from reaching the DB and
    crashing GET /api/tasks during result conversion."""
    if not value:
        return None
    if isinstance(value, date):
        return value
    s = str(value).strip()
    try:
        d = datetime.strptime(s[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None
    if not (1900 <= d.year <= 2100):
        return None
    return d

def _filtered_query():
    # superadmin sees all workspaces (workspace_filter bypasses for superadmin)
    return workspace_filter(Task.query.filter_by(is_deleted=False), Task)

@tasks_bp.get('/')
@jwt_required()
def get_tasks():
    tasks = _filtered_query().order_by(Task.id.desc()).all()
    return jsonify([t.to_dict() for t in tasks]), 200

@tasks_bp.get('/<int:task_id>')
@jwt_required()
def get_task(task_id):
    task = _filtered_query().filter_by(id=task_id).first()
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task.to_dict()), 200

@tasks_bp.post('/')
@jwt_required()
def create_task():
    data = request.get_json()
    if not data or not data.get('title') or not data.get('caseid'):
        return jsonify({'error': 'title and caseid are required'}), 400

    case = Case.query.filter_by(id=data.get('caseid'), is_deleted=False).first()
    if not case:
        return jsonify({'error': 'Case not found'}), 404

    task = Task(
        workspace_id=get_current_workspace_id() or 1,
        caseid=data.get('caseid'),
        userid=data.get('userid'),
        title=data.get('title'),
        description=data.get('description'),
        status=data.get('status', 'pending'),
        priority=data.get('priority', 'Medium'),
        duedate=_safe_date(data.get('duedate'))
    )
    db.session.add(task)
    db.session.commit()
    actor_id = int(get_jwt_identity())
    log_activity(actor_id, "task", task.id, "created", f"Task '{task.title}' created")

    # Optional: also reflect the task on the workspace calendar (uses due date).
    if data.get('add_to_calendar') and task.duedate:
        from ..models.calendar_event import CalendarEvent
        from datetime import datetime, time
        start = datetime.combine(task.duedate, time(9, 0))
        end = start.replace(hour=10)
        ev = CalendarEvent(
            workspace_id=task.workspace_id,
            caseid=task.caseid,
            title=task.title,
            description=task.description,
            event_type='meeting',
            start_datetime=start,
            end_datetime=end,
            is_all_day=False,
            status='scheduled',
            notes=f"task:{task.id}",
        )
        db.session.add(ev)
        db.session.commit()
        log_activity(actor_id, "case" if task.caseid else "task", task.caseid or task.id,
                     "event_created", f"Calendar event '{task.title}' created from task")
    return jsonify(task.to_dict()), 201

@tasks_bp.put('/<int:task_id>')
@jwt_required()
def update_task(task_id):
    task = _filtered_query().filter_by(id=task_id).first()
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    data = request.get_json()
    for field in ['title', 'description', 'status', 'priority']:
        if field in data:
            setattr(task, field, data[field])
    if 'duedate' in data:
        task.duedate = _safe_date(data['duedate'])
    if 'userid' in data:
        task.userid = data['userid']
    db.session.commit()
    actor_id = int(get_jwt_identity())
    log_activity(actor_id, "task", task.id, "updated", f"Task '{task.title}' updated")
    return jsonify(task.to_dict()), 200

@tasks_bp.delete('/<int:task_id>')
@jwt_required()
def delete_task(task_id):
    task = _filtered_query().filter_by(id=task_id).first()
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    db.session.delete(task)
    db.session.commit()
    actor_id = int(get_jwt_identity())
    log_activity(actor_id, "task", task.id, "deleted", f"Task '{task.title}' deleted")
    return jsonify({'message': 'Task deleted'}), 200
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models.task import Task
from ..models.case import Case
from ..models.user import User
from ..workspace import get_current_workspace_id

tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')

def _filtered_query():
    q = Task.query.filter_by(is_deleted=False)
    wid = get_current_workspace_id()
    if wid is not None:
        q = q.filter_by(workspace_id=wid)
    return q

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
        duedate=data.get('duedate')
    )
    db.session.add(task)
    db.session.commit()
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
        task.duedate = data['duedate']
    if 'userid' in data:
        task.userid = data['userid']
    db.session.commit()
    return jsonify(task.to_dict()), 200

@tasks_bp.delete('/<int:task_id>')
@jwt_required()
def delete_task(task_id):
    task = _filtered_query().filter_by(id=task_id).first()
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({'message': 'Task deleted'}), 200
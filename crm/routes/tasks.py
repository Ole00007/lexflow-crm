from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models.task import Task
from ..models.case import Case
from ..models.user import User
from datetime import datetime

tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')

@tasks_bp.get('/')
@jwt_required()
def get_tasks():
    # Filter out deleted tasks
    tasks = Task.query.filter_by(is_deleted=False).order_by(Task.id.desc()).all()
    return jsonify([t.to_dict() for t in tasks]), 200

@tasks_bp.get('/<int:task_id>')
@jwt_required()
def get_task(task_id):
    task = Task.query.filter_by(id=task_id, is_deleted=False).first()
    
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
    
    if data.get('userid'):
        user = User.query.filter_by(id=data.get('userid'), is_deleted=False).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
    
    task = Task(
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
    task = Task.query.filter_by(id=task_id, is_deleted=False).first()
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    data = request.get_json()
    
    if 'title' in data:
        task.title = data['title']
    if 'description' in data:
        task.description = data['description']
    if 'status' in data:
        task.status = data['status']
    if 'priority' in data:
        task.priority = data['priority']
    if 'duedate' in data:
        task.duedate = data['duedate']
    if 'userid' in data:
        if data['userid'] is not None:
            user = User.query.filter_by(id=data['userid'], is_deleted=False).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404
        task.userid = data['userid']
    
    db.session.commit()
    
    return jsonify(task.to_dict()), 200

@tasks_bp.delete('/<int:task_id>')
@jwt_required()
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, is_deleted=False).first()
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # Soft delete
    task.is_deleted = True
    task.deleted_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'deleted': True}), 200

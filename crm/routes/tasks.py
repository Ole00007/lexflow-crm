from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db, limiter
from ..models.task import Task
from ..models.case import Case
from ..models.user import User
from ..validators import validate_string, validate_date, validate_enum, validate_integer
from datetime import datetime

tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')

VALID_STATUS = ["pending", "in_progress", "completed", "cancelled"]
VALID_PRIORITY = ["Low", "Medium", "High", "Critical"]

@tasks_bp.get('/')
@jwt_required()
@limiter.limit("60 per minute")
def get_tasks():
    """Get all active tasks"""
    tasks = Task.query.filter_by(is_deleted=False).order_by(Task.id.desc()).all()
    return jsonify([t.to_dict() for t in tasks]), 200

@tasks_bp.get('/<int:task_id>')
@jwt_required()
@limiter.limit("60 per minute")
def get_task(task_id):
    """Get task by ID"""
    task = Task.query.filter_by(id=task_id, is_deleted=False).first()
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify(task.to_dict()), 200

@tasks_bp.post('/')
@jwt_required()
@limiter.limit("30 per minute")
def create_task():
    """Create a new task"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400
    
    # Validate caseid
    is_valid, msg = validate_integer(data.get('caseid'), 'caseid', required=True)
    if not is_valid:
        return jsonify({'error': msg}), 400
    
    # Validate title
    is_valid, title = validate_string(data.get('title'), 'title', min_length=3, max_length=255, required=True)
    if not is_valid:
        return jsonify({'error': title}), 400
    
    # Verify case exists
    case = Case.query.filter_by(id=data.get('caseid'), is_deleted=False).first()
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    
    # Validate userid if provided
    if data.get('userid'):
        is_valid, user_id = validate_integer(data.get('userid'), 'userid', required=False)
        if not is_valid:
            return jsonify({'error': user_id}), 400
        user = User.query.filter_by(id=user_id, is_deleted=False).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
    
    # Validate description if provided
    description = None
    if data.get('description'):
        is_valid, desc = validate_string(data.get('description'), 'description', min_length=1, max_length=2000, required=False)
        if not is_valid:
            return jsonify({'error': desc}), 400
        description = desc
    
    # Validate status
    status = data.get('status', 'pending')
    is_valid, status_val = validate_enum(status, 'status', VALID_STATUS, required=False)
    if not is_valid:
        return jsonify({'error': status_val}), 400
    
    # Validate priority
    priority = data.get('priority', 'Medium')
    is_valid, priority_val = validate_enum(priority, 'priority', VALID_PRIORITY, required=False)
    if not is_valid:
        return jsonify({'error': priority_val}), 400
    
    # Validate duedate if provided
    duedate = None
    if data.get('duedate'):
        is_valid, dd = validate_date(data.get('duedate'), 'duedate', required=False)
        if not is_valid:
            return jsonify({'error': dd}), 400
        duedate = dd
    
    task = Task(
        caseid=data.get('caseid'),
        userid=data.get('userid'),
        title=title,
        description=description,
        status=status_val,
        priority=priority_val,
        duedate=duedate
    )
    
    db.session.add(task)
    db.session.commit()
    
    return jsonify(task.to_dict()), 201

@tasks_bp.put('/<int:task_id>')
@jwt_required()
@limiter.limit("30 per minute")
def update_task(task_id):
    """Update task"""
    task = Task.query.filter_by(id=task_id, is_deleted=False).first()
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400
    
    # Update title with validation
    if 'title' in data:
        if data['title'] is not None:
            is_valid, title = validate_string(data['title'], 'title', min_length=3, max_length=255, required=True)
            if not is_valid:
                return jsonify({'error': title}), 400
            task.title = title
    
    # Update description with validation
    if 'description' in data:
        if data['description'] is not None:
            is_valid, desc = validate_string(data['description'], 'description', min_length=1, max_length=2000, required=False)
            if not is_valid:
                return jsonify({'error': desc}), 400
            task.description = desc
        else:
            task.description = None
    
    # Update status with validation
    if 'status' in data:
        is_valid, status_val = validate_enum(data['status'], 'status', VALID_STATUS, required=False)
        if not is_valid:
            return jsonify({'error': status_val}), 400
        task.status = status_val
    
    # Update priority with validation
    if 'priority' in data:
        is_valid, priority_val = validate_enum(data['priority'], 'priority', VALID_PRIORITY, required=False)
        if not is_valid:
            return jsonify({'error': priority_val}), 400
        task.priority = priority_val
    
    # Update duedate with validation
    if 'duedate' in data:
        is_valid, duedate = validate_date(data['duedate'], 'duedate', required=False)
        if not is_valid:
            return jsonify({'error': duedate}), 400
        task.duedate = duedate
    
    # Update userid with validation
    if 'userid' in data:
        if data['userid'] is not None:
            is_valid, user_id = validate_integer(data['userid'], 'userid', required=False)
            if not is_valid:
                return jsonify({'error': user_id}), 400
            user = User.query.filter_by(id=user_id, is_deleted=False).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404
            task.userid = user_id
        else:
            task.userid = None
    
    db.session.commit()
    
    return jsonify(task.to_dict()), 200

@tasks_bp.delete('/<int:task_id>')
@jwt_required()
@limiter.limit("30 per minute")
def delete_task(task_id):
    """Soft delete task"""
    task = Task.query.filter_by(id=task_id, is_deleted=False).first()
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # Soft delete
    task.is_deleted = True
    task.deleted_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'deleted': True}), 200


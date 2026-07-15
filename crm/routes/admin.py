from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db, limiter
from ..models.user import User

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

def is_admin(user_id):
    """Check if user has admin role"""
    user = User.query.filter_by(id=user_id, is_deleted=False).first()
    return user and user.role == 'admin'

@admin_bp.get('/health')
@limiter.limit("100 per hour")
def admin_health():
    """Admin health check - no auth required"""
    return jsonify({"status": "Admin endpoint operational"}), 200

@admin_bp.get('/users')
@jwt_required()
@limiter.limit("50 per hour")
def list_all_users():
    """List all users - admin only"""
    user_id = get_jwt_identity()
    
    if not is_admin(user_id):
        return jsonify({'error': 'Unauthorized - admin access required'}), 403
    
    users = User.query.filter_by(is_deleted=False).all()
    return jsonify([u.to_dict() for u in users]), 200

@admin_bp.get('/users/<int:user_id>')
@jwt_required()
@limiter.limit("50 per hour")
def get_user_details(user_id):
    """Get specific user details - admin only"""
    current_user_id = get_jwt_identity()
    
    if not is_admin(current_user_id):
        return jsonify({'error': 'Unauthorized - admin access required'}), 403
    
    user = User.query.filter_by(id=user_id, is_deleted=False).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(user.to_dict()), 200

@admin_bp.put('/users/<int:user_id>/role')
@jwt_required()
@limiter.limit("20 per hour")
def update_user_role(user_id):
    """Update user role - admin only"""
    current_user_id = get_jwt_identity()
    
    if not is_admin(current_user_id):
        return jsonify({'error': 'Unauthorized - admin access required'}), 403
    
    data = request.get_json()
    if not data or 'role' not in data:
        return jsonify({'error': 'role is required'}), 400
    
    valid_roles = ['admin', 'staff', 'user']
    if data['role'] not in valid_roles:
        return jsonify({'error': f'role must be one of: {", ".join(valid_roles)}'}), 400
    
    user = User.query.filter_by(id=user_id, is_deleted=False).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user.role = data['role']
    db.session.commit()
    
    return jsonify(user.to_dict()), 200

@admin_bp.delete('/users/<int:user_id>')
@jwt_required()
@limiter.limit("20 per hour")
def delete_user_admin(user_id):
    """Soft delete user - admin only"""
    current_user_id = get_jwt_identity()
    
    if not is_admin(current_user_id):
        return jsonify({'error': 'Unauthorized - admin access required'}), 403
    
    if user_id == current_user_id:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    
    user = User.query.filter_by(id=user_id, is_deleted=False).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    from datetime import datetime
    user.is_deleted = True
    user.deleted_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'deleted': True}), 200

@admin_bp.get('/stats')
@jwt_required()
@limiter.limit("30 per hour")
def get_admin_stats():
    """Get system statistics - admin only"""
    current_user_id = get_jwt_identity()
    
    if not is_admin(current_user_id):
        return jsonify({'error': 'Unauthorized - admin access required'}), 403
    
    from ..models.contact import Contact
    from ..models.case import Case
    from ..models.task import Task
    
    stats = {
        'total_users': User.query.filter_by(is_deleted=False).count(),
        'total_contacts': Contact.query.filter_by(is_deleted=False).count(),
        'total_cases': Case.query.filter_by(is_deleted=False).count(),
        'total_tasks': Task.query.filter_by(is_deleted=False).count(),
        'deleted_users': User.query.filter_by(is_deleted=True).count(),
        'deleted_contacts': Contact.query.filter_by(is_deleted=True).count(),
        'deleted_cases': Case.query.filter_by(is_deleted=True).count(),
        'deleted_tasks': Task.query.filter_by(is_deleted=True).count(),
    }
    
    return jsonify(stats), 200

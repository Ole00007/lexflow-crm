from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from ..extensions import db, limiter
from ..models.user import User
from ..validators import validate_email, validate_string

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.post('/login')
@limiter.limit("10 per minute")  # Strict rate limit to prevent bruteforce
def login():
    """Login with email and password"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400
    
    # Validate email
    email = data.get('email', '').strip() if data.get('email') else None
    is_valid, email_result = validate_email(email)
    if not is_valid:
        return jsonify({'error': email_result}), 400
    
    # Validate password
    password = data.get('password')
    is_valid, msg = validate_string(password, 'Password', min_length=1, required=True)
    if not is_valid:
        return jsonify({'error': msg}), 400
    
    user = User.query.filter_by(email=email_result, is_deleted=False).first()
    
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    access_token = create_access_token(identity=user.id)
    return jsonify({
        'access_token': access_token,
        'user': user.to_dict()
    }), 200

@auth_bp.get('/me')
@jwt_required()
@limiter.limit("60 per minute")
def get_current_user():
    """Get current authenticated user"""
    user_id = get_jwt_identity()
    user = User.query.filter_by(id=user_id, is_deleted=False).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(user.to_dict()), 200

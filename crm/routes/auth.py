from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from ..extensions import db
from ..models.user import User

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.post('/login')
def login():
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password are required'}), 400

    user = User.query.filter_by(email=data.get('email')).first()

    if not user or not user.check_password(data.get('password')):
        return jsonify({'error': 'Invalid email or password'}), 401

    access_token = create_access_token(identity=str(user.id))
    user_data = user.to_dict()
    # Include workspace info
    if user.workspace:
        user_data['workspace'] = user.workspace.to_dict()

    return jsonify({
        'access_token': access_token,
        'user': user_data
    }), 200

@auth_bp.get('/me')
@jwt_required()
def get_current_user():
    user_id = int(get_jwt_identity())
    user = User.query.filter_by(id=user_id, is_deleted=False).first()

    if not user:
        return jsonify({'error': 'User not found'}), 404

    user_data = user.to_dict()
    if user.workspace:
        user_data['workspace'] = user.workspace.to_dict()
    return jsonify(user_data), 200
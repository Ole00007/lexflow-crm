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


@auth_bp.post('/seed')
def seed_production():
    """Seed initial users and workspaces. Only works if no users exist."""
    from ..models.workspace import Workspace
    from datetime import datetime

    if User.query.first():
        return jsonify({'error': 'Database already has users'}), 400

    # Workspaces
    ws_data = [
        ('lexflow', 'LexFlow Default', 'Default workspace'),
        ('avibeagency', 'AVIBE Agency', ''),
        ('pagliano', 'Avvocato Pagliano', ''),
        ('romanelli-studio', 'Studio Romanelli', ''),
        ('romanelli-audit', 'Romanelli Audit', ''),
        ('tommasoferro', 'Avv. Tommaso Ferro', ''),
    ]
    workspaces = []
    for slug, name, desc in ws_data:
        ws = Workspace(slug=slug, name=name, description=desc, is_active=True)
        db.session.add(ws)
        db.session.flush()
        workspaces.append(ws)

    # Users
    users_data = [
        ('olesya00007@yahoo.com', 'Test12345!', 'superadmin', workspaces[0].id),
        ('avibe@lexflow.test', 'Avibe@12345', 'admin', workspaces[0].id),
        ('pagliano@lexflow.test', 'Pag@12345', 'admin', workspaces[2].id),
        ('romanelli@lexflow.test', 'Rom@12345', 'admin', workspaces[3].id),
        ('audit@lexflow.test', 'Audit@12345', 'admin', workspaces[4].id),
        ('ferro@lexflow.test', 'Ferro@12345', 'admin', workspaces[5].id),
    ]
    for email, pw, role, wid in users_data:
        user = User(email=email, role=role, workspace_id=wid)
        user.set_password(pw)
        db.session.add(user)

    db.session.commit()
    return jsonify({'success': True, 'users_created': len(users_data), 'workspaces_created': len(ws_data)}), 201
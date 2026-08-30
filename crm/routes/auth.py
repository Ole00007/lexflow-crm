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


@auth_bp.post('/change-credentials')
@jwt_required()
def change_credentials():
    """Change own password and/or email, with email verification notifications.

    Body (JSON): {current_password, new_password?, new_email?}
    - current_password is always required (re-auth).
    - Sends notification to the OLD email (if email changed) and to the NEW
      email (if provided), plus a password-changed notice.
    """
    from ..notification_service import send_email

    user_id = int(get_jwt_identity())
    user = User.query.filter_by(id=user_id, is_deleted=False).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json() or {}
    current_password = data.get('current_password', '')
    new_password = data.get('new_password')
    new_email = (data.get('new_email') or '').strip().lower()
    old_email = user.email

    if not current_password or not user.check_password(current_password):
        return jsonify({'error': 'Current password is incorrect'}), 401

    # Validate + apply email change
    email_changed = False
    if new_email and new_email != user.email:
        import re
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', new_email):
            return jsonify({'error': 'Invalid email address'}), 400
        existing = User.query.filter_by(email=new_email).first()
        if existing and existing.id != user.id:
            return jsonify({'error': 'Email already in use'}), 409
        old_email = user.email
        user.email = new_email
        email_changed = True

    # Apply password change
    if new_password:
        if len(new_password) < 6:
            return jsonify({'error': 'New password must be at least 6 characters'}), 400
        user.set_password(new_password)

    db.session.commit()

    # Email notifications
    ws_name = user.workspace.name if user.workspace else 'LexFlow'
    if email_changed and new_email:
        send_email(
            to_email=old_email,
            subject=f"[{ws_name}] Login email changed",
            html_body=f"<h3>Your {ws_name} login email was changed</h3>"
                      f"<p>From <b>{old_email}</b> to <b>{new_email}</b>.</p>"
                      f"<p>If you did not make this change, contact your administrator immediately.</p>",
        )
        send_email(
            to_email=new_email,
            subject=f"Welcome to {ws_name} — login confirmed",
            html_body=f"<h3>Your {ws_name} account</h3>"
                      f"<p>Your login is now <b>{new_email}</b>.</p>"
                      f"<p>If you did not make this change, contact your administrator immediately.</p>",
        )
    if new_password:
        target = new_email if email_changed else user.email
        send_email(
            to_email=target,
            subject=f"[{ws_name}] Password changed",
            html_body=f"<h3>Your {ws_name} password was changed</h3>"
                      f"<p>The password for <b>{user.email}</b> was updated successfully.</p>"
                      f"<p>If you did not make this change, contact your administrator immediately.</p>",
        )

    return jsonify({'success': True, 'email_changed': email_changed, 'password_changed': bool(new_password)}), 200


@auth_bp.post('/seed')
def seed_production():
    """Seed initial users and workspaces."""
    from ..models.workspace import Workspace
    from datetime import datetime

    # Clear existing data first
    User.query.delete()
    Workspace.query.delete()
    db.session.commit()

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
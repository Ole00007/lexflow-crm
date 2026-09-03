"""Firm team directory — INTERNAL staff directory (two-model contact split).

The team belongs to the FIRM's workspace (e.g. romanelli-studio). Client
sub-workspaces (romanelli-cl1..clN) see their parent firm's team READ-ONLY
(their lawyer, assistant, office phone) — never other tenants' data.

Visibility rules (user-confirmed 2026-09-03):
  - client sub-workspace user  -> sees ONLY active members of their PARENT firm
  - firm workspace user        -> sees their own workspace's team (full roster)
  - superadmin                 -> sees ALL workspaces, or ?workspace_id=<id>

Management rules:
  - superadmin, or the FIRM's own admin (workspace with no parent) only.
  - a client sub-tenant admin MUST get 403 on POST/PUT/DELETE.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models.firm_team import FirmTeamMember
from ..models.user import User
from ..models.workspace import Workspace

firm_team_bp = Blueprint('firm_team', __name__, url_prefix='/api/firm-team')

VALID_ROLES = {'avvocato', 'assistente', 'office'}


def _current_user():
    """Return the authenticated User or None (deleted/unknown identity)."""
    try:
        uid = get_jwt_identity()
        if not uid:
            return None
        return User.query.filter_by(id=int(uid), is_deleted=False).first()
    except Exception:
        return None


def _team_workspace_id(user):
    """The workspace whose team this user may SEE.

    - client sub-workspace user -> parent firm's workspace id
    - firm workspace user       -> their own workspace id
    - superadmin                -> None (see all, optional ?workspace_id=)
    """
    if user.role == 'superadmin':
        return None
    ws = user.workspace
    if not ws:
        return None
    if ws.parent_workspace_id:
        return ws.parent_workspace_id
    return ws.id


def _can_manage(user, workspace_id):
    """Management rights: superadmin anywhere; the FIRM's own admin only.

    A client sub-workspace admin (role='admin' but parent_workspace_id set)
    must NEVER manage the firm's team -> False -> 403.
    """
    if not user:
        return False
    if user.role == 'superadmin':
        return True
    if user.role != 'admin':
        return False
    ws = user.workspace
    if not ws or ws.parent_workspace_id is not None:
        return False  # sub-tenant admin: read-only
    return ws.id == workspace_id


@firm_team_bp.get('')
@jwt_required()
def list_firm_team():
    """List the team directory for the current user's (parent) firm.

    Query params:
      workspace_id=<id>  superadmin only — restrict to one workspace.
    """
    user = _current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    query = FirmTeamMember.query
    if user.role == 'superadmin':
        wid = request.args.get('workspace_id', type=int)
        if wid is not None:
            ws = db.session.get(Workspace, wid)
            if not ws:
                return jsonify({'error': 'Workspace not found'}), 404
            query = query.filter_by(workspace_id=wid)
    else:
        team_ws_id = _team_workspace_id(user)
        if team_ws_id is None:
            return jsonify({'error': 'No firm workspace associated with this account'}), 404
        query = query.filter_by(workspace_id=team_ws_id)
        if user.workspace.parent_workspace_id is not None:
            # client sub-tenant: read-only, active members only
            query = query.filter_by(is_active=True)

    members = query.order_by(FirmTeamMember.id.asc()).all()
    return jsonify([m.to_dict() for m in members]), 200


@firm_team_bp.get('/<int:member_id>')
@jwt_required()
def get_firm_team_member(member_id):
    """Single member — same visibility rules as the list endpoint."""
    user = _current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    member = FirmTeamMember.query.filter_by(id=member_id).first()
    if not member:
        return jsonify({'error': 'Team member not found'}), 404

    # superadmin sees all; everyone else must belong to their (parent) firm
    if user.role != 'superadmin':
        if member.workspace_id != _team_workspace_id(user):
            return jsonify({'error': 'Team member not found'}), 404
        if user.workspace.parent_workspace_id is not None and not member.is_active:
            return jsonify({'error': 'Team member not found'}), 404

    return jsonify(member.to_dict()), 200


@firm_team_bp.post('')
@jwt_required()
def create_firm_team_member():
    """Create a team member. Superadmin (workspace_id in body) or the FIRM's
    own admin (implicitly their own workspace). Sub-tenant -> 403."""
    user = _current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}

    if user.role == 'superadmin':
        wid = data.get('workspace_id')
        if not wid:
            return jsonify({'error': 'workspace_id is required for superadmin'}), 400
        ws = db.session.get(Workspace, int(wid)) if str(wid).isdigit() else None
        if not ws:
            return jsonify({'error': 'Workspace not found'}), 404
        if ws.parent_workspace_id is not None:
            return jsonify({'error': 'Team members belong to a firm workspace (no parent)'}), 400
        workspace_id = ws.id
    else:
        workspace_id = _team_workspace_id(user)
        if not _can_manage(user, workspace_id):
            return jsonify({'error': 'Forbidden - only the firm admin or superadmin can manage the team'}), 403

    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    role = data.get('role') or 'avvocato'
    if role not in VALID_ROLES:
        return jsonify({'error': f"role must be one of: {', '.join(sorted(VALID_ROLES))}"}), 400

    member = FirmTeamMember(
        workspace_id=workspace_id,
        name=name,
        role=role,
        email=(data.get('email') or '').strip() or None,
        phone=(data.get('phone') or '').strip() or None,
        is_active=bool(data.get('is_active', True)),
    )
    db.session.add(member)
    db.session.commit()
    return jsonify(member.to_dict()), 201


@firm_team_bp.put('/<int:member_id>')
@jwt_required()
def update_firm_team_member(member_id):
    """Update a team member. Same management rule as POST (403 for sub-tenant)."""
    user = _current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    member = FirmTeamMember.query.filter_by(id=member_id).first()
    if not member:
        return jsonify({'error': 'Team member not found'}), 404

    if not _can_manage(user, member.workspace_id):
        return jsonify({'error': 'Forbidden - only the firm admin or superadmin can manage the team'}), 403

    data = request.get_json(silent=True) or {}

    if 'name' in data:
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': 'name cannot be empty'}), 400
        member.name = name
    if 'role' in data:
        if data['role'] not in VALID_ROLES:
            return jsonify({'error': f"role must be one of: {', '.join(sorted(VALID_ROLES))}"}), 400
        member.role = data['role']
    if 'email' in data:
        member.email = (data.get('email') or '').strip() or None
    if 'phone' in data:
        member.phone = (data.get('phone') or '').strip() or None
    if 'is_active' in data and isinstance(data['is_active'], bool):
        member.is_active = data['is_active']

    db.session.commit()
    return jsonify(member.to_dict()), 200


@firm_team_bp.delete('/<int:member_id>')
@jwt_required()
def delete_firm_team_member(member_id):
    """Delete a team member. Same management rule as POST (403 for sub-tenant)."""
    user = _current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    member = FirmTeamMember.query.filter_by(id=member_id).first()
    if not member:
        return jsonify({'error': 'Team member not found'}), 404

    if not _can_manage(user, member.workspace_id):
        return jsonify({'error': 'Forbidden - only the firm admin or superadmin can manage the team'}), 403

    db.session.delete(member)
    db.session.commit()
    return jsonify({'deleted': True, 'id': member_id}), 200

"""
Workspace middleware — enforces multi-tenant data isolation.
"""
from flask import g
from flask_jwt_extended import get_jwt_identity
from .extensions import db
from .models.user import User
from .models.workspace import Workspace
import logging

logger = logging.getLogger(__name__)


def get_current_workspace_id():
    """Return the workspace_id from the currently authenticated user."""
    try:
        uid = get_jwt_identity()
        if uid:
            user = db.session.get(User, int(uid))
            if user:
                g.current_workspace_id = user.workspace_id
                return user.workspace_id
            else:
                logger.warning(f"User {uid} not found in DB")
    except Exception as e:
        logger.warning(f"get_current_workspace_id error: {e}")
    g.current_workspace_id = None
    return None


def get_visible_workspace_ids():
    """Return the list of workspace ids visible to the current user.

    - superadmin → None (meaning all, no filter)
    - normal user → [their own workspace_id] plus any sub-workspaces
      whose parent is their workspace (parent admins see child spaces too).
    """
    try:
        uid = get_jwt_identity()
        if uid:
            user = db.session.get(User, int(uid))
            if user:
                if user.role == 'superadmin':
                    return None
                own = user.workspace_id
                subs = [w.id for w in Workspace.query.filter_by(parent_workspace_id=own, is_active=True).all()]
                return [own] + subs if own else None
    except Exception as e:
        logger.warning(f"get_visible_workspace_ids error: {e}")
    return None


def workspace_filter(query, model):
    """Apply workspace filtering to a query.
    Superadmin users bypass the filter (see all data). Parent workspace admins
    see their own data plus sub-workspace data. Sub-workspace admins see only
    their own workspace.
    """
    try:
        uid = get_jwt_identity()
        if uid:
            user = db.session.get(User, int(uid))
            if user and user.role == 'superadmin':
                return query
    except Exception as e:
        logger.warning(f"workspace_filter error: {e}")

    ids = get_visible_workspace_ids()
    if ids:
        return query.filter(model.workspace_id.in_(ids))
    return query
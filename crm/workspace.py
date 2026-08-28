"""
Workspace middleware — enforces multi-tenant data isolation.
"""
from flask import g
from flask_jwt_extended import get_jwt_identity
import logging

logger = logging.getLogger(__name__)


def get_current_workspace_id():
    """Return the workspace_id from the currently authenticated user."""
    try:
        uid = get_jwt_identity()
        if uid:
            from ..extensions import db
            from ..models.user import User
            user = db.session.get(User, int(uid))
            if user:
                g.current_workspace_id = user.workspace_id
                return user.workspace_id
            else:
                # Don't silently pass - log the issue
                logger.warning(f"User {uid} not found in database (get_jwt_identity returned '{uid}', type={type(uid).__name__})")
    except Exception as e:
        logger.warning(f"Error in get_current_workspace_id: {e}")
    g.current_workspace_id = None
    return None


def workspace_filter(query, model):
    """Apply workspace filtering to a query.
    Superadmin users bypass the filter (see all data).
    """
    from ..extensions import db
    from ..models.user import User

    try:
        uid = get_jwt_identity()
        if uid:
            user = db.session.get(User, int(uid))
            if user and user.role == 'superadmin':
                return query
    except Exception as e:
        logger.warning(f"Error in workspace_filter: {e}")

    workspace_id = getattr(g, 'current_workspace_id', None) or get_current_workspace_id()
    if workspace_id:
        return query.filter(model.workspace_id == workspace_id)
    return query
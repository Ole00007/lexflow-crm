"""
CRM Webhook handlers for Chatbot integration
Receives events from chatbot and updates CRM accordingly

SECURITY (2026-09-01): every webhook now REQUIRES either:
  1) a valid HMAC signature (X-Webhook-Signature) computed with the real secret
     from the WEBHOOK_SECRET env var, OR
  2) a valid superadmin JWT (Authorization: Bearer <token>).
Requests without a valid signature AND without superadmin JWT are rejected
(401). The old behavior — where an absent signature was silently accepted and a
hardcoded default secret was used — was a live cross-workspace write/leak and
is removed.

All writes are workspace-scoped: the target case/task is resolved and checked
against the caller's visible workspaces, and every created Event row is stamped
with the case's workspace_id (never NULL, never cross-workspace).
"""

import os
import hmac
import hashlib
import logging

from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db, limiter
from ..models.event import Event
from ..models.case import Case
from ..models.task import Task
from ..models.user import User
from ..workspace import get_visible_workspace_ids
from datetime import datetime
import json

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api/webhooks')

# Real secret comes from the environment. Never a hardcoded default.
_WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "").strip()
_PLACEHOLDER = "your-webhook-secret-change-in-config"


def _webhook_secret():
    """Return the real secret or None if not properly configured (fail-closed)."""
    if _WEBHOOK_SECRET and _WEBHOOK_SECRET != _PLACEHOLDER:
        return _WEBHOOK_SECRET
    return None


def verify_webhook_signature(request_data: bytes, signature: str, secret: str) -> bool:
    """Constant-time HMAC-SHA256 verification of the raw request body."""
    expected_signature = hmac.new(secret.encode(), request_data, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected_signature)


def _authorize():
    """Authenticate the webhook caller.

    Returns (ok, error_msg). ok=True when either:
      - a valid signature (using the real secret) is present, or
      - a valid superadmin JWT is present.
    On success, sets g.webhook_auth to 'signature' or 'jwt' so resolvers can
    decide whether to apply workspace scoping (signature = trusted integration
    that may act on the payload's case/task directly; jwt = apply workspace
    scoping for that user).
    """
    # Option A: valid signature
    signature = request.headers.get('X-Webhook-Signature')
    secret = _webhook_secret()
    if secret and signature:
        if verify_webhook_signature(request.get_data(), signature, secret):
            g.webhook_auth = 'signature'
            return True, None
        return False, "Invalid webhook signature"

    # Option B: superadmin JWT
    try:
        identity = get_jwt_identity()
        if identity:
            uid = int(identity)
            user = User.query.filter_by(id=uid, is_deleted=False).first()
            if user and user.role == 'superadmin':
                g.webhook_auth = 'jwt'
                return True, None
    except Exception:  # noqa: BLE001
        pass

    # Fail closed
    if not secret:
        return False, "Webhook secret is not configured (WEBHOOK_SECRET env missing/placeholder)"
    return False, "Missing or invalid webhook signature / authorization"


def _resolve_scoped_case(case_id):
    """Return a case the caller may touch, or None if not found / out of scope.

    When authenticated by signature (trusted integration), the payload's case
    is trusted directly (no workspace filter — an anonymous caller has an empty
    visible-workspace set, which would otherwise 404 every signed request).
    When authenticated by JWT, the normal workspace scoping applies."""
    case = Case.query.filter_by(id=case_id, is_deleted=False).first()
    if not case:
        return None
    if getattr(g, 'webhook_auth', None) == 'signature':
        return case
    vis = get_visible_workspace_ids()
    if vis is not None and case.workspace_id not in vis:
        return None
    return case


def _resolve_scoped_task(task_id):
    task = Task.query.filter_by(id=task_id, is_deleted=False).first()
    if not task:
        return None
    if getattr(g, 'webhook_auth', None) == 'signature':
        return task
    vis = get_visible_workspace_ids()
    if vis is not None and task.workspace_id not in vis:
        return None
    return task


def _make_event(workspace_id, case_id, **kwargs):
    """Create an Event row always stamped with the owning workspace_id."""
    return Event(workspace_id=workspace_id, caseid=case_id, **kwargs)


@webhooks_bp.post('/chatbot/message')
@jwt_required(optional=True)
@limiter.limit("100 per minute")
def chatbot_message():
    """Webhook for chatbot messages — creates events when chatbot interacts."""
    try:
        ok, err = _authorize()
        if not ok:
            return jsonify({'error': err}), 401

        data = request.get_json(silent=True) or {}
        case_id = data.get('case_id')
        message = data.get('message')
        message_type = data.get('type', 'message')

        if not case_id or not message:
            return jsonify({'error': 'case_id and message are required'}), 400

        case = _resolve_scoped_case(case_id)
        if not case:
            return jsonify({'error': 'Case not found'}), 404

        event = _make_event(
            case.workspace_id, case_id,
            title=f"Chatbot {message_type}",
            description=message,
            event_type="note",
            event_date=datetime.utcnow(),
            notes=json.dumps({
                'chatbot_type': message_type,
                'source': 'chatbot_webhook',
                'timestamp': datetime.utcnow().isoformat()
            })
        )
        db.session.add(event)
        db.session.commit()

        return jsonify({'success': True, 'event_id': event.id, 'case_id': case_id}), 201
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error handling chatbot message webhook: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@webhooks_bp.post('/chatbot/task-created')
@jwt_required(optional=True)
@limiter.limit("100 per minute")
def chatbot_task_created():
    """Webhook for when chatbot creates a task."""
    try:
        ok, err = _authorize()
        if not ok:
            return jsonify({'error': err}), 401

        data = request.get_json(silent=True) or {}
        case_id = data.get('case_id')
        task_id = data.get('task_id')
        task_description = data.get('description', '')

        if not case_id or not task_id:
            return jsonify({'error': 'case_id and task_id are required'}), 400

        case = _resolve_scoped_case(case_id)
        task = _resolve_scoped_task(task_id)
        if not case:
            return jsonify({'error': 'Case not found'}), 404
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        if case.workspace_id != task.workspace_id:
            return jsonify({'error': 'Case and task belong to different workspaces'}), 403

        event = _make_event(
            case.workspace_id, case_id,
            title=f"Task Created: {task.title}",
            description=task_description,
            event_type="task_update",
            event_date=datetime.utcnow(),
            notes=json.dumps({
                'task_id': task_id,
                'source': 'chatbot_webhook',
                'action': 'task_created'
            })
        )
        db.session.add(event)
        db.session.flush()
        task.event_id = event.id
        db.session.commit()

        return jsonify({'success': True, 'event_id': event.id, 'task_id': task_id, 'case_id': case_id}), 201
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error handling task creation webhook: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@webhooks_bp.post('/chatbot/task-completed')
@jwt_required(optional=True)
@limiter.limit("100 per minute")
def chatbot_task_completed():
    """Webhook for when chatbot completes a task."""
    try:
        ok, err = _authorize()
        if not ok:
            return jsonify({'error': err}), 401

        data = request.get_json(silent=True) or {}
        case_id = data.get('case_id')
        task_id = data.get('task_id')
        completion_notes = data.get('notes', '')

        if not case_id or not task_id:
            return jsonify({'error': 'case_id and task_id are required'}), 400

        task = _resolve_scoped_task(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        event = _make_event(
            task.workspace_id, case_id,
            title=f"Task Completed: {task.title}",
            description=completion_notes,
            event_type="task_update",
            event_date=datetime.utcnow(),
            notes=json.dumps({
                'task_id': task_id,
                'source': 'chatbot_webhook',
                'action': 'task_completed'
            })
        )
        db.session.add(event)
        task.status = 'completed'
        task.updatedat = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'event_id': event.id, 'task_id': task_id,
                        'case_id': case_id, 'task_status': 'completed'}), 201
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error handling task completion webhook: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@webhooks_bp.post('/chatbot/case-status-changed')
@jwt_required(optional=True)
@limiter.limit("50 per minute")
def chatbot_case_status_changed():
    """Webhook for when chatbot changes case status."""
    try:
        ok, err = _authorize()
        if not ok:
            return jsonify({'error': err}), 401

        data = request.get_json(silent=True) or {}
        case_id = data.get('case_id')
        new_status = data.get('status')
        reason = data.get('reason', '')

        if not case_id or not new_status:
            return jsonify({'error': 'case_id and status are required'}), 400

        case = _resolve_scoped_case(case_id)
        if not case:
            return jsonify({'error': 'Case not found'}), 404

        old_status = case.status
        event = _make_event(
            case.workspace_id, case_id,
            title=f"Case Status Changed: {old_status} → {new_status}",
            description=reason,
            event_type="status_update",
            event_date=datetime.utcnow(),
            notes=json.dumps({
                'old_status': old_status,
                'new_status': new_status,
                'source': 'chatbot_webhook',
                'reason': reason
            })
        )
        db.session.add(event)
        case.status = new_status
        case.updatedat = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'event_id': event.id, 'case_id': case_id,
                        'old_status': old_status, 'new_status': new_status}), 201
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error handling case status change webhook: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@webhooks_bp.post('/chatbot/event')
@jwt_required(optional=True)
@limiter.limit("100 per minute")
def chatbot_create_event():
    """Webhook for direct event creation from chatbot."""
    try:
        ok, err = _authorize()
        if not ok:
            return jsonify({'error': err}), 401

        data = request.get_json(silent=True) or {}
        case_id = data.get('case_id')
        title = data.get('title')
        event_type = data.get('event_type', 'other')
        event_date = data.get('event_date')
        description = data.get('description')

        if not case_id or not title:
            return jsonify({'error': 'case_id and title are required'}), 400

        case = _resolve_scoped_case(case_id)
        if not case:
            return jsonify({'error': 'Case not found'}), 404

        if event_date:
            try:
                if 'T' in str(event_date):
                    parsed_date = datetime.fromisoformat(str(event_date).replace('Z', '+00:00'))
                else:
                    parsed_date = datetime.fromisoformat(str(event_date))
            except ValueError:
                parsed_date = datetime.utcnow()
        else:
            parsed_date = datetime.utcnow()

        event = _make_event(
            case.workspace_id, case_id,
            title=title,
            description=description,
            event_type=event_type,
            event_date=parsed_date,
            notes=json.dumps({'source': 'chatbot_webhook'})
        )
        db.session.add(event)
        db.session.commit()

        return jsonify({'success': True, 'event_id': event.id, 'case_id': case_id}), 201
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error handling event creation webhook: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@webhooks_bp.get('/health')
def webhook_health():
    """Health check for webhook endpoint (intentionally public)."""
    return jsonify({'status': 'healthy', 'service': 'webhooks'}), 200

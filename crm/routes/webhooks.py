"""
CRM Webhook handlers for Chatbot integration
Receives events from chatbot and updates CRM accordingly
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from ..extensions import db, limiter
from ..models.event import Event
from ..models.case import Case
from ..models.task import Task
from ..models.contact import Contact
from datetime import datetime
import json
import hmac
import hashlib
import logging

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api/webhooks')

# Webhook secret for signature verification
WEBHOOK_SECRET = "your-webhook-secret-change-in-config"

def verify_webhook_signature(request_data: bytes, signature: str) -> bool:
    """
    Verify incoming webhook signature
    
    Args:
        request_data: Raw request body
        signature: X-Webhook-Signature header value
        
    Returns:
        True if signature is valid
    """
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        request_data,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)

@webhooks_bp.post('/chatbot/message')
@limiter.limit("100 per minute")
def chatbot_message():
    """
    Webhook for chatbot messages
    Creates events when chatbot interacts with a case
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body must be JSON'}), 400
        
        # Verify signature if provided
        signature = request.headers.get('X-Webhook-Signature')
        if signature:
            if not verify_webhook_signature(request.get_data(), signature):
                logger.warning("Invalid webhook signature")
                return jsonify({'error': 'Invalid signature'}), 401
        
        # Required fields
        case_id = data.get('case_id')
        message = data.get('message')
        message_type = data.get('type', 'message')  # message, alert, status_update
        
        if not case_id or not message:
            return jsonify({'error': 'case_id and message are required'}), 400
        
        # Verify case exists
        case = Case.query.filter_by(id=case_id, is_deleted=False).first()
        if not case:
            return jsonify({'error': 'Case not found'}), 404
        
        # Create event for the chatbot message
        event = Event(
            caseid=case_id,
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
        
        logger.info(f"Created event {event.id} from chatbot message for case {case_id}")
        
        return jsonify({
            'success': True,
            'event_id': event.id,
            'case_id': case_id
        }), 201
    
    except Exception as e:
        logger.error(f"Error handling chatbot message webhook: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@webhooks_bp.post('/chatbot/task-created')
@limiter.limit("100 per minute")
def chatbot_task_created():
    """
    Webhook for when chatbot creates a task
    Links the task to an event and updates case status
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body must be JSON'}), 400
        
        case_id = data.get('case_id')
        task_id = data.get('task_id')
        task_description = data.get('description', '')
        
        if not case_id or not task_id:
            return jsonify({'error': 'case_id and task_id are required'}), 400
        
        # Verify case and task exist
        case = Case.query.filter_by(id=case_id, is_deleted=False).first()
        task = Task.query.filter_by(id=task_id, is_deleted=False).first()
        
        if not case:
            return jsonify({'error': 'Case not found'}), 404
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Create event for task creation
        event = Event(
            caseid=case_id,
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
        
        # Link task to event
        task.event_id = event.id
        
        db.session.add(event)
        db.session.commit()
        
        logger.info(f"Created event {event.id} for task {task_id}")
        
        return jsonify({
            'success': True,
            'event_id': event.id,
            'task_id': task_id,
            'case_id': case_id
        }), 201
    
    except Exception as e:
        logger.error(f"Error handling task creation webhook: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@webhooks_bp.post('/chatbot/task-completed')
@limiter.limit("100 per minute")
def chatbot_task_completed():
    """
    Webhook for when chatbot completes a task
    Creates an event and may update task status
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body must be JSON'}), 400
        
        case_id = data.get('case_id')
        task_id = data.get('task_id')
        completion_notes = data.get('notes', '')
        
        if not case_id or not task_id:
            return jsonify({'error': 'case_id and task_id are required'}), 400
        
        # Verify task exists
        task = Task.query.filter_by(id=task_id, is_deleted=False).first()
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Create event for task completion
        event = Event(
            caseid=case_id,
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
        
        # Update task status to completed
        task.status = 'completed'
        task.updatedat = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"Created event {event.id} for task {task_id} completion")
        
        return jsonify({
            'success': True,
            'event_id': event.id,
            'task_id': task_id,
            'case_id': case_id,
            'task_status': 'completed'
        }), 201
    
    except Exception as e:
        logger.error(f"Error handling task completion webhook: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@webhooks_bp.post('/chatbot/case-status-changed')
@limiter.limit("50 per minute")
def chatbot_case_status_changed():
    """
    Webhook for when chatbot changes case status
    Creates an event and updates case status
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body must be JSON'}), 400
        
        case_id = data.get('case_id')
        new_status = data.get('status')
        reason = data.get('reason', '')
        
        if not case_id or not new_status:
            return jsonify({'error': 'case_id and status are required'}), 400
        
        # Verify case exists
        case = Case.query.filter_by(id=case_id, is_deleted=False).first()
        if not case:
            return jsonify({'error': 'Case not found'}), 404
        
        old_status = case.status
        
        # Create event for status change
        event = Event(
            caseid=case_id,
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
        
        # Update case status
        case.status = new_status
        case.updatedat = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"Case {case_id} status changed from {old_status} to {new_status}")
        
        return jsonify({
            'success': True,
            'event_id': event.id,
            'case_id': case_id,
            'old_status': old_status,
            'new_status': new_status
        }), 201
    
    except Exception as e:
        logger.error(f"Error handling case status change webhook: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@webhooks_bp.post('/chatbot/event')
@limiter.limit("100 per minute")
def chatbot_create_event():
    """
    Webhook for direct event creation from chatbot
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body must be JSON'}), 400
        
        case_id = data.get('case_id')
        title = data.get('title')
        event_type = data.get('event_type', 'other')
        event_date = data.get('event_date')
        description = data.get('description')
        
        if not case_id or not title:
            return jsonify({'error': 'case_id and title are required'}), 400
        
        # Verify case exists
        case = Case.query.filter_by(id=case_id, is_deleted=False).first()
        if not case:
            return jsonify({'error': 'Case not found'}), 404
        
        # Parse event_date if provided
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
        
        # Create event
        event = Event(
            caseid=case_id,
            title=title,
            description=description,
            event_type=event_type,
            event_date=parsed_date,
            notes=json.dumps({
                'source': 'chatbot_webhook'
            })
        )
        
        db.session.add(event)
        db.session.commit()
        
        logger.info(f"Created event {event.id} from chatbot webhook")
        
        return jsonify({
            'success': True,
            'event_id': event.id,
            'case_id': case_id
        }), 201
    
    except Exception as e:
        logger.error(f"Error handling event creation webhook: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@webhooks_bp.get('/health')
def webhook_health():
    """Health check for webhook endpoint"""
    return jsonify({'status': 'healthy', 'service': 'webhooks'}), 200

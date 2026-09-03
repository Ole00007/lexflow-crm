from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db, limiter
from ..models.calendar_event import CalendarEvent
from ..models.case import Case
from ..models.contact import Contact
from ..models.workspace import Workspace
from ..models.user import User
from ..notification_service import send_email
from ..activity_logger import log_activity
from ..workspace import get_current_workspace_id, workspace_filter
from datetime import datetime
import os

calendar_bp = Blueprint('calendar', __name__, url_prefix='/api/calendar')

def _filtered_query():
    # superadmin sees all workspaces (workspace_filter bypasses for superadmin)
    return workspace_filter(CalendarEvent.query.filter_by(is_deleted=False), CalendarEvent)


def _resolve_client_email(event):
    """Find the client email linked to this event (contactid → contact, else caseid → contact)."""
    try:
        if event.contactid:
            c = Contact.query.filter_by(id=event.contactid, is_deleted=False).first()
            if c and c.email:
                return c.email
        if event.caseid:
            case = Case.query.filter_by(id=event.caseid, is_deleted=False).first()
            if case and case.contactid:
                c = Contact.query.filter_by(id=case.contactid, is_deleted=False).first()
                if c and c.email:
                    return c.email
    except Exception:
        pass
    return None


def _notify_event_created(event):
    """Send automatic email notifications when a calendar event is created.

    RULE (2026-09-03, scheme 2/3/4): notifications go BOTH to
      - the client (email resolved from the linked contact — NOT a fixed address), and
      - the superadmin / workspace owner (configurable, default ADMIN_EMAIL=Yahoo).
    Fires automatically at event creation (not on a cron). Email failures are
    non-fatal — the event itself is never rolled back because mail failed.
    """
    try:
        client_email = _resolve_client_email(event)
        ws_name = event.workspace.name if event.workspace else "LexFlow"
        when = event.start_datetime.strftime("%d/%m/%Y %H:%M") if event.start_datetime else "TBD"

        # 1) client email
        if client_email:
            send_email(
                to_email=client_email,
                subject=f"Appuntamento confermato - {ws_name}",
                html_body=f"<h3>Ciao,</h3>"
                          f"<p>Ti confermiamo l'appuntamento:</p>"
                          f"<ul><li><b>Evento:</b> {event.title}</li>"
                          f"<li><b>Data:</b> {when}</li>"
                          f"<li><b>Tipo:</b> {event.event_type or 'meeting'}</li>"
                          f"<li><b>Note:</b> {event.notes or '—'}</li></ul>"
                          f"<p>Studio {ws_name}</p>",
            )

        # 2) superadmin / workspace owner (never a fixed client address)
        owner_email = os.environ.get("NOTIFY_SUPERADMIN_EMAIL") or os.environ.get("ADMIN_EMAIL", "")
        if not owner_email:
            sa = User.query.filter_by(role="superadmin", is_deleted=False).first()
            if sa:
                owner_email = sa.email
        if owner_email:
            send_email(
                to_email=owner_email,
                subject=f"[{ws_name}] New calendar event: {event.title}",
                html_body=f"<h3>New calendar event</h3>"
                          f"<p><b>Evento:</b> {event.title}</p>"
                          f"<p><b>Data:</b> {when}</p>"
                          f"<p><b>Tipo:</b> {event.event_type or 'meeting'}</p>"
                          f"<p><b>Cliente:</b> {client_email or '—'}</p>"
                          f"<p><b>Note:</b> {event.notes or '—'}</p>",
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Event email notify failed (non-fatal): {e}")

@calendar_bp.get('')
@jwt_required()
@limiter.limit("120 per minute")
def list_events():
    args = request.args
    query = _filtered_query()
    if args.get('caseid', type=int): query = query.filter_by(caseid=args.get('caseid', type=int))
    if args.get('event_type'): query = query.filter_by(event_type=args['event_type'])
    if args.get('date_from'): query = query.filter(CalendarEvent.start_datetime >= datetime.fromisoformat(args['date_from']))
    if args.get('date_to'): query = query.filter(CalendarEvent.start_datetime <= datetime.fromisoformat(args['date_to']))
    return jsonify([e.to_dict() for e in query.order_by(CalendarEvent.start_datetime).all()]), 200

@calendar_bp.get('/<int:event_id>')
@jwt_required()
def get_event(event_id):
    event = _filtered_query().filter_by(id=event_id).first()
    if not event: return jsonify({'error': 'Event not found'}), 404
    return jsonify(event.to_dict()), 200

@calendar_bp.post('')
@jwt_required()
@limiter.limit("30 per minute")
def create_event():
    data = request.get_json()
    if not data: return jsonify({'error': 'No data provided'}), 400
    if not data.get('title') or not data.get('start_datetime'):
        return jsonify({'error': 'title and start_datetime are required'}), 400
    wid = get_current_workspace_id()
    if not wid:
        return jsonify({'error': 'Authentication required'}), 401
    event = CalendarEvent(
        workspace_id=wid,
        caseid=data.get('caseid'), contactid=data.get('contactid'),
        ownerid=data.get('ownerid'), title=data['title'],
        description=data.get('description'), event_type=data.get('event_type', 'hearing'),
        location=data.get('location'), court_name=data.get('court_name'),
        judge_name=data.get('judge_name'),
        start_datetime=datetime.fromisoformat(data['start_datetime']) if isinstance(data['start_datetime'], str) else data['start_datetime'],
        end_datetime=datetime.fromisoformat(data['end_datetime']) if data.get('end_datetime') and isinstance(data['end_datetime'], str) else data.get('end_datetime'),
        is_all_day=data.get('is_all_day', False), status=data.get('status', 'scheduled'), notes=data.get('notes'))
    db.session.add(event); db.session.commit()
    log_activity(int(get_jwt_identity()), 'case' if event.caseid else 'contact', event.caseid or event.contactid or 0,
                 'event_created', f"Calendar event '{event.title}' created ({event.event_type})")
    _notify_event_created(event)
    return jsonify(event.to_dict()), 201

@calendar_bp.put('/<int:event_id>')
@jwt_required()
def update_event(event_id):
    event = _filtered_query().filter_by(id=event_id).first()
    if not event: return jsonify({'error': 'Event not found'}), 404
    data = request.get_json()
    if not data: return jsonify({'error': 'No data provided'}), 400
    for field in ['title', 'description', 'event_type', 'location', 'court_name', 'judge_name', 'status', 'notes', 'is_all_day', 'caseid', 'contactid']:
        if field in data: setattr(event, field, data[field])
    if 'start_datetime' in data:
        event.start_datetime = datetime.fromisoformat(data['start_datetime']) if isinstance(data['start_datetime'], str) else data['start_datetime']
    if 'end_datetime' in data:
        event.end_datetime = datetime.fromisoformat(data['end_datetime']) if isinstance(data['end_datetime'], str) else data['end_datetime']
    db.session.commit()
    log_activity(int(get_jwt_identity()), 'case' if event.caseid else 'contact', event.caseid or event.contactid or 0,
                 'event_updated', f"Calendar event '{event.title}' updated ({event.event_type})")
    return jsonify(event.to_dict()), 200

@calendar_bp.delete('/<int:event_id>')
@jwt_required()
def delete_event(event_id):
    event = _filtered_query().filter_by(id=event_id).first()
    if not event: return jsonify({'error': 'Event not found'}), 404
    event.is_deleted = True; event.deleted_at = datetime.utcnow()
    db.session.commit()
    log_activity(int(get_jwt_identity()), 'case' if event.caseid else 'contact', event.caseid or event.contactid or 0,
                 'event_deleted', f"Calendar event '{event.title}' deleted")
    return jsonify({'deleted': True}), 200
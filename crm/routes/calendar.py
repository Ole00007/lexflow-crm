from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from ..extensions import db, limiter
from ..models.calendar_event import CalendarEvent
from ..models.case import Case
from ..models.contact import Contact
from ..activity_logger import log_activity
from ..workspace import get_current_workspace_id
from datetime import datetime

calendar_bp = Blueprint('calendar', __name__, url_prefix='/api/calendar')

def _filtered_query():
    q = CalendarEvent.query.filter_by(is_deleted=False)
    wid = get_current_workspace_id()
    if wid is not None: q = q.filter_by(workspace_id=wid)
    return q

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
    log_activity(1, 'case' if event.caseid else 'contact', event.caseid or event.contactid or 0,
                 'event_created', f"Calendar event '{event.title}' created ({event.event_type})")
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
    return jsonify(event.to_dict()), 200

@calendar_bp.delete('/<int:event_id>')
@jwt_required()
def delete_event(event_id):
    event = _filtered_query().filter_by(id=event_id).first()
    if not event: return jsonify({'error': 'Event not found'}), 404
    event.is_deleted = True; event.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'deleted': True}), 200
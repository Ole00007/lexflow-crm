from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from ..extensions import db
from ..models.deadline import Deadline
from ..models.case import Case
from ..workspace import get_current_workspace_id
from datetime import date, datetime

deadlines_bp = Blueprint('deadlines', __name__, url_prefix='/api/deadlines')

def _filtered_query():
    q = Deadline.query.filter_by(is_deleted=False)
    wid = get_current_workspace_id()
    if wid is not None:
        q = q.filter_by(workspace_id=wid)
    return q

@deadlines_bp.get('/')
@jwt_required()
def get_deadlines():
    case_id = request.args.get('caseid', type=int)
    query = _filtered_query()
    if case_id:
        query = query.filter_by(caseid=case_id)
    return jsonify([d.to_dict() for d in query.order_by(Deadline.deadline_date).all()]), 200

@deadlines_bp.get('/<int:deadline_id>')
@jwt_required()
def get_deadline(deadline_id):
    deadline = _filtered_query().filter_by(id=deadline_id).first()
    if not deadline:
        return jsonify({'error': 'Deadline not found'}), 404
    return jsonify(deadline.to_dict()), 200

@deadlines_bp.post('/')
@jwt_required()
def create_deadline():
    data = request.get_json()
    if not data or not data.get('caseid') or not data.get('title') or not data.get('deadline_date'):
        return jsonify({'error': 'caseid, title, and deadline_date are required'}), 400

    case = Case.query.filter_by(id=data.get('caseid'), is_deleted=False).first()
    if not case:
        return jsonify({'error': 'Case not found'}), 404

    deadline = Deadline(
        workspace_id=get_current_workspace_id() or 1,
        caseid=data.get('caseid'),
        title=data.get('title'),
        description=data.get('description'),
        deadline_date=date.fromisoformat(data['deadline_date']) if isinstance(data['deadline_date'], str) else data['deadline_date'],
        deadline_type=data.get('deadline_type', 'other'),
        status=data.get('status', 'pending'),
        priority=data.get('priority', 'Medium'),
    )
    db.session.add(deadline)
    db.session.commit()
    return jsonify(deadline.to_dict()), 201

@deadlines_bp.put('/<int:deadline_id>')
@jwt_required()
def update_deadline(deadline_id):
    deadline = _filtered_query().filter_by(id=deadline_id).first()
    if not deadline:
        return jsonify({'error': 'Deadline not found'}), 404
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    for field in ['title', 'description', 'deadline_type', 'status', 'priority']:
        if field in data:
            setattr(deadline, field, data[field])
    if 'deadline_date' in data:
        deadline.deadline_date = date.fromisoformat(data['deadline_date']) if isinstance(data['deadline_date'], str) else data['deadline_date']
    db.session.commit()
    return jsonify(deadline.to_dict()), 200

@deadlines_bp.delete('/<int:deadline_id>')
@jwt_required()
def delete_deadline(deadline_id):
    deadline = _filtered_query().filter_by(id=deadline_id).first()
    if not deadline:
        return jsonify({'error': 'Deadline not found'}), 404
    deadline.is_deleted = True
    deadline.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'deleted': True}), 200
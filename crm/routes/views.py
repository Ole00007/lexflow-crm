"""
Views blueprint — serves Jinja2 templates for the CRM UI.
Handles intake form submission, booking/calendar with email notifications.
"""
from flask import Blueprint, render_template, jsonify, request, abort, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity
from pathlib import Path
import os
import secrets
from datetime import datetime, date
from uuid import uuid4
from werkzeug.utils import secure_filename
from ..extensions import db
from ..models.contact import Contact
from ..models.case import Case
from ..models.task import Task
from ..models.deadline import Deadline
from ..models.calendar_event import CalendarEvent
from ..models.note import Note
from ..models.activity import ActivityLog
from ..models.workspace import Workspace
from ..models.attachment import Attachment
from ..activity_logger import log_activity
from ..workspace import get_current_workspace_id
from ..notification_service import send_booking_notification, send_email

# Intake constants
PRACTICES = ["Commercial", "Employment", "Real Estate", "Family",
             "Debt Collection", "Shipping / Logistics", "Other"]
STATUSES = ["New intake", "Conflict check", "Lawyer review",
            "Waiting client docs", "Quoted", "Engaged", "Closed"]

views_bp = Blueprint('views', __name__)


# ── Dashboard ──────────────────────────────────────────────────────
@views_bp.route('/dashboard')
@jwt_required(optional=True)
def dashboard():
    try:
        wid = get_current_workspace_id()
        c_filter = {'is_deleted': False}
        if wid: c_filter['workspace_id'] = wid
        contacts = Contact.query.filter_by(**c_filter).count()
        cases = Case.query.filter_by(**c_filter).count()
        tasks = Task.query.filter_by(**c_filter).count()
        pending_tasks = Task.query.filter_by(**{**c_filter, 'status': 'pending'}).count()
        upcoming_deadlines = Deadline.query.filter_by(**{**c_filter, 'status': 'pending'}).order_by(Deadline.deadline_date).limit(5).all()
        recent_activity = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()
    except Exception:
        contacts = cases = tasks = pending_tasks = 0
        upcoming_deadlines = []; recent_activity = []
    return render_template('dashboard.html', contact_count=contacts, case_count=cases,
        task_count=tasks, pending_count=pending_tasks, deadlines=upcoming_deadlines, activities=recent_activity)


# ── Kanban Board ───────────────────────────────────────────────────
@views_bp.route('/kanban')
@jwt_required(optional=True)
def kanban():
    statuses = ['Intake', 'Conflict Check', 'Review', 'Engaged', 'Closed']
    wid = get_current_workspace_id()
    c_filter = {'is_deleted': False}
    if wid: c_filter['workspace_id'] = wid
    cases_by_status = {s: Case.query.filter_by(**{**c_filter, 'status': s}).all() for s in statuses}
    return render_template('kanban.html', statuses=statuses, cases_by_status=cases_by_status)


# ── Calendar View ─────────────────────────────────────────────────
@views_bp.route('/calendar')
@jwt_required(optional=True)
def calendar():
    return render_template('calendar.html')


@views_bp.route('/contacts')
@jwt_required(optional=True)
def contacts():
    return render_template('contacts.html')


@views_bp.route('/tasks')
@jwt_required(optional=True)
def tasks():
    return render_template('tasks.html')


# ── Intake Routes ──────────────────────────────────────────────────
@views_bp.route('/')
def index():
    return render_template('index.html', practices=PRACTICES)


@views_bp.route('/submit', methods=['POST'])
def submit():
    """Handle intake form submission with email notification."""
    client_name = request.form.get('client_name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    company = request.form.get('company', '').strip()
    practice_area = request.form.get('practice_area', '').strip()
    urgency = request.form.get('urgency', 'Medium').strip()
    description = request.form.get('description', '').strip()

    if not client_name or not email or not practice_area:
        flash('Name, email, and practice area are required.', 'error')
        return redirect(url_for('views.index'))

    wid = get_current_workspace_id() or 1
    token = secrets.token_hex(8).upper()
    now = datetime.utcnow()

    # Find or create contact
    contact = Contact.query.filter_by(email=email, workspace_id=wid).first()
    if not contact:
        contact = Contact(workspace_id=wid, fullname=client_name, email=email,
                          phone=phone, company=company, status='lead')
        db.session.add(contact)
        db.session.flush()

    # Create case
    case = Case(workspace_id=wid, contactid=contact.id, title=description[:255] or f"Intake: {client_name}",
                casetype=practice_area, status='Intake', priority=urgency, openedat=date.today())
    db.session.add(case)
    db.session.commit()

    # Save uploaded intake documents and create Attachment rows linked to the new case
    _base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    upload_folder = os.environ.get(
        'UPLOAD_FOLDER',
        os.path.join(_base_dir, 'uploads')
    )
    os.makedirs(upload_folder, exist_ok=True)
    for doc in request.files.getlist('documents'):
        if not doc or not doc.filename:
            continue
        original_name = secure_filename(doc.filename) or doc.filename
        ext = os.path.splitext(original_name)[1].lower()
        stored_name = uuid4().hex + ext
        doc.save(os.path.join(upload_folder, stored_name))
        attachment = Attachment(
            workspace_id=wid,
            filename=original_name,
            stored_name=stored_name,
            filepath=os.path.join('uploads', stored_name),
            mime_type=doc.mimetype or 'application/octet-stream',
            size_bytes=doc.content_length or 0,
            target_type='case',
            target_id=case.id,
            uploaded_by=None,
        )
        db.session.add(attachment)
    db.session.commit()

    # Notify workspace owner(s)
    workspace = Workspace.query.get(wid)
    workspace_name = workspace.name if workspace else 'LexFlow'
    admin_contact = send_email(
        to_email=os.environ.get('ADMIN_EMAIL', ''),
        subject=f"New intake: {client_name} - {practice_area}",
        html_body=f"<h2>New intake received</h2><p><strong>Client:</strong> {client_name}</p>"
                  f"<p><strong>Email:</strong> {email}</p><p><strong>Practice:</strong> {practice_area}</p>"
                  f"<p><strong>Urgency:</strong> {urgency}</p>"
    )

    flash('Intake submitted successfully. You will receive updates via email.', 'success')
    return redirect(url_for('views.case_status', token=case.id))


# ── Booking / Meeting Reservation ─────────────────────────────────
@views_bp.route('/book', methods=['GET', 'POST'])
def book_meeting():
    """Booking page — creates calendar event + sends email notifications."""
    if request.method == 'GET':
        return render_template('booking.html', workspaces=Workspace.query.filter_by(is_active=True).all())

    data = request.get_json() or request.form
    client_name = data.get('client_name', '').strip()
    client_email = data.get('client_email', '').strip()
    phone = data.get('phone', '').strip()
    booking_type = data.get('booking_type', 'meeting')
    booking_time = data.get('booking_time', '').strip()
    notes = data.get('notes', '').strip()
    workspace_slug = data.get('workspace', '').strip()
    court_name = data.get('court_name', '').strip()

    if not client_name or not client_email or not booking_time:
        return jsonify({'error': 'Name, email, and time are required'}), 400

    # Resolve workspace
    workspace = Workspace.query.filter_by(slug=workspace_slug, is_active=True).first()
    if not workspace:
        workspace = Workspace.query.get(1)  # fallback to default
    wid = workspace.id

    # Find or create contact in workspace
    contact = Contact.query.filter_by(email=client_email, workspace_id=wid).first()
    if not contact:
        contact = Contact(workspace_id=wid, fullname=client_name, email=client_email,
                          phone=phone, status='lead')
        db.session.add(contact)
        db.session.flush()

    # Parse booking time
    try:
        start_dt = datetime.fromisoformat(booking_time.replace('Z', ''))
    except ValueError:
        start_dt = datetime.strptime(booking_time, '%Y-%m-%dT%H:%M')

    # Auto-create a case if not exists
    case = Case.query.filter_by(contactid=contact.id, workspace_id=wid, status='Intake').first()
    if not case:
        case = Case(workspace_id=wid, contactid=contact.id,
                    title=f"Booking: {client_name} - {booking_type}",
                    casetype='Consultation', status='Intake', priority='Medium', openedat=date.today())
        db.session.add(case)
        db.session.flush()

    # Create calendar event
    event = CalendarEvent(
        workspace_id=wid, caseid=case.id, contactid=contact.id,
        title=f"{booking_type.capitalize()} - {client_name}",
        event_type=booking_type, start_datetime=start_dt,
        end_datetime=None, court_name=court_name or None,
        notes=notes or None, status='scheduled')
    db.session.add(event)
    db.session.commit()

    # Find workspace owner email and phone
    owner_email = os.environ.get('ADMIN_EMAIL', '')
    owner_phone = os.environ.get('ADMIN_PHONE', '')
    from ..models.user import User
    owner = User.query.filter_by(workspace_id=wid, role='admin').first()
    if owner:
        owner_email = owner.email

    # Send notifications (email + WhatsApp if configured)
    send_booking_notification(
        client_email=client_email, client_phone=phone or '',
        client_name=client_name,
        owner_email=owner_email, owner_phone=owner_phone,
        booking_type=booking_type,
        booking_time=start_dt.strftime('%d/%m/%Y %H:%M'),
        notes=notes, workspace_name=workspace.name,
        court_name=court_name
    )

    if request.is_json:
        return jsonify({'success': True, 'event_id': event.id, 'case_id': case.id}), 201
    flash('Meeting booked! Check your email for confirmation.', 'success')
    return redirect(url_for('views.index'))


# ── Status Page ────────────────────────────────────────────────────
@views_bp.route('/status/<token>')
def case_status(token):
    case = None
    try:
        case_id = int(token)
        case = Case.query.filter_by(id=case_id, is_deleted=False).first()
    except ValueError:
        pass
    return render_template('status.html', matter=case, docs=[], events=[], statuses=STATUSES)


# ── Admin List ─────────────────────────────────────────────────────
@views_bp.route('/admin')
def admin_list():
    wid = get_current_workspace_id()
    query = Case.query.filter_by(is_deleted=False)
    if wid: query = query.filter_by(workspace_id=wid)
    cases = query.order_by(Case.id.desc()).all()
    return render_template('admin.html', matters=cases)


@views_bp.route('/admin/matter/<int:matter_id>', methods=['GET', 'POST'])
def admin_matter(matter_id):
    case = Case.query.filter_by(id=matter_id, is_deleted=False).first()
    if not case: abort(404)
    if request.method == 'POST':
        case.status = request.form.get('status', case.status)
        db.session.commit()
    notes = Note.query.filter_by(target_type='case', target_id=matter_id).order_by(Note.created_at.desc()).all()
    activities = ActivityLog.query.filter_by(target_type='case', target_id=matter_id).order_by(ActivityLog.created_at.desc()).all()
    return render_template('admin_matter.html', matter=case, notes=notes, activities=activities, statuses=STATUSES)


# ── Error handlers ─────────────────────────────────────────────────
@views_bp.app_errorhandler(404)
def not_found(e):
    return render_template('base.html', error='Page not found'), 404

@views_bp.route('/pagliano')
def pagliano_lp():
    """Render the Pagliano landing page."""
    return render_template('pagliano.html', success=False)


@views_bp.route('/api/intake/<workspace_slug>', methods=['POST'])
def intake_from_lp(workspace_slug):
    """Handle intake form submission from a landing page (multi-tenant).
    Creates contact + case in the correct workspace based on URL.
    Sends email notification to workspace owner.
    """
    import secrets
    from datetime import date
    from ..models.workspace import Workspace
    from ..models.user import User
    from ..notification_service import send_email

    # Resolve workspace
    ws = Workspace.query.filter_by(slug=workspace_slug, is_active=True).first()
    if not ws:
        return jsonify({'error': 'Invalid workspace'}), 404
    wid = ws.id

    # Get form data (JSON or form-encoded)
    data = request.get_json() if request.is_json else request.form
    fullname = data.get('fullname', '').strip() or data.get('client_name', '').strip() or data.get('name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    practice_area = data.get('practice_area', '').strip() or data.get('casetype', '').strip()
    message = data.get('message', '').strip() or data.get('description', '').strip()
    gdpr = data.get('gdpr_consent') in ('true', 'True', '1', True, 'on')

    if not fullname or not email:
        return jsonify({'error': 'Name and email are required'}), 400

    # Find or create contact
    contact = Contact.query.filter_by(email=email, workspace_id=wid).first()
    if not contact:
        contact = Contact(workspace_id=wid, fullname=fullname, email=email,
                          phone=phone, source='intake', status='lead',
                          gdpr_consent=gdpr, gdpr_consent_ts=datetime.utcnow() if gdpr else None)
        db.session.add(contact)
        db.session.flush()

    # Create case from intake
    case = Case(workspace_id=wid, contactid=contact.id,
                title=message[:255] if message else f"Consulenza: {fullname}",
                casetype=practice_area or 'Consultation',
                status='Intake', priority='Medium', openedat=date.today())
    db.session.add(case)
    db.session.commit()

    # Log activity
    log_activity(None, 'contact', contact.id, 'created', f"Contact from {ws.name} LP")
    log_activity(None, 'case', case.id, 'created', f"Intake from {ws.name} LP")

    # Notify workspace owner
    owner = User.query.filter_by(workspace_id=wid, role='admin').first()
    owner_email = owner.email if owner else os.environ.get('ADMIN_EMAIL', '')
    if owner_email:
        send_email(
            to_email=owner_email,
            subject=f"New intake from {ws.name}: {fullname}",
            html_body=f"<h2>New intake from {ws.name}</h2>"
                      f"<p><strong>Client:</strong> {fullname}</p>"
                      f"<p><strong>Email:</strong> {email}</p>"
                      f"<p><strong>Phone:</strong> {phone or '—'}</p>"
                      f"<p><strong>Practice area:</strong> {practice_area or '—'}</p>"
                      f"<p><strong>Message:</strong> {message or '—'}</p>"
                      f"<p><strong>GDPR:</strong> {'Yes' if gdpr else 'No'}</p>"
        )

    if request.is_json or request.accept_mimetypes.accept_json:
        return jsonify({'success': True, 'contact': contact.to_dict(), 'case': case.to_dict()}), 201
    return render_template('pagliano.html', success=True, name=fullname)


# ── Chatbot Appointment Booking (public, from landing-page chat widget) ────
@views_bp.route('/api/appointments', methods=['POST'])
def create_appointment():
    """Handle chatbot appointment booking from the landing page chat widget.

    Payload (JSON): fullname, email, phone, event_date (ISO datetime),
    title, description, location, gdpr_consent, source.

    Creates a Contact + Case + CalendarEvent in the resolved workspace
    (from source/slug) and sends booking notifications. Public endpoint —
    no JWT, like the intake endpoint.
    """
    import secrets
    from ..models.user import User

    data = request.get_json(silent=True) or request.form
    fullname = (data.get('fullname') or data.get('client_name') or '').strip()
    email = (data.get('email') or '').strip()
    phone = (data.get('phone') or '').strip()
    event_date = (data.get('event_date') or data.get('booking_time') or '').strip()
    title = (data.get('title') or f"Appuntamento — {fullname}").strip()
    description = (data.get('description') or '').strip()
    location = (data.get('location') or '').strip()
    gdpr = data.get('gdpr_consent') in ('true', 'True', '1', 1, True, 'on')
    source = (data.get('source') or 'chatbot').strip()

    # Resolve workspace from source slug (e.g. 'pagliano_chatbot' -> 'pagliano')
    slug = source.replace('_chatbot', '').replace('_lp', '').strip()
    ws = Workspace.query.filter_by(slug=slug, is_active=True).first()
    if not ws:
        ws = Workspace.query.filter_by(slug='pagliano', is_active=True).first()
    if not ws:
        ws = Workspace.query.first()
    wid = ws.id

    if not fullname or not email:
        return jsonify({'error': 'Name and email are required'}), 400
    if not event_date:
        return jsonify({'error': 'A date and time are required'}), 400

    # Find or create contact in the workspace
    contact = Contact.query.filter_by(email=email, workspace_id=wid).first()
    if not contact:
        contact = Contact(workspace_id=wid, fullname=fullname, email=email,
                          phone=phone, source='chatbot', status='lead',
                          gdpr_consent=gdpr,
                          gdpr_consent_ts=datetime.utcnow() if gdpr else None)
        db.session.add(contact)
        db.session.flush()

    # Auto-create a case if none open for this contact
    case = Case.query.filter_by(contactid=contact.id, workspace_id=wid, status='Intake', is_deleted=False).first()
    if not case:
        case = Case(workspace_id=wid, contactid=contact.id,
                    title=description[:255] or f"Appuntamento: {fullname}",
                    casetype='Consultation', status='Intake', priority='Medium',
                    openedat=date.today())
        db.session.add(case)
        db.session.flush()

    # Parse the event datetime
    try:
        start_dt = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
        # Normalize naive -> treat as local
        if start_dt.tzinfo is not None:
            start_dt = start_dt.replace(tzinfo=None)
    except ValueError:
        try:
            start_dt = datetime.strptime(event_date, '%Y-%m-%dT%H:%M')
        except ValueError:
            return jsonify({'error': 'Invalid event_date format'}), 400

    # Create calendar event
    event = CalendarEvent(
        workspace_id=wid, caseid=case.id, contactid=contact.id,
        title=title[:255], description=description or None,
        event_type='appointment', location=location or None,
        start_datetime=start_dt, end_datetime=None,
        status='scheduled', notes=f"Source: {source}")
    db.session.add(event)
    db.session.commit()

    # Activity logging
    log_activity(None, 'contact', contact.id, 'appointment_requested',
                 f"Appointment requested by {fullname} ({ws.name})")
    log_activity(None, 'case', case.id, 'appointment_requested',
                 f"Appointment '{title}' requested via {ws.name} chatbot")
    log_activity(None, 'case', case.id, 'event_created',
                 f"Calendar event '{title}' created ({event.event_type})")

    # Notify workspace owner + client
    owner = User.query.filter_by(workspace_id=wid, role='admin').first()
    owner_email = owner.email if owner else os.environ.get('ADMIN_EMAIL', '')
    owner_phone = os.environ.get('ADMIN_PHONE', '')
    send_booking_notification(
        client_email=email, client_phone=phone or '',
        client_name=fullname,
        owner_email=owner_email, owner_phone=owner_phone or '',
        booking_type='appointment',
        booking_time=start_dt.strftime('%d/%m/%Y %H:%M'),
        notes=description, workspace_name=ws.name,
        court_name=location
    )

    return jsonify({
        'success': True,
        'appointment': event.to_dict(),
        'event_id': event.id,
        'case_id': case.id,
        'contact_id': contact.id,
    }), 201


from flask import Blueprint, jsonify, g
from flask_jwt_extended import get_jwt_identity, jwt_required

debug_bp = Blueprint('debug', __name__)

@debug_bp.get('/debug/whoami')
@jwt_required(optional=True)
def whoami():
    '''Debug endpoint - shows JWT identity and workspace_id.'''
    from ..extensions import db
    from ..models.user import User
    uid = get_jwt_identity()
    wid = None
    role = None
    if uid:
        user = db.session.get(User, int(uid))
        if user:
            wid = user.workspace_id
            role = user.role
    return jsonify({
        'uid': uid,
        'workspace_id': wid,
        'role': role,
        'g_current_workspace_id': getattr(g, 'current_workspace_id', None),
    })

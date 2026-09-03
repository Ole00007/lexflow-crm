"""
Views blueprint — serves Jinja2 templates for the CRM UI.
Handles intake form submission, booking/calendar with email notifications.
"""
from flask import Blueprint, render_template, jsonify, request, abort, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity
from pathlib import Path
import os
import logging
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
from ..workspace import get_current_workspace_id, get_visible_workspace_ids
from ..notification_service import send_booking_notification, send_email

# Intake constants
PRACTICES = ["Commercial", "Employment", "Real Estate", "Family",
             "Debt Collection", "Shipping / Logistics", "Other"]
STATUSES = ["New intake", "Conflict check", "Lawyer review",
            "Waiting client docs", "Quoted", "Engaged", "Closed"]

views_bp = Blueprint('views', __name__)
logger = logging.getLogger(__name__)


# ── Dashboard ──────────────────────────────────────────────────────
@views_bp.route('/dashboard')
@jwt_required(optional=True)
def dashboard():
    from ..models.user import User
    try:
        uid = get_jwt_identity()
        user = User.query.filter_by(id=int(uid), is_deleted=False).first() if uid else None
        ws_ids = get_visible_workspace_ids() if user else []
        c_filter = {'is_deleted': False}
        if ws_ids is not None:
            c_filter['workspace_id'] = ws_ids
        if isinstance(c_filter.get('workspace_id'), list):
            contacts = Contact.query.filter_by(is_deleted=False).filter(Contact.workspace_id.in_(ws_ids)).count()
            cases = Case.query.filter_by(is_deleted=False).filter(Case.workspace_id.in_(ws_ids)).count()
            tasks = Task.query.filter_by(is_deleted=False).filter(Task.workspace_id.in_(ws_ids)).count()
            pending_tasks = Task.query.filter_by(is_deleted=False, status='pending').filter(Task.workspace_id.in_(ws_ids)).count()
            upcoming_deadlines = Deadline.query.filter_by(is_deleted=False, status='pending').filter(Deadline.workspace_id.in_(ws_ids)).order_by(Deadline.deadline_date).limit(5).all()
        else:
            contacts = Contact.query.filter_by(is_deleted=False).count()
            cases = Case.query.filter_by(is_deleted=False).count()
            tasks = Task.query.filter_by(is_deleted=False).count()
            pending_tasks = Task.query.filter_by(is_deleted=False, status='pending').count()
            upcoming_deadlines = Deadline.query.filter_by(is_deleted=False, status='pending').order_by(Deadline.deadline_date).limit(5).all()
        recent_activity = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()
    except Exception:
        contacts = cases = tasks = pending_tasks = 0
        upcoming_deadlines = []; recent_activity = []; user = None
    return render_template('dashboard.html', contact_count=contacts, case_count=cases,
        task_count=tasks, pending_count=pending_tasks, deadlines=upcoming_deadlines,
        activities=recent_activity, current_user=user)


@views_bp.route('/api/stats')
@jwt_required(optional=True)
def api_stats():
    """Per-user live stats (contacts/cases/tasks/pending) scoped to visible workspaces.
    Client-side dashboard fetches this with the stored JWT so counts update after login
    (page navigation does not carry the Authorization header)."""
    from ..models.user import User
    try:
        uid = get_jwt_identity()
        user = User.query.filter_by(id=int(uid), is_deleted=False).first() if uid else None
        if not user:
            return jsonify({'authenticated': False}), 200
        ws_ids = get_visible_workspace_ids()
        if ws_ids is not None:
            contacts = Contact.query.filter_by(is_deleted=False).filter(Contact.workspace_id.in_(ws_ids)).count()
            cases = Case.query.filter_by(is_deleted=False).filter(Case.workspace_id.in_(ws_ids)).count()
            tasks = Task.query.filter_by(is_deleted=False).filter(Task.workspace_id.in_(ws_ids)).count()
            pending_tasks = Task.query.filter_by(is_deleted=False, status='pending').filter(Task.workspace_id.in_(ws_ids)).count()
        else:
            contacts = Contact.query.filter_by(is_deleted=False).count()
            cases = Case.query.filter_by(is_deleted=False).count()
            tasks = Task.query.filter_by(is_deleted=False).count()
            pending_tasks = Task.query.filter_by(is_deleted=False, status='pending').count()
        return jsonify({
            'authenticated': True,
            'workspace': (user.workspace.to_dict() if user.workspace else None),
            'contacts': contacts, 'cases': cases,
            'tasks': tasks, 'pending': pending_tasks,
        }), 200
    except Exception as e:
        return jsonify({'authenticated': False, 'error': str(e)}), 500


@views_bp.route('/intake')
def intake():
    """Intake form — accessible to logged-in users too (so dashboard 'New case' can
    reach it; the public '/' redirects logged-in users to their dashboard)."""
    return render_template('index.html', practices=PRACTICES)


@views_bp.route('/login')
def login():
    """Branded per-workspace login page (like the legacy ab54f /login): tenant name,
    AREA RISERVATA, email + password, ← Torna al sito. The tenant is derived from a
    ?ws= or ?tenant= query param (or defaults to LexFlow). The login form posts to
    POST /api/auth/login and stores the JWT in localStorage (same as kanban)."""
    slug = request.args.get('ws') or request.args.get('tenant') or request.args.get('slug') or ''
    workspace = Workspace.query.filter_by(slug=slug, is_active=True).first() if slug else None
    tenant = workspace.name if workspace else 'LexFlow'
    main_url = request.args.get('back') or '#'
    return render_template('login.html', tenant=tenant, tenant_slug=workspace.slug if workspace else None,
                           main_site_url=main_url, favicon_url=(
                               '/static/favicons/romanelli.svg'
                               if workspace and workspace.slug in ('romanelli-studio', 'romanelli-audit')
                               else None
                           ))


# ── Kanban Board ───────────────────────────────────────────────────
@views_bp.route('/kanban')
@jwt_required(optional=True)
def kanban():
    statuses = ['Intake', 'Conflict Check', 'Review', 'In Progress', 'Waiting Docs', 'To Verify', 'Engaged', 'Closed']
    ws_ids = get_visible_workspace_ids()
    if ws_ids is not None:
        cases_by_status = {
            s: Case.query.filter_by(is_deleted=False, status=s).filter(Case.workspace_id.in_(ws_ids)).all()
            for s in statuses
        }
    else:
        cases_by_status = {s: Case.query.filter_by(is_deleted=False, status=s).all() for s in statuses}
    return render_template('kanban.html', statuses=statuses, cases_by_status=cases_by_status)


@views_bp.route('/kanban/roadmap')
@jwt_required(optional=True)
def roadmap():
    """Workspace-aware board for '/kanban/roadmap'.

    - superadmin or 'lexflow' (ws7) user  -> agentic roadmap (docs JSON)
    - other workspace users (e.g. Romanelli Studio) -> per-person-per-staff
      board: each staff member (FirmTeamMember) + their cases/projects.
    - anonymous -> redirect to /kanban (no leak).
    """
    import json as _json
    import os as _os
    from ..models.user import User as _User
    from ..models.firm_team import FirmTeamMember

    uid = None
    try:
        uid = int(get_jwt_identity()) if get_jwt_identity() else None
    except Exception:
        uid = None
    user = None
    if uid:
        user = _User.query.filter_by(id=uid, is_deleted=False).first()

    # ── Access gate: no leak to non-lexflow tenants ─────────────────
    if not user:
        return redirect(url_for('views.kanban'))
    is_internal = user.role == 'superadmin' or (user.workspace and user.workspace.slug == 'lexflow')

    # ── Staff board for firm workspaces (per-person-per-staff) ──────
    if not is_internal:
        ws = user.workspace
        team_ws_id = ws.parent_workspace_id if ws and ws.parent_workspace_id else (ws.id if ws else None)
        members = FirmTeamMember.query.filter_by(workspace_id=team_ws_id, is_active=True).all() if team_ws_id else []
        from ..models.case import Case
        ws_ids = get_visible_workspace_ids()
        cases = []
        if ws_ids is not None:
            cases = Case.query.filter(Case.is_deleted == False, Case.workspace_id.in_(ws_ids)).all()
        else:
            cases = Case.query.filter_by(is_deleted=False).all()
        return render_template('staff_board.html', members=members, cases=cases)

    # ── Internal agentic roadmap (lexflow / superadmin only) ────────
    roadmap_path = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))),
        'docs', 'LexFlow_Agentic_Roadmap.json'
    )
    data = {}
    if _os.path.exists(roadmap_path):
        with open(roadmap_path, 'r', encoding='utf-8') as f:
            data = _json.load(f)

    columns = data.get('kanban_columns', ['backlog', 'in_progress', 'blocked',
                                          'awaiting_confirmation', 'local_verified',
                                          'deployed', 'done'])
    tasks = data.get('tasks', [])
    by_column = {col: [] for col in columns}
    for t in tasks:
        col = t.get('column', 'backlog')
        if col not in by_column:
            by_column[col] = []
        by_column[col].append(t)

    return render_template('roadmap.html',
                           columns=columns,
                           by_column=by_column,
                           roadmap=data)


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


@views_bp.route('/settings')
@jwt_required(optional=True)
def settings_page():
    """Account settings — change password and/or email (uses /api/auth/change-credentials)."""
    return render_template('settings.html')


# ── Intake Routes ──────────────────────────────────────────────────
@views_bp.route('/')
def index():
    # Logged-in users land on their workspace home (dashboard) instead of the public intake form
    try:
        if get_jwt_identity():
            return redirect(url_for('views.dashboard'))
    except Exception:
        pass
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

    # Resolve workspace: authenticated user's workspace, else from ?ws= slug,
    # else the 'lexflow' workspace, else the first active workspace. NEVER fall
    # back to a hardcoded id (prod workspace ids start at 7, id 1 does not exist
    # and caused ForeignKeyViolation on contacts.workspace_id_fkey).
    wid = get_current_workspace_id()
    if not wid:
        slug = (request.args.get('ws') or request.form.get('ws') or '').strip()
        ws = Workspace.query.filter_by(slug=slug, is_active=True).first() if slug else None
        if not ws:
            ws = Workspace.query.filter_by(slug='lexflow', is_active=True).first()
        if not ws:
            ws = Workspace.query.filter_by(is_active=True).order_by(Workspace.id).first()
        wid = ws.id if ws else None
    if not wid:
        return jsonify({'error': 'No workspace available for intake'}), 503
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

    # Notify the CLIENT too (auto-confirmation) — 2026-09-03 (Ole):
    # intake must reach both the owner AND the person who submitted it.
    try:
        send_email(
            to_email=email,
            subject=f"Riceviamo la tua richiesta — {workspace_name}",
            html_body=f"<h3>Gentile {client_name},</h3>"
                      f"<p>abbiamo ricevuto la tua richiesta presso <b>{workspace_name}</b>.</p>"
                      f"<p><strong>Oggetto:</strong> {practice_area or 'Consulenza'}</p>"
                      f"<p><strong>Messaggio:</strong> {description or '—'}</p>"
                      f"<p>Ti ricontatteremo al più presto. Grazie.</p>"
                      f"<p style='color:#94A3B8;font-size:12px'>Questo è un messaggio automatico di conferma.</p>"
        )
    except Exception as _e:
        logger.warning(f"Submit client email failed (non-fatal): {_e}")

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
@jwt_required(optional=True)
def case_status(token):
    case = None
    try:
        case_id = int(token)
        case = Case.query.filter_by(id=case_id, is_deleted=False).first()
    except ValueError:
        pass

    # SECURITY (audit 2026-09-01): if an authenticated user (staff) opens a
    # status page, scope it to their visible workspaces — a Romanelli admin
    # must NOT be able to view a Pagliano case by guessing its id. Anonymous
    # clients keep the public tracking link (that is the feature's purpose).
    if get_jwt_identity():
        vis = get_visible_workspace_ids()
        if vis is not None and (not case or case.workspace_id not in vis):
            abort(404)

    # Build a plain dict the template can index (matter["..."]), including
    # the linked contact's name/email so the client-facing page renders.
    matter = None
    if case:
        contact = case.contact if case.contact else None
        matter = {
            'id': case.id,
            'practice_area': case.casetype or 'General',
            'urgency': case.priority or 'Medium',
            'status': case.status or 'Intake',
            'created_at': case.createdat.strftime('%d %b %Y') if case.createdat else '',
            'client_name': (contact.fullname if contact else case.title or 'Client'),
            'description': case.title,
        }
    return render_template('status.html', matter=matter, docs=[], events=[], statuses=STATUSES)


# ── Admin List ─────────────────────────────────────────────────────
@views_bp.route('/admin')
@jwt_required(optional=True)
def admin_list():
    # Server-rendered shell only. On normal navigation the JWT lives in
    # localStorage (not the request header), so the server cannot know the
    # user here — the page's client-side JS fetches /api/cases with the stored
    # token and renders the user's OWN matters (anonymous → login prompt).
    return render_template('admin.html', matters=[])


@views_bp.route('/admin/matter/<int:matter_id>', methods=['GET', 'POST'])
@jwt_required(optional=True)
def admin_matter(matter_id):
    # Server-rendered shell only. The JWT is in localStorage (not the request
    # header on navigation), so the server cannot scope here — the page's
    # client-side JS fetches /api/cases/<id>, notes and activity with the stored
    # token (404 for foreign/unauthorized cases; login prompt if anonymous).
    return render_template('admin_matter.html', matter_id=matter_id)


# ── Super-Admin Panel (all workspaces + accounts) ─────────────────
def _is_superadmin():
    """Return True if the JWT identity maps to a superadmin user."""
    from ..models.user import User
    uid = get_jwt_identity()
    if not uid:
        return False
    try:
        u = User.query.filter_by(id=int(uid), is_deleted=False).first()
        return bool(u and u.role == 'superadmin')
    except Exception:
        return False


@views_bp.route('/workspace')
@jwt_required(optional=True)
def workspace_panel():
    """Scoped workspace panel — shows the CURRENT user's own workspace (not
    superadmin's global view). Parent admins see their sub-workspaces too."""
    from ..models.user import User
    user = None
    try:
        uid = get_jwt_identity()
        user = User.query.filter_by(id=int(uid), is_deleted=False).first() if uid else None
    except Exception:
        user = None
    if not user:
        return redirect(url_for('views.index'))
    return render_template('workspace_panel.html', current_user=user)


@views_bp.route('/api/workspace')
@jwt_required()
def api_workspace():
    """Scoped workspace JSON: the current user's own workspace + visible
    sub-workspaces + their accounts. Never returns password hashes."""
    from ..models.user import User
    uid = get_jwt_identity()
    user = User.query.filter_by(id=int(uid), is_deleted=False).first() if uid else None
    if not user:
        return jsonify({'error': 'Not found'}), 404

    # own workspace + any sub-workspaces whose parent is this user's workspace
    ws_ids = get_visible_workspace_ids()
    if ws_ids is None:
        ws_ids = [user.workspace_id]
    workspaces = Workspace.query.filter(Workspace.id.in_(ws_ids), Workspace.is_active == True).order_by(Workspace.id).all()
    out = []
    for ws in workspaces:
        users = User.query.filter_by(workspace_id=ws.id, is_deleted=False).all()
        out.append({
            'workspace': ws.to_dict(),
            'users': [{'id': u.id, 'email': u.email, 'role': u.role,
                       'created_at': u.created_at.isoformat() if u.created_at else None} for u in users],
        })
    return jsonify(out), 200


@views_bp.route('/admin/panel')
@jwt_required(optional=True)
def superadmin_panel():
    """Super-admin dashboard: every workspace + its accounts. Superadmin only.
    The page renders shell always; client-side JS verifies the token via
    /api/admin/workspaces and redirects non-superadmins to home."""
    return render_template('admin_panel.html', panel=[])


@views_bp.route('/api/workspace/<int:workspace_id>', methods=['PATCH'])
@jwt_required()
def api_workspace_rename(workspace_id):
    """Rename a workspace (or sub-workspace). Superadmin may rename any; a
    parent-workspace admin may rename their own sub-workspaces. Client
    sub-tenant admins may rename their OWN workspace (their studio name)."""
    from ..models.user import User
    uid = get_jwt_identity()
    user = User.query.filter_by(id=int(uid), is_deleted=False).first() if uid else None
    if not user:
        return jsonify({'error': 'Not found'}), 404

    ws = Workspace.query.filter_by(id=workspace_id, is_active=True).first()
    if not ws:
        return jsonify({'error': 'Workspace not found'}), 404

    data = request.get_json(silent=True) or {}
    new_name = (data.get('name') or '').strip()
    if not new_name or len(new_name) > 255:
        return jsonify({'error': 'name (1-255 chars) is required'}), 400

    # Permission: superadmin OR owner of this workspace OR parent admin of a sub-workspace
    is_super = user.role == 'superadmin'
    is_owner = user.workspace_id == ws.id
    is_parent_admin = ws.parent_workspace_id and user.workspace_id == ws.parent_workspace_id and user.role == 'admin'
    if not (is_super or is_owner or is_parent_admin):
        return jsonify({'error': 'Not allowed to rename this workspace'}), 403

    ws.name = new_name
    db.session.commit()
    return jsonify({'success': True, 'workspace': ws.to_dict()}), 200


@views_bp.route('/api/workspace/<int:workspace_id>/user', methods=['POST'])
@jwt_required()
def api_workspace_add_user(workspace_id):
    """Add a login (admin/staff/user) to a workspace. Superadmin OR parent
    admin of the workspace may add users. Returns the created account."""
    from ..models.user import User
    uid = get_jwt_identity()
    user = User.query.filter_by(id=int(uid), is_deleted=False).first() if uid else None
    if not user:
        return jsonify({'error': 'Not found'}), 404

    ws = Workspace.query.filter_by(id=workspace_id, is_active=True).first()
    if not ws:
        return jsonify({'error': 'Workspace not found'}), 404

    is_super = user.role == 'superadmin'
    is_owner = user.workspace_id == ws.id and user.role == 'admin'
    is_parent_admin = ws.parent_workspace_id and user.workspace_id == ws.parent_workspace_id and user.role == 'admin'
    if not (is_super or is_owner or is_parent_admin):
        return jsonify({'error': 'Not allowed to add users here'}), 403

    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    role = data.get('role') or 'user'
    import re
    if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return jsonify({'error': 'Valid email is required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'password (min 6 chars) is required'}), 400
    if role not in ('admin', 'staff', 'user'):
        return jsonify({'error': 'role must be admin|staff|user'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already in use'}), 409

    new_user = User(email=email, role=role, workspace_id=ws.id)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'success': True, 'user': {'id': new_user.id, 'email': new_user.email, 'role': new_user.role}}), 201


@views_bp.route('/api/admin/workspaces')
@jwt_required()
def api_superadmin_workspaces():
    """JSON list of all workspaces + their accounts (superadmin only).
    Never returns password hashes — only email + role."""
    from ..models.user import User
    if not _is_superadmin():
        return jsonify({'error': 'Superadmin only'}), 403
    workspaces = Workspace.query.filter_by(is_active=True).order_by(Workspace.id).all()
    out = []
    for ws in workspaces:
        users = User.query.filter_by(workspace_id=ws.id, is_deleted=False).all()
        out.append({
            'workspace': ws.to_dict(),
            'users': [{'id': u.id, 'email': u.email, 'role': u.role, 'created_at': u.created_at.isoformat() if u.created_at else None} for u in users],
        })
    return jsonify(out), 200


@views_bp.route('/api/admin/reset-password', methods=['POST'])
@jwt_required()
def api_admin_reset_password():
    """Superadmin resets another user's password. Emails the reset user a
    notice (never the plaintext over insecure channels)."""
    from ..models.user import User
    from ..notification_service import send_email
    if not _is_superadmin():
        return jsonify({'error': 'Superadmin only'}), 403
    data = request.get_json(silent=True) or {}
    target_email = (data.get('email') or '').strip().lower()
    new_password = data.get('new_password') or ''
    if not target_email or len(new_password) < 6:
        return jsonify({'error': 'email and new_password (min 6 chars) are required'}), 400
    target = User.query.filter_by(email=target_email, is_deleted=False).first()
    if not target:
        return jsonify({'error': 'User not found'}), 404
    target.set_password(new_password)
    db.session.commit()
    ws_name = target.workspace.name if target.workspace else 'LexFlow'
    send_email(
        to_email=target_email,
        subject=f"[{ws_name}] Credentials updated by administrator",
        html_body=f"<h3>Your {ws_name} credentials were updated by an administrator</h3>"
                  f"<p>Your login (<b>{target_email}</b>) has a new password.</p>"
                  f"<p>If you did not request this, contact your administrator immediately.</p>",
    )
    return jsonify({'success': True, 'email': target_email}), 200


@views_bp.route('/api/admin/google-cal-sync', methods=['POST'])
@jwt_required()
def api_admin_google_cal_sync():
    """Superadmin-only: trigger a Google Calendar <-> LexFlow (ws7) sync.
    Body {direction: 'pull'|'push'|'both'} (default 'pull'). Events are scoped
    ONLY to the 'lexflow' workspace — never any client workspace.
    NOTE: with only an API key, Google exposes only calendars the owner made
    public; a private calendar needs OAuth. Push REQUIRES OAuth (API key cannot
    write). The sync reports the real result either way."""
    from ..google_cal_sync import sync_google_to_lexflow, push_lexflow_to_google
    if not _is_superadmin():
        return jsonify({'error': 'Superadmin only'}), 403
    direction = (request.get_json(silent=True) or {}).get('direction', 'pull')
    results = {}
    status = 200
    if direction in ('pull', 'both'):
        results['pull'] = sync_google_to_lexflow()
        if not results['pull'].get('ok'):
            status = 502
    if direction in ('push', 'both'):
        results['push'] = push_lexflow_to_google()
        if not results['push'].get('ok'):
            status = 502 if direction != 'both' else max(status, 200)
    return jsonify(results), status


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
    Sends email + WhatsApp notification to workspace owner (WhatsApp best-effort).
    """
    import secrets
    from datetime import date
    from ..models.workspace import Workspace
    from ..models.user import User
    from ..notification_service import send_email, send_whatsapp

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

    # Notify the CLIENT too (auto-confirmation) — 2026-09-03 (Ole):
    # intake must reach both the owner AND the person who submitted it.
    try:
        send_email(
            to_email=email,
            subject=f"Riceviamo la tua richiesta — {ws.name}",
            html_body=f"<h3>Gentile {fullname},</h3>"
                      f"<p>abbiamo ricevuto la tua richiesta presso <b>{ws.name}</b>.</p>"
                      f"<p><strong>Oggetto:</strong> {practice_area or 'Consulenza'}</p>"
                      f"<p><strong>Messaggio:</strong> {message or '—'}</p>"
                      f"<p>Ti ricontatteremo al più presto. Grazie.</p>"
                      f"<p style='color:#94A3B8;font-size:12px'>Questo è un messaggio automatico di conferma.</p>"
        )
    except Exception as _e:
        logger.warning(f"Intake client email failed (non-fatal): {_e}")

    # WhatsApp to workspace owner (UltraMsg) — best-effort, never crash the intake
    owner_phone = os.environ.get('ADMIN_PHONE', '')
    if not owner_phone:
        logger.warning("WhatsApp skipped: no ADMIN_PHONE set for intake notification (workspace=%s)", ws.slug)
    else:
        try:
            send_whatsapp(
                owner_phone,
                f"🔔 New intake from {ws.name}: {fullname}\n"
                f"Email: {email}\n"
                f"Phone: {phone or '—'}\n"
                f"Practice area: {practice_area or '—'}\n"
                f"Message: {message or '—'}"
            )
        except Exception as e:
            logger.warning("WhatsApp notification failed for intake (workspace=%s): %s", ws.slug, e)

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

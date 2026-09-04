"""Attachments (Allegati) blueprint — file upload/download/delete."""
import os
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, jsonify, request, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models.attachment import Attachment
from ..models.workspace import Workspace
from ..models.user import User
from ..models.contact import Contact
from ..models.case import Case
from ..notification_service import send_email
from ..workspace import get_current_workspace_id, get_visible_workspace_ids, workspace_filter

attachments_bp = Blueprint('attachments', __name__, url_prefix='/api/attachments')

# Upload directory at repo root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_FOLDER = Path(os.environ.get('UPLOAD_FOLDER', str(BASE_DIR / 'uploads')))
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg', '.txt'}
ALLOWED_MIME_TYPES = {
    'application/pdf': ('.pdf',),
    'application/msword': ('.doc',),
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ('.docx',),
    'image/png': ('.png',),
    'image/jpeg': ('.jpg', '.jpeg'),
    'text/plain': ('.txt',),
    'application/octet-stream': None,  # generic — rely on extension check
}
VALID_TARGET_TYPES = {"case", "contact", "task"}


def _is_allowed(filename, mimetype):
    """Validate extension + (when a concrete mime is provided) its match."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False
    mime = (mimetype or '').lower().split(';')[0].strip()
    if not mime:
        return True
    expected = ALLOWED_MIME_TYPES.get(mime)
    if expected is None:
        # Generic/unknown mime (octet-stream, empty) — fall back to extension check only
        return mime in ('application/octet-stream',)
    return ext in expected


def _filtered_query():
    # superadmin sees all workspaces (workspace_filter bypasses for superadmin)
    return workspace_filter(Attachment.query, Attachment).order_by(Attachment.created_at.desc())


def _get_attachment(attachment_id):
    """Fetch an attachment by id, scoped to what the current user may see.
    Superadmin (get_visible_workspace_ids() is None) sees all; a normal user
    only attachments in their own (+ visible sub-) workspaces; anonymous/empty
    scope sees nothing."""
    q = Attachment.query.filter_by(id=attachment_id)
    try:
        vis = get_visible_workspace_ids()
    except Exception:
        vis = get_current_workspace_id()
    if vis is not None:
        ids = vis if isinstance(vis, (list, tuple, set)) else [vis]
        q = q.filter(Attachment.workspace_id.in_(ids))
    return q.first()


def _resolve_client_email(target_type, target_id):
    """Resolve the client email linked to an attachment target.

    target_type 'contact' → the contact's email; 'case' → the case's linked
    contact (contactid → Contact) email. Best-effort: returns None on any
    lookup failure so notifications never break the upload.
    """
    try:
        if target_type == "contact":
            c = Contact.query.filter_by(id=target_id, is_deleted=False).first()
            return c.email if c and c.email else None
        if target_type == "case":
            case = Case.query.filter_by(id=target_id, is_deleted=False).first()
            if case and case.contactid:
                c = Contact.query.filter_by(id=case.contactid, is_deleted=False).first()
                return c.email if c and c.email else None
    except Exception:
        pass
    return None


def _notify_attachment_uploaded(attachment, original_name, uploader_email):
    """Send best-effort email notifications on a successful file upload.

    NEW EVENT (2026-09-04, analogous to calendar-event notify c81f8af):
      - superadmin / workspace owner  → ADMIN_EMAIL or first superadmin user
      - the CLIENT whose file it is   → email resolved from the attachment
        target (contact → email, case → contactid → contact email)
    Non-fatal: any failure is logged and swallowed — the 201 is never
    affected by mail delivery.
    """
    try:
        ws_name = attachment.workspace.name if attachment.workspace else "LexFlow"
        client_email = _resolve_client_email(attachment.target_type, attachment.target_id)

        # 1) Superadmin / workspace owner (never a fixed client address)
        owner_email = os.environ.get("NOTIFY_SUPERADMIN_EMAIL") or os.environ.get("ADMIN_EMAIL", "")
        if not owner_email:
            sa = User.query.filter_by(role="superadmin", is_deleted=False).first()
            if sa:
                owner_email = sa.email
        if owner_email:
            send_email(
                to_email=owner_email,
                subject=f"[LexFlow] File uploaded: {original_name}",
                html_body=f"<h3>File uploaded</h3>"
                          f"<p><b>Workspace:</b> {ws_name}</p>"
                          f"<p><b>Uploaded by:</b> {uploader_email or '—'}</p>"
                          f"<p><b>Target:</b> {attachment.target_type} #{attachment.target_id}</p>"
                          f"<p><b>File:</b> {original_name} "
                          f"({attachment.size_bytes} bytes, {attachment.mime_type or '—'})</p>"
                          f"<p><b>Cliente:</b> {client_email or '—'}</p>",
            )

        # 2) Client whose file it is (Italian subject — clients are Italian)
        if client_email and client_email.lower() != owner_email.lower():
            send_email(
                to_email=client_email,
                subject=f"Il tuo documento è stato caricato — {ws_name}",
                html_body=f"<h3>Ciao,</h3>"
                          f"<p>Ti informiamo che un documento è stato caricato nel tuo spazio:</p>"
                          f"<ul><li><b>Documento:</b> {original_name}</li>"
                          f"<li><b>Studio:</b> {ws_name}</li></ul>"
                          f"<p>Puoi consultarlo nella tua area riservata.</p>"
                          f"<p>Studio {ws_name}</p>",
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Attachment email notify failed (non-fatal): {e}")


@attachments_bp.post('/')
@jwt_required()
def upload_attachment():
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({"error": "file is required"}), 400

    target_type = (request.form.get('target_type') or '').strip().lower()
    target_id = request.form.get('target_id', type=int)
    if target_type not in VALID_TARGET_TYPES:
        return jsonify({"error": "Invalid target_type"}), 400
    if not target_id:
        return jsonify({"error": "target_id is required"}), 400

    # Enforce max size 20MB
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > MAX_FILE_SIZE:
        return jsonify({"error": "File exceeds 20MB limit"}), 413

    original_name = secure_filename(file.filename) or file.filename
    ext = os.path.splitext(original_name)[1].lower()
    if not _is_allowed(original_name, file.mimetype):
        return jsonify({"error": "File type not allowed"}), 400

    stored_name = uuid4().hex + ext
    file.save(str(UPLOAD_FOLDER / stored_name))

    attachment = Attachment(
        workspace_id=get_current_workspace_id(),
        filename=original_name,
        stored_name=stored_name,
        filepath=str(Path('uploads') / stored_name),
        mime_type=file.mimetype or 'application/octet-stream',
        size_bytes=size,
        target_type=target_type,
        target_id=target_id,
        uploaded_by=int(get_jwt_identity()),
    )
    db.session.add(attachment)
    db.session.commit()

    # NEW (2026-09-04): best-effort email notification on successful upload —
    # superadmin/owner + linked client. Never breaks the 201 (all failures
    # are caught inside _notify_attachment_uploaded).
    try:
        uploader = User.query.filter_by(id=attachment.uploaded_by, is_deleted=False).first()
        _notify_attachment_uploaded(attachment, original_name, uploader.email if uploader else None)
    except Exception:
        pass

    return jsonify(attachment.to_dict()), 201


@attachments_bp.get('/')
@jwt_required()
def list_attachments():
    query = _filtered_query()
    target_type = request.args.get('target_type')
    target_id = request.args.get('target_id', type=int)
    if target_type:
        if target_type not in VALID_TARGET_TYPES:
            return jsonify({"error": "Invalid target_type"}), 400
        query = query.filter_by(target_type=target_type)
    if target_id:
        query = query.filter_by(target_id=target_id)
    return jsonify([a.to_dict() for a in query.all()]), 200


@attachments_bp.get('/<int:attachment_id>/download')
@jwt_required()
def download_attachment(attachment_id):
    attachment = _get_attachment(attachment_id)
    if not attachment:
        return jsonify({"error": "Attachment not found"}), 404
    return send_from_directory(
        str(UPLOAD_FOLDER),
        attachment.stored_name,
        as_attachment=True,
        download_name=attachment.filename,
    )


@attachments_bp.delete('/<int:attachment_id>')
@jwt_required()
def delete_attachment(attachment_id):
    """Delete an attachment.

    RULE (client sub-tenants): a sub-workspace (client) admin can VIEW and
    UPLOAD documents but must NOT delete existing ones. Delete is allowed for:
      - superadmin
      - the workspace OWNER admin (non-sub, e.g. Romanelli studio itself)
      - the PARENT admin of the attachment's sub-workspace
    A client (sub-tenant admin) on their own workspace -> 403.
    """
    attachment = _get_attachment(attachment_id)
    if not attachment:
        return jsonify({"error": "Attachment not found"}), 404

    uid = get_jwt_identity()
    user = User.query.filter_by(id=int(uid), is_deleted=False).first() if uid else None
    if not user:
        return jsonify({"error": "User not found"}), 404

    ws = Workspace.query.get(attachment.workspace_id) if attachment.workspace_id else None

    # Client sub-tenant (has a parent workspace): the client admin can VIEW and
    # UPLOAD but must NOT delete existing docs. Delete allowed for superadmin
    # or the PARENT (firm) admin only.
    if ws and ws.parent_workspace_id:
        is_super = user.role == 'superadmin'
        is_parent_admin = user.workspace_id == ws.parent_workspace_id and user.role == 'admin'
        if not (is_super or is_parent_admin):
            return jsonify({"error": "Client sub-tenant may not delete documents"}), 403

    file_path = UPLOAD_FOLDER / attachment.stored_name
    try:
        if file_path.exists():
            file_path.unlink()
    except OSError:
        pass
    db.session.delete(attachment)
    db.session.commit()
    return jsonify({"deleted": True}), 200

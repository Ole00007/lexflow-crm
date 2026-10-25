"""Notification buttons — Telegram / WhatsApp (WS-C).

Endpoints (all JWT-protected, tenant-scoped via workspace_filter, and gated by
the NOTIFY_BUTTONS_ENABLED feature flag — default OFF in production):

  GET  /api/notify/task/<id>/links  -> deep links + firm-team recipients
  POST /api/notify/task/<id>/send   -> real Telegram send (token + consent only)
  PUT  /api/notify/consent          -> persist a per-recipient consent record

Recipients come from the firm Team (crm/models/firm_team.py). The Gantt branch
is expected to add a `task_assignees` table (roles case_owner/docs_supply/
legal_assistant/lawyer_review); it does NOT exist on this branch, so we degrade
gracefully to the firm team of the task's (parent) firm workspace.
"""
import os
import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..extensions import db
from ..models.task import Task
from ..models.user import User
from ..models.workspace import Workspace
from ..models.firm_team import FirmTeamMember
from ..models.notify_consent import NotifyConsent
from ..workspace import workspace_filter
from ..services import notify_links

logger = logging.getLogger(__name__)

notify_bp = Blueprint("notify", __name__, url_prefix="/api/notify")

VALID_CHANNELS = {"telegram", "whatsapp"}
_ON = ("1", "true", "yes", "on")


def _flag_on():
    return os.environ.get("NOTIFY_BUTTONS_ENABLED", "false").strip().lower() in _ON


@notify_bp.before_request
def _require_flag():
    """Feature flag: the whole blueprint is 404 when the flag is off."""
    if not _flag_on():
        return jsonify({"error": "Not found"}), 404


def _current_user():
    try:
        uid = get_jwt_identity()
        if not uid:
            return None
        return User.query.filter_by(id=int(uid), is_deleted=False).first()
    except Exception:
        return None


def _visible_task(task_id):
    """Task fetched THROUGH workspace_filter -> None when not in a visible workspace.

    This is the tenant-isolation boundary: an admin of another workspace simply
    gets None (then 404), never another tenant's task.
    """
    return (
        workspace_filter(Task.query.filter_by(is_deleted=False), Task)
        .filter_by(id=task_id)
        .first()
    )


def _team_ws_for_task(task):
    """The firm workspace whose team notifies on this task.

    Firm team members belong to the firm (parent) workspace; a client
    sub-workspace task is served by its parent firm's team.
    """
    ws = db.session.get(Workspace, task.workspace_id)
    if not ws:
        return task.workspace_id
    return ws.parent_workspace_id or ws.id


def _team_workspace_id_for(user):
    if user.role == "superadmin":
        return None
    ws = user.workspace
    if not ws:
        return None
    return ws.parent_workspace_id or ws.id


# ── GET links + recipients ───────────────────────────────────────────────────
@notify_bp.get("/task/<int:task_id>/links")
@jwt_required()
def task_links(task_id):
    user = _current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    task = _visible_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    payload = notify_links.build_links(task)

    team_ws = _team_ws_for_task(task)
    members = (
        FirmTeamMember.query.filter_by(workspace_id=team_ws, is_active=True)
        .order_by(FirmTeamMember.id.asc())
        .all()
    )

    consents = {}
    member_ids = [m.id for m in members]
    if member_ids:
        for c in NotifyConsent.query.filter(NotifyConsent.member_id.in_(member_ids)).all():
            consents[(c.member_id, c.channel)] = bool(c.granted)

    recipients = []
    for m in members:
        channels = ["telegram"]  # deep link / share always available
        if notify_links.normalize_phone(m.phone) is not None:
            channels.append("whatsapp")
        recipients.append(
            {
                "member_id": m.id,
                "name": m.name,
                "role": m.role,
                "channels": channels,
                "consented": {
                    "telegram": consents.get((m.id, "telegram"), False),
                    "whatsapp": consents.get((m.id, "whatsapp"), False),
                },
            }
        )

    payload["recipients"] = recipients
    return jsonify(payload), 200


# ── POST real send ───────────────────────────────────────────────────────────
@notify_bp.post("/task/<int:task_id>/send")
@jwt_required()
def task_send(task_id):
    user = _current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    task = _visible_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True) or {}
    channel = (data.get("channel") or "").strip().lower()
    member_id = data.get("member_id")

    if channel not in VALID_CHANNELS:
        return jsonify({"error": "channel must be 'telegram' or 'whatsapp'"}), 400

    # WhatsApp real send is out of scope (Meta verification) -> 501 + deep link.
    if channel == "whatsapp":
        return (
            jsonify(
                {
                    "error": "WhatsApp real send not implemented; use the wa.me deep link",
                    "deeplink": notify_links.whatsapp_link(None, task),
                }
            ),
            501,
        )

    # --- telegram real send ---
    if not member_id:
        return jsonify({"error": "member_id is required"}), 400

    team_ws = _team_ws_for_task(task)
    member = FirmTeamMember.query.filter_by(id=int(member_id), workspace_id=team_ws).first()
    if not member:
        return jsonify({"error": "Team member not found"}), 404

    token = os.environ.get("LEXFLOW_TELEGRAM_BOT_TOKEN")
    if not token:
        # No separate LexFlow bot token configured -> real send unavailable.
        return jsonify({"error": "Telegram sending is not configured"}), 501

    consent = NotifyConsent.query.filter_by(member_id=member.id, channel="telegram").first()
    if not consent or not consent.granted:
        return (
            jsonify({"error": "Recipient has not consented to Telegram notifications"}),
            403,
        )

    if not consent.telegram_chat_id:
        return (
            jsonify(
                {
                    "error": "No Telegram chat on file for this recipient "
                    "(they must start the LexFlow bot first)"
                }
            ),
            422,
        )

    raw = data.get("message")
    text = notify_links.sanitize_text(raw) if raw else notify_links.build_message_text(task)

    try:
        notify_links.send_telegram_message(token, consent.telegram_chat_id, text)
    except NotImplementedError as e:
        return jsonify({"error": str(e)}), 501
    except Exception as e:  # never leak token/details
        logger.warning("telegram send failed: %s", type(e).__name__)
        return jsonify({"error": "Send failed"}), 502

    return jsonify({"sent": True, "channel": "telegram", "member_id": member.id}), 200


# ── PUT consent ──────────────────────────────────────────────────────────────
@notify_bp.put("/consent")
@jwt_required()
def put_consent():
    user = _current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    if user.role not in ("admin", "superadmin"):
        return jsonify({"error": "Forbidden - admin or superadmin only"}), 403

    data = request.get_json(silent=True) or {}
    member_id = data.get("member_id")
    channel = (data.get("channel") or "").strip().lower()
    granted = data.get("granted")

    if not member_id or channel not in VALID_CHANNELS or not isinstance(granted, bool):
        return (
            jsonify(
                {
                    "error": "member_id, channel ('telegram'|'whatsapp') and "
                    "granted (bool) are required"
                }
            ),
            400,
        )

    member = FirmTeamMember.query.filter_by(id=int(member_id)).first()
    if not member:
        return jsonify({"error": "Team member not found"}), 404

    # Tenant scope: a non-superadmin may only manage their OWN firm's team, and a
    # client sub-tenant admin (workspace with a parent) is read-only.
    if user.role != "superadmin":
        ws = user.workspace
        if (
            ws is None
            or ws.parent_workspace_id is not None
            or member.workspace_id != _team_workspace_id_for(user)
        ):
            return jsonify({"error": "Forbidden"}), 403

    consent = NotifyConsent.query.filter_by(member_id=member.id, channel=channel).first()
    if not consent:
        consent = NotifyConsent(
            workspace_id=member.workspace_id,
            member_id=member.id,
            channel=channel,
            granted=granted,
            consented_by=user.id,
        )
        db.session.add(consent)
    else:
        consent.granted = granted
        consent.consented_by = user.id

    # Optional delivery target for Telegram, captured out of band.
    chat_id = data.get("telegram_chat_id")
    if channel == "telegram" and chat_id is not None:
        consent.telegram_chat_id = (str(chat_id)[:64] or None)

    db.session.commit()
    return jsonify(consent.to_dict()), 200

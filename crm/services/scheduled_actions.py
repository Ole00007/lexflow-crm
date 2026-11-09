"""Event-driven delay engine (T-009). Recurring reminders stay a Railway cron;
this engine handles one-shot delayed actions (drips, follow-ups, AI-decided).

    enqueue(...)            -> row in `scheduled_actions`
    @register_handler(kind) -> fn(action, contact) ; return value ignored, raise to retry
    poll_once(now)          -> claims due rows atomically, gates via should_notify, fires handler once
    cancel_by_key(key)      -> suppress pending rows (e.g. contact replied)
"""
import json
import logging
from datetime import datetime, timedelta

from ..extensions import db
from ..models.contact import Contact
from ..models.scheduled_action import ScheduledAction
from .notify_gate import should_notify

log = logging.getLogger(__name__)

# From reflection_rules[] in docs/LexFlow_Agentic_Roadmap.json (no_response_24h/72h/7d)
DRIP_DELAYS = {
    "followup_24h": timedelta(hours=24),
    "followup_72h": timedelta(hours=72),
    "final_checkin_7d": timedelta(days=7),
}

_HANDLERS = {}


def register_handler(kind):
    def deco(fn):
        _HANDLERS[kind] = fn
        return fn
    return deco


def get_handlers():
    return _HANDLERS


def enqueue(workspace_id, kind, due_at, contact_id=None, case_id=None, channel=None,
            notif_type=None, suppression_key=None, payload=None, source="rule",
            max_attempts=3):
    row = ScheduledAction(
        workspace_id=workspace_id, kind=kind, due_at=due_at, contact_id=contact_id,
        case_id=case_id, channel=channel, notif_type=notif_type,
        suppression_key=suppression_key, source=source, max_attempts=max_attempts,
        payload=json.dumps(payload) if payload is not None else None, state="pending",
    )
    db.session.add(row)
    db.session.commit()
    return row


def enqueue_drip(contact, start=None, channel="email"):
    """Enqueue the 24h/72h/7d no-response drip; all share one suppression key."""
    start = start or datetime.utcnow()
    key = f"contact:{contact.id}:drip"
    return [
        enqueue(contact.workspace_id, kind, start + delay, contact_id=contact.id,
                channel=channel, notif_type="marketing", suppression_key=key)
        for kind, delay in DRIP_DELAYS.items()
    ]


def cancel_by_key(suppression_key, state="suppressed"):
    n = ScheduledAction.query.filter_by(suppression_key=suppression_key, state="pending") \
        .update({"state": state, "processed_at": datetime.utcnow()})
    db.session.commit()
    return n


def _claim(action_id, now):
    """Atomic pending->processing; only one worker wins."""
    n = ScheduledAction.query.filter_by(id=action_id, state="pending") \
        .update({"state": "processing", "locked_at": now,
                 "attempts": ScheduledAction.attempts + 1})
    db.session.commit()
    return n == 1


def poll_once(now=None, limit=50, stale_after=timedelta(minutes=15)):
    now = now or datetime.utcnow()
    # recover rows stuck in 'processing' (worker died mid-run)
    ScheduledAction.query.filter(ScheduledAction.state == "processing",
                                 ScheduledAction.locked_at < now - stale_after) \
        .update({"state": "pending"})
    db.session.commit()
    ids = [r.id for r in ScheduledAction.query.filter(
        ScheduledAction.state == "pending", ScheduledAction.due_at <= now)
        .order_by(ScheduledAction.due_at).limit(limit).all()]
    stats = {"fired": 0, "suppressed": 0, "failed": 0, "retry": 0}
    for aid in ids:
        if not _claim(aid, now):
            continue
        a = db.session.get(ScheduledAction, aid)
        contact = db.session.get(Contact, a.contact_id) if a.contact_id else None
        if a.channel and not should_notify(contact, a.channel, a.notif_type or "transactional"):
            a.state, a.processed_at = "suppressed", now
            stats["suppressed"] += 1
        else:
            handler = _HANDLERS.get(a.kind)
            try:
                if handler is None:
                    raise LookupError(f"no handler registered for kind={a.kind!r}")
                handler(a, contact)
                a.state, a.processed_at = "done", now
                stats["fired"] += 1
            except Exception as exc:  # noqa: BLE001 - worker must survive handler bugs
                log.exception("scheduled_action %s failed", a.id)
                a.last_error = str(exc)[:1000]
                if a.attempts >= a.max_attempts or handler is None:
                    a.state, a.processed_at = "failed", now
                    stats["failed"] += 1
                else:
                    a.state = "pending"
                    a.due_at = now + timedelta(minutes=5 * a.attempts)
                    stats["retry"] += 1
        db.session.commit()
    return stats

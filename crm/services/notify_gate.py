"""Shared suppression gate for outbound contact messages (email + WhatsApp).

Per docs/WhatsApp-Business-API-Scoping-2026-10-06.md: ONE should_notify(contact,
channel, notif_type) used by every channel so they cannot contradict each other.
Conservative baseline: fail closed. Channel-specific opt-ins (wa_opt_in, Meta 24h
window) extend this function when T-005 is approved; callers do not change.
"""
CHANNELS = ("email", "whatsapp")
TYPES = ("transactional", "marketing")


def should_notify(contact, channel, notif_type="transactional"):
    if contact is None or getattr(contact, "is_deleted", False):
        return False
    if channel not in CHANNELS or notif_type not in TYPES:
        return False
    if channel == "email" and not contact.email:
        return False
    if channel == "whatsapp" and not contact.phone:
        return False
    if notif_type == "marketing" and not contact.gdpr_consent:
        return False
    return True

"""
Email notification service using Resend API.
Sends intake confirmations, booking notifications, and status updates.
"""
import os
import logging
from flask import current_app

logger = logging.getLogger(__name__)

# Lazy import Resend (optional dependency)
resend = None
try:
    import resend as _resend
    resend = _resend
except ImportError:
    pass


def send_email(to_email: str, subject: str, html_body: str, from_name: str = "LexFlow") -> bool:
    """Send an email via Resend. Returns True if sent successfully."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get("EMAIL_FROM", "onboarding@resend.dev")

    if not api_key:
        logger.warning(f"Email not sent: missing RESEND_API_KEY (to={to_email}, subject={subject})")
        return False

    if resend is None:
        logger.warning(f"Email not sent: resend package not installed (to={to_email})")
        return False

    try:
        resend.api_key = api_key
        response = resend.Emails.send({
            "from": f"{from_name} <{from_addr}>",
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        })
        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_booking_notification(client_email: str, client_name: str, owner_email: str,
                               booking_type: str, booking_time: str, notes: str = "",
                               workspace_name: str = "", court_name: str = "") -> bool:
    """Send booking confirmation to client AND notification to workspace owner.

    Returns True if at least one email was sent.
    """
    client_subject = f"Appuntamento confermato - {workspace_name or 'LexFlow'}"
    client_html = f"""
    <div style="font-family:Inter,sans-serif;max-width:600px;margin:auto;padding:24px">
        <h2 style="color:#3B7DD8">Appuntamento Confermato</h2>
        <p>Ciao <strong>{client_name}</strong>,</p>
        <p>Il tuo appuntamento è stato registrato con successo.</p>
        <div style="background:#f4f8fb;border-radius:12px;padding:20px;margin:20px 0">
            <p><strong>Data/ora:</strong> {booking_time}</p>
            <p><strong>Tipo:</strong> {booking_type}</p>
            {f'<p><strong>Note:</strong> {notes}</p>' if notes else ''}
            {f'<p><strong>Luogo:</strong> {court_name}</p>' if court_name else ''}
        </div>
        <p style="color:#64748b;font-size:14px">Riceverai un promemoria prima dell'appuntamento.</p>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0">
        <p style="color:#94a3b8;font-size:12px">{workspace_name or 'LexFlow'} — Legal CRM</p>
    </div>
    """

    owner_subject = f"Nuovo appuntamento: {client_name} - {booking_type}"
    owner_html = f"""
    <div style="font-family:Inter,sans-serif;max-width:600px;margin:auto;padding:24px">
        <h2 style="color:#3B7DD8">Nuovo Appuntamento</h2>
        <p>Un nuovo appuntamento è stato registrato tramite il form di prenotazione.</p>
        <div style="background:#f4f8fb;border-radius:12px;padding:20px;margin:20px 0">
            <p><strong>Cliente:</strong> {client_name}</p>
            <p><strong>Email:</strong> {client_email}</p>
            <p><strong>Data/ora:</strong> {booking_time}</p>
            <p><strong>Tipo:</strong> {booking_type}</p>
            {f'<p><strong>Note:</strong> {notes}</p>' if notes else ''}
            {f'<p><strong>Luogo:</strong> {court_name}</p>' if court_name else ''}
        </div>
        <p style="color:#64748b;font-size:14px">Accedi al CRM per gestire l'appuntamento.</p>
    </div>
    """

    sent_client = send_email(client_email, client_subject, client_html)
    sent_owner = send_email(owner_email, owner_subject, owner_html)

    return sent_client or sent_owner
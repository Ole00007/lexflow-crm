"""
Notification service — sends email via Resend and WhatsApp via UltraMsg.
Both have free tiers. Falls back gracefully if credentials are missing.
"""
import os
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# ── Email via Resend (free tier: 100 emails/day) ──────────────────

_resend = None
try:
    import resend as _r
    _resend = _r
except ImportError:
    pass


def send_email(to_email: str, subject: str, html_body: str, from_name: str = "LexFlow") -> bool:
    # Preferred: SMTP (e.g. Yahoo app password) — set SMTP_HOST/PORT/USER/PASSWORD/EMAIL_FROM
    smtp_host = os.environ.get("SMTP_HOST", "")
    if smtp_host:
        return _send_email_smtp(to_email, subject, html_body, from_name)
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get("EMAIL_FROM", "onboarding@resend.dev")
    if not api_key:
        logger.info(f"Email skipped: no RESEND_API_KEY (to={to_email})")
        return False
    if _resend is None:
        logger.info(f"Email skipped: resend package not installed")
        return False
    try:
        _resend.api_key = api_key
        _resend.Emails.send({
            "from": f"{from_name} <{from_addr}>",
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        })
        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.warning(f"Email failed to {to_email}: {e}")
        return False


def _send_email_smtp(to_email: str, subject: str, html_body: str, from_name: str) -> bool:
    """Send via SMTP (Yahoo/Gmail app-password pattern). Best-effort."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    host = os.environ.get("SMTP_HOST", "")
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("EMAIL_FROM", user)
    if not host or not user or not password:
        logger.info("Email skipped: SMTP configured but SMTP_USER/PASSWORD missing")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_addr}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            server.starttls()
        server.login(user, password)
        server.sendmail(from_addr, [to_email], msg.as_string())
        server.quit()
        logger.info(f"Email sent via SMTP to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.warning(f"SMTP email failed to {to_email}: {e}")
        return False


# ── WhatsApp via UltraMsg (free tier: 100 messages/day) ──────────

def send_whatsapp(to_phone: str, message: str) -> bool:
    """Send WhatsApp message via UltraMsg. Free tier: 100 messages/day.
    Requires ULTRAMSG_INSTANCE_ID and ULTRAMSG_TOKEN env vars."""
    instance_id = os.environ.get("ULTRAMSG_INSTANCE_ID", "")
    token = os.environ.get("ULTRAMSG_TOKEN", "")
    if not instance_id or not token:
        logger.info(f"WhatsApp skipped: no ULTRAMSG_INSTANCE_ID/TOKEN (to={to_phone})")
        return False
    try:
        payload = json.dumps({
            "token": token,
            "to": to_phone,
            "body": message,
        }).encode()
        url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        if result.get("sent"):
            logger.info(f"WhatsApp sent to {to_phone}")
            return True
        logger.warning(f"WhatsApp send returned: {result}")
        return False
    except Exception as e:
        logger.warning(f"WhatsApp failed to {to_phone}: {e}")
        return False


# ── Combined notification ─────────────────────────────────────────

def notify_client_and_owner(client_email: str, client_phone: str, client_name: str,
                             owner_email: str, owner_phone: str,
                             subject: str, client_message: str, owner_message: str,
                             html_body: str = "") -> dict:
    """Send email + WhatsApp to both client and workspace owner.
    Returns dict with results: {client_email, client_whatsapp, owner_email, owner_whatsapp}"""
    results = {}

    # Email to client
    results['client_email'] = send_email(client_email, subject, html_body or client_message)

    # Email to owner
    results['owner_email'] = send_email(owner_email, f"[Admin] {subject}", html_body or owner_message)

    # WhatsApp to client
    if client_phone:
        results['client_whatsapp'] = send_whatsapp(client_phone, client_message)

    # WhatsApp to owner
    if owner_phone:
        results['owner_whatsapp'] = send_whatsapp(owner_phone, owner_message)

    return results


def send_booking_notification(client_email: str, client_phone: str, client_name: str,
                               owner_email: str, owner_phone: str,
                               booking_type: str, booking_time: str,
                               notes: str = "", workspace_name: str = "",
                               court_name: str = "") -> dict:
    """Send booking confirmation via email + WhatsApp (both channels, if configured)."""
    subject = f"Appuntamento confermato - {workspace_name or 'LexFlow'}"
    client_msg = f"✅ {workspace_name or 'LexFlow'} - Appuntamento confermato!\n\n" \
                 f"Tipo: {booking_type}\nData: {booking_time}\n" \
                 f"{'Luogo: ' + court_name + chr(10) if court_name else ''}" \
                 f"{'Note: ' + notes + chr(10) if notes else ''}" \
                 f"\nGrazie, {client_name}."
    owner_msg = f"📅 Nuovo appuntamento: {client_name}\n\n" \
                f"Tipo: {booking_type}\nData: {booking_time}\n" \
                f"{'Luogo: ' + court_name + chr(10) if court_name else ''}" \
                f"{'Note: ' + notes + chr(10) if notes else ''}"

    html = f"""
    <div style="font-family:Inter,sans-serif;max-width:600px;margin:auto;padding:24px">
        <h2 style="color:#3B7DD8">Appuntamento Confermato</h2>
        <p>Ciao <strong>{client_name}</strong>,</p>
        <p>Il tuo appuntamento è stato registrato.</p>
        <div style="background:#f4f8fb;border-radius:12px;padding:20px;margin:20px 0">
            <p><strong>Data/ora:</strong> {booking_time}</p>
            <p><strong>Tipo:</strong> {booking_type}</p>
            {f'<p><strong>Note:</strong> {notes}</p>' if notes else ''}
            {f'<p><strong>Luogo:</strong> {court_name}</p>' if court_name else ''}
        </div>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0">
        <p style="color:#94a3b8;font-size:12px">{workspace_name or 'LexFlow'} — Legal CRM</p>
    </div>
    """

    return notify_client_and_owner(
        client_email=client_email, client_phone=client_phone,
        client_name=client_name,
        owner_email=owner_email, owner_phone=owner_phone,
        subject=subject, client_message=client_msg,
        owner_message=owner_msg, html_body=html
    )
"""Deep-link + message builders for Telegram / WhatsApp task notifications.

Pure, side-effect-free link/text builders (NO network) plus a Telegram
`sendMessage` helper whose HTTP transport is INJECTABLE so tests never touch
the network.

Decisions (Smoothy ops + Admy CEO, 2026-10-24):
  - Deep links first — shippable with no bot token.
  - Message text carries NO client PII: only the matter number + task title
    (+ due date). Client full names are never included by default.
  - Phone numbers are normalised to E.164 digits (7..15); anything else is
    rejected (injection like '+39 333; DROP' collapses to too few digits).
  - Telegram `start` payload restricted to [A-Za-z0-9_-], max 64 chars
    (Telegram's own deep-link constraint).
  - Message text is stripped of control chars / newlines and length-capped.
  - The Telegram bot token is NEVER logged.
"""
import os
import re
import logging
from urllib.parse import quote, urlencode

logger = logging.getLogger(__name__)

# ── Caps / constants ────────────────────────────────────────────────────────
MAX_TEXT_LEN = 300
MAX_TITLE_LEN = 120
MAX_START_PAYLOAD = 64
MIN_PHONE_DIGITS = 7
MAX_PHONE_DIGITS = 15
TELEGRAM_API = "https://api.telegram.org"

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")  # control chars incl. newlines/tabs


# ── Sanitising helpers ──────────────────────────────────────────────────────
def normalize_phone(raw):
    """Return E.164 digits (no leading '+') or None.

    Accepts '+39 333 1234567', '0039-333-...', etc. Strips every non-digit so
    injection payloads (';', 'DROP', spaces) simply vanish; the result is then
    length-checked. A '00' international prefix is dropped.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if digits.startswith("00"):
        digits = digits[2:]
    if not (MIN_PHONE_DIGITS <= len(digits) <= MAX_PHONE_DIGITS):
        return None
    return digits


def sanitize_text(s, max_len=MAX_TEXT_LEN):
    """Collapse control chars / whitespace to single spaces and length-cap.

    Unicode (emoji, accents) is preserved; control characters and newlines are
    replaced so nothing can smuggle a second line / header into the message.
    """
    if not s:
        return ""
    s = _CONTROL_RE.sub(" ", str(s))
    s = re.sub(r"\s+", " ", s).strip()
    return s[:max_len]


def _matter_no(task):
    """The matter display id (e.g. 'R-01' or '#6'), or None — never the client name."""
    try:
        if getattr(task, "case", None) is not None:
            return task.case.display_id()
    except Exception:
        pass
    return None


def build_message_text(task):
    """Compose the notification text.

    PRIVACY: only matter number + task title (+ due date). No client full name,
    email, phone or any other field is ever added here.
    """
    title = sanitize_text(getattr(task, "title", "") or "", MAX_TITLE_LEN)
    parts = []
    matter = _matter_no(task)
    if matter:
        parts.append(matter)
    if title:
        parts.append(title)
    label = " \u00b7 ".join(parts) if parts else "LexFlow task"
    due = getattr(task, "duedate", None)
    if due is not None:
        try:
            label += " (due %s)" % due.isoformat()
        except Exception:
            pass
    return sanitize_text(label)


def task_url(task, app_url=None):
    """A link back to the task on the Gantt view (task detail pages are not public)."""
    base = (app_url or os.environ.get("LEXFLOW_APP_BASE_URL") or "").strip().rstrip("/")
    tid = getattr(task, "id", "")
    path = "/gantt#task-%s" % tid
    return (base + path) if base else path


# ── Deep links ──────────────────────────────────────────────────────────────
def _start_payload(task):
    pid = "task%s" % (getattr(task, "id", "") or "")
    pid = re.sub(r"[^A-Za-z0-9_-]", "", pid)
    return pid[:MAX_START_PAYLOAD]


def telegram_deeplink(task):
    """https://t.me/<bot>?start=task<id> — or None when no bot username is set.

    Falls back to the share link (see telegram_share_link) when None.
    """
    bot = (os.environ.get("LEXFLOW_TELEGRAM_BOT") or "").strip().lstrip("@")
    bot = re.sub(r"[^A-Za-z0-9_]", "", bot)
    if not bot:
        return None
    return "https://t.me/%s?start=%s" % (bot, _start_payload(task))


def telegram_share_link(task, app_url=None):
    """https://t.me/share/url?url=...&text=... — always available (no bot needed)."""
    qs = urlencode({"url": task_url(task, app_url), "text": build_message_text(task)})
    return "https://t.me/share/url?" + qs


def whatsapp_link(phone, task):
    """https://wa.me/<digits>?text=... — or https://wa.me/?text=... when no valid phone.

    When `phone` is None/invalid the number is omitted so the user picks a
    contact inside WhatsApp (used for the generic top-level link).
    """
    text = quote(build_message_text(task))
    digits = normalize_phone(phone)
    if digits:
        return "https://wa.me/%s?text=%s" % (digits, text)
    return "https://wa.me/?text=%s" % text


def build_links(task):
    """The GET /links payload (deep links only — no recipients)."""
    return {
        "telegram": {
            "deeplink": telegram_deeplink(task),
            "share": telegram_share_link(task),
        },
        "whatsapp": {
            # generic: the sender picks the contact inside WhatsApp
            "link": whatsapp_link(None, task),
        },
    }


# ── Real send (Telegram only) ───────────────────────────────────────────────
def _default_http_post(url, json_body, timeout=10):
    import requests  # imported lazily; tests override http_post so this never runs

    return requests.post(url, json=json_body, timeout=timeout)


# Injection point: tests monkeypatch `notify_links.http_post`.
http_post = _default_http_post


def send_telegram_message(token, chat_id, text, sender=None):
    """Send via Telegram Bot API `sendMessage`.

    `sender(url, json_body)` is injectable (tests pass a fake recorder) so no
    network call happens in tests. The token lives in the URL path per the Bot
    API and is NEVER logged — only a redacted marker is logged.
    """
    if not token:
        raise ValueError("missing telegram bot token")
    if not chat_id:
        raise ValueError("missing telegram chat_id")
    post = sender or http_post
    url = "%s/bot%s/sendMessage" % (TELEGRAM_API, token)
    body = {"chat_id": chat_id, "text": sanitize_text(text)}
    # NOTE: never log `url` or `token`.
    logger.info("telegram sendMessage chat_id=%s text_len=%d", chat_id, len(body["text"]))
    return post(url, body)


def send_whatsapp_message(*args, **kwargs):
    """WhatsApp real send via Meta Cloud API — OUT OF SCOPE (stub).

    Raises NotImplementedError. The Meta WhatsApp Cloud API requires a verified
    WhatsApp Business Account, an approved message template, a phone-number ID,
    and a permanent system-user access token (WHATSAPP_* env vars). Until that
    business verification is complete, only the wa.me deep link is supported.
    Do not wire this up without Ole's approval.
    """
    raise NotImplementedError(
        "WhatsApp Cloud API send requires Meta business verification; "
        "use the wa.me deep link instead."
    )

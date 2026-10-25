"""Rule-based intent parsing for Eliza (offline brain): create tasks, manage the agenda.

English + Italian. Deliberately small: the LLM brain handles free-form language,
this keeps the feature working (and testable) with no external model.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

_TASK_VERBS = r"(?:create|add|new|make|crea|aggiungi|nuovo|nuova)"
_TASK_RE = re.compile(
    rf"\b{_TASK_VERBS}\s+(?:a\s+|an\s+|un\s+|uno\s+)?(?:new\s+|nuovo\s+)?(?:task|attivit[aà]|compito)\b\s*(?:called|named|titled|:|to|-)?\s*(?P<rest>.*)$",
    re.I,
)
_EVENT_RE = re.compile(
    r"\b(schedule|book|add (?:an? )?(?:event|hearing|meeting|appointment)|create (?:an? )?(?:event|hearing|meeting|appointment)|"
    r"add (?:it )?to (?:the |my )?(?:agenda|calendar)|put (?:it )?(?:in|on) (?:the |my )?(?:agenda|calendar)|"
    r"metti in agenda|aggiungi in agenda|aggiungi (?:all'|al )?(?:agenda|calendario)|fissa|prenota|crea (?:un )?(?:evento|udienza|appuntamento|riunione))\b",
    re.I,
)
_MATTER_RE = re.compile(r"\b(?:matter|case|pratica|caso|fascicolo)\s+[\"“']?(?P<m>[^\"”']+?)[\"”']?(?=\s+(?:due|by|on|at|entro|before|priority|with|il|alle)\b|[.,;]|$)", re.I)
_STOP_RE = re.compile(r"\s+(?:for|on|in|per|due|by|entro|before|at|alle|il|su)\b.*$", re.I)


def is_task_create(goal: str) -> bool:
    return bool(_TASK_RE.search(goal or ''))


def is_event_create(goal: str) -> bool:
    return bool(_EVENT_RE.search(goal or '')) and not is_task_create(goal)


def parse_date(text: str, today: Optional[date] = None) -> Optional[str]:
    today = today or date.today()
    t = (text or '').lower()
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})[/.\-](\d{1,2})(?:[/.\-](\d{2,4}))?\b", t)
    if m:
        d, mo = int(m[1]), int(m[2])
        y = int(m[3]) if m[3] else today.year
        if y < 100:
            y += 2000
        try:
            out = date(y, mo, d)
            if not m[3] and out < today:
                out = date(y + 1, mo, d)
            return out.isoformat()
        except ValueError:
            return None
    if re.search(r"\b(dopodomani|day after tomorrow)\b", t):
        return (today + timedelta(days=2)).isoformat()
    if re.search(r"\b(tomorrow|domani)\b", t):
        return (today + timedelta(days=1)).isoformat()
    if re.search(r"\b(today|oggi)\b", t):
        return today.isoformat()
    days = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6,
            'lunedì': 0, 'lunedi': 0, 'martedì': 1, 'martedi': 1, 'mercoledì': 2, 'mercoledi': 2, 'giovedì': 3,
            'giovedi': 3, 'venerdì': 4, 'venerdi': 4, 'sabato': 5, 'domenica': 6}
    for name, idx in days.items():
        if re.search(rf"\b{name}\b", t):
            delta = (idx - today.weekday()) % 7 or 7
            return (today + timedelta(days=delta)).isoformat()
    return None


def parse_time(text: str) -> Optional[str]:
    t = (text or '').lower()
    m = re.search(r"\b(\d{1,2})[:.h](\d{2})\b", t)
    if m and int(m[1]) < 24 and int(m[2]) < 60 and not re.search(r"\b\d{1,2}[.]\d{2}[.]\d{2,4}\b", t):
        return f"{int(m[1]):02d}:{int(m[2]):02d}"
    m = re.search(r"\b(?:at|alle|ore)\s+(\d{1,2})\s*(am|pm)?\b", t)
    if m:
        h = int(m[1])
        if m[2] == 'pm' and h < 12:
            h += 12
        if h < 24:
            return f"{h:02d}:00"
    return None


def parse_priority(text: str) -> Optional[str]:
    t = (text or '').lower()
    for word, val in (('urgent', 'Urgent'), ('urgente', 'Urgent'), ('high', 'High'), ('alta', 'High'),
                      ('low', 'Low'), ('bassa', 'Low')):
        if re.search(rf"\b{word}\b", t):
            return val
    return None


def matter_hint(goal: str) -> str:
    m = _MATTER_RE.search(goal or '')
    return (m.group('m').strip() if m else '')


def _clean_title(raw: str) -> str:
    raw = (raw or '').strip()
    raw = _MATTER_RE.sub('', raw)
    raw = _STOP_RE.sub('', raw)
    return raw.strip(' "“”\'.,;:-')


def task_title(goal: str) -> str:
    m = _TASK_RE.search(goal or '')
    return _clean_title(m.group('rest')) if m else ''


def event_title(goal: str) -> str:
    g = _EVENT_RE.sub('', goal or '', count=1)
    g = _MATTER_RE.sub('', g)
    g = re.sub(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?)\b", '', g)
    g = re.sub(r"\b(?:at|alle|ore)\s+\d{1,2}(?:[:.h]\d{2})?\s*(?:am|pm)?\b", '', g, flags=re.I)
    g = re.sub(r"\b(tomorrow|today|domani|oggi|dopodomani|day after tomorrow|on|per|il|a|an|the|to|in|my|agenda|calendar|calendario)\b", ' ', g, flags=re.I)
    g = re.sub(r"\s+", ' ', g)
    return g.strip(' "“”\'.,;:-')


def event_type(goal: str) -> str:
    t = (goal or '').lower()
    for word, val in (('hearing', 'hearing'), ('udienza', 'hearing'), ('deadline', 'deadline'), ('scadenza', 'deadline'),
                      ('call', 'call'), ('chiamata', 'call'), ('appointment', 'appointment'), ('appuntamento', 'appointment')):
        if word in t:
            return val
    return 'meeting'


def build_task_args(goal: str, caseid: int) -> Dict[str, Any]:
    args: Dict[str, Any] = {'title': task_title(goal)[:255] or 'New task', 'caseid': int(caseid)}
    due = parse_date(goal)
    if due:
        args['duedate'] = due
    pr = parse_priority(goal)
    if pr:
        args['priority'] = pr
    return args


def build_event_args(goal: str, caseid: Optional[int] = None) -> Dict[str, Any]:
    d = parse_date(goal) or (date.today() + timedelta(days=1)).isoformat()
    tm = parse_time(goal) or '09:00'
    start = datetime.fromisoformat(f"{d}T{tm}:00")
    args: Dict[str, Any] = {
        'title': event_title(goal)[:255] or 'New event',
        'start_datetime': start.isoformat(),
        'end_datetime': (start + timedelta(hours=1)).isoformat(),
        'event_type': event_type(goal),
    }
    if caseid:
        args['caseid'] = int(caseid)
    return args


def date_issue(goal: str, today: Optional[date] = None) -> Optional[str]:
    """Return a clarification message if the goal holds an unparseable or past date, else None."""
    today = today or date.today()
    t = (goal or '').lower()
    has_token = re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?\b", t)
    d = parse_date(goal, today)
    if has_token and not d:
        return f"I could not read that date ('{has_token.group(0)}'). Could you give it as YYYY-MM-DD or DD/MM/YYYY?"
    if d and d < today.isoformat():
        return f"{d} is in the past. Which date should I use instead?"
    return None

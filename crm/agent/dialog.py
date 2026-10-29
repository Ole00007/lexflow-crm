"""Elisa conversation layer: follow-ups, pending questions, small talk — all offline (zero model tokens).

The chat endpoint used to treat every message as a brand-new goal, so "yes please" / "Rasing separazione" after a
question had no referent. The client now echoes back the last turns and a tiny ``pending`` object; ``resolve`` turns
a follow-up into a complete goal, or answers trivial messages directly without running the brain at all.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

MAX_TURNS = 8
MAX_TURN_CHARS = 300
AWAITING = ('matter', 'confirm')

_YES = {'yes', 'yes please', 'yep', 'yeah', 'ok', 'okay', 'sure', 'go ahead', 'please do', 'do it', 'si', 'sì', 'certo',
        'va bene', 'ok grazie', 'yes do it'}
_NO = {'no', 'no thanks', 'nope', 'cancel', 'never mind', 'nevermind', 'no grazie', 'annulla', 'stop'}
_PING = {'are you thinking', 'are you there', 'are you working', 'still there', 'hello', 'hi', 'hey', 'ciao', 'buongiorno',
         'buonasera', 'thinking', 'anyone there', 'you there'}
_BLOCK = re.compile(r"\b(block(ed|ing)?|stuck|waiting)\b", re.I)
HELP_TEXT = ('I\'m here. I can: list your open or blocked tasks, show the agenda, summarize a document, draft a client '
             'update for a matter, create a task or schedule a hearing (I always ask you to confirm before writing). '
             'Try: "what is blocking me?" or "draft client update for matter <name>".')


def clean_history(raw: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for item in raw[-MAX_TURNS:]:
        if not isinstance(item, dict):
            continue
        role = 'assistant' if str(item.get('role')) in ('assistant', 'bot') else 'user'
        text = str(item.get('content') or item.get('text') or '').strip()[:MAX_TURN_CHARS]
        if text:
            out.append({'role': role, 'content': text})
    return out


def clean_pending(raw: Any) -> Optional[Dict[str, str]]:
    if not isinstance(raw, dict):
        return None
    goal = str(raw.get('goal') or '').strip()[:500]
    awaiting = str(raw.get('awaiting') or '')
    if not goal or awaiting not in AWAITING:
        return None
    return {'goal': goal, 'awaiting': awaiting}


def clean_page(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    path = str(raw.get('path') or '')[:120]
    if path.startswith('/'):
        out['path'] = path
    for key in ('matter_id', 'case_id'):
        try:
            if raw.get(key) not in (None, ''):
                out['matter_id'] = int(raw[key])
        except (TypeError, ValueError):
            pass
    return out


def _norm(message: str) -> str:
    return re.sub(r'\s+', ' ', message.strip().lower().strip(' .!?,;:'))


def resolve(message: str, history: List[Dict[str, str]], pending: Optional[Dict[str, str]]) -> Dict[str, Any]:
    """Return {'goal': str} to run the brain, or {'reply': str} to answer directly (no brain, no tokens)."""
    m = _norm(message)
    if m in _PING:
        return {'reply': HELP_TEXT}
    if pending and m in _NO:
        return {'reply': 'Okay, I will not do it. Anything else?'}
    if pending and m in _YES:
        if pending['awaiting'] == 'confirm':
            return {'goal': pending['goal']}
        return {'reply': 'Which matter? Give me its name, e.g. "Rasing separazione".'}
    if pending and pending['awaiting'] == 'matter' and m and len(m.split()) <= 8:
        return {'goal': f"{pending['goal'].rstrip(' .')} for matter {message.strip()}"}
    if _BLOCK.search(m) and any(w in m for w in ('what', 'which', 'show', 'list', 'my', 'any')) and 'task' not in m:
        return {'goal': 'show my blocked tasks'}
    return {'goal': message.strip()}


def pending_from_reply(goal: str, reply: str) -> Optional[Dict[str, str]]:
    """If Elisa's reply asked for the matter, remember the goal so the next short message completes it."""
    r = (reply or '').lower()
    if r.startswith('for which matter') or r.startswith('which matter'):
        return {'goal': goal[:500], 'awaiting': 'matter'}
    return None

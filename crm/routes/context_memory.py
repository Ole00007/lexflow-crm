"""
Context memory blueprint — read-only Hindsight recall as a second node source for /graph (T-027).

GET /api/context/memory -> {"nodes": [...], "edges": [...], "source": "hindsight"|"unconfigured"|"unavailable"}
GET /api/context/digest -> {"date": "YYYY-MM-DD", "items": [...], "source": ...}

Rules:
  * Off by default: env CONTEXT_MEMORY_ENABLED must be true, otherwise 404.
  * JWT required; ONLY role 'superadmin' (others 403, anonymous 401).
  * Needs HINDSIGHT_URL + HINDSIGHT_API_KEY (Railway variables). Unset -> no network, source 'unconfigured'.
    Optional HINDSIGHT_BANK_ID (default avibe-hq), HINDSIGHT_MAX_NODES (default 25, ceiling 40).
  * Server-side proxy: the browser never sees the key or URL. Queries are fixed server-side.
  * Read-only (recall only). Raw Hindsight text is scrubbed (client names -> 'Avv.Pagl', emails, phones,
    URLs removed) before it leaves this module; only scrubbed output is cached, in memory, 5 min.
  * No new registry: nothing is persisted.
"""
import os
import re
import time
import json
import urllib.request
from datetime import datetime, timezone

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..models.user import User

context_memory_bp = Blueprint('context_memory', __name__, url_prefix='/api/context')

DEFAULT_BANK = 'avibe-hq'
DEFAULT_MAX_NODES = 25
HARD_MAX_NODES = 40
DIGEST_MAX = 8
EXCERPT_LEN = 240
MAX_ENTITIES = 6
TIMEOUT_S = 20   # measured: recall takes ~7.5 s on the Railway instance
CACHE_TTL_S = 300
GRAPH_QUERY = 'LexFlow CRM decisions, status and client work'
DIGEST_QUERY = 'LexFlow what was done and decided today'

_TASK_RE = re.compile(r'\bT-\d{3}\b')
_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_URL_RE = re.compile(r'https?://\S+')
_PHONE_RE = re.compile(r'(?<!\w)\+?\d[\d\s().-]{7,}\d')
_CLIENT_RE = re.compile(r'\b(?:Avv\.?\s*)?(?:Diego\s+)?(?:Pagliano|PAGLIANO)\b')   # case-sensitive: lowercase slug stays
CLIENT_ALIAS = 'Avv.Pagl'

_cache = {}


def _enabled():
    return os.environ.get('CONTEXT_MEMORY_ENABLED', '').strip().lower() in ('1', 'true', 'yes', 'on')


def _max_nodes():
    try:
        n = int(os.environ.get('HINDSIGHT_MAX_NODES', DEFAULT_MAX_NODES))
    except ValueError:
        n = DEFAULT_MAX_NODES
    return max(1, min(n, HARD_MAX_NODES))


def scrub(text):
    """Pure: remove client-identifying / contact text from recalled memory."""
    s = _EMAIL_RE.sub('[email]', text or '')
    s = _URL_RE.sub('[link]', s)
    s = _CLIENT_RE.sub(CLIENT_ALIAS, s)
    s = _PHONE_RE.sub('[phone]', s)
    return re.sub(r'\s+', ' ', s).strip()


def _recall(query, limit):
    """POST recall to Hindsight. Returns list of result dicts or None when unavailable."""
    base = os.environ.get('HINDSIGHT_URL', '').strip().rstrip('/')
    key = os.environ.get('HINDSIGHT_API_KEY', '').strip()
    if not base or not key:
        return 'unconfigured'
    bank = os.environ.get('HINDSIGHT_BANK_ID', DEFAULT_BANK).strip() or DEFAULT_BANK
    if not re.match(r'^[A-Za-z0-9_-]{1,64}$', bank):
        return None
    url = '%s/v1/default/banks/%s/memories/recall' % (base, bank)
    body = json.dumps({'query': query, 'max_tokens': 1500}).encode()
    req = urllib.request.Request(url, data=body, method='POST', headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            data = json.loads(r.read(2 * 1024 * 1024).decode('utf-8', 'replace'))
    except Exception:
        return None
    res = data.get('results') if isinstance(data, dict) else None
    return res[:limit] if isinstance(res, list) else None


def _cached(name, fn):
    now = time.time()
    hit = _cache.get(name)
    if hit and now - hit[0] < CACHE_TTL_S:
        return hit[1]
    val = fn()
    if val is not None and val.get('source') == 'hindsight':
        _cache[name] = (now, val)
    elif hit:
        return hit[1]   # upstream down: serve last good (already scrubbed) payload
    return val


def _item(r):
    text = scrub(str(r.get('text') or ''))
    if not text:
        return None
    ents = [scrub(str(e))[:60] for e in (r.get('entities') or []) if isinstance(e, str)][:MAX_ENTITIES]
    when = r.get('occurred_start') or r.get('mentioned_at')
    return {'id': str(r.get('id') or ''), 'text': text[:EXCERPT_LEN], 'type': str(r.get('type') or 'memory')[:24],
            'entities': ents, 'when': str(when)[:32] if when else None, 'tasks': sorted(set(_TASK_RE.findall(text)))}


def build_memory_payload(results):
    """Pure (testable): recall results -> graph payload."""
    if results == 'unconfigured':
        return {'nodes': [], 'edges': [], 'source': 'unconfigured'}
    if results is None:
        return {'nodes': [], 'edges': [], 'source': 'unavailable'}
    nodes, edges, seen = [], [], set()
    for r in results:
        it = _item(r) if isinstance(r, dict) else None
        if not it or not it['id'] or it['id'] in seen:
            continue
        seen.add(it['id'])
        nid = 'mem-' + re.sub(r'[^a-z0-9]', '', it['id'].lower())[:16]
        label = it['text'][:60] + ('…' if len(it['text']) > 60 else '')
        nodes.append({'id': nid, 'type': 'memory', 'label': label,
                      'data': {'excerpt': it['text'], 'kind': it['type'], 'entities': it['entities'],
                               'updated': it['when'], 'tags': it['entities']}})
        for tid in it['tasks']:
            edges.append({'source': nid, 'target': 'task-ref:' + tid, 'type': 'mentions'})
        if len(nodes) >= _max_nodes():
            break
    return {'nodes': nodes, 'edges': edges, 'source': 'hindsight'}


def build_digest_payload(results, today=None):
    """Pure (testable): items dated today (UTC) first; falls back to most recent, flagged."""
    today = today or datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if results == 'unconfigured':
        return {'date': today, 'items': [], 'source': 'unconfigured'}
    if results is None:
        return {'date': today, 'items': [], 'source': 'unavailable'}
    items = [i for i in (_item(r) for r in results if isinstance(r, dict)) if i]
    todays = [i for i in items if (i['when'] or '').startswith(today)]
    chosen = todays if todays else sorted(items, key=lambda i: i['when'] or '', reverse=True)
    out = [{'text': i['text'], 'when': i['when'], 'entities': i['entities'], 'tasks': i['tasks']}
           for i in chosen[:DIGEST_MAX]]
    return {'date': today, 'items': out, 'source': 'hindsight', 'is_today': bool(todays)}


def _guard():
    if not _enabled():
        return jsonify({'error': 'Not found'}), 404
    user = User.query.filter_by(id=int(get_jwt_identity()), is_deleted=False).first()
    if not user or user.role != 'superadmin':
        return jsonify({'error': 'Unauthorized - superadmin access required'}), 403
    return None


@context_memory_bp.get('/memory')
@jwt_required()
def context_memory():
    denied = _guard()
    if denied:
        return denied
    payload = _cached('memory', lambda: build_memory_payload(_recall(GRAPH_QUERY, HARD_MAX_NODES * 2)))
    return jsonify(payload or build_memory_payload(None)), 200


@context_memory_bp.get('/digest')
@jwt_required()
def context_digest():
    denied = _guard()
    if denied:
        return denied
    day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    payload = _cached('digest-' + day, lambda: build_digest_payload(_recall(DIGEST_QUERY, 40), day))
    return jsonify(payload or build_digest_payload(None, day)), 200

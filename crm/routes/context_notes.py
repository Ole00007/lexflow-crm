"""
Context notes blueprint — read-only Obsidian-vault notes for the live context graph.

GET /api/context/notes -> {"nodes": [...], "edges": [...], "source": "obsidian"|"unconfigured",
                           "vault_name": "<basename of LEXFLOW_VAULT_DIR>"}

Rules:
  * Off by default: env CONTEXT_NOTES_ENABLED must be true, otherwise 404.
  * JWT required; ONLY role 'superadmin' (everyone else 403, anonymous 401).
  * Vault dir from env LEXFLOW_VAULT_DIR. Only <vault>/01-Projects/LexFlow/*.md is
    scanned (non-recursive, max 300 files, files >200KB skipped, symlinks that
    resolve outside the vault are never followed).
  * Never returns full note bodies — only a short excerpt. Nothing else is read.
  * Optional Hindsight hook: HINDSIGHT_URL unset -> no-op (no network in this module).
"""
import os
import re
from datetime import datetime, timezone

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..models.user import User

context_notes_bp = Blueprint('context_notes', __name__, url_prefix='/api/context')

NOTES_SUBDIR = ('01-Projects', 'LexFlow')
MAX_FILES = 300
MAX_BYTES = 200 * 1024
EXCERPT_LEN = 240

_TASK_RE = re.compile(r'\bT-\d{3}\b')
_WIKI_RE = re.compile(r'\[\[([^\]\|#]+)(?:[#\|][^\]]*)?\]\]')
_H1_RE = re.compile(r'^#\s+(.+?)\s*$', re.M)


def _enabled():
    return os.environ.get('CONTEXT_NOTES_ENABLED', '').strip().lower() in ('1', 'true', 'yes', 'on')


def _slug(stem):
    s = re.sub(r'[^a-z0-9]+', '-', stem.lower()).strip('-')
    return s or 'note'


def _split_frontmatter(text):
    """Return (frontmatter_dict, body). Tiny YAML subset: scalar keys + inline/dash lists."""
    fm = {}
    if text.startswith('---'):
        m = re.match(r'^---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)', text, re.S)
        if m:
            block, text = m.group(1), text[m.end():]
            key = None
            for line in block.splitlines():
                kv = re.match(r'^([A-Za-z_][\w-]*)\s*:\s*(.*)$', line)
                if kv:
                    key, val = kv.group(1).lower(), kv.group(2).strip()
                    if val.startswith('[') and val.endswith(']'):
                        fm[key] = [x.strip().strip('\'"') for x in val[1:-1].split(',') if x.strip()]
                    elif val == '':
                        fm[key] = []
                    else:
                        fm[key] = val.strip('\'"')
                elif key and re.match(r'^\s*-\s+', line) and isinstance(fm.get(key), list):
                    fm[key].append(re.sub(r'^\s*-\s+', '', line).strip().strip('\'"'))
    return fm, text


def _tags(fm):
    t = fm.get('tags', fm.get('tag', []))
    if isinstance(t, str):
        t = [x for x in re.split(r'[,\s]+', t) if x]
    return [str(x).lstrip('#')[:40] for x in t][:12]


def _excerpt(body):
    s = re.sub(r'```.*?```', ' ', body, flags=re.S)
    s = re.sub(r'^#+\s*', '', s, flags=re.M)
    s = _WIKI_RE.sub(lambda m: m.group(1), s)
    s = re.sub(r'[*_`>]+', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:EXCERPT_LEN]


def _inside(root_real, path):
    real = os.path.realpath(path)
    return real == root_real or real.startswith(root_real + os.sep)


def build_notes_payload(vault_dir):
    """Pure function (testable): scan the vault dir and return the payload dict."""
    empty = {'nodes': [], 'edges': [], 'source': 'unconfigured'}
    if not vault_dir or not os.path.isdir(vault_dir):
        return empty
    root_real = os.path.realpath(vault_dir)
    notes_dir = os.path.join(root_real, *NOTES_SUBDIR)
    if not os.path.isdir(notes_dir) or not _inside(root_real, notes_dir):
        return {'nodes': [], 'edges': [], 'source': 'obsidian', 'vault_name': os.path.basename(root_real)}

    parsed = []
    try:
        names = sorted(os.listdir(notes_dir))
    except OSError:
        names = []
    for name in names:
        if len(parsed) >= MAX_FILES:
            break
        if not name.lower().endswith('.md') or name.startswith('.') or '/' in name or '\\' in name:
            continue
        full = os.path.join(notes_dir, name)
        # reject symlinks (or anything) resolving outside the vault; require a real file
        if not _inside(root_real, full) or not os.path.isfile(full):
            continue
        try:
            st = os.stat(full)
            if st.st_size > MAX_BYTES:
                continue
            with open(full, 'r', encoding='utf-8', errors='replace') as fh:
                text = fh.read(MAX_BYTES + 1)
        except OSError:
            continue
        fm, body = _split_frontmatter(text)
        stem = name[:-3]
        h1 = _H1_RE.search(body)
        title = (fm.get('title') if isinstance(fm.get('title'), str) and fm.get('title') else None) \
            or (h1.group(1) if h1 else None) or stem
        parsed.append({
            'stem': stem, 'title': title[:160], 'fm': fm, 'body': body,
            'rel': '/'.join(NOTES_SUBDIR + (name,)),
            'mtime': datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        })

    # unique ids
    used, stem_to_id, nodes = set(), {}, []
    for p in parsed:
        nid = 'note-' + _slug(p['stem'])
        base, i = nid, 2
        while nid in used:
            nid = '%s-%d' % (base, i); i += 1
        used.add(nid)
        p['id'] = nid
        stem_to_id[p['stem'].lower()] = nid
        status = p['fm'].get('status')
        nodes.append({
            'id': nid, 'type': 'note', 'label': p['title'],
            'data': {
                'path_rel': p['rel'], 'updated': p['mtime'],
                'status': status if isinstance(status, str) else None,
                'tags': _tags(p['fm']), 'excerpt': _excerpt(p['body']),
            },
        })

    edges, seen = [], set()
    for p in parsed:
        for m in _WIKI_RE.finditer(p['body']):
            target = stem_to_id.get(os.path.basename(m.group(1).strip()).lower())
            if target and target != p['id'] and (p['id'], target, 'wikilink') not in seen:
                seen.add((p['id'], target, 'wikilink'))
                edges.append({'source': p['id'], 'target': target, 'type': 'wikilink'})
        for tid in sorted(set(_TASK_RE.findall(p['body']))):
            edges.append({'source': p['id'], 'target': 'task-ref:' + tid, 'type': 'mentions'})

    return {'nodes': nodes, 'edges': edges, 'source': 'obsidian',
            'vault_name': os.path.basename(root_real)}


def _hindsight_enrich(payload):
    """Optional stub. No-op unless HINDSIGHT_URL is set; never calls the network here."""
    if not os.environ.get('HINDSIGHT_URL'):
        return payload
    return payload  # reserved for a future, explicitly-reviewed integration


@context_notes_bp.get('/notes')
@jwt_required()
def context_notes():
    if not _enabled():
        return jsonify({'error': 'Not found'}), 404
    user = User.query.filter_by(id=int(get_jwt_identity()), is_deleted=False).first()
    if not user or user.role != 'superadmin':
        return jsonify({'error': 'Unauthorized - superadmin access required'}), 403
    payload = build_notes_payload(os.environ.get('LEXFLOW_VAULT_DIR', '').strip())
    return jsonify(_hindsight_enrich(payload)), 200

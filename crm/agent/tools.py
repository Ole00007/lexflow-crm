from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional

from flask import current_app

import json

from .guard import MAX_TOOL_RESULT_BYTES, wrap_untrusted_data


@dataclass
class ToolResult:
    status_code: int
    body: Any

    def as_untrusted(self) -> Dict[str, Any]:
        return wrap_untrusted_data({'status_code': self.status_code, 'body': self.body})


class AgentTools:
    """Thin wrappers over LexFlow's own REST API."""

    def __init__(self, token: Optional[str]):
        self.token = token or ''

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {'Accept': 'application/json'}
        if self.token:
            headers['Authorization'] = self.token
        if extra:
            headers.update(extra)
        return headers

    def _call(self, method: str, path: str, *, json: Optional[Dict[str, Any]] = None,
              query: Optional[Dict[str, Any]] = None, extra_headers: Optional[Dict[str, str]] = None,
              raw: bool = False) -> Any:
        client = current_app.test_client()
        response = client.open(
            path,
            method=method,
            headers=self._headers(extra_headers),
            json=json,
            query_string=query,
        )
        payload = response.get_json(silent=True)
        if payload is None:
            payload = {'text': response.get_data(as_text=True)[:2048]}
        if raw:
            return payload
        return ToolResult(response.status_code, payload).as_untrusted()

    def _body(self, wrapped: Dict[str, Any]) -> Any:
        data = wrapped.get('untrusted_data', {}) if isinstance(wrapped, dict) else wrapped
        if isinstance(data, dict):
            return data.get('body')
        return data

    def list_matters(self, *, query: str = '', status: str = '', limit: int = 200) -> Dict[str, Any]:
        rows = self._call('GET', '/api/cases/', raw=True)
        rows = rows if isinstance(rows, list) else []
        q = (query or '').strip().lower()
        s = (status or '').strip().lower()
        if q or s:
            filtered = []
            for row in rows:
                text = ' '.join(str(row.get(k, '')) for k in ('title', 'display_id', 'casetype', 'status', 'contact_name'))
                if q and q not in text.lower():
                    continue
                if s and str(row.get('status', '')).strip().lower() != s:
                    continue
                filtered.append(row)
            rows = filtered
        keep = ('id', 'display_id', 'title', 'status', 'casetype', 'contact_name', 'ownerid', 'assignedto')
        rows = [{k: r.get(k) for k in keep if k in r} for r in rows]
        return wrap_untrusted_data(rows[: max(1, min(int(limit or 200), 40))])

    def get_gantt_tasks(self, *, query: str = '', limit: int = 200) -> Dict[str, Any]:
        rows = self._call('GET', '/api/gantt/tasks', raw=True)
        rows = rows if isinstance(rows, list) else []
        q = (query or '').strip().lower()
        if q:
            filtered = []
            for row in rows:
                hay = ' '.join(str(row.get(k, '')) for k in ('name', 'id', 'dependencies'))
                team = ' '.join(str(m.get('name', '')) for m in row.get('team', []))
                if q in hay.lower() or q in team.lower():
                    filtered.append(row)
            rows = filtered
        return wrap_untrusted_data(rows[: max(1, int(limit or 200))])

    def get_task_docs(self, *, task_id: int) -> Dict[str, Any]:
        return self._call('GET', f'/api/gantt/tasks/{int(task_id)}/docs')

    def get_open_flags(self, *, task_id: Optional[int] = None) -> Dict[str, Any]:
        rows = self._call('GET', '/api/gantt/tasks', raw=True)
        rows = rows if isinstance(rows, list) else []
        out = []
        for row in rows:
            if task_id is not None and int(row.get('id', -1)) != int(task_id):
                continue
            count = int(row.get('open_flags') or 0)
            if count:
                out.append({'task_id': row.get('id'), 'name': row.get('name'), 'open_flags': count})
        return wrap_untrusted_data({'count': sum(item['open_flags'] for item in out), 'items': out})

    def get_calendar(self, *, caseid: Optional[int] = None, event_type: str = '',
                     date_from: str = '', date_to: str = '', deadline_events: bool = True) -> Dict[str, Any]:
        from datetime import timedelta
        if not date_from and not date_to:
            date_from = date.today().isoformat()
            date_to = (date.today() + timedelta(days=30)).isoformat()
        query = {'deadline_events': 'true' if deadline_events else 'false'}
        if caseid is not None:
            query['caseid'] = int(caseid)
        if event_type:
            query['event_type'] = event_type
        if date_from:
            query['date_from'] = date_from
        if date_to:
            query['date_to'] = date_to
        rows = self._call('GET', '/api/calendar', query=query, raw=True)
        res = wrap_untrusted_data(rows)
        if isinstance(rows, list):
            keep = ('id', 'title', 'start_datetime', 'end_datetime', 'event_type', 'caseid', 'location')
            rows = [{k: r.get(k) for k in keep if k in r} for r in rows]
            rows.sort(key=lambda r: str(r.get('start_datetime') or ''))
            today = date.today().isoformat()
            upcoming = [r for r in rows if str(r.get('start_datetime') or '') >= today] or rows
            upcoming = [{**r, 'title': str(r.get('title'))[:80]} for r in upcoming]
            upcoming = [{k: v for k, v in r.items() if k not in ('end_datetime', 'location') or v} for r in upcoming]
            upcoming.sort(key=lambda r: (r.get('event_type') == 'task_due', str(r.get('start_datetime') or '')))
            upcoming = upcoming[:40]
            while upcoming and len(json.dumps(upcoming, default=str)) > MAX_TOOL_RESULT_BYTES - 200:
                upcoming = upcoming[:-1]
            return wrap_untrusted_data(upcoming)
        return res

    def next_actions(self, *, case_id: Optional[int] = None, matter_id: Optional[int] = None,
                     query: str = '') -> Dict[str, Any]:
        params = {}
        if case_id is not None:
            params['case_id'] = int(case_id)
        if matter_id is not None:
            params['matter_id'] = int(matter_id)
        if query:
            params['query'] = query
        response = self._call('GET', '/api/checklist/next-actions', query=params or None)
        body = response.get('untrusted_data', {})
        if isinstance(body, dict) and body.get('status_code') == 404:
            return wrap_untrusted_data({'feature_not_available': True, 'message': 'next-actions endpoint not available in this build'})
        return response

    def flag_lawyer(self, *, task_id: int, reason: str) -> Dict[str, Any]:
        return self._call(
            'POST',
            f'/api/gantt/tasks/{int(task_id)}/flag-lawyer',
            json={'reason': reason},
            extra_headers={'X-Agent-Name': 'lexflow-agent'},
        )

    def update_task_status(self, *, task_id: int, status: str) -> Dict[str, Any]:
        return self._call('PUT', f'/api/tasks/{int(task_id)}', json={'status': status})

    # ------------------------------------------------------------------ documents
    def _fetch_bytes(self, path: str):
        resp = current_app.test_client().open(path, method='GET', headers=self._headers())
        return resp.status_code, resp.data, (resp.mimetype or '')

    def _case_task_ids(self, caseid: int):
        rows = self._call('GET', '/api/tasks/', raw=True)
        rows = rows if isinstance(rows, list) else []
        return [r for r in rows if int(r.get('caseid') or -1) == int(caseid)][:25]

    def _doc_candidates(self, query: str = '', caseid: Optional[int] = None):
        """All documents the caller may see through LexFlow's own API: attachments + vault docs."""
        out = []
        q = (query or '').strip().lower()
        atts = []
        if caseid is not None:
            atts += self._call('GET', '/api/attachments/', query={'target_type': 'case', 'target_id': int(caseid)}, raw=True) or []
            tasks = self._case_task_ids(caseid)
            for t in tasks:
                atts += self._call('GET', '/api/attachments/', query={'target_type': 'task', 'target_id': int(t['id'])}, raw=True) or []
        else:
            atts = self._call('GET', '/api/attachments/', raw=True) or []
            tasks = [r for r in (self._call('GET', '/api/tasks/', raw=True) or []) if isinstance(r, dict)][:60]
        for a in atts if isinstance(atts, list) else []:
            out.append({'source': 'attachment', 'id': a.get('id'), 'name': a.get('filename'), 'mime': a.get('mime_type'),
                        'size': a.get('size_bytes'), 'target': f"{a.get('target_type')} #{a.get('target_id')}"})
        for t in tasks:  # vault docs: the API itself enforces superadmin-only (403 -> skipped)
            res = self._call('GET', f"/api/gantt/tasks/{int(t['id'])}/docs", raw=True)
            for d in (res.get('docs') if isinstance(res, dict) else None) or []:
                out.append({'source': 'vault', 'task_id': t['id'], 'name': d.get('name'), 'path_rel': d.get('path_rel'),
                            'size': d.get('size'), 'target': f"task #{t['id']}"})
        if q:
            out = [d for d in out if q in str(d.get('name', '')).lower()]
        return out

    def list_documents(self, *, query: str = '', caseid: Optional[int] = None) -> Dict[str, Any]:
        all_docs = self._doc_candidates(query, caseid)
        docs = [{**d, 'name': str(d.get('name'))[:70]} for d in all_docs[:30]]
        while docs and len(json.dumps({'count': len(all_docs), 'documents': docs}, default=str)) > MAX_TOOL_RESULT_BYTES - 200:
            docs = docs[:-1]
        return wrap_untrusted_data({'count': len(all_docs), 'shown': len(docs), 'documents': docs})

    def _load_document(self, doc):
        from .doctext import extract_text
        if doc['source'] == 'attachment':
            status, data, mime = self._fetch_bytes(f"/api/attachments/{int(doc['id'])}/download")
            if status != 200:
                return '', {}, f'could not download the document (HTTP {status})'
            return extract_text(doc['name'] or '', doc.get('mime') or mime, data)
        import os
        root = os.environ.get('LEXFLOW_VAULT_DIR', '').strip()
        if not root:
            return '', {}, 'vault not configured'
        root = os.path.realpath(root)
        real = os.path.realpath(os.path.join(root, doc['path_rel']))
        if not (real.startswith(root + os.sep) and os.path.isfile(real)):
            return '', {}, 'document path is outside the vault'
        with open(real, 'rb') as fh:
            data = fh.read(8 * 1024 * 1024 + 1)
        return extract_text(doc['name'] or '', '', data)

    def _pick_document(self, query: str, caseid: Optional[int]):
        cands = self._doc_candidates(query, caseid)
        if not cands:
            return None, {'found': False, 'message': f"No document matching '{query}'."}
        exact = [d for d in cands if str(d.get('name', '')).lower() == query.strip().lower()]
        pick = exact or cands
        if len(pick) > 1:
            return None, {'found': True, 'ambiguous': True, 'candidates': [d['name'] for d in pick[:8]]}
        return pick[0], None

    def read_document(self, *, query: str, caseid: Optional[int] = None, max_chars: int = 2500) -> Dict[str, Any]:
        doc, problem = self._pick_document(query, caseid)
        if problem:
            return wrap_untrusted_data(problem)
        text, meta, note = self._load_document(doc)
        return wrap_untrusted_data({'found': True, 'name': doc['name'], 'source': doc['source'], 'note': note,
                                    'chars': len(text), 'excerpt': text[: int(max_chars)]})

    def summarize_document(self, *, query: str, caseid: Optional[int] = None) -> Dict[str, Any]:
        from .doctext import summarize_text
        doc, problem = self._pick_document(query, caseid)
        if problem:
            return wrap_untrusted_data(problem)
        text, meta, note = self._load_document(doc)
        if not text:
            return wrap_untrusted_data({'found': True, 'name': doc['name'], 'source': doc['source'], 'note': note or 'empty document'})
        out = {'found': True, 'name': doc['name'], 'source': doc['source'], 'pages': meta.get('pages'), 'summary': summarize_text(text)}
        from . import llm
        if llm.enabled():  # opt-in, provider-agnostic; extractive summary above is always kept (both ways)
            try:
                out['ai_summary'] = llm.summarize(text)
            except llm.LLMError as e:
                out['ai_note'] = 'Model summary unavailable (' + str(e)[:60] + '); showing the extractive summary only.'
        return wrap_untrusted_data(out)

    def draft_document(self, *, kind: str, caseid: int, language: str = 'en', note: str = '') -> Dict[str, Any]:
        from .drafts import build_draft
        cases = self._call('GET', '/api/cases/', raw=True)
        matter = next((c for c in (cases if isinstance(cases, list) else []) if int(c.get('id') or -1) == int(caseid)), None)
        if not matter:
            return wrap_untrusted_data({'found': False, 'message': f'Matter #{caseid} not found.'})
        tasks = self._case_task_ids(caseid)
        events = self._call('GET', '/api/calendar', query={'caseid': int(caseid), 'deadline_events': 'false'}, raw=True)
        events = [e for e in (events if isinstance(events, list) else []) if str(e.get('start_datetime') or '') >= date.today().isoformat()]
        events.sort(key=lambda e: str(e.get('start_datetime') or ''))
        d = build_draft(kind, language, matter, tasks, events, note)
        text, ai = d['text'], False
        from . import llm
        if llm.enabled():  # model polishes the template; any failure keeps the template draft
            try:
                facts = {'matter': matter.get('title'), 'ref': matter.get('display_id') or matter.get('case_no'),
                         'status': matter.get('status'), 'client': (matter.get('contact_name') or '').replace('(client)', '').strip(),
                         'upcoming_dates': [str(e.get('start_datetime'))[:16] + ' ' + str(e.get('title') or '') for e in events[:5]]}
                polished = llm.polish_draft(kind, language, d['text'], facts, note)
                first = d['text'].splitlines()[0] if d['text'].lstrip().upper().startswith('DRAFT') else ''
                text = polished if (not first or polished.lstrip().upper().startswith('DRAFT')) else first + '\n\n' + polished
                ai = True
            except llm.LLMError:
                pass
        return wrap_untrusted_data({'found': True, 'subject': d['subject'], 'draft': text[:3300], 'ai': ai})

    def list_tasks(self, *, query: str = '', status: str = '', limit: int = 50) -> Dict[str, Any]:
        rows = self._call('GET', '/api/tasks/', raw=True)
        rows = rows if isinstance(rows, list) else []
        q, st = (query or '').strip().lower(), (status or '').strip().lower()
        out = []
        for row in rows:
            if q and q not in ' '.join(str(row.get(k, '')) for k in ('title', 'description', 'caseid')).lower():
                continue
            if st and str(row.get('status', '')).strip().lower() != st:
                continue
            out.append(row)
        keep = ('id', 'title', 'status', 'priority', 'duedate', 'caseid')
        out = [{k: r.get(k) for k in keep if k in r} for r in out]
        return wrap_untrusted_data(out[: max(1, min(int(limit or 50), 40))])

    def create_task(self, **args: Any) -> Dict[str, Any]:
        return self._call('POST', '/api/tasks/', json=args, extra_headers={'X-Agent-Name': 'lexflow-agent'})

    def create_calendar_event(self, **args: Any) -> Dict[str, Any]:
        return self._call('POST', '/api/calendar', json=args, extra_headers={'X-Agent-Name': 'lexflow-agent'})

    def draft_notification(self, *, subject: str, body: str, recipient: Optional[str] = None,
                           token: Optional[str] = None) -> Dict[str, Any]:
        draft = {
            'subject': subject,
            'body': body,
            'recipient': recipient,
            'preview': f'Oggetto: {subject}\n\n{body}' if subject or body else '',
        }
        if recipient:
            draft['recipient'] = recipient
        if token:
            draft['token'] = token
        return wrap_untrusted_data(draft)

    def call(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if tool == 'list_matters':
            return self.list_matters(**args)
        if tool == 'get_gantt_tasks':
            return self.get_gantt_tasks(**args)
        if tool == 'get_task_docs':
            return self.get_task_docs(**args)
        if tool == 'get_open_flags':
            return self.get_open_flags(**args)
        if tool == 'get_calendar':
            return self.get_calendar(**args)
        if tool == 'next_actions':
            return self.next_actions(**args)
        if tool == 'flag_lawyer':
            return self.flag_lawyer(**args)
        if tool == 'update_task_status':
            return self.update_task_status(**args)
        if tool == 'list_tasks':
            return self.list_tasks(**args)
        if tool in ('list_documents', 'read_document', 'summarize_document', 'draft_document'):
            return getattr(self, tool)(**args)
        if tool == 'create_task':
            return self.create_task(**args)
        if tool == 'create_calendar_event':
            return self.create_calendar_event(**args)
        if tool == 'draft_notification':
            return self.draft_notification(**args)
        raise ValueError(f'Unknown tool: {tool}')

    def execute(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return self.call(tool, args)

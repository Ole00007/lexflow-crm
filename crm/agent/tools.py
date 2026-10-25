from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional

from flask import current_app

from .guard import wrap_untrusted_data


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
            return wrap_untrusted_data(upcoming[:40])
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
        if tool == 'create_task':
            return self.create_task(**args)
        if tool == 'create_calendar_event':
            return self.create_calendar_event(**args)
        if tool == 'draft_notification':
            return self.draft_notification(**args)
        raise ValueError(f'Unknown tool: {tool}')

    def execute(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return self.call(tool, args)

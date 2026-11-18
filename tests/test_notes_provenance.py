"""Mindmap note provenance: server-assigned source, traceability filters, tenant isolation.

`notes` is the human record. A client can never write source='agent' through the
REST route; agent provenance only appears via draft promotion (DB-level path).
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'tests'))

from crm.extensions import db  # noqa: E402
from crm.models.note import Note  # noqa: E402
from test_agent import build_state  # noqa: E402


def _post_note(state, who='super', **overrides):
    payload = {'target_type': 'task', 'target_id': state['task_id'], 'content': 'Mindmap note'}
    payload.update(overrides)
    return state['client'].post('/api/notes/', headers=state['headers'][who], json=payload)


def test_note_is_human_by_default_and_reports_author():
    st = build_state()
    r = _post_note(st)
    assert r.status_code == 201, r.get_json()
    d = r.get_json()
    assert d['source'] == 'human'
    assert d['source_ref'] is None
    assert d['author_id'] and d['author_email']


def test_client_cannot_forge_agent_provenance():
    st = build_state()
    r = _post_note(st, source='agent', source_ref='draft-7')
    assert r.status_code == 201, r.get_json()
    d = r.get_json()
    assert d['source'] == 'human'
    assert d['source_ref'] is None


def test_promoted_agent_note_is_filterable():
    st = build_state()
    assert _post_note(st, content='human wrote this').status_code == 201
    with st['app'].app_context():
        db.session.add(Note(
            workspace_id=1,
            author_id=1,
            target_type='task',
            target_id=st['task_id'],
            content='promoted from agent draft',
            source='agent',
            source_ref='draft-42',
        ))
        db.session.commit()

    h = st['headers']['super']
    human = st['client'].get('/api/notes/?source=human', headers=h).get_json()
    agent = st['client'].get('/api/notes/?source=agent', headers=h).get_json()
    assert [n['content'] for n in human] == ['human wrote this']
    assert [(n['content'], n['source_ref']) for n in agent] == [('promoted from agent draft', 'draft-42')]


def test_invalid_source_and_date_are_rejected():
    st = build_state()
    h = st['headers']['super']
    assert st['client'].get('/api/notes/?source=robot', headers=h).status_code == 400
    assert st['client'].get('/api/notes/?date_from=18-11-2026', headers=h).status_code == 400


def test_date_and_text_filters():
    st = build_state()
    h = st['headers']['super']
    assert _post_note(st, content='alpha deadline').status_code == 201
    assert _post_note(st, content='beta invoice').status_code == 201

    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    hit = st['client'].get(f'/api/notes/?date_from={today}&date_to={tomorrow}', headers=h).get_json()
    assert {n['content'] for n in hit} == {'alpha deadline', 'beta invoice'}
    assert st['client'].get(f'/api/notes/?date_to={yesterday}', headers=h).get_json() == []
    assert [n['content'] for n in st['client'].get('/api/notes/?q=invoice', headers=h).get_json()] == ['beta invoice']


def test_workspace_target_is_allowed():
    st = build_state()
    h = st['headers']['super']
    r = st['client'].post('/api/notes/', headers=h, json={
        'target_type': 'workspace', 'target_id': 1, 'content': 'project-level note',
    })
    assert r.status_code == 201, r.get_json()
    assert r.get_json()['target_type'] == 'workspace'


def test_notes_do_not_leak_across_tenants():
    st = build_state()
    assert _post_note(st, content='tenant A only').status_code == 201
    foreign = st['client'].get('/api/notes/', headers=st['headers']['foreign']).get_json()
    assert all(n['content'] != 'tenant A only' for n in foreign)

"""Agent draft sandbox: caps, kill switch, expiry, atomic accept, tenancy, promotion shape."""
from __future__ import annotations

import os
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'tests'))

import pytest  # noqa: E402

from crm.extensions import db  # noqa: E402
from crm.models.activity import ActivityLog  # noqa: E402
from crm.models.agent_draft import AgentDraft  # noqa: E402
from crm.models.note import Note  # noqa: E402
from crm.models.user import User  # noqa: E402
from test_agent import build_state  # noqa: E402

AGENT = {'X-Agent-Name': 'elisa'}


@pytest.fixture(autouse=True)
def _restore_env():
    # build_state() repoints DATABASE_URL / Config at a temp DB; undo it so later modules are unaffected.
    from crm.config import Config
    snap = dict(os.environ)
    uri = Config.SQLALCHEMY_DATABASE_URI
    yield
    Config.SQLALCHEMY_DATABASE_URI = uri
    os.environ.clear()
    os.environ.update(snap)


def _uid(st, email):
    with st['app'].app_context():
        return User.query.filter_by(email=email).first().id


def _mk(st, **kw):
    with st['app'].app_context():
        sup = User.query.filter_by(email='olesya00007@yahoo.com').first()
        now = datetime.utcnow()
        d = AgentDraft(workspace_id=kw.pop('workspace_id', sup.workspace_id), target_type='task',
                       target_id=st['task_id'], content='Proposed text', origin='human_request',
                       requested_by=kw.pop('requested_by', sup.id), requested_by_agent='elisa',
                       evidence='because', status='proposed', expires_at=now + timedelta(days=7),
                       created_at=now, updated_at=now, **kw)
        db.session.add(d)
        db.session.commit()
        return d.id


def _h(st, who, extra=None):
    h = dict(st['headers'][who])
    h.update(extra or {})
    return h


def _delegate(st, scope='*'):
    r = st['client'].post('/api/agent/delegations', headers=_h(st, 'super'),
                          json={'to_agent': 'elisa', 'scope': scope, 'ttl_hours': 2})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _post_draft(st, who='super', **over):
    body = {'target_type': 'task', 'target_id': st['task_id'], 'content': 'idea',
            'origin': 'human_request', 'evidence': 'e'}
    body.update(over)
    return st['client'].post('/api/agent/drafts', headers=_h(st, who, AGENT), json=body)


def test_accept_promotes_note_with_provenance_and_audit():
    st = build_state()
    did = _mk(st)
    r = st['client'].post(f'/api/agent/drafts/{did}/accept', headers=_h(st, 'super'))
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['draft']['status'] == 'accepted' and body['draft']['note_id'] == body['note']['id']
    assert body['note']['source'] == 'agent' and body['note']['source_ref'] == str(did)
    sup_id = _uid(st, 'olesya00007@yahoo.com')
    assert body['note']['author_id'] == sup_id
    with st['app'].app_context():
        n = db.session.get(Note, body['note']['id'])
        assert (n.source, n.source_ref, n.author_id, n.content) == ('agent', str(did), sup_id, 'Proposed text')
        log = ActivityLog.query.filter_by(action='agent_draft_promoted').one()
        assert log.actor_id == sup_id
    # filterable via the notes API
    agent_notes = st['client'].get('/api/notes/?source=agent', headers=_h(st, 'super')).get_json()
    assert [x['source_ref'] for x in agent_notes] == [str(did)]


def test_double_accept_is_409_and_creates_one_note():
    st = build_state()
    did = _mk(st)
    assert st['client'].post(f'/api/agent/drafts/{did}/accept', headers=_h(st, 'super')).status_code == 200
    assert st['client'].post(f'/api/agent/drafts/{did}/accept', headers=_h(st, 'super')).status_code == 409
    assert st['client'].post(f'/api/agent/drafts/{did}/reject', headers=_h(st, 'super')).status_code == 409
    with st['app'].app_context():
        assert Note.query.filter_by(source='agent', source_ref=str(did)).count() == 1


def test_concurrent_accept_single_winner():
    st = build_state()
    did = _mk(st)
    codes = []

    def go():
        codes.append(st['app'].test_client().post(
            f'/api/agent/drafts/{did}/accept', headers=_h(st, 'super')).status_code)
    ts = [threading.Thread(target=go) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert codes.count(200) == 1, codes
    with st['app'].app_context():
        assert Note.query.filter_by(source='agent', source_ref=str(did)).count() == 1


def test_expired_draft_is_410_and_row_kept():
    st = build_state()
    did = _mk(st)
    with st['app'].app_context():
        d = db.session.get(AgentDraft, did)
        d.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
    assert st['client'].post(f'/api/agent/drafts/{did}/accept', headers=_h(st, 'super')).status_code == 410
    assert st['client'].post(f'/api/agent/drafts/{did}/reject', headers=_h(st, 'super')).status_code == 410
    with st['app'].app_context():
        d = db.session.get(AgentDraft, did)
        assert d is not None and d.status == 'expired'
        assert Note.query.filter_by(source='agent').count() == 0


def test_reject_and_missing_and_listing():
    st = build_state()
    did = _mk(st)
    r = st['client'].post(f'/api/agent/drafts/{did}/reject', headers=_h(st, 'super'))
    assert r.status_code == 200 and r.get_json()['draft']['status'] == 'rejected'
    assert st['client'].post('/api/agent/drafts/99999/accept', headers=_h(st, 'super')).status_code == 404
    assert st['client'].get('/api/agent/drafts?status=proposed', headers=_h(st, 'super')).get_json() == []
    assert st['client'].get('/api/agent/drafts?status=bogus', headers=_h(st, 'super')).status_code == 400


def test_cross_tenant_and_wrong_user_403():
    st = build_state()
    did = _mk(st)
    r = st['client'].post(f'/api/agent/drafts/{did}/accept', headers=_h(st, 'foreign'))
    assert r.status_code == 403
    assert st['client'].post(f'/api/agent/drafts/{did}/reject', headers=_h(st, 'foreign')).status_code == 403
    # foreign tenant cannot even list it
    assert st['client'].get('/api/agent/drafts', headers=_h(st, 'foreign')).get_json() == []
    # same workspace but not the requester -> 403
    with st['app'].app_context():
        rom = User.query.filter_by(email='olesya00007@google.com').first()
        sub = User.query.filter_by(email='cl1@romanelli.test').first()
        rom_id, ws = rom.id, sub.workspace_id  # draft in sub's workspace, requested by another user
    did2 = _mk(st, workspace_id=ws, requested_by=rom_id)
    assert st['client'].post(f'/api/agent/drafts/{did2}/accept', headers=_h(st, 'sub')).status_code == 403
    with st['app'].app_context():
        assert db.session.get(AgentDraft, did2).status == 'proposed'
        assert Note.query.filter_by(source='agent').count() == 0


def test_internal_post_requires_agent_identity_and_rejects_browser():
    st = build_state()
    _delegate(st)
    body = {'target_type': 'task', 'target_id': st['task_id'], 'content': 'x', 'origin': 'human_request'}
    c = st['client']
    assert c.post('/api/agent/drafts', headers=_h(st, 'super'), json=body).status_code == 403
    assert c.post('/api/agent/drafts', headers=_h(st, 'super', {**AGENT, 'Origin': 'http://localhost:3000'}),
                  json=body).status_code == 403
    assert c.post('/api/agent/drafts', headers=_h(st, 'super', {**AGENT, 'Sec-Fetch-Mode': 'cors'}),
                  json=body).status_code == 403
    assert c.post('/api/agent/drafts', headers={**AGENT}, json=body).status_code in (401, 422)
    r = _post_draft(st)
    assert r.status_code == 201, r.get_json()
    d = r.get_json()
    assert d['status'] == 'proposed' and d['requested_by_agent'] == 'elisa' and d['origin'] == 'human_request'
    with st['app'].app_context():
        assert Note.query.filter_by(source='agent').count() == 0  # agents never write notes


def test_no_delegation_or_policy_is_403():
    st = build_state()
    assert _post_draft(st).status_code == 403
    assert _post_draft(st, origin='event_rule', event_key='task_overdue').status_code == 403


def test_delegation_scope_expiry_and_revoke():
    st = build_state()
    d = _delegate(st, scope={'target_types': ['case']})
    assert _post_draft(st).status_code == 403  # task not in scope
    st['client'].delete(f"/api/agent/delegations/{d['id']}", headers=_h(st, 'super'))
    d2 = _delegate(st)
    assert _post_draft(st).status_code == 201
    r = st['client'].delete(f"/api/agent/delegations/{d2['id']}", headers=_h(st, 'super'))
    assert r.status_code == 200 and r.get_json()['revoked_at']
    assert _post_draft(st).status_code == 403
    assert st['client'].delete(f"/api/agent/delegations/{d2['id']}", headers=_h(st, 'foreign')).status_code == 403
    # expiry
    d3 = _delegate(st)
    with st['app'].app_context():
        from crm.models.agent_delegation import AgentDelegation
        row = db.session.get(AgentDelegation, d3['id'])
        row.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
    assert _post_draft(st).status_code == 403


def test_daily_cap_enforced_default_and_policy():
    st = build_state()
    _delegate(st)
    assert [_post_draft(st).status_code for _ in range(3)] == [201, 201, 201]
    assert _post_draft(st).status_code == 429  # default max_per_day=3
    # policy-configured cap on another target scope
    st2 = build_state()
    _delegate(st2)
    p = st2['client'].put('/api/agent/policies/custom', headers=_h(st2, 'super'),
                          json={'enabled': True, 'max_per_day': 1})
    assert p.status_code == 200 and p.get_json()['require_review'] is True
    assert _post_draft(st2).status_code == 201
    assert _post_draft(st2).status_code == 429


def test_policies_superadmin_only_and_require_review_immutable():
    st = build_state()
    c = st['client']
    assert c.put('/api/agent/policies/task_overdue', headers=_h(st, 'romanelli'),
                 json={'enabled': True}).status_code == 403
    r = c.put('/api/agent/policies/task_overdue', headers=_h(st, 'super'),
              json={'enabled': True, 'max_per_day': 2, 'require_review': False})
    assert r.status_code == 200 and r.get_json()['require_review'] is True
    assert c.put('/api/agent/policies/nope', headers=_h(st, 'super'), json={}).status_code == 400
    assert c.put('/api/agent/policies/task_overdue', headers=_h(st, 'super'),
                 json={'max_per_day': 0}).status_code == 400
    assert [p['event_key'] for p in c.get('/api/agent/policies', headers=_h(st, 'super')).get_json()] == ['task_overdue']
    assert c.get('/api/agent/policies', headers=_h(st, 'foreign')).get_json() == []


def test_kill_switch_stops_event_rule_generation_immediately():
    st = build_state()
    c = st['client']
    c.put('/api/agent/policies/task_overdue', headers=_h(st, 'super'), json={'enabled': True})
    assert _post_draft(st, origin='event_rule', event_key='task_overdue').status_code == 201
    assert c.post('/api/agent/policies/kill-switch', headers=_h(st, 'romanelli'),
                  json={'enabled': False}).status_code == 403
    r = c.post('/api/agent/policies/kill-switch', headers=_h(st, 'super'), json={'enabled': False})
    assert r.status_code == 200 and r.get_json()['kill_switch'] is True
    assert _post_draft(st, origin='event_rule', event_key='task_overdue').status_code == 403
    # release restores generation
    c.post('/api/agent/policies/kill-switch', headers=_h(st, 'super'), json={'enabled': True})
    assert _post_draft(st, origin='event_rule', event_key='task_overdue').status_code == 201
    assert c.post('/api/agent/policies/kill-switch', headers=_h(st, 'super'), json={}).status_code == 400


def test_mindmap_page_route_degrades_gracefully():
    st = build_state()
    r = st['client'].get('/mindmap')
    assert r.status_code == 200 and b'Mindmap' in r.data

"""Approval hardening for Elisa writes: bound to exact content, expiry, single-use under concurrency, tenant isolation."""
from __future__ import annotations

import os
import sys
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'tests'))

import pytest  # noqa: E402

from test_agent import build_state, _restore_env  # noqa: E402,F401
from crm.extensions import db  # noqa: E402
from crm.models.agent_audit import AgentPendingAction  # noqa: E402
from crm.models.task import Task  # noqa: E402

MSG = f'Create task Hardening probe for matter Rasing separazione due {(date.today() + timedelta(days=2)).isoformat()}'


def _propose(state, who='super', msg=MSG):
    os.environ['AGENT_ENABLED'] = '1'
    r = state['client'].post('/api/agent/chat', headers=state['headers'][who], json={'message': msg})
    d = r.get_json()
    assert r.status_code == 200 and d['pending_action'], d
    return d['pending_action']['id']


def _count(state, title='Hardening probe'):
    with state['app'].app_context():
        return Task.query.filter_by(title=title).count()


def test_proposal_carries_hash_and_expiry():
    st = build_state()
    aid = _propose(st)
    with st['app'].app_context():
        a = db.session.get(AgentPendingAction, aid)
        assert a.payload_hash and len(a.payload_hash) == 64
        assert a.expires_at and a.expires_at > datetime.utcnow()


def test_tampered_payload_is_refused_and_nothing_written():
    st = build_state()
    aid = _propose(st)
    with st['app'].app_context():
        a = db.session.get(AgentPendingAction, aid)
        a.args_json = a.args_json.replace('Hardening probe', 'Evil swapped title')
        db.session.commit()
    r = st['client'].post(f'/api/agent/chat/actions/{aid}/approve', headers=st['headers']['super'])
    assert r.status_code == 403, r.get_json()
    assert _count(st) == 0 and _count(st, 'Evil swapped title') == 0
    with st['app'].app_context():
        assert db.session.get(AgentPendingAction, aid).status == 'failed'


def test_expired_proposal_is_refused_with_410():
    st = build_state()
    aid = _propose(st)
    with st['app'].app_context():
        a = db.session.get(AgentPendingAction, aid)
        a.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
    r = st['client'].post(f'/api/agent/chat/actions/{aid}/approve', headers=st['headers']['super'])
    assert r.status_code == 410, r.get_json()
    assert _count(st) == 0
    # an expired proposal cannot be revived by a second try
    assert st['client'].post(f'/api/agent/chat/actions/{aid}/approve', headers=st['headers']['super']).status_code == 409


def test_ttl_is_configurable(monkeypatch):
    monkeypatch.setenv('LEXFLOW_AGENT_APPROVAL_TTL_MIN', '1')
    st = build_state()
    aid = _propose(st)
    with st['app'].app_context():
        a = db.session.get(AgentPendingAction, aid)
        assert a.expires_at - datetime.utcnow() < timedelta(minutes=2)


def test_double_approve_executes_exactly_once():
    st = build_state()
    aid = _propose(st)
    codes = []
    def go():
        c = st['app'].test_client()
        codes.append(c.post(f'/api/agent/chat/actions/{aid}/approve', headers=st['headers']['super']).status_code)
    ts = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert _count(st) == 1, codes          # the write happened once, whatever the race looked like
    assert 200 in codes


def test_other_tenant_cannot_approve_or_reject():
    st = build_state()
    aid = _propose(st, 'super')
    for who in ('foreign', 'sub', 'romanelli'):
        for verb in ('approve', 'reject'):
            r = st['client'].post(f'/api/agent/chat/actions/{aid}/{verb}', headers=st['headers'][who])
            assert r.status_code in (403, 404), (who, verb, r.status_code, r.get_json())
    assert _count(st) == 0
    with st['app'].app_context():
        assert db.session.get(AgentPendingAction, aid).status == 'pending'


def test_pending_list_does_not_leak_across_tenants():
    st = build_state()
    _propose(st, 'super')
    r = st['client'].get('/api/agent/runs', headers=st['headers']['foreign'])
    assert r.status_code in (403, 404), r.status_code


def test_superadmin_may_reject_but_not_approve_someone_elses_action():
    import uuid
    from crm.agent.runner import payload_hash, approval_ttl
    from crm.agent.guard import serialize_args
    from crm.models.agent_audit import AgentRun
    from crm.models.user import User
    st = build_state()
    os.environ['AGENT_ENABLED'] = '1'
    with st['app'].app_context():
        owner = User.query.filter_by(email='olesya00007@google.com').first()
        rid = str(uuid.uuid4())
        args_json = serialize_args({'title': 'Hardening probe two', 'duedate': '2026-11-03'})
        db.session.add(AgentRun(workspace_id=owner.workspace_id, user_id=owner.id, run_id=rid,
                                goal='probe', status='pending_approval'))
        a = AgentPendingAction(workspace_id=owner.workspace_id, user_id=owner.id, run_id=rid, tool='create_task',
                               args_json=args_json, status='pending',
                               payload_hash=payload_hash(rid, owner.id, owner.workspace_id, 'create_task', args_json),
                               expires_at=datetime.utcnow() + approval_ttl())
        db.session.add(a); db.session.commit(); aid = a.id
    r = st['client'].post(f'/api/agent/chat/actions/{aid}/approve', headers=st['headers']['super'])
    assert r.status_code == 403, r.get_json()
    assert _count(st, 'Hardening probe two') == 0
    assert st['client'].post(f'/api/agent/chat/actions/{aid}/reject', headers=st['headers']['super']).status_code == 200

"""T-009: enqueue -> poll -> handler fires once -> suppression honoured."""
from datetime import datetime, timedelta

from crm.extensions import db
from crm.models import Contact, ScheduledAction, Workspace
from crm.services import scheduled_actions as sa


def _contact(app, email="drip@example.com", consent=True):
    ws = Workspace.query.filter_by(slug="t009-test").first()
    if ws is None:
        ws = Workspace(name="T009 test", slug="t009-test")
        db.session.add(ws)
        db.session.commit()
    c = Contact(workspace_id=ws.id, fullname="Drip Test", email=email, gdpr_consent=consent)
    db.session.add(c)
    db.session.commit()
    return c


def test_enqueue_poll_fires_once_and_not_before_due(app):
    calls = []
    sa.register_handler("t009_fire")(lambda a, c: calls.append(a.id))
    with app.app_context():
        c = _contact(app, "once@example.com")
        now = datetime.utcnow()
        row = sa.enqueue(c.workspace_id, "t009_fire", now + timedelta(hours=24),
                         contact_id=c.id, channel="email", notif_type="marketing")
        assert sa.poll_once(now)["fired"] == 0 and calls == []          # not due yet
        assert sa.poll_once(now + timedelta(hours=25))["fired"] == 1
        assert sa.poll_once(now + timedelta(hours=26))["fired"] == 0    # never twice
        assert calls == [row.id]
        assert db.session.get(ScheduledAction, row.id).state == "done"


def test_suppression_key_and_gate_honoured(app):
    calls = []
    sa.register_handler("t009_sup")(lambda a, c: calls.append(a.id))
    with app.app_context():
        c = _contact(app, "sup@example.com")
        now = datetime.utcnow()
        rows = sa.enqueue_drip(c, start=now)
        assert [r.kind for r in rows] == ["followup_24h", "followup_72h", "final_checkin_7d"]
        assert sa.cancel_by_key(f"contact:{c.id}:drip") == 3            # contact replied
        for r in rows:
            sa.register_handler(r.kind)(lambda a, ct: calls.append(a.id))
        assert sa.poll_once(now + timedelta(days=8)) == {"fired": 0, "suppressed": 0, "failed": 0, "retry": 0}
        # should_notify gate: marketing without GDPR consent is suppressed at fire time
        nc = _contact(app, "noconsent@example.com", consent=False)
        r = sa.enqueue(nc.workspace_id, "t009_sup", now, contact_id=nc.id,
                       channel="email", notif_type="marketing")
        assert sa.poll_once(now + timedelta(seconds=1))["suppressed"] == 1
        assert db.session.get(ScheduledAction, r.id).state == "suppressed"
        assert calls == []


def test_failing_handler_retries_then_fails(app):
    def boom(a, c):
        raise RuntimeError("x")
    sa.register_handler("t009_boom")(boom)
    with app.app_context():
        c = _contact(app, "boom@example.com")
        now = datetime.utcnow()
        r = sa.enqueue(c.workspace_id, "t009_boom", now, contact_id=c.id, max_attempts=2)
        assert sa.poll_once(now)["retry"] == 1
        assert sa.poll_once(now + timedelta(hours=1))["failed"] == 1
        assert db.session.get(ScheduledAction, r.id).state == "failed"


def test_registered_in_models_graph_and_migration_head():
    import re, glob
    from crm import models
    assert models.ScheduledAction.__tablename__ == "scheduled_actions"
    src = open(glob.glob("migrations/versions/l3a4b5c6d7e8_*.py")[0]).read()
    assert "down_revision = 'k2f3a4b5c6d7'" in src and "create_table(\n        'scheduled_actions'" in src

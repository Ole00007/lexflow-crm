"""Regression: the roadmap seeder must not fabricate dates for dateless nodes."""
import datetime
import pytest
import seed_gantt_data as sg
from crm.extensions import db
from crm.models.task import Task
from crm.models.case import Case

FIXTURE = [
    {"id": "T-9901", "title": "Dated node", "column": "done", "priority": "P2",
     "start_date": "2026-10-01", "due_date": "2026-10-09"},
    {"id": "T-9902", "title": "Dateless node", "column": "backlog", "priority": "P3"},
]


@pytest.fixture(autouse=True, scope="module")
def _cleanup(app):
    """The test DB is session-shared: remove the seeded rows so other tests see an empty gantt."""
    yield
    with app.app_context():
        for c in Case.query.filter(Case.case_no.in_(["ROAD-T-9901", "ROAD-T-9902"])).all():
            Task.query.filter_by(caseid=c.id).delete()
            db.session.delete(c)
        db.session.commit()


def _row(app, tid):
    with app.app_context():
        c = Case.query.filter_by(case_no=f"ROAD-{tid}").first()
        t = Task.query.filter_by(caseid=c.id, is_deleted=False).first()
        return t.startdate, t.duedate, Task.query.filter_by(caseid=c.id).count()


def test_dateless_node_stays_null_and_not_in_gantt(app, client, superadmin_headers):
    sg.main(roadmap_tasks=FIXTURE)
    assert _row(app, "T-9901")[:2] == (datetime.date(2026, 10, 1), datetime.date(2026, 10, 9))
    assert _row(app, "T-9902")[:2] == (None, None)

    r = client.get("/api/gantt/tasks", headers=superadmin_headers)
    assert r.status_code == 200
    names = {t["name"]: t for t in r.get_json()}
    assert "[T-9902] Dateless node" not in names  # excluded, no fake bar
    d = names["[T-9901] Dated node"]
    assert (d["start"], d["end"]) == ("2026-10-01", "2026-10-09")
    for t in r.get_json():
        assert t["start"] and t["end"]  # no null/empty dates reach Frappe


def test_reseed_idempotent_and_clears_fabricated_dates(app):
    with app.app_context():  # simulate an old fabricated seed
        c = Case.query.filter_by(case_no="ROAD-T-9902").first()
        t = Task.query.filter_by(caseid=c.id).first()
        t.startdate, t.duedate = datetime.date(2026, 12, 1), datetime.date(2026, 12, 22)
        db.session.commit()
    sg.main(roadmap_tasks=FIXTURE)
    sg.main(roadmap_tasks=FIXTURE)
    assert _row(app, "T-9902") == (None, None, 1)
    assert _row(app, "T-9901")[2] == 1

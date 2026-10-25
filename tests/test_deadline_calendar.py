"""Deadline/Calendar tests - pytest."""
import os


def test_cal_off(client, superadmin_headers):
    """Without flag, OK."""
    os.environ["CALENDAR_DEADLINES_ENABLED"] = "false"
    r = client.get("/api/calendar", headers=superadmin_headers)
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


def test_cal_on_task(client, superadmin_headers):
    """Task duedate appears with flag."""
    os.environ["CALENDAR_DEADLINES_ENABLED"] = "true"
    r = client.post("/api/contacts", json={
        "full_name": "DD", "email": "dd@x.it", "status": "lead",
    }, headers=superadmin_headers)
    assert r.status_code in (200, 201)
    cid = r.get_json()["id"]
    r = client.post("/api/cases", json={
        "title": "DD", "contactid": cid, "status": "Active",
    }, headers=superadmin_headers)
    assert r.status_code in (200, 201)
    cc = r.get_json()["id"]
    r = client.post("/api/tasks/", json={
        "title": "Due", "caseid": cc,
        "status": "in_progress", "priority": "Medium",
        "duedate": "2026-10-30",
    }, headers=superadmin_headers)
    assert r.status_code in (200, 201)
    r = client.get("/api/calendar?deadline_events=true", headers=superadmin_headers)
    assert r.status_code == 200
    evs = r.get_json()
    te = [e for e in evs if e.get("kind") == "task_due"]
    assert len(te) >= 1


def test_cal_on_deadline(client, superadmin_headers):
    """Deadline row appears with flag."""
    os.environ["CALENDAR_DEADLINES_ENABLED"] = "true"
    r = client.post("/api/contacts", json={
        "full_name": "DD2", "email": "dd2@x.it", "status": "lead",
    }, headers=superadmin_headers)
    assert r.status_code in (200, 201)
    cid = r.get_json()["id"]
    r = client.post("/api/cases", json={
        "title": "DD2", "contactid": cid, "status": "Active",
    }, headers=superadmin_headers)
    assert r.status_code in (200, 201)
    cc = r.get_json()["id"]
    r = client.post("/api/deadlines/", json={
        "caseid": cc, "title": "Udienza",
        "deadline_type": "udienza", "deadline_date": "2026-11-15",
        "status": "pending", "priority": "High",
    }, headers=superadmin_headers)
    assert r.status_code in (200, 201)
    r = client.get("/api/calendar?deadline_events=true", headers=superadmin_headers)
    assert r.status_code == 200
    evs = r.get_json()
    dv = [e for e in evs if e.get("kind") == "deadline"]
    assert len(dv) >= 1


def test_done_excluded(client, superadmin_headers):
    """Done tasks do not appear."""
    os.environ["CALENDAR_DEADLINES_ENABLED"] = "true"
    r = client.post("/api/contacts", json={
        "full_name": "DD3", "email": "dd3@x.it", "status": "lead",
    }, headers=superadmin_headers)
    assert r.status_code in (200, 201)
    cid = r.get_json()["id"]
    r = client.post("/api/cases", json={
        "title": "DD3", "contactid": cid, "status": "Active",
    }, headers=superadmin_headers)
    assert r.status_code in (200, 201)
    cc = r.get_json()["id"]
    r = client.post("/api/tasks/", json={
        "title": "Done", "caseid": cc,
        "status": "done", "priority": "Medium",
        "duedate": "202-10-30",
    }, headers=superadmin_headers)
    assert r.status_code in (200, 201)
    r = client.get("/api/calendar?deadline_events=true", headers=superadmin_headers)
    assert r.status_code == 200
    evs = r.get_json()
    tv = [e for e in evs if e.get("kind") == "task_due" and e.get("title") == "[Due] Done"]
    assert len(tv) == 0


def test_null_date_ok(client, superadmin_headers):
    """Null duedate does not crash."""
    os.environ["CALENDAR_DEADLINES_ENABLED"] = "true"
    r = client.post("/api/contacts", json={
        "full_name": "DD4", "email": "dd4@x.it", "status": "lead",
    }, headers=superadmin_headers)
    assert r.status_code in (200, 201)
    cid = r.get_json()["id"]
    r = client.post("/api/cases", json={
        "title": "DD4", "contactid": cid, "status": "Active",
    }, headers=superadmin_headers)
    assert r.status_code in (200, 201)
    cc = r.get_json()["id"]
    r = client.post("/api/tasks/", json={
        "title": "Null", "caseid": cc,
        "status": "pending", "priority": "Medium",
    }, headers=superadmin_headers)
    assert r.status_code in (200, 201)
    r = client.get("/api/calendar?deadline_events=true", headers=superadmin_headers)
    assert r.status_code == 200
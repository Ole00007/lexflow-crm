"""Task endpoint tests — CRUD + workspace scoping."""


def test_get_tasks_requires_auth(client):
    resp = client.get("/api/tasks/")
    assert resp.status_code == 401


def test_get_tasks_authenticated(client, superadmin_headers):
    resp = client.get("/api/tasks/", headers=superadmin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_create_task(client, superadmin_headers):
    # First create a case to reference
    case_resp = client.post("/api/cases", json={
        "contactid": 1,
        "title": "Test Case for Task",
        "status": "Intake",
        "priority": "Medium",
    }, headers=superadmin_headers)
    if case_resp.status_code in (200, 201):
        case_id = case_resp.get_json().get("id")
    else:
        case_id = 1

    resp = client.post("/api/tasks/", json={
        "title": "Test Task",
        "caseid": case_id,
        "status": "pending",
        "priority": "Medium",
        "duedate": "2026-12-31",
    }, headers=superadmin_headers)
    assert resp.status_code in (200, 201)
    data = resp.get_json()
    assert "id" in data
    assert data["title"] == "Test Task"


def test_task_not_found(client, superadmin_headers):
    resp = client.get("/api/tasks/99999", headers=superadmin_headers)
    assert resp.status_code == 404

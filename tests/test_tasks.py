"""Task endpoint tests — CRUD + workspace scoping."""


def test_get_tasks_requires_auth(client):
    resp = client.get("/api/tasks/")
    assert resp.status_code == 401


def test_get_tasks_authenticated(client, superadmin_headers):
    resp = client.get("/api/tasks/", headers=superadmin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_create_task(client, superadmin_headers):
    # Create a contact first (needed for case FK)
    contact_resp = client.post("/api/contacts", json={
        "full_name": "Test Contact",
        "email": "test_contact_lexflow@test.com",
        "status": "lead",
    }, headers=superadmin_headers)
    assert contact_resp.status_code in (200, 201), f"Contact creation failed: {contact_resp.status_code}"
    contact_id = contact_resp.get_json().get("id")

    # Create a case
    case_resp = client.post("/api/cases", json={
        "contactid": contact_id,
        "title": "Test Case for Task",
        "status": "Intake",
        "priority": "Medium",
    }, headers=superadmin_headers)
    assert case_resp.status_code in (200, 201), f"Case creation failed: {case_resp.status_code}"
    case_id = case_resp.get_json().get("id")

    # Create a task
    resp = client.post("/api/tasks/", json={
        "title": "Test Task",
        "caseid": case_id,
        "status": "pending",
        "priority": "Medium",
        "duedate": "2026-12-31",
    }, headers=superadmin_headers)
    assert resp.status_code in (200, 201), f"Task creation failed: {resp.status_code}"
    data = resp.get_json()
    assert "id" in data
    assert data["title"] == "Test Task"


def test_task_not_found(client, superadmin_headers):
    resp = client.get("/api/tasks/99999", headers=superadmin_headers)
    assert resp.status_code == 404

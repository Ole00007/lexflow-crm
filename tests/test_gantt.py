"""Gantt endpoint tests — auth, authorization, whitelist, exclusions."""
import pytest


# ── Auth ───────────────────────────────────────────────────────────────────

def test_gantt_requires_auth(client):
    resp = client.get("/api/gantt/tasks")
    assert resp.status_code == 401


# ── Basic authenticated request ────────────────────────────────────────────

def test_gantt_returns_empty_list_when_no_tasks(client, superadmin_headers):
    resp = client.get("/api/gantt/tasks", headers=superadmin_headers)
    assert resp.status_code == 200
    assert resp.get_json() == []


# ── Whitelist: exact keys, no leakage ───────────────────────────────────────

def test_gantt_whitelist_exact_keys(client, superadmin_headers):
    """Create a task with start+end and verify the response contains
    ONLY the whitelisted keys — no description, notes, tokens, etc."""
    # Create contact + case first
    contact_id = _create_contact(client, superadmin_headers)
    case_id = _create_case(client, superadmin_headers, contact_id)

    # Create task with startdate and duedate
    resp = client.post("/api/tasks/", json={
        "title": "Gantt Whitelist Test",
        "caseid": case_id,
        "status": "in_progress",
        "priority": "Medium",
        "startdate": "2026-10-14",
        "duedate": "2026-10-25",
    }, headers=superadmin_headers)
    assert resp.status_code in (200, 201)

    # Fetch gantt
    resp = client.get("/api/gantt/tasks", headers=superadmin_headers)
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert len(tasks) >= 1

    # Find our task
    gantt_task = next(t for t in tasks if t["name"] == "Gantt Whitelist Test")

    core_keys = {'id', 'name', 'start', 'end', 'progress', 'dependencies', 'custom_class'}
    # Contract extended by the team-roles feature (WS-A): team[], vault (superadmin only), open_flags
    expected_keys = core_keys | {'team', 'vault', 'open_flags'}
    assert set(gantt_task.keys()) == expected_keys, (
        f"Whitelist violation: got {set(gantt_task.keys())}, expected {expected_keys}"
    )
    assert gantt_task['team'] == [] and gantt_task['open_flags'] == 0

    # Verify no leaked fields
    for forbidden in ('description', 'notes', 'userid', 'workspace_id', 'caseid',
                      'status', 'priority', 'createdat', 'updatedat', 'is_deleted'):
        assert forbidden not in gantt_task, f"Leaked field: {forbidden}"


# ── Status → progress map ──────────────────────────────────────────────────

def test_gantt_status_progress_map(client, superadmin_headers):
    contact_id = _create_contact(client, superadmin_headers)
    case_id = _create_case(client, superadmin_headers, contact_id)

    statuses = [
        ("pending", 0, "gantt-status-pending"),
        ("in_progress", 50, "gantt-status-in-progress"),
        ("done", 100, "gantt-status-done"),
        ("unknown_status", 0, "gantt-status-unknown"),
    ]
    for i, (status, expected_progress, expected_class) in enumerate(statuses):
        resp = client.post("/api/tasks/", json={
            "title": f"Status Test {i}",
            "caseid": case_id,
            "status": status,
            "priority": "Medium",
            "startdate": "2026-10-14",
            "duedate": "2026-12-31",
        }, headers=superadmin_headers)
        assert resp.status_code in (200, 201)

    resp = client.get("/api/gantt/tasks", headers=superadmin_headers)
    tasks = resp.get_json()

    for i, (status, expected_progress, expected_class) in enumerate(statuses):
        t = next(t for t in tasks if t["name"] == f"Status Test {i}")
        assert t["progress"] == expected_progress, f"Status {status}: progress {t['progress']} != {expected_progress}"
        assert expected_class in t["custom_class"], f"Status {status}: class {t['custom_class']} missing {expected_class}"


# ── Overdue modifier ───────────────────────────────────────────────────────

def test_gantt_overdue_class(client, superadmin_headers):
    contact_id = _create_contact(client, superadmin_headers)
    case_id = _create_case(client, superadmin_headers, contact_id)

    # Create an overdue task (end in past, not done)
    resp = client.post("/api/tasks/", json={
        "title": "Overdue Task",
        "caseid": case_id,
        "status": "pending",
        "priority": "Medium",
        "startdate": "2026-09-01",
        "duedate": "2026-09-10",  # in the past
    }, headers=superadmin_headers)
    assert resp.status_code in (200, 201)

    resp = client.get("/api/gantt/tasks", headers=superadmin_headers)
    tasks = resp.get_json()
    overdue = next(t for t in tasks if t["name"] == "Overdue Task")
    assert "gantt-status-overdue" in overdue["custom_class"]


def test_gantt_not_overdue_when_done(client, superadmin_headers):
    contact_id = _create_contact(client, superadmin_headers)
    case_id = _create_case(client, superadmin_headers, contact_id)

    # Done task in past — should NOT have overdue class
    resp = client.post("/api/tasks/", json={
        "title": "Done Past Task",
        "caseid": case_id,
        "status": "done",
        "priority": "Medium",
        "startdate": "2026-09-01",
        "duedate": "2026-09-10",
    }, headers=superadmin_headers)
    assert resp.status_code in (200, 201)

    resp = client.get("/api/gantt/tasks", headers=superadmin_headers)
    tasks = resp.get_json()
    done_task = next(t for t in tasks if t["name"] == "Done Past Task")
    assert "gantt-status-overdue" not in done_task["custom_class"]


# ── Exclusions ─────────────────────────────────────────────────────────────

def test_gantt_drops_missing_dates(client, superadmin_headers):
    contact_id = _create_contact(client, superadmin_headers)
    case_id = _create_case(client, superadmin_headers, contact_id)

    # Task with no duedate — should be dropped
    resp = client.post("/api/tasks/", json={
        "title": "No End Task",
        "caseid": case_id,
        "status": "pending",
        "priority": "Medium",
        "startdate": "2026-10-14",
        # no duedate
    }, headers=superadmin_headers)
    assert resp.status_code in (200, 201)

    # Task with no startdate — should be dropped
    resp = client.post("/api/tasks/", json={
        "title": "No Start Task",
        "caseid": case_id,
        "status": "pending",
        "priority": "Medium",
        "duedate": "2026-12-31",
        # no startdate
    }, headers=superadmin_headers)
    assert resp.status_code in (200, 201)

    # Valid task — should be included
    resp = client.post("/api/tasks/", json={
        "title": "Valid Task",
        "caseid": case_id,
        "status": "pending",
        "priority": "Medium",
        "startdate": "2026-10-14",
        "duedate": "2026-12-31",
    }, headers=superadmin_headers)
    assert resp.status_code in (200, 201)

    resp = client.get("/api/gantt/tasks", headers=superadmin_headers)
    tasks = resp.get_json()
    names = [t["name"] for t in tasks]
    assert "No End Task" not in names
    assert "No Start Task" not in names
    assert "Valid Task" in names


def test_gantt_drops_end_before_start(client, superadmin_headers):
    contact_id = _create_contact(client, superadmin_headers)
    case_id = _create_case(client, superadmin_headers, contact_id)

    # Task where end < start — should be dropped
    resp = client.post("/api/tasks/", json={
        "title": "End Before Start Task",
        "caseid": case_id,
        "status": "pending",
        "priority": "Medium",
        "startdate": "2026-10-25",
        "duedate": "2026-10-14",  # before start
    }, headers=superadmin_headers)
    assert resp.status_code in (200, 201)

    resp = client.get("/api/gantt/tasks", headers=superadmin_headers)
    tasks = resp.get_json()
    names = [t["name"] for t in tasks]
    assert "End Before Start Task" not in names


# ── Dependencies field is always empty ─────────────────────────────────────

def test_gantt_dependencies_empty(client, superadmin_headers):
    contact_id = _create_contact(client, superadmin_headers)
    case_id = _create_case(client, superadmin_headers, contact_id)

    resp = client.post("/api/tasks/", json={
        "title": "Deps Test",
        "caseid": case_id,
        "status": "pending",
        "priority": "Medium",
        "startdate": "2026-10-14",
        "duedate": "2026-12-31",
    }, headers=superadmin_headers)
    assert resp.status_code in (200, 201)

    resp = client.get("/api/gantt/tasks", headers=superadmin_headers)
    tasks = resp.get_json()
    deps_task = next(t for t in tasks if t["name"] == "Deps Test")
    assert deps_task["dependencies"] == ""


# ── Helpers ────────────────────────────────────────────────────────────────

def _create_contact(client, headers):
    resp = client.post("/api/contacts", json={
        "full_name": "Gantt Test Contact",
        "email": f"gantt_test_{id(object())}@test.com",
        "status": "lead",
    }, headers=headers)
    assert resp.status_code in (200, 201)
    return resp.get_json()["id"]


def _create_case(client, headers, contact_id):
    resp = client.post("/api/cases", json={
        "contactid": contact_id,
        "title": "Gantt Test Case",
        "status": "Intake",
        "priority": "Medium",
    }, headers=headers)
    assert resp.status_code in (200, 201)
    return resp.get_json()["id"]

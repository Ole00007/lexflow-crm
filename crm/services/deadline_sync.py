"""
Deadline-to-calendar sync service.

Maps Task.duedate and Deadline rows into calendar-compatible dictionary entries
for the /api/calendar endpoint (enabled via CALENDAR_DEADLINES_ENABLED flag).

Each entry has a stable id/kind/source-link back to the original record.
"""

from datetime import date, datetime
from typing import List, Dict, Optional
from ..extensions import db
from ..models.task import Task
from ..models.deadline import Deadline
from ..models.case import Case


# Deadline type vocabulary for Italian legal practice
DEADLINE_TYPE_VOCABULARY = {
    "udienza": "Hearing / court session date",
    "termine_perentorio": "Peremptory deadline — expiry of a time limit that forfeits the right",
    "termine_ordinatorio": "Procedural deadline — time limit that does not forfeit the right",
    "deposito": "Filing deadline — document submission to the court registry",
    "scadenza_interna": "Internal studio deadline — preparatory step before a formal deadline",
}

# Common Italian deadline titles
ITALIAN_DEADLINE_TITLES = [
    "Deposito ricorso",
    "Udienza",
    "Termine per deposito documenti",
    "Scadenza nota spese",
    "Termine per impugnazione",
    "Memoria ex art. 183 c.p.c.",
    "Precisazione conclusioni",
    "Deposito comparsa conclusionale",
    "Termine per mediazione",
    "Scadenza interna — preparazione udienza",
]


def _deadline_to_event(deadline: Deadline) -> dict:
    """Convert a Deadline row to a calendar-compatible event dict."""
    d = deadline
    start = datetime.combine(d.deadline_date, datetime.min.time())
    return {
        "id": f"deadline-{d.id}",
        "workspace_id": d.workspace_id,
        "caseid": d.caseid,
        "title": d.title,
        "description": d.description,
        "kind": "deadline",
        "deadline_type": d.deadline_type,
        "deadline_id": d.id,
        "start_datetime": start.isoformat(),
        "end_datetime": None,
        "is_all_day": True,
        "status": d.status,
        "event_type": f"deadline_{d.deadline_type}",
        "source": f"/api/deadlines/{d.id}",
    }


def _task_due_to_event(task: Task) -> dict:
    """Convert a Task with duedate to a calendar-compatible event dict."""
    start = datetime.combine(task.duedate, datetime.min.time())
    return {
        "id": f"task-due-{task.id}",
        "workspace_id": task.workspace_id,
        "caseid": task.caseid,
        "title": f"[Due] {task.title}",
        "description": task.description,
        "kind": "task_due",
        "task_id": task.id,
        "start_datetime": start.isoformat(),
        "end_datetime": None,
        "is_all_day": True,
        "status": task.status,
        "event_type": "task_due",
        "source": f"/api/tasks/{task.id}",
    }



def _to_date(value):
    """Tolerant ISO parse: the calendar page sends full datetimes ('2026-09-28T00:00:00'),
    other clients send plain dates. Always return a date."""
    s = str(value).strip()
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None   # malformed filter value: ignore it rather than 500


def get_deadline_events(
    workspace_ids: Optional[List[int]] = None,
    caseid: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[dict]:
    """Return calendar-compatible entries for task due dates and Deadline rows.

    Deduplicated: if a task's duedate and a Deadline row fall on the same date
    for the same case, both are returned (they have distinct kinds/ids).

    Args:
        workspace_ids: If set, scope to these workspace IDs. If None, no filter
            (caller handles superadmin vs scoped — pass None for superadmin).
        caseid: Optional case filter.
        date_from: ISO date string (inclusive, e.g. '2026-10-01').
        date_to: ISO date string (inclusive).

    Returns:
        List of dicts with CalendarEvent-like fields including 'kind',
        'deadline_type' (if kind='deadline'), 'task_id'/'deadline_id',
        and 'source' (API link back to the original record).
    """
    date_from_d = _to_date(date_from) if date_from else None
    date_to_d = _to_date(date_to) if date_to else None
    results: List[dict] = []

    # 1) Task due dates — only incomplete tasks (not "done"/"completed"/"cancelled")
    task_query = Task.query.filter(
        Task.is_deleted == False,
        Task.duedate.isnot(None),
        ~Task.status.in_(["done", "completed", "cancelled"]),
    )
    if workspace_ids is not None:
        task_query = task_query.filter(Task.workspace_id.in_(workspace_ids))
    if caseid:
        task_query = task_query.filter(Task.caseid == caseid)
    if date_from_d:
        task_query = task_query.filter(Task.duedate >= date_from_d)
    if date_to_d:
        task_query = task_query.filter(Task.duedate <= date_to_d)

    for task in task_query.all():
        results.append(_task_due_to_event(task))

    # 2) Deadline rows — only non-deleted
    deadline_query = Deadline.query.filter(
        Deadline.is_deleted == False,
        Deadline.deadline_date.isnot(None),
    )
    if workspace_ids is not None:
        deadline_query = deadline_query.filter(Deadline.workspace_id.in_(workspace_ids))
    if caseid:
        deadline_query = deadline_query.filter(Deadline.caseid == caseid)
    if date_from_d:
        deadline_query = deadline_query.filter(Deadline.deadline_date >= date_from_d)
    if date_to_d:
        deadline_query = deadline_query.filter(Deadline.deadline_date <= date_to_d)

    for deadline in deadline_query.all():
        results.append(_deadline_to_event(deadline))

    # Sort by start_datetime
    results.sort(key=lambda e: e.get("start_datetime") or "")
    return results
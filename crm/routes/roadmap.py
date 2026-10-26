"""
Roadmap graph blueprint — read-only diagram-view foundation (T-021).

GET /api/roadmap/graph -> {"nodes": [...], "edges": [...]}

n8n / Obsidian-graph style execution diagram for the CURRENT user's visible
workspaces (workspace_filter + get_visible_workspace_ids — same isolation as
every other /api route; superadmin sees all, tenant admins see own + children,
anonymous sees nothing).

Node types: case, contact, task, staff, event, status
Edge types: belongs_to (case->contact), has_task (case->task),
            assigned_to (task/case->staff), status (task/case->status),
            has_event (case->event), scheduled_as (task->event via notes "task:N")

Read-only: no POST/PUT/DELETE here. The frontend (frontend-developer) renders
the diagram from this payload.
"""
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from ..extensions import db
from ..models.case import Case
from ..models.contact import Contact
from ..models.task import Task
from ..models.calendar_event import CalendarEvent
from ..models.user import User
from ..workspace import workspace_filter
from datetime import datetime

roadmap_bp = Blueprint('roadmap', __name__, url_prefix='/api/roadmap')


def _iso(v):
    try:
        return v.isoformat() if v else None
    except Exception:
        return None


@roadmap_bp.get('/graph')
@jwt_required()
def graph():
    """Return {nodes:[], edges:[]} for the visible workspaces (read-only)."""
    nodes = []
    edges = []
    seen_edges = set()

    def add_edge(src, dst, etype, label=None):
        key = (src, dst, etype)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append({
            "source": src,
            "target": dst,
            "type": etype,
            "label": label,
        })

    # ── Cases ────────────────────────────────────────────────────────
    cases = workspace_filter(Case.query.filter_by(is_deleted=False), Case).all()
    status_values = set()

    for c in cases:
        cid = f"case-{c.id}"
        nodes.append({
            "id": cid,
            "type": "case",
            "label": f"{c.display_id()} — {c.title}",
            "data": {
                "case_id": c.id,
                "display_id": c.display_id(),
                "workspace_id": c.workspace_id,
                "status": c.status,
                "priority": c.priority,
                "casetype": c.casetype,
                "duedate": _iso(c.duedate),
                "openedat": _iso(c.openedat),
                "createdat": _iso(c.createdat),
            },
        })
        if c.status:
            status_values.add(c.status)

    # ── Contacts referenced by visible cases ─────────────────────────
    contact_ids = {c.contactid for c in cases if c.contactid}
    contacts = {}
    if contact_ids:
        q = Contact.query.filter(
            Contact.id.in_(contact_ids), Contact.is_deleted == False
        )
        for ct in workspace_filter(q, Contact).all():
            contacts[ct.id] = ct
            nodes.append({
                "id": f"contact-{ct.id}",
                "type": "contact",
                "label": ct.fullname,
                "data": {
                    "contact_id": ct.id,
                    "workspace_id": ct.workspace_id,
                    "email": ct.email,
                    "phone": ct.phone,
                    "company": ct.company,
                    "status": ct.status,
                },
            })

    # ── Tasks ────────────────────────────────────────────────────────
    tasks = workspace_filter(Task.query.filter_by(is_deleted=False), Task).all()
    task_ids = {t.id for t in tasks}
    from .task_team import team_payload
    try:
        _resp = team_payload(tasks, None)  # superadmin-only vault data is skipped (user=None); names/roles only
    except Exception:
        _resp = {}
    for t in tasks:
        tid = f"task-{t.id}"
        nodes.append({
            "id": tid,
            "type": "task",
            "label": t.title,
            "data": {
                "task_id": t.id,
                "workspace_id": t.workspace_id,
                "caseid": t.caseid,
                "userid": t.userid,
                "status": t.status,
                "priority": t.priority,
                "duedate": _iso(t.duedate),
                "createdat": _iso(t.createdat),
                # who is responsible (role-coloured in the UI): [{name, role, role_label, color, inferred}]
                "responsible": [{k: m.get(k) for k in ('name', 'role', 'role_label', 'color', 'inferred')}
                                for m in (_resp.get(t.id, {}).get('team') or [])],
            },
        })
        if t.status:
            status_values.add(t.status)

    # ── Status nodes (shared across cases+tasks, n8n-style states) ───
    status_ids = {}
    for sv in sorted(status_values):
        sid = f"status-{sv}"
        status_ids[sv] = sid
        nodes.append({"id": sid, "type": "status", "label": sv, "data": {"status": sv}})

    # ── Calendar events (visible workspaces) ─────────────────────────
    events = workspace_filter(
        CalendarEvent.query.filter_by(is_deleted=False), CalendarEvent
    ).all()
    # events whose notes follow the "task:<id>" convention made by
    # POST /api/tasks add_to_calendar — link task -> event too
    task_events = {}  # task_id -> event node id
    for e in events:
        eid = f"event-{e.id}"
        nodes.append({
            "id": eid,
            "type": "event",
            "label": e.title,
            "data": {
                "event_id": e.id,
                "workspace_id": e.workspace_id,
                "caseid": e.caseid,
                "contactid": e.contactid,
                "event_type": e.event_type,
                "status": e.status,
                "start_datetime": _iso(e.start_datetime),
                "end_datetime": _iso(e.end_datetime),
                "notes": e.notes,
            },
        })
        if e.notes and str(e.notes).startswith("task:"):
            try:
                task_events[int(str(e.notes).split(":", 1)[1])] = eid
            except (ValueError, IndexError):
                pass

    # ── Staff (users referenced by cases/tasks) ──────────────────────
    staff_ids = set()
    for c in cases:
        if c.ownerid:
            staff_ids.add(c.ownerid)
        if c.assignedto:
            staff_ids.add(c.assignedto)
    for t in tasks:
        if t.userid:
            staff_ids.add(t.userid)
    staff = {}
    if staff_ids:
        for u in User.query.filter(User.id.in_(staff_ids), User.is_deleted == False).all():
            staff[u.id] = u
            nodes.append({
                "id": f"staff-{u.id}",
                "type": "staff",
                "label": f"{u.email} ({u.role})",
                "data": {"user_id": u.id, "email": u.email, "role": u.role,
                         "workspace_id": u.workspace_id},
            })

    # ── Edges ────────────────────────────────────────────────────────
    for c in cases:
        cid = f"case-{c.id}"
        if c.contactid and c.contactid in contacts:
            add_edge(cid, f"contact-{c.contactid}", "belongs_to", label="client")
        if c.status and c.status in status_ids:
            add_edge(cid, status_ids[c.status], "status")
        if c.assignedto and c.assignedto in staff:
            add_edge(cid, f"staff-{c.assignedto}", "assigned_to", label="assigned")
        if c.ownerid and c.ownerid in staff:
            add_edge(cid, f"staff-{c.ownerid}", "assigned_to", label="owner")

    for t in tasks:
        tid = f"task-{t.id}"
        if t.caseid:
            add_edge(f"case-{t.caseid}", tid, "has_task", label="case task")
        if t.status and t.status in status_ids:
            add_edge(tid, status_ids[t.status], "status")
        if t.userid and t.userid in staff:
            add_edge(tid, f"staff-{t.userid}", "assigned_to", label="assignee")
        if t.id in task_events:
            add_edge(tid, task_events[t.id], "scheduled_as", label="calendar event")

    for e in events:
        eid = f"event-{e.id}"
        if e.caseid:
            add_edge(f"case-{e.caseid}", eid, "has_event", label="hearing/meeting")
        if e.contactid and e.contactid in contacts:
            add_edge(eid, f"contact-{e.contactid}", "belongs_to", label="client")

    return jsonify({
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "note": "Read-only diagram foundation (T-021). Frontend renders nodes/edges.",
        },
    }), 200

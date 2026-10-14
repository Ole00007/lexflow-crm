# Gantt C — Backend Dev Handover

**Date:** 2026-10-14
**From:** Hermes (orchestrator)
**To:** Backend Dev
**Priority:** SHIP TODAY

---

## What's already built (scaffold — do NOT rebuild)

| Component | Location | Status |
|---|---|---|
| Vendored Frappe Gantt 1.2.2 | `static/vendor/frappe-gantt/1.2.2/` | ✅ Done, checksummed |
| Page shell | `templates/gantt.html` | ✅ Done (extends base.html) |
| Component skeleton | `static/js/gantt/gantt_view.js` | ✅ Done — `render()` is a STUB |
| Isolated styles | `static/css/gantt/gantt.css` | ✅ Done |
| Page route | `crm/routes/views.py` `/gantt` | ✅ Done, gated by `GANTT_VIEW_ENABLED` |
| Security fixes | A1 (seed endpoint) + A2 (hardcoded creds) | ✅ Done |
| Test suite | `tests/` (14 tests, all passing) | ✅ Done |

---

## What you need to build (M2 — the actual chart)

### 1. Backend endpoint: `GET /api/gantt/tasks`

**File:** New blueprint `crm/routes/gantt.py`, register in `crm/__init__.py`

**Auth:** `@jwt_required()` — unauthenticated → 401

**Authorization (P3 approved rule):**
```python
# Staff-scoped task visibility
# A task may be returned only if:
#   tasks.workspace_id IN caller's visible workspaces
#   AND caller is either:
#     (a) workspace admin (role IN {admin, superadmin}), OR
#     (b) the task's assignee (tasks.userid == caller.id), OR
#     (c) the owner/assignee of the task's case
#        (cases.ownerid == caller.id OR cases.assignedto == caller.id)
# Applied IN THE DATABASE QUERY — never filter in browser JS.
```

**Response — EXACT whitelist per object:**
```json
[
  {
    "id": 1,
    "name": "Task title",
    "start": "2026-10-14",
    "end": "2026-10-25",
    "progress": 50,
    "dependencies": "",
    "custom_class": "gantt-status-in-progress"
  }
]
```

**Must NOT appear:** description, notes, documents, tokens, personal data.

**Exclusion rules (server-side):**
- Drop tasks missing `start` or `end` → report aggregate count
- Drop tasks where `end < start` → log non-sensitive warning (task id only)
- Dependencies: omit (no approved relationship exists)
- Milestones: omit (no approved milestone type exists)

**Status → progress map (approved):**
| Status | Progress | custom_class |
|---|---|---|
| `pending` | 0 | `gantt-status-pending` |
| `in_progress` | 50 | `gantt-status-in-progress` |
| `done` | 100 | `gantt-status-done` |
| *(any other)* | 0 | `gantt-status-unknown` |

**Overdue modifier:** `end < today AND progress < 100` → add `gantt-status-overdue` class

### 2. Task start date field (P2 — approved by Olesia)

**Migration:** Additive, `tasks.startdate DATE NULL`
```python
# migrations/versions/<new>/xxxx_add_task_startdate.py
def upgrade():
    op.add_column('tasks', sa.Column('startdate', sa.Date(), nullable=True))
def downgrade():
    op.drop_column('tasks', 'startdate')
```

**Model:** Add `startdate = db.Column(db.Date, nullable=True)` to `crm/models/task.py`
**API:** Add `"startdate"` to `Task.to_dict()`, accept on POST/PUT
**Form:** Add `startdate` date input to `templates/tasks.html`

### 3. Frontend render function

**File:** `static/js/gantt/gantt_view.js` — replace the `render()` stub

```javascript
function render(tasks) {
  // 1. Drop tasks missing start/end (count them)
  // 2. Drop tasks where end < start (warn, no client data in log)
  // 3. Map status → custom_class via the approved map
  // 4. Instantiate: new Gantt('#gantt', tasks, GANTT_OPTIONS)
  // 5. NEVER issue POST/PUT/PATCH
}
```

**Gantt options (already defined in GANTT_OPTIONS):**
- `readonly: true, readonly_dates: true, readonly_progress: true`
- `move_dependencies: false`
- `view_mode: 'Day', view_mode_select: true`
- `infinite_padding: false`

---

## What I need from you (backend dev)

**Before you start, tell me:**
1. What skills do you lack for this task? (e.g., Flask blueprint patterns, SQLAlchemy migrations, Frappe Gantt API, CSS/DOM)
2. What tools do you need that you don't have? (e.g., MCP server for frontend, browser dev tools, testing framework)
3. What's your estimated time for M2 (endpoint + migration + render)?

**I will:**
- Provide any missing skills/tools
- Coordinate cross-tests (CT1–CT5)
- Handle staging smoke test + Railway deploy

---

## Cross-test checklist (before merge to main)

| Test | What | Pass condition |
|---|---|---|
| CT1 | Auth & authorization | 0 unauthorized successes, 0 server 500s |
| CT2 | JSON field leakage | Exact whitelist, 0 extra keys |
| CT3 | C semantics fixture | Every inclusion/exclusion/class matches |
| CT4 | Empty/loading/error states | All visible, no overflow at 375px |
| CT5 | Regression | Existing tests pass, 0 writes while flag off |

---

## Files you'll touch

```
crm/routes/gantt.py          (NEW — endpoint)
crm/__init__.py              (register blueprint)
crm/models/task.py           (add startdate field)
migrations/versions/xxx/     (NEW — additive migration)
templates/tasks.html         (add startdate input)
static/js/gantt/gantt_view.js (implement render())
tests/test_gantt.py          (NEW — endpoint tests)
```

---

## Reference docs

- `docs/gantt/gantt_integration_approach.md` — full integration spec
- `docs/gantt_bar_semantics.md` — status→progress map
- `docs/gantt_gate_report.md` — P0–P4 gates + authz rule
- `static/vendor/frappe-gantt/1.2.2/VENDOR.md` — library options
- `Frappe-Gantt/LexFlow-Gantt-Plan-v4-2.md` — master plan

---

**Ship target: TODAY. Report blockers immediately.**

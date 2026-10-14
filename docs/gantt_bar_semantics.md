# Gantt C — Bar semantics (status → progress map) (P2)

**Gate:** P2 (status prerequisite) of `Frappe-Gantt/LexFlow-Gantt-Plan-v4-2.md` §4
**Date:** 2026-10-14 · **Branch:** `feat/gantt-c`
**Scope:** the read-only internal staff view **C** (task-level timeline).

---

## 1. What the real data actually contains

There are **two independent status vocabularies** in the CRM. They must not be conflated.

### (a) TASK statuses — drive Gantt C bars

Source of truth: `templates/tasks.html` (the create form) + `crm/models/task.py`
(`status` default `"pending"`). This is what C renders (plan §7: "INTERNAL TASK").

| value (exact string) | where set | meaning |
|---|---|---|
| `pending` | `Task.status` default; `tasks.html` option (selected) | not started |
| `in_progress` | `tasks.html` option | active |
| `done` | `tasks.html` option | finished |

> Note: the API accepts **any** string for `status` (`crm/routes/tasks.py` POST/PUT set it
> verbatim, no enum). So real rows may hold values outside this list — hence the
> `unknown` rule below.

### (b) CASE statuses — drive the **Kanban board**, not the Gantt bars

Source of truth: `crm/routes/views.py::kanban()` (line ~147) and
`templates/kanban.html` (`const STATUSES = [...]`).

```
Intake, Conflict Check, Review, In Progress, Waiting Docs, To Verify, Engaged, Closed
```

`Case.status` default is `"Intake"` (`crm/models/case.py`). The `/kanban` route groups
**cases** (not tasks) by these. C is a **task** timeline, so these do not set bar progress —
but they are the authoritative case state if C ever groups by case, and they must stay
consistent with the Kanban board (cross-test CT5: "Kanban/calendar dates match").

### (c) Priority values (for bar styling only, if approved)

Task form: `Low, Medium, High, Urgent` (default `Medium`). Case default `Medium`.

---

## 2. Status → progress map (exact, for Gantt C)

Frappe Gantt `progress` is an integer 0–100.

| task status | progress | `custom_class` | bar fill |
|---|---:|---|---|
| `pending` | **0** | `gantt-status-pending` | 0% |
| `in_progress` | **50** | `gantt-status-in-progress` | 50% |
| `done` | **100** | `gantt-status-done` | 100% |
| *(any other value)* | **0** | `gantt-status-unknown` | 0% + unknown styling |

**Overdue** (plan §7): bar gets `gantt-status-overdue` when `end < today` **and**
`progress < 100`. Overdue is a modifier class, not a separate progress value.

### Unknown-status handling (plan §4)

- Add class `gantt-status-unknown`.
- Log **only** the task id and the unknown value — never client data.
- **Fail** the semantics cross-test (CT3) until the value is either mapped here or
  deliberately excluded. Do not silently default an unmapped status to `done`/`in_progress`.

---

## 3. Inclusion / exclusion rules (plan §7 C rules)

| Rule | Behavior |
|---|---|
| Start | **approved task start field only** (see §4 — currently **absent**) |
| End | `tasks.duedate` (approved deadline field) |
| Missing start **or** end | **Exclude** from payload; report an **aggregate exclusion count** (no per-row client data) |
| End before start | **Reject** from payload; log a non-sensitive data-quality warning (task id only) |
| Dependencies | **Omit** unless an approved dependency relationship exists (none today) |
| Milestone | **Omit** unless an approved milestone type exists (none today) |
| Progress | Derived from the map above (no real progress column exists) |

---

## 4. Blocking gap: no approved task start field (P2 stop condition)

**Verified absent.** `crm/models/task.py` and the initial migration
(`migrations/versions/913a482dc55f`) contain **no** `startdate`/`start_date` column on
`tasks`. The only task date is `duedate`. Calendar `start_datetime` belongs to
`CalendarEvent`, not tasks. **Do not infer start from `createdat`, case `openedat`, or any
other date** (plan §4).

A minimal proposal is in `docs/gantt_gate_report.md` §P2. **No migration may be created or
applied until Olesia approves the field** (plan §4, §14 P2).

---

## 5. Reference for the renderer

The concurrent scaffold (`static/js/gantt/gantt_view.js`) references a path
`docs/gantt/gantt_bar_semantics.md`. This file is the canonical semantics doc; either move
it to that path or update the scaffold's comment when the scaffold is reviewed. (Flagged,
not changed — the scaffold is not this task's to edit.)

# Gantt C — Prerequisite gate report (P0–P4)

**Plan:** `Frappe-Gantt/LexFlow-Gantt-Plan-v4-2.md`
**Branch:** `feat/gantt-c`
**Commit SHA (base):** `82d1f09e995492e057ba9058d3e962c2820f4d57`
**Date:** 2026-10-14
**Author/model:** Admy gate coordinator, model route `meituan/longcat-2.5-preview:free` (Nous Portal)
**Scope executed:** P0 → P4 only. **No Gantt production code written.**

> ⚠️ **Two hard flags up front:**
> 1. **P0 STOP CONDITION IS ACTIVE** — a concurrent process wrote Gantt scaffold code into
>    this working tree during P0 (11:47–11:48). See `docs/gantt_p0_inventory.md`.
> 2. **This report was produced by a free route.** Plan §12.7: "Do not let a free/promotional
>    model approve a gate." These P-gates must be **cross-approved** by a non-free route
>    (Admy = GLM 5.3 Flash) and/or Olesia before M0.

---

## P0 — Backup and inventory

Full detail: `docs/gantt_p0_inventory.md`. Summary:

- **State at start:** clean (`feat/gantt-c` @ `82d1f09`; only untracked `.DS_Store`, `Frappe-Gantt/`). Single worktree, empty stash.
- **State at end:** **dirty** — `M crm/routes/views.py`, `M templates/base.html`, plus untracked `templates/gantt.html`, `static/js/gantt/`, `static/css/gantt/`, `static/vendor/frappe-gantt/1.2.2/`. Created by a **concurrent process** (a live `smoothy_op_dir` profile is running), not by this task.
- **Existing Gantt work found:** (a) legacy demo on `legacy-recovered/feat/t021-diagram-gantt` (`docs/t021-demo/`), and (b) the uncommitted in-tree scaffold above.
- **Provenance gap:** the concurrent `static/vendor/frappe-gantt/1.2.2/frappe-gantt.umd.js` is **byte-identical** (sha256 `f5b9de3b…`, 48175 B) to the legacy demo's copy — so it came from the legacy branch, **not** a verified fresh npm download, despite `VENDOR.md` claiming the archive checksum.
- **Flag-name mismatch:** concurrent `/gantt` route gates on `GANTT_VIEW_ENABLED`; plan §10 names `GANTT_WRITE_ENABLED`.
- **Backups:** two verified tarballs + `backups/gantt-p0/ROLLBACK.md`. Rollback = `git reset --hard 82d1f09…` or restore a snapshot.
- **Verdict:** ⛔ **STOP** — working state is dirty/ambiguous with unreviewed Gantt work.

---

## P1 — Architecture reconciliation

Full detail: `docs/gantt_architecture_decision.md`.

**Decision:** **Flask CRM monolith (`/crm`)** — Jinja templates + vanilla JS, Flask-SQLAlchemy
models, `workspace_filter` scoping, JWT, Railway deploy.

- No `CLAUDE.md`, no `apps/web` → first branch of the plan's rule is false.
- Flask-first override is active (only complete + deployed app) → use Flask.
- Do **not** create `/apps/web`; do **not** put Flask code in `/apps/api`; no third frontend.
- Test command: **none reliable today** (curl scripts are path-stale).
- Rollback path: git reset + snapshot.

**Escalate:** plan §3 says a "current project rules" doc describes `/apps/web`; that doc is
**not present locally**. Confirm with Olesia, but local evidence unambiguously supports Flask.

---

## P2 — Required data capability

### Task start field — **ABSENT** (stop condition)

Verified in `crm/models/task.py` and `migrations/versions/913a482dc55f`: `tasks` has
`duedate` only. No `startdate`/`start_date`. Calendar `start_datetime` is on `CalendarEvent`.
**No approved task start field exists.** Per plan §4, **no migration** is created/applied
without Olesia's approval.

**Minimal proposal (proposal only — not approved, not applied):**

| Aspect | Proposal |
|---|---|
| Name / type | `tasks.startdate` — `DATE`, **NULLABLE** |
| Validation | strict `YYYY-MM-DD`, year 1900–2100 (mirror `crm/routes/tasks.py::_safe_date`); when both present, require `startdate <= duedate` else reject/exclude |
| API impact | add `"startdate"` to `Task.to_dict()`; accept `startdate` on `POST/PUT /api/tasks` (after approval); no change to existing keys |
| Form impact | `templates/tasks.html`: add a `startdate` date input next to Due Date |
| Kanban/calendar impact | **none** — Kanban groups by case status; calendar uses `CalendarEvent`; task↔calendar link uses `duedate` |
| Existing records | NULL → excluded from Gantt with an **aggregate** exclusion count; **no backfill** from `createdat`/`openedat` |
| Migration | new **additive** migration chained from current head **`e2f3a4b5c6d7`**: `op.add_column('tasks', sa.Column('startdate', sa.Date(), nullable=True))` |
| Rollback | `op.drop_column('tasks','startdate')` (data-loss-free; column was additive) |

### Kanban statuses — real values (verified)

- **Task statuses** (drive Gantt bars): `pending`, `in_progress`, `done`.
- **Case statuses** (drive `/kanban`): `Intake, Conflict Check, Review, In Progress, Waiting Docs, To Verify, Engaged, Closed`.
- Full status→progress map + unknown handling: `docs/gantt_bar_semantics.md`.

---

## P3 — Authorization prerequisite

Full map below; **rule needs Olesia approval** (plan §14 P3).

| Item | Finding |
|---|---|
| JWT identity | `str(user.id)` — `create_access_token(identity=str(user.id))` (`crm/routes/auth.py`) |
| Role claims | **None in the JWT.** Role is read from `users.role` **per request**. Values: `superadmin`, `admin`, `staff`, `user` |
| `tasks.userid` | `Integer` FK → `users.id`, nullable, `ON DELETE SET NULL` — the assignee |
| `tasks.caseid` | `Integer` FK → `cases.id`, **NOT NULL**, `ON DELETE CASCADE` |
| `cases.ownerid` | plain `Integer`, **no FK** — holds a **user id** (per `views.py` comment) |
| `cases.assignedto` | `Integer` — FK → `users.id` in migration `913a…` but **no FK in the current model** (schema/model drift) |
| Admin behavior | `superadmin` → `workspace_filter` bypasses (all tenants). Non-superadmin → own workspace **+ child sub-workspaces**. |
| Tenant scope | `workspace_id` on every model; enforced **in the SQL query** by `crm/workspace.py::workspace_filter` / `get_visible_workspace_ids`. Anonymous/unknown → `[]` → **sees nothing** (never `None`). |

**Critical gap:** there is **no per-user scoping anywhere**. Any authenticated user sees
**every task in their workspace(s)** — `GET /api/tasks/` is workspace-scoped only. So
"User A cannot see User B's task" is **not** enforced today. (The plan's note that the
task route uses an "unscoped `Task.query…all()`" is **outdated** — it *is* workspace-scoped
now, but not user-scoped.)

**Proposed staff visibility rule (ONE rule — for Olesia to approve):**

> **Staff-scoped task visibility.** A task may be returned only if
> `tasks.workspace_id` is in the caller's visible workspaces **AND** the caller is either
> (a) a workspace admin (`role ∈ {admin, superadmin}`), or (b) the task's assignee
> (`tasks.userid == caller.id`) **or** the owner/assignee of the task's case
> (`cases.ownerid == caller.id OR cases.assignedto == caller.id`).
> The rule is applied **in the database query**, never by filtering JSON in the browser.

**Minimum authorization tests (must all pass before C ships):**

| # | Test | Expected |
|---|---|---|
| 1 | Unauthenticated HTML `/gantt` | denied (redirect/login or 404) |
| 2 | Unauthenticated JSON `/api/gantt/tasks` | 401, no body data |
| 3 | User A requests User B's task (foreign workspace) | 404 / absent — 0 unauthorized rows |
| 4 | User A requests a case outside approved scope | 404 / absent |
| 5 | Admin behavior matches the approved role policy | admin sees workspace set; staff sees own only |
| 6 | Response contains **no** sensitive fields | exact whitelist `id, name, start, end, progress, dependencies, custom_class`; 0 extra keys |

**Additional auth risks found (out of scope, flag only):**
- `crm/routes/cases.py::delete_case` has **no `@jwt_required()`** decorator (anonymous → empty workspace filter → 404, so not currently exploitable, but the decorator should be added).
- `get_visible_workspace_ids()` returns child sub-workspaces to **any** authenticated user, not only admins.
- `cases.assignedto` FK exists in the migration but not the model.

---

## P4 — Existing UI prerequisite

| Requirement | Status | Evidence |
|---|---|---|
| Authenticated CRM base layout | ✅ | `templates/base.html` — sidebar nav, secure-workspace banner, theme toggle, skip-link, toast container, per-tenant favicon |
| Kanban / task list (authoritative task source) | ✅ | `/kanban` (cases by status, `views.py::kanban`); `/tasks` (task list via `GET /api/tasks/`). **Authoritative task source = the `tasks` table via `/api/tasks`** |
| Calendar | ✅ | `/calendar` (`templates/calendar.html`) + `crm/routes/calendar.py`, `crm/services/calendar.py` (`CalendarEvent`) |
| Navigation pattern | ✅ | `base.html` `nav-list`: Dashboard / Contacts / Kanban / Calendar / Tasks / Matters / Firm Team / Settings (+ Super Admin) |
| Empty / loading / error / denied states | ⚠️ **Partial** | `tasks.html` has empty + "Failed to load" + "Login to view"; `base.html` has `toast()`; Kanban has its own copy. **No unified state pattern**; access-denied is `abort(404)`/redirect |
| Baseline test suite passes | ❌ **No reliable suite** | No pytest/`tests/`/`conftest.py`. `run_local_tests.sh` & `test_runner.sh` hard-code `cd ~/Desktop/LexFlow/lexflow_hermes_v1` (absent) and need a server on `:5001` → **non-runnable as-is** |
| CRM runs locally without production secrets | ⚠️ **Not live-verified** | No `.env` present; `crm/config.py` falls back to `sqlite:///crm_local.db` and dev keys; entry points `app.py`/`wsgi.py`. A live boot needs `pip install -r requirements.txt` in a venv, which **the sandbox blocked pending consent** this run |

**P4 verdict:** the authenticated shell, task source, calendar and nav **exist** — good.
But the plan requires "**Baseline test suite passes**" before Gantt, and there is effectively
**no automated baseline suite**, and the local boot was not confirmed. Both should be closed
as small separate tasks before M0.

---

## Changed files (this task)

```
docs/gantt_p0_inventory.md            (new)
docs/gantt_architecture_decision.md   (new)
docs/gantt_bar_semantics.md           (new)
docs/gantt_gate_report.md             (new, this file)
backups/gantt-p0/ROLLBACK.md          (new)
backups/gantt-p0/*.tar.gz             (new, untracked — do NOT commit; ~5.6 MB each)
```
**Not touched by this task:** `crm/`, `templates/`, `static/`, `migrations/` (the concurrent
scaffold changes to `crm/routes/views.py` and `templates/base.html` are **not** mine).

## Test output

- No project test suite exists; the shell scripts are path-stale and were not run.
- Verification actually performed (read-only): `git status/branch/worktree/stash/log/diff`,
  keyword greps, model/migration inspection, `shasum -a 256` of vendored assets,
  `tar -tzf` backup readability check. All succeeded; evidence inline above.
- **A live local boot was NOT performed** (dependency install blocked by sandbox consent).

## Risks / stop events

| Risk | Severity | Mitigation |
|---|---|---|
| Concurrent writer in the same tree (two agents, same files) | **High** | Stop; attribute & review the scaffold before M0 |
| Missing approved task start date | **High** | P2 proposal; needs Olesia approval before any migration |
| No per-user authorization rule yet | **High** | P3 proposed rule; needs Olesia approval + the 6 tests |
| No baseline test suite; local boot unverified | Medium | Close as separate small task before M0 |
| Vendored library provenance unverified | Medium | Re-download 1.2.2, verify archive + file checksums |
| Free model produced this gate report | Medium | Cross-approve with a non-free route (plan §12.7) |
| `GANTT_VIEW_ENABLED` vs `GANTT_WRITE_ENABLED` mismatch | Low | Pick one canonical flag at M1 |
| `delete_case` missing `@jwt_required` | Low | Fix in a separate approved task |

## Rollback steps

1. `cd /Users/olesiarasing/Projects/lexflow-crm && git checkout feat/gantt-c`
2. `git reset --hard 82d1f09e995492e057ba9058d3e962c2820f4d57`
3. If untracked files must be restored: `tar -xzf backups/gantt-p0/lexflow-concurrent-state_20261014_114902.tar.gz -C .`
4. Verify: `shasum -a 256 backups/gantt-p0/*.tar.gz`

## Hours and cost

- **Hours:** ~0.6 h equivalent (P0–P4 inspection + deliverables). Wall-clock 11:44–11:52 CEST.
- **Cost:** **$0.00 measured** — all work ran on the free Nous route `meituan/longcat-2.5-preview:free`. No paid model calls. Budget cap ($20) / stop ($10) not approached.
- **Provider lock:** respected — only the configured Nous Portal route was used; no OpenRouter/direct providers.

## Exact git commands (docs only — no push to `main`)

```bash
cd /Users/olesiarasing/Projects/lexflow-crm
git add docs/gantt_p0_inventory.md docs/gantt_architecture_decision.md \
        docs/gantt_bar_semantics.md docs/gantt_gate_report.md backups/gantt-p0/ROLLBACK.md
git commit -m "docs(gantt): P0-P4 prerequisite gate report + architecture/bar-semantics decisions"
# push the FEATURE branch only (never main):
git push -u legacy-recovered feat/gantt-c   # or: git push -u origin feat/gantt-c
```

## Verification command

```bash
cd /Users/olesiarasing/Projects/lexflow-crm && \
git rev-parse HEAD && git status --short && ls docs/gantt_*.md backups/gantt-p0/
```

---

## Smallest next action

**Stop the concurrent writer / attribute the scaffold, then re-run P0 on a clean tree.**
In parallel, put the three approvals to Olesia: (1) confirm **Flask** architecture (P1),
(2) approve or reject `tasks.startdate` (P2), (3) approve the **staff visibility rule** (P3).
Do not begin M0 until P0's dirty-state stop condition is cleared.

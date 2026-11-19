# How this build was done — every trick, 2026-11-18 → 19

For Ole, morning of 19 Nov 2026. Branch `integration/mindmap-demo` @ `9091366`,
mirrored on `backup/mindmap-demo-2026-11-18`. Nothing merged into
`lexflow_hermes_v1`, nothing deployed.

---

## 1. Four worktrees instead of one branch

`git worktree add` gives each agent its own checkout of the same repository, so
Backy (server), Fronty (UI), the integration branch and the merge branch never
fought over files or `git status`.

```
lexflow-crm-wt-hmerge        integration/elisa-hardening-merge   (my hardening lane)
lexflow-crm-wt-drafts-server feat/mindmap-drafts-server          (Backy)
lexflow-crm-wt-drafts-ui     feat/mindmap-ui                     (Fronty)
lexflow-crm-wt-integration   integration/mindmap-demo            (the demo)
lexflow-crm-wt-preview       feat/elisa-hardening                (ROI/calendar, :5058)
```

**Trick:** the demo branch is never edited directly by a specialist — it only
receives `git merge --no-edit feat/...`, which is a fast-forward-or-clean-merge
almost every time because the branches are short-lived.

## 2. Cherry-pick instead of merge (the scope trap)

`feat/elisa-hardening` was named "hardening" but carried **~3,700 lines** of ROI,
calendar and task-filter work. A full merge would have dragged all of it in.

```bash
git merge --no-commit --no-ff feat/elisa-hardening   # inspect
git merge --abort
git cherry-pick bd21460 0b3d3db ab2a1e6 258e16d       # only the hardening commits
```

**Trick:** always merge with `--no-commit --no-ff` first and read `--stat`. A
branch name is a claim, not a fact.

## 3. Alembic: re-parent, don't merge revisions

Cherry-picking left two heads (`m4b5c6d7e8f9`, `m4a5b6c7d8e9`) because the ROI
migration `l3f4a5b6c7d8` was excluded. Instead of adding a merge revision, the new
migration's `down_revision` was edited to point at the head that actually exists,
and the throwaway merge revision was deleted.

```bash
python -m alembic heads     # must print exactly one
```

**Trick:** with Alembic, "one head" is a test assertion, not a convention —
`tests/test_agent.py` asserts it, so a bad topology fails CI-by-pytest.

## 4. Structural guarantees instead of permission flags

Agents cannot write to `notes`. Not because a flag says so, but because:

- `notes` is only writable through `POST /api/notes/`, which **forces**
  `source="human"` server-side; a client sending `source="agent"` is ignored
  (covered by a test);
- agent output lives in a **separate table** `agent_drafts`;
- the only bridge is `POST /api/agent/drafts/<id>/accept`, which is a human action.

**Trick:** when a rule must never leak, move it out of the permission layer and
into the data model. A separate table cannot be "configured away".

## 5. Atomic single-use approval

Two clicks on Approve must not create two tasks. The claim is a conditional
`UPDATE`, not a read-then-write:

```sql
UPDATE agent_drafts SET status='accepted' WHERE id=:id AND status='proposed';
-- affected rows must equal 1, otherwise 409
```

Same pattern for Elisa's action approvals. Expired → `410 Gone`, wrong tenant →
`403`, second accept → `409`.

## 6. UTC at the boundary (two bugs, one root cause)

Browser rendered "5 hr ago" for a note written minutes earlier. Cause: SQLite
stores naive UTC; `isoformat()` emits `2026-11-18T23:50:12` with **no timezone
marker**, and JS `new Date()` parses that as **local** time.

Fix in `crm/models/note.py` and `agent_draft.py`:

```python
return value.isoformat() + ('' if value.tzinfo else 'Z')
```

Same root cause bit the test suite at 00:50 CET: `date.today()` is local, the
column is UTC — between 00:00 and 01:00 they disagree and the filter returned
nothing. Test now builds its window from `datetime.now(timezone.utc).date()`.

**Trick:** every timestamp leaving the API carries `Z`. Every date filter is
computed in UTC. Anything else is a one-hour lie twice a year.

## 7. Postgres-only SQL silently failing on SQLite

Boot log on the preview server showed:

```
heal task dates skipped: (sqlite3.OperationalError) near "FROM": syntax error
  UPDATE tasks SET duedate = NULL ... EXTRACT(YEAR FROM duedate) < 1900 ...
```

The heal was wrapped in `try/except`, so it **never ran on the demo DB** and
nobody noticed — until a corrupted due date would have crashed `GET /api/tasks`
in front of the client.

Portable replacement:

```python
conn.execute(_text(
  "UPDATE tasks SET duedate = NULL WHERE duedate IS NOT NULL "
  "AND (duedate < :lo OR duedate > :hi)"), {"lo": "1900-01-01", "hi": "2100-12-31"})
```

**Trick:** a `try/except` around a boot-time maintenance query turns a real bug
into a log line. Baseline the boot log, not just the HTTP status codes.

## 8. The page renders before the token exists

`data-ws-id="{{ current_user.workspace.id }}"` rendered **empty**, because a page
navigation carries no `Authorization` header — the JWT only exists in
`localStorage`, which the browser sends on `fetch`, not on navigation.

Result: the Workspace tab queried `target_id=null` and printed "No notes yet"
while data existed.

Fix: the JS resolves its own workspace before the first load:

```js
ensureWorkspace().then(() => { loadNotes(); loadDrafts(); });
```

**Trick:** never render identity into a template that is fetched without
credentials. Let the client ask `/api/auth/me` once.

## 9. Cross-testing found what the builders could not

Backy reviewed Fronty's UI against the live server and found four real defects in
fifteen minutes: a CSS class collision (`mm-draft` used by both the chip and the
tray card), the UTC timestamps, an author filter silently ignored for non-numeric
input, and a composer that failed silently on tabs with no target.

**Trick:** the reviewer must *drive* the page, not read the diff. Three of those
four are invisible in a diff.

## 10. Driving the real page found the rest

I logged into `:5057` with a browser and clicked through the demo, instead of
trusting the fixture screenshots. That is how the empty `data-ws-id` (item 8) and
the floating Elisa launcher covering the last draft's Accept button were found.

**Trick:** a fixture-driven screenshot proves the design; only a live click proves
the product.

## 11. Memory discipline

Two agents in parallel OOM-killed the machine (swap 12.4/13.3 GB). Rule applied:
**one heavy agent at a time**, and short, self-contained prompts. When the test
suite was SIGKILLed mid-run, the preview server was stopped first and the suite
passed immediately (89 tests, 83 s).

## 12. Backup ladder (three rungs)

1. `git bundle create` → `~/projects/lexflow/backups/*.bundle` (local, no approval,
   verified by restoring into a throwaway repo);
2. `backup/mindmap-demo-2026-11-18` on origin — a **dead branch**: no PR, no merge,
   and the repo has no CI workflows, so nothing can build from it;
3. the demo branch itself stays local until the Monday gate.

**Trick:** a backup branch that no pipeline watches is the cheapest insurance
there is.

## 13. Demo state is part of the demo

`scripts/demo_reset.py` removes promoted agent notes and all drafts, then
`seed_mindmap_demo.py` recreates them. Without it, rehearsal consumes the very
drafts the demo needs to show — the single most likely Tuesday failure.

`scripts/demo_smoke.py` then proves, in one run: health, login, gated action,
single-use execution, human note, forged-provenance refusal, agent filter, draft
tray, accept, provenance preserved, double-accept 409.

---

## What was deleted tonight (and what was not)

- **Deleted:** 3 local branches fully merged into `lexflow_hermes_v1`
  (`feat/gantt-c`, `feat/progress-visualiser`, `feat/t021-styled-demo`) and 1
  prunable worktree pointing at `/private/tmp`. Snapshot of all 44 branches with
  SHAs saved to `~/projects/lexflow/backups/branches-before-cleanup.txt`.
- **Not deleted:** 34 worktrees, 41 branches, the 151 MB legacy Desktop copy,
  the `legacy-recovered` remote. They need your eyes, not mine.

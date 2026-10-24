# P0 — Backup and local/remote inventory (LexFlow CRM · Frappe-Gantt C)

**Gate:** P0 of `Frappe-Gantt/LexFlow-Gantt-Plan-v4-2.md` §2
**Date:** 2026-10-14
**Repo:** `/Users/olesiarasing/Projects/lexflow-crm`
**Branch:** `feat/gantt-c`
**Commit:** `82d1f09e995492e057ba9058d3e962c2820f4d57` (`docs(roadmap): daily status 2026-10-14`)
**Worktree:** single — `/Users/olesiarasing/Projects/lexflow-crm` (no linked worktrees)
**Stash:** empty
**Prepared by:** Admy (acting gate coordinator only — Owner election audit not yet run)

---

## ⛔ P0 STOP CONDITION TRIGGERED — concurrent writes to the working tree

The plan's P0 stop condition fires on "dirty or ambiguous working state … or existing
Gantt work that has not been reviewed." **Both are now true.**

Between the first inspection (11:44) and 11:48, a **separate process wrote Gantt
scaffold code into this same working tree while this gate was running.** The files did
not exist at the start of P0 and appeared during it:

| Path | State | mtime (CEST) |
|---|---|---|
| `templates/gantt.html` | untracked (new) | 11:48:33 |
| `templates/base.html` | **modified** (`+{% block head %}`, `+{% block scripts %}`) | 11:48:28 |
| `crm/routes/views.py` | **modified** (`+/gantt` route, env-gated) | 11:48:44 |
| `static/js/gantt/gantt_view.js` | untracked (new, render() is a stub) | 11:48:12 |
| `static/css/gantt/gantt.css` | untracked (new, 79 lines) | 11:47 |
| `static/vendor/frappe-gantt/1.2.2/*` | untracked (new: umd.js, css, license.txt, VENDOR.md) | 11:47:35 |

A live `smoothy_op_dir` Hermes profile process is running (pid 34733), in addition to
this session's `admy_ceo` profile. This is the "two agents editing the same file" hazard
the plan warns about (§11). **This gate task did not create or touch any of these files.**

Consequences:
1. The working tree is **dirty** (2 tracked files modified, 5 untracked paths added).
2. There is **unreviewed Gantt work** in the tree.
3. Per plan §22 and §2, P0 must **stop and report** rather than proceed to M0.
4. The P0→P4 analysis below was still completed (read-only), but **no Gantt production
   code was written or modified by this task**, and nothing here should be merged until
   the concurrent work is attributed and reviewed.

### Provenance gap in the concurrent vendoring (flag)

`static/vendor/frappe-gantt/1.2.2/frappe-gantt.umd.js` is **byte-identical** to the
library already committed on the legacy demo branch `legacy-recovered/feat/t021-diagram-gantt`
(`docs/t021-demo/frappe-gantt.umd.js`):

```
f5b9de3b618b72e675dfa7f159f2091fcf2055e62826309dfc4604d7ca649e41   (both, 48175 bytes)
```

`static/vendor/frappe-gantt/1.2.2/VENDOR.md` claims the file came from a fresh download of
`https://registry.npmjs.org/frappe-gantt/-/frappe-gantt-1.2.2.tgz` with archive SHA-256
`2e8c82de7b5423466cf28e7e6f52c163f34f2e65dedf2b0e2b5ea217529fc2c5`. The archive checksum
**cannot be verified locally** (the `.tgz` is not present), and the byte-identical match
with the legacy demo means the vendored file's true provenance is **the legacy branch, not
an independently downloaded archive.** Either re-download 1.2.2 and re-verify, or record
the legacy source honestly. (Same file size 48175 = same legacy artifact.)

Also inconsistent with the plan: the concurrent `/gantt` route is gated by a new env var
**`GANTT_VIEW_ENABLED`**, whereas the plan (§10 Layer 3) names **`GANTT_WRITE_ENABLED`**.
Decide which flag is canonical before M1.

---

## Inventory table

| location | branch/worktree | commit | relevant files | reusable | conflict | recommended action |
|---|---|---|---|---|---|---|
| `~/Projects/lexflow-crm` | `feat/gantt-c` (only worktree) | `82d1f09` | `crm/` Flask app, `templates/`, `static/`, `migrations/`, `apps/api` (TS), `packages/db` (TS) | **Yes** — the whole Flask CRM | **Yes** — tree dirty with concurrent Gantt scaffold (see stop condition) | Attribute/review concurrent writes; do not start M0 until tree is clean or the scaffold is reviewed & committed by its author |
| `legacy-recovered/feat/t021-diagram-gantt` | remote-tracking, not checked out | `87b847c` | `docs/t021-demo/{index.html, frappe-gantt.umd.js, frappe-gantt.es.js, frappe-gantt.css}` | Reference only (library copy + demo pattern) | None with `feat/gantt-c` (different branch, not in tree) | Keep as reference; **do not merge**; vendor fresh 1.2.2 from npm |
| `legacy-recovered/lexflow_hermes_v1` | remote-tracking | `82d1f09` (same tip) | roadmap/board history | Reference | None | none |
| `origin/lexflow_hermes_v1` | remote | `8c17456` (behind local) | — | — | `feat/gantt-c` is **+19 / −1** vs origin | Do not push to `main`; feature branch not yet pushed |
| `apps/api` + `packages/db` | in-tree (tracked at `82d1f09`) | — | `apps/api/src/*.ts` (4 routes: attivita/clienti/pratiche/registro), `packages/db/repositories/*.ts`, `packages/db/migrations/001_initial_schema.sql` | Partial | **No `apps/web`; no tests; no CLAUDE.md** | Do **not** use for Gantt; do **not** create `/apps/web` (plan §3) |

## Keyword search (tracked + untracked)

| keyword | hits | notes |
|---|---|---|
| `gantt` | `Frappe-Gantt/*`, `docs/LexFlow_Agentic_Roadmap.json`, **+ new concurrent scaffold files** | Roadmap JSON only mentions gantt in a status note |
| `frappe-gantt` | plan, roadmap JSON, **+ `static/vendor/frappe-gantt/1.2.2/`** | library vendored by the concurrent process |
| `apps/web` | plan only | **no `apps/web` exists** (locally or on `main`) |
| `CLAUDE.md` | plan + owner-audit prompt only | **no root `CLAUDE.md` present** |
| `startdate` | `Field-Decision-Reason_*.csv` (cases/relationship), plan | **not** in `crm/models/task.py` or any migration |
| `start_date` | `calendar_event.py`, `migrations/2b5f63c3a9e1`, `google_cal_sync.py`, `routes/{tasks,roadmap,calendar,views}.py`, `templates/calendar.html` | all calendar/event, **not** task start |
| `kanban` | `crm/__init__.py`, `crm/routes/{cases,views}.py`, many templates | live board = `/kanban` (case statuses) |
| `calendar` | `crm/models/calendar_event.py`, `crm/routes/calendar.py`, `crm/services/calendar.py`, `templates/calendar.html` | live calendar (CalendarEvent) |
| `GANTT_WRITE_ENABLED` | plan only | **not in code**; concurrent route instead uses `GANTT_VIEW_ENABLED` |
| `Admy` / `Smothy` | plan + owner-audit prompt only | no code/config references |

## Backup checkpoint

- **Snapshot 1 (pre-concurrent, partial):** `backups/gantt-p0/lexflow-crm-worktree_20261014_114712.tar.gz`
  — 5,656,606 bytes, 220 entries, SHA-256 `aade47b4530815ca0dde004bb99be19bb20a6744fd285591623186144bd51b7d`
- **Snapshot 2 (post-concurrent-state capture):** `backups/gantt-p0/lexflow-concurrent-state_20261014_114902.tar.gz`
  — captures the tree *including* the concurrent Gantt scaffold, for evidence.
- **Readable?** Yes — `tar -tzf` lists 220 entries; `tar -xzOf … ./crm/models/task.py` returns file contents.
- **Git checkpoint:** `82d1f09e995492e057ba9058d3e962c2820f4d57` (clean branch tip; the only committed state).
- **Rollback command** (see `backups/gantt-p0/ROLLBACK.md`):
  ```bash
  cd /Users/olesiarasing/Projects/lexflow-crm
  git checkout feat/gantt-c && git reset --hard 82d1f09e995492e057ba9058d3e962c2820f4d57
  # then, if needed, restore the working tree from snapshot 2:
  tar -xzf backups/gantt-p0/lexflow-concurrent-state_20261014_114902.tar.gz -C .
  ```
- **Backups are untracked** (`backups/gantt-p0/` is not committed; `*.db` already gitignored). Do not commit the 5.6 MB tarballs.

## Smallest next action

**Stop.** Have the concurrent writer either (a) commit the Gantt scaffold on its own
branch, or (b) stand down, so `feat/gantt-c` has a clean, attributable working tree —
then re-run P0. Do **not** begin M0 or write Gantt code on top of an unattributed dirty
tree.

---

## Addendum — 2026-10-14 11:50 CEST

The concurrent writer **committed its scaffold as `299c151` ("vendor frappe-gantt 1.2.2 +
read-only C view scaffold (M1)")** before this task's docs commit (`2a6d497`). So the tree
is now clean, but **M1 scaffold work is already on `feat/gantt-c` ahead of the P0–P4 gates**.
See the gate report addendum. The dirty-tree stop condition is *resolved as a commit*, but
the attribution/review requirement still stands.

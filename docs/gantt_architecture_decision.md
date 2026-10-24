# Gantt C — Architecture decision (P1)

**Gate:** P1 of `Frappe-Gantt/LexFlow-Gantt-Plan-v4-2.md` §3
**Date:** 2026-10-14 · **Branch:** `feat/gantt-c` · **Commit:** `82d1f09`
**Status:** decided from local evidence; **needs Olesia confirmation** because the plan flags this as a conflict point (§3, §14 P1).

---

## Sources read (plan §3 priority order)

1. **Local `CLAUDE.md`** — **not present** (searched tracked + untracked). No rule makes `/apps/web` active.
2. **Latest approved Master Plan** — `LexFlow_Hermes_Context.md` (Master Plan v4 Enhanced, owner Olesia). §1 stack: *Flask (REST API) + React (SPA) + PostgreSQL + Railway + JWT*. §2 "DO NOT REBUILD": backend is the **Flask REST API under `crm/`**. §5 approved schema lives in `tasks`/`cases`/`users`/`contacts`. §7 rules: don't touch `app.py`, don't edit existing migrations, Master Plan v4 wins on conflict.
3. **Latest approved Flask/backend Starter** — the in-repo Flask app factory `crm/__init__.py` (`create_app()`), blueprints, and `crm/models/*`. This *is* the shipped backend.
4. **`LexFlow_Hermes_Context.md`** — as above (the authoritative stack doc).
5. **Current entry points / deploy / tests** —
   - Entry points: `app.py` and `wsgi.py` both `from crm import create_app`.
   - Deploy: `Procfile` → `gunicorn wsgi:app`; `Procfile.crm` → `gunicorn "crm:create_app()"`; `runtime.txt` python-3.11.8; Railway.
   - Tests: **curl-based shell scripts only** (`run_local_tests.sh`, `test_runner.sh`, `test_all_endpoints.sh`). **No pytest suite, no `tests/`, no `conftest.py`.** The two main scripts hard-code `cd ~/Desktop/LexFlow/lexflow_hermes_v1` (a path that does **not** exist here) → they are **stale/non-runnable as-is**.
6. **Local-only branches/worktrees** — one worktree; extra remote-tracking branches only (see P0 inventory). No competing local architecture.

## Decision table

| candidate architecture | complete locally | deployed | tests pass | approved source | missing pieces | recommendation |
|---|---|---|---|---|---|---|
| **Flask CRM monolith (`/crm`)** — Jinja templates + vanilla JS in `static/` | **Yes** — 17 models, 20 route modules, 20 templates, calendar, kanban, tasks | **Yes** (Railway, `wsgi.py`/`crm:create_app()`) | **Unverified** — only stale curl scripts; no automated suite | `LexFlow_Hermes_Context.md` §1/§2/§5; plan §3 Flask-first override | task start date (P2); per-user authz rule (P3) | ✅ **USE** |
| Next.js/Node monorepo (`/apps/web` + `/apps/api` + `/packages/db`) | **No** — `apps/web` absent; `apps/api` is partial TS (4 routes: attivita/clienti/pratiche/registro) | No | **No** — no test setup | None active (no `CLAUDE.md`) | `apps/web`, `CLAUDE.md`, tests, full API | ❌ **DO NOT USE** — do not create `/apps/web` |
| Legacy Gantt demo (`legacy-recovered/feat/t021-diagram-gantt`) | N/A (standalone demo) | No (local-only isolated branch) | No | No | — | 📎 **Reference only** — do not merge |
| Concurrent in-tree Gantt scaffold (uncommitted, 11:47–11:48) | No (render() is a stub) | No | No | No (unreviewed) | backend `/api/gantt/tasks` | ⛔ **STOP & review** (see P0) |

## Decision (per plan §3 rule)

> "Otherwise, if the latest approved Plan's Flask-first override remains active, use the
> Flask CRM for this Gantt sprint. Do not create `/apps/web` only to host Gantt. Do not
> put Flask code in `/apps/api`."

There is **no complete local `/apps/web`** and **no `CLAUDE.md`** making it active →
the first branch of the rule is false. The Flask-first override **is** active (the Flask
CRM is the only complete, deployed, feature-bearing app) → **use the Flask CRM.**

**Active architecture for Gantt C:**

| Dimension | Decision |
|---|---|
| **Frontend** | Jinja2 server-rendered templates in `templates/` + plain JS in `static/`. **Not** Next.js. New Gantt page = `templates/gantt.html` extending `templates/base.html`, styles under `static/css/`, script under `static/js/`. |
| **Backend** | Flask app factory `crm:create_app()` (`crm/__init__.py`), blueprints under `crm/routes/`. Gantt JSON endpoint = a new blueprint/route registered in `create_app()`. |
| **Database access** | **Flask-SQLAlchemy models + query helpers** (`crm/models/*`, `crm/workspace.py::workspace_filter`). **No** repository layer, **no** `/packages/db` (that is TS and unused by the CRM). |
| **Auth pattern** | `Flask-JWT-Extended`, `@jwt_required()`. Identity = `str(user.id)` (no role/workspace claim in the JWT). Role + workspace read from DB per request. Tenant scoping via `crm/workspace.py`. |
| **Deploy target** | Railway, `gunicorn wsgi:app` (`Procfile`). |
| **Test command** | **None reliable today.** Existing scripts are curl-based and path-stale. Establish a real test command at M1 (see P4 gap). |
| **Rollback path** | `git reset --hard 82d1f09…` + snapshot restore (`backups/gantt-p0/ROLLBACK.md`). |

## Evidence / verification commands

```bash
# no /apps/web, no CLAUDE.md
test -d apps/web && echo "apps/web EXISTS" || echo "no apps/web"
test -f CLAUDE.md && echo "CLAUDE.md EXISTS" || echo "no CLAUDE.md"
# Flask is the shipped app
grep -n "create_app" app.py wsgi.py
grep -n "gunicorn" Procfile Procfile.crm
# models + blueprints
ls crm/models crm/routes
```

## Residual conflict to escalate

The plan (§3) says "current LexFlow project rules describe `/apps/web`, `/apps/api` and
`/packages/db/repositories` as the stable architecture." **No local file states this** —
`CLAUDE.md` is absent and the only authoritative doc (`LexFlow_Hermes_Context.md`) says
Flask. If the `/apps/web` rule lives in a document not present in this repo, it must be
supplied before M0. Per plan §3 ("If the documents still conflict, stop and report to
Olesia before code") — **flag for Olesia**, but the local evidence is unambiguous enough
to proceed on Flask if she confirms.

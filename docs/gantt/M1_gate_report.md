# Gantt C — M1 gate report (vendored library + read-only view scaffold)

**Gate:** M1 of `Frappe-Gantt/LexFlow-Gantt-Plan-v4-2.md` §14 — *"API contract, semantics
file, vendored library/license"* (quick approval).
**Date:** 2026-10-14 · **Branch:** `feat/gantt-c`
**Scaffold commit:** `299c151c961067ebefefd8b7c2f4fec4be82ed11`
**Author:** Fronty scaffold task (see *Model / cost* below)
**Scope delivered:** vendored Frappe Gantt 1.2.2 (checksum-verified), component scaffold
(skeleton only — no chart code), integration approach document. **No** Gantt page logic,
**no** backend endpoint, **no** schema change.

> This report covers **preparation for M1**. M1 sign-off itself must be given by the elected
> Owner / Olesia, not by this task.

---

## 1. Branch and commit

| Item | Value |
|---|---|
| Branch | `feat/gantt-c` (never pushed to `main`) |
| Base commit | `82d1f09` (`docs(roadmap): daily status 2026-10-14`) |
| Scaffold commit | `299c151c961067ebefefd8b7c2f4fec4be82ed11` |
| Gate-report commit | `e7082112c1f9816dbd3f75b86bad9c08efa31c8c` |

## 2. Changed files

| Path | Change | Notes |
|---|---|---|
| `static/vendor/frappe-gantt/1.2.2/frappe-gantt.umd.js` | **new** | verbatim from npm archive |
| `static/vendor/frappe-gantt/1.2.2/frappe-gantt.css` | **new** | verbatim |
| `static/vendor/frappe-gantt/1.2.2/license.txt` | **new** | MIT, verbatim |
| `static/vendor/frappe-gantt/1.2.2/VENDOR.md` | **new** | provenance + checksums |
| `static/css/gantt/gantt.css` | **new** | isolated styles + state/status hooks (skeleton) |
| `static/js/gantt/gantt_view.js` | **new** | config + options + fetch + states; `render()` stub |
| `templates/gantt.html` | **new** | page shell + 4 UI states (no chart) |
| `templates/base.html` | **modified** | additive `{% block head %}` / `{% block scripts %}` only |
| `crm/routes/views.py` | **modified** | `/gantt` route, gated by `GANTT_VIEW_ENABLED` (default off) |
| `docs/gantt/gantt_integration_approach.md` | **new** | integration approach (deliverable) |
| `docs/gantt/M1_gate_report.md` | **new** | this report |

Not touched: `crm/models/*`, `migrations/*`, `crm/routes/tasks.py`, any auth/payment/config,
any existing page logic.

## 3. Test output / verification evidence

| Check | Command | Result |
|---|---|---|
| Archive SHA-256 matches the plan | `shasum -a 256 frappe-gantt-1.2.2.tgz` | ✅ `2e8c82de7b5423466cf28e7e6f52c163f34f2e65dedf2b0e2b5ea217529fc2c5` — **exact match** with plan §1 |
| Archive contents | `tar -tzf frappe-gantt-1.2.2.tgz` | ✅ contains `package/dist/frappe-gantt.umd.js`, `package/dist/frappe-gantt.css`, `package/license.txt` |
| Package version | `grep version package/package.json` | ✅ `1.2.2` |
| Vendored file hashes | `shasum -a 256 static/vendor/.../*` | ✅ umd `f5b9de3b…`, css `74ccfd23…`, license `f0ee9b13…` |
| `readonly*` options exist in 1.2.2 | `grep -oE '.{140}readonly_progress.{120}' dist/frappe-gantt.umd.js` | ✅ all three present; defaults `false` (`src/defaults.js`) |
| Python syntax | editor linter on `crm/routes/views.py` | ✅ `status: ok` |
| JS syntax | editor linter on `static/js/gantt/gantt_view.js` | ✅ `status: ok` |
| Live Flask route smoke test | `python3 -c "…create_app().test_client()…"` | ⛔ **not run** — interpreter execution blocked by this environment's consent gate (see Risks) |

One verification command (repeatable):

```bash
cd /Users/olesiarasing/Projects/lexflow-crm \
  && shasum -a 256 static/vendor/frappe-gantt/1.2.2/frappe-gantt.umd.js \
  && test -f static/vendor/frappe-gantt/1.2.2/license.txt \
  && grep -q "GANTT_VIEW_ENABLED" crm/routes/views.py \
  && echo "M1 scaffold present and vendored"
```

## 4. Architecture / schema decisions

- **Architecture:** Flask + Jinja2 + client-side JSON fetch (per `docs/gantt_architecture_decision.md`, P1). No bundler ⇒ plain `<link>`/`<script>` tags. No new frontend.
- **Vendor location:** `static/vendor/frappe-gantt/1.2.2/` (Flask `static_folder` is repo-root `static/`). No CDN, no fork.
- **Schema:** **none.** No migration created or applied (plan §4, §14 P2 gate).
- **Read-only:** Layer 1 sets `readonly: true`, `readonly_dates: true`, `readonly_progress: true`, `move_dependencies: false`. No write code exists; `GANTT_WRITE_ENABLED` remains unused/reserved.
- **Endpoint contract** requested: `GET /api/gantt/tasks`, JWT-protected, workspace-scoped in the query, exact whitelist `id, name, start, end, progress, dependencies, custom_class`.

## 5. Risks and stop events

| Risk | Status | Note |
|---|---|---|
| Library behaviour drift | **cleared** | 1.2.2 confirmed; all three readonly options present |
| Provenance doubt (byte-identical to legacy demo) | **addressed** | identical bytes are expected for the same 1.2.2 build; independent archive checksum verified. See `VENDOR.md`. |
| Flag naming ambiguity (`GANTT_VIEW_ENABLED` vs plan's `GANTT_WRITE_ENABLED`) | **open — needs M1 decision** | two distinct concerns; documented in the integration doc. Confirm naming at M1. |
| No approved task start date (P2) | **open — blocks M2** | no bars can render until approved; migration not created |
| Staff visibility rule (P3) | **open — blocks M2** | endpoint scope must be approved in-query |
| Interpreter/consent gate blocked live smoke test | **open — environment** | route is default-off (404), so production behaviour is unchanged; a live test is still owed before M2 |
| Two agents editing the tree (plan §11) | **mitigated** | scaffold is now committed and attributable as `299c151` |

**Stop events hit:** none that block M1. **Stop events pending:** P2 (start date) and P3
(authorization) block M2, not M1.

## 6. Rollback steps

The change is additive and fully reversible.

```bash
cd /Users/olesiarasing/Projects/lexflow-crm
git checkout feat/gantt-c
git reset --hard 82d1f09e995492e057ba9058d3e962c2820f4d57   # base before this scaffold
# then remove the untracked scaffold artefacts if a clean tree is required:
git clean -fd static/vendor/frappe-gantt static/css/gantt static/js/gantt docs/gantt
git checkout -- templates/base.html crm/routes/views.py       # only if not already reset
```

Runtime rollback needs **no** action: `/gantt` returns 404 unless `GANTT_VIEW_ENABLED` is
truthy, and no production route, model or migration changed. Expected restoration time
< 5 minutes (plan §19).

## 7. Cost / hours / model

| Item | Value |
|---|---|
| Model route | `meituan/longcat-2.5-preview:free` (provider `nous`) |
| Provider lock | Nous Portal only — no OpenRouter/direct provider used |
| Measured cost | **$0** (free route; no paid model probes run) |
| Budget | cap **$20**; this task spent nothing against it |
| Approximate effort | ~1 scaffold session |

> ⚠️ Plan §12: *"Do not let a free/promotional model approve a gate."* This free route
> produced **preparation artefacts only**. M1 approval must come from the elected Owner /
> Olesia on an approved route, not from this model.

## 8. Exact git commands

```bash
cd /Users/olesiarasing/Projects/lexflow-crm
git add static/vendor/frappe-gantt/1.2.2/ \
        static/css/gantt/gantt.css static/js/gantt/gantt_view.js \
        templates/gantt.html templates/base.html \
        crm/routes/views.py \
        docs/gantt/gantt_integration_approach.md docs/gantt/M1_gate_report.md
git commit -m "feat(gantt): vendor frappe-gantt 1.2.2 + read-only C view scaffold (M1)"
git push -u origin feat/gantt-c        # feature branch only — NEVER main
```

## 9. Request to save important changes

Please **save / commit** the M1 scaffold and vendor artefacts so they are attributable
(plan §20). Nothing is pushed to `main`; the feature branch is safe to review.

## 10. What the backend team must provide next (blocking M2)

1. `GET /api/gantt/tasks` — JWT-protected, workspace-scoped **in the query**, exact whitelist
   `id, name, start, end, progress, dependencies, custom_class`; 401 unauth / 403 out-of-scope.
2. **Approved task start field** (P2) — nullable, additive, reversible migration; Olesia's
   approval required. Without it, no bar can render.
3. **Status → progress** implemented server-side per `docs/gantt_bar_semantics.md`
   (`pending`→0, `in_progress`→50, `done`→100, else `gantt-status-unknown`).
4. **Approved staff visibility rule** (P3) + CT1 authorization tests.
5. Exclusion rules server-side: drop missing `start`/`end` (aggregate count only), reject
   `end < start` (non-sensitive warning).

**Done | Next | Risks**

- **Done:** vendored 1.2.2 (archive + file checksums verified), scaffold committed on
  `feat/gantt-c`, integration approach documented, M1 report.
- **Next:** M1 quick approval (Owner/Olesia); confirm flag naming; then Backend builds
  `/api/gantt/tasks` and P2/P3 are approved before M2 chart code.
- **Risks:** no start date (blocks M2), authorization rule unapproved (blocks M2), flag-name
  ambiguity, and a live route smoke test still owed (interpreter gate blocked it here).

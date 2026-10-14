# Gantt integration approach — LexFlow CRM (C, internal staff, read-only)

**Status:** scaffold decision record for gate **M1** (API contract, semantics file,
vendored library/license). No Gantt chart code is implemented yet.

**Scope:** how the vendored Frappe Gantt 1.2.2 library is loaded, how data flows from the
backend to the component, and the read-only option semantics. C (internal staff) only.
D (client-safe) is a separate future phase gated by `D_READY` and is **not** covered here.

---

## 1. Active frontend architecture (P1 evidence)

The Gantt view is a **Flask + Jinja2 server-rendered shell with client-side JSON fetch**.
There is no React/Next app and no bundler in the active path.

| Evidence | Finding |
|---|---|
| `app.py`, `wsgi.py` | WSGI entry point → `crm.create_app()` (Flask factory) |
| `crm/__init__.py:183-186` | `Flask(..., template_folder=.../templates, static_folder=.../static)` |
| `templates/*.html` | Jinja templates; 12 extend `templates/base.html` |
| `crm/routes/views.py` | Page routes render templates (`/kanban`, `/calendar`, `/tasks`, …) |
| `crm/routes/*.py` | JSON blueprints registered under `/api/...` |
| `templates/tasks.html:117,126`, `templates/calendar.html:182,208` | Data loaded by browser JS: `localStorage['jwt']` → `fetch('/api/...', {Authorization: 'Bearer …'})` |
| `apps/api` (Node/TS) | Partial, **not** the active frontend; no `/apps/web` exists |

**Consequences**

1. The page shell is rendered server-side but **carries no task data** — on normal
   navigation the JWT is in `localStorage`, so the server cannot scope the request.
   All authorization therefore lives on the **JSON endpoint**, and the browser fetches it.
2. There is **no bundler** (no Vite/webpack/rollup config, no `package.json` at repo root),
   so the library is loaded with plain `<link>` / `<script>` tags, not an import.

> ⚠️ This record reflects the *current local* repository state. Plan §3 (P1) requires an
> explicit architecture decision (`docs/gantt_architecture_decision.md`) before M2. If P1
> later selects the Node/`/apps/web` path, the loader mechanism (script tag → bundler) and
> the endpoint path change, but the component contract and option semantics below stand.

---

## 2. How the vendored library is loaded

Vendored, immutable copy — see `static/vendor/frappe-gantt/1.2.2/VENDOR.md` for provenance
and checksums.

| Asset | Served URL | Loaded via |
|---|---|---|
| `frappe-gantt.umd.js` | `/static/vendor/frappe-gantt/1.2.2/frappe-gantt.umd.js` | `<script src>` (exposes global `Gantt`) |
| `frappe-gantt.css` | `/static/vendor/frappe-gantt/1.2.2/frappe-gantt.css` | `<link rel="stylesheet">` |
| `license.txt` | not served | MIT notice kept alongside the build |

**Loading mechanism — script tag, not a bundler**

- Flask's static folder is `<repo>/static`, so both files are same-origin under `/static/…`.
- `templates/gantt.html` loads them via `url_for('static', filename=…)` inside two new
  additive base blocks: `{% block head %}` (CSS) and `{% block scripts %}` (JS). Both blocks
  were added to `templates/base.html`; they are empty for every existing page, so no other
  page's output changes.
- **Order matters:** the UMD build must run before `static/js/gantt/gantt_view.js`.

**Why not a CDN / not a fork**

- Production CSP in `crm/__init__.py::add_security_headers` is
  `script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'`.
  A third-party origin is **blocked in production**, and smoke step 4 requires
  "Frappe Gantt loads from the LexFlow domain, not a CDN".
- Plan §1: vendor the built JS/CSS/license from one immutable npm archive; do not fork.

**Alternative considered (documented, not chosen):** copying the library into
`crm/static/` instead of the repo-root `static/`. Rejected because the Flask app's
`static_folder` points at the repo-root `static/` (where all existing assets live).

---

## 3. Data flow: backend → component

```
Approved task source (tasks + cases, workspace-scoped)
        │  server-side staff authorization  (plan §5)
        ▼
Read-only C adapter / repository / service      ← Backend agent, NOT YET BUILT
        │  exact field whitelist
        ▼
GET /api/gantt/tasks   (JWT-protected JSON)
        │  Authorization: Bearer <jwt from localStorage>
        ▼
static/js/gantt/gantt_view.js  →  new Gantt('#gantt', tasks, GANTT_OPTIONS)
```

**Endpoint contract requested from the backend team**

- **Method/route:** `GET /api/gantt/tasks` (read-only; no POST/PUT/PATCH in Layers 1–2).
- **Auth:** `@jwt_required()`; unauthenticated JSON → **401**, out-of-scope → **403**/empty.
- **Scope:** the same workspace/record rule approved at P3, applied **in the database
  query** — never by filtering in the browser. Do **not** reuse the unscoped
  `Task.query…all()` from `crm/routes/tasks.py`.
- **Response:** a JSON array of task objects. **Exact whitelist per object** (plan §10):

  | Key | Type | Meaning |
  |---|---|---|
  | `id` | int/str | stable task id |
  | `name` | str | task title (staff-operational) |
  | `start` | `YYYY-MM-DD` | approved **task start** field |
  | `end` | `YYYY-MM-DD` | approved **task due date** |
  | `progress` | int 0–100 | derived from the approved status map |
  | `dependencies` | str | `""` until an approved relationship exists |
  | `custom_class` | str | status/priority styling hook |

- **Must NOT appear:** description, notes, documents, tokens, unnecessary personal data
  (plan §7). CT2 fails on any extra or sensitive key.
- **Exclusion rules (server-side, plan §7):** drop tasks missing `start` or `end` and
  report an **aggregate** exclusion count; drop and warn on `end < start` (non-sensitive
  warning only). Milestones: one-day bar only if an approved milestone type exists.

`gantt_view.js` currently **fetches** this endpoint and drives the four page states; its
`render()` is an explicit stub (`throw`) until M2. It never issues a write request.

---

## 4. Read-only option semantics (`readonly`, `readonly_dates`, `readonly_progress`)

Verified against `src/defaults.js` and the built `dist/frappe-gantt.umd.js` of the
**vendored 1.2.2 archive** (all three exist; all default to `false`):

| Option | Default | Behaviour in 1.2.2 | Where enforced in the UMD |
|---|---|---|---|
| `readonly` | `false` | Master switch. Resize handles are not drawn, handle/progress positions are not updated, and bar drag-move is blocked. | `draw_resize_handles()` early-return; `update_handle_position()` early-return; `update_progressbar_position()` early-return; drag-move guarded by `!options.readonly` |
| `readonly_dates` | `false` | Blocks **date** edits: no resize handles and no bar drag-move. Does **not** suppress the progress handle on its own. | `!readonly_dates && !fixed_duration` before pushing resize handles; drag-move guarded by `!options.readonly_dates` |
| `readonly_progress` | `false` | Suppresses only the circular **progress** drag handle. | `!this.gantt.options.readonly_progress` before creating `$handle_progress` |

**Decision for Layer 1:** set **all three** to `true`
(`static/js/gantt/gantt_view.js` → `GANTT_OPTIONS`). `readonly: true` alone is sufficient in
1.2.2, but pinning all three makes intent explicit and means no partial code path can
re-enable manipulation. Layer 2 manipulation checks (plan §16) — "drag/resize controls are
absent or inert; zero client-state date changes; zero write requests" — depend on this.

**Other options pinned for this view**

| Option | Value | Reason |
|---|---|---|
| `move_dependencies` | `false` | never re-link bars on drag (library default is `true`) |
| `view_mode` | `'Day'` | default view |
| `view_mode_select` | `true` | Layer 2 Day/Week/Month switch (library default `false`) |
| `infinite_padding` | `false` | keep the timeline inside its own scroller at 375 px (plan §18) |
| `today_button` | `true` | navigation aid |
| `popup_on` | `'click'` | internal-safe popup (plan §10 Layer 2) |

Layer 3 (staff persistence) stays **off**; `GANTT_WRITE_ENABLED=false` by default and no
write code exists.

---

## 5. Files in this scaffold

| Path | Role |
|---|---|
| `static/vendor/frappe-gantt/1.2.2/frappe-gantt.umd.js` | vendored library (verbatim) |
| `static/vendor/frappe-gantt/1.2.2/frappe-gantt.css` | vendored stylesheet (verbatim) |
| `static/vendor/frappe-gantt/1.2.2/license.txt` | MIT notice (verbatim) |
| `static/vendor/frappe-gantt/1.2.2/VENDOR.md` | provenance + checksums |
| `static/css/gantt/gantt.css` | isolated, scoped page styles + state/status hooks |
| `static/js/gantt/gantt_view.js` | component skeleton: config, options, fetch, states; `render()` stub |
| `templates/gantt.html` | page shell + four UI states (no chart) |
| `crm/routes/views.py` | `/gantt` page route, gated by `GANTT_VIEW_ENABLED` (default off) |
| `templates/base.html` | **additive** `{% block head %}` / `{% block scripts %}` only |

---

## 6. What is needed from the backend team (blocking M2)

1. **`GET /api/gantt/tasks`** implementing the contract in §3 — JWT-protected,
   workspace-scoped in the query, returning the exact whitelist.
2. **An approved task start date.** The current `Task` model (`crm/models/task.py`) has
   `duedate` but **no start field**. A Gantt bar needs a real start; `createdat` must not
   be used. This is plan **P2** — requires Olesia's approval of a nullable field (e.g.
   `tasks.startdate DATE NULL`) and an additive, reversible migration before any bar can render.
3. **The approved status → progress map** in `docs/gantt/gantt_bar_semantics.md` (plan §4).
   Real Kanban statuses must be inspected; unknown values get `gantt-status-unknown` and
   fail the semantics cross-test until mapped. No map exists yet.
4. **The approved staff visibility rule** (plan **P3**) — needed for the query scope and the
   CT1 authorization tests. The existing `crm/routes/tasks.py` query is unscoped and must not be reused.

## 7. Open questions / risks

- **P1 architecture conflict is unresolved.** This scaffold assumes the Flask path because
  that is what exists locally. Plan §3 requires the decision to be recorded and, if the
  documents still conflict, escalated to Olesia before M2.
- **No start date ⇒ no bars.** Until P2 lands, the component can only show the empty state.
- **Headless verification gap:** this scaffold's Python/JS were syntax-checked by the editor
  linters; a live Flask route smoke test could not be run in this environment (interpreter
  execution was blocked). The route is default-off, so this does not affect production.

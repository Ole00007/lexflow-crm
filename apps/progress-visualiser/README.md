# Progress Visualiser

A standalone **React + Vite** app that makes **any human's project progress visually obvious**,
using the **LexFlow CRM roadmap as its data base**. It renders how far the LexFlow work has
actually progressed — a real, checkable demo of itself.

> This is the **standalone visualiser** (Kanban card `t_7048b1a6`).
> The **in-CRM Frappe Gantt** is a separate deliverable — roadmap **T-021** (card `t_f0f709f5`).
> They are kept linked, not duplicated (AGENT_RULES §9).

## Run it locally

```bash
cd apps/progress-visualiser
npm install          # first time only
npm run dev          # → http://localhost:5180/   (dev server, HMR)
# or a production build + static preview:
npm run build && npm run preview   # → http://localhost:5180/
```

Open **http://localhost:5180/**.

## What you see

- **Pulse** — a weighted-progress ring, completed/in-flight/blocked counters, a stacked
  stage bar and legend. Progress is obvious at a glance; "done & shipped" items are surfaced.
- **Flow / Gantt** — a kanban-by-stage swimlane *and* a progress Gantt. The Gantt x-axis is
  **completion %, not time** — the roadmap has no dates, so none are invented. Backlog/blocked
  items render as milestone diamonds; dependencies (`depends_on`) order the rows.
- Click any task for a read-only detail drawer (owner, priority, dependencies, blocks, notes).
- A **project switcher** (LexFlow roadmap ↔ a generic demo project) proves the visualiser is
  not LexFlow-specific — it works for *any* human's project.

## Data (single source of truth — §9)

- The only authority for LexFlow status is **`docs/LexFlow_Agentic_Roadmap.json`** (repo root `docs/`).
- `scripts/sync-data.mjs` copies it into `src/data/lexflow-roadmap.generated.json` as a **derived,
  read-only** snapshot (labelled with a `_derived` block), regenerated on every `predev`/`prebuild`.
  It is **never hand-edited and never written back** to the authority.
- **Live mode (optional):** pass `?crm=<base-url>` (or build with `VITE_CRM_BASE`) to probe a live
  LexFlow CRM `GET /api/gantt/tasks`. The status chip reports up / auth-required / down **honestly**
  and never fabricates data. (Production is currently 404 — see the roadmap `open_p0`.)

## Read-only & additive

Nothing here mutates CRM data, changes a model, or adds a migration. Drag/resize is not implemented —
showing or moving an item never executes anything.

See **DEPLOY.md** for the (unexecuted) Cloudflare Workers and Railway deployment plans.

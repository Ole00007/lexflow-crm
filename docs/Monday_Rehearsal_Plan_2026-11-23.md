# Monday 2026-11-23 — rehearsal & gate plan

Demo: **Tuesday 2026-11-24**, Avv. Tommaso Ferro, on Ole's localhost.
Branch under test: `integration/mindmap-demo` (mirror `backup/mindmap-demo-2026-11-18`).
Prod `web-production-031a6` is **not** the demo host.

---

## 09:00–11:00 — Testy (non-blocking)

Runs against `:5057` while nothing else changes. Exit criteria:

| Check | Command / evidence |
|---|---|
| Full suite green | `python -m pytest -q --ignore=tests/test_context_memory.py` → **89 passed** |
| Golden smoke | `python scripts/demo_smoke.py` → **RESULT: PASS** |
| Single-use honesty | accept a draft twice → second returns **409** |
| Tenant isolation | a second workspace's user cannot list or accept the first workspace's drafts (**403**) |
| No dead send | grep for mail/whatsapp in `templates/mindmap.html`, `static/js/mindmap/*` → none |

Testy writes findings as Kanban comments; **no code edits after 11:00 without Ole's word**.

## 11:00–15:30 — Buffer / fixes only if the gate demands

If Testy finds a blocker, the fix lands on `integration/mindmap-demo` and the
suite is re-run. Nothing new is added. Admy re-reviews the diff.

## 16:00 — Ole's manual review on `:5057`

```bash
cd ~/projects/lexflow/lexflow-crm-wt-integration
python scripts/demo_reset.py && python seed_mindmap_demo.py --workspace lexflow
./run_demo.sh            # or confirm the running process is on this commit
```

He walks: Mindmap (notes + tray) → accept → Elisa propose → confirm → kill switch.
Design gate: **his review is the deploy precondition**, not a formality.

## 18:00 — Merge decision (Admy)

Admy rules on merging `integration/mindmap-demo` → `lexflow_hermes_v1` using the
six numbered conditions from the original plan. Merge is a **separate, verified
step**; it does not authorise a deploy by itself.

## 19:00 — Push/deploy **only on Ole's explicit per-push authorisation**

If granted, in this order:

1. `git merge --no-ff integration/mindmap-demo` into `lexflow_hermes_v1`
2. push `lexflow_hermes_v1` (this is the deploy-triggering branch)
3. verify Railway build → `/health` → `/agent` still `404` unless `AGENT_ENABLED` is set
4. rollback path recorded before the push: previous good commit + Railway redeploy-previous

**If not granted:** the demo stays on localhost, which is the approved plan.

---

## Tuesday 06:00–10:00 — freeze

- No commits after this point.
- `demo_reset.py` → one full dry run → **do not touch code again**.
- Have `docs/demo-shots/` open in a second window as fallback (Backy's point: the
  likeliest failure on the day is state drift, not a missing feature).

## Known-good facts (19 Nov, 00:xx)

- 89 tests pass; smoke PASS; all nav routes 200 (`/`, `/dashboard`, `/contacts`,
  `/kanban`, `/mindmap`, `/calendar`, `/tasks`, `/workspace`, `/agent`,
  `/settings`, `/admin`, `/admin/panel`)
- 2 drafts proposed, 3 human notes seeded, kill switch released
- Backup `backup/mindmap-demo-2026-11-18` == local `75569c5`

## Open decisions (Ole)

1. Heritage deletion batch — 34 worktrees / 41 branches / 151 MB legacy Desktop copy.
2. Whether to flip prod **Monday 19:00** or keep the demo localhost-only.

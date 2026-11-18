# Preview: ROI calculator, calendar, task filters — NOT MERGED

These screenshots come from the work that was **deliberately excluded** from the
Tuesday demo build. Nothing here is on `integration/mindmap-demo` and nothing is
on `backup/mindmap-demo-2026-11-18`.

| | |
|---|---|
| Branch | `feat/elisa-hardening` @ `0b3d3db` |
| Worktree | `/Users/olesiarasing/projects/lexflow/lexflow-crm-wt-preview` |
| Boot script | `~/.hermes/profiles/smoothy_op_dir/cache/scratch/preview_boot_5058.py` |
| Port | `127.0.0.1:5058` (demo stays on `:5057`) |
| DB | `~/.hermes/profiles/smoothy_op_dir/cache/scratch/preview_roi.db` |
| Feature flag | `ROI_CALCULATOR_ENABLED=1` (otherwise `/roi-calculator` → 404) |
| Size vs demo branch | 55 files, +4,223 / −1,805 |

## Boot

```bash
cd ~/projects/lexflow/lexflow-crm-wt-preview
ROI_CALCULATOR_ENABLED=1 ~/projects/lexflow/lexflow-crm-wt-hmerge/local_venv/bin/python \
  ~/.hermes/profiles/smoothy_op_dir/cache/scratch/preview_boot_5058.py
```

Then open `http://127.0.0.1:5058/roi-calculator`, `/calendar`, `/tasks`.

## Why it is not merged

- migration `l3f4a5b6c7d8` (roi_progress) is **not** in the demo chain — merging would
  create a second Alembic head or break the revision graph days before the demo;
- `static/js/filters/task_filters.js` (+418) is built against kanban/gantt template
  edits that would stay behind, so a cherry-pick loads against mismatched DOM;
- the design gate requires Ole's UI review before any design change deploys.

Admy and Backy both ruled: keep it excluded, show it separately if Ole wants to see it.

## Frames

- `preview-roi.png` — `/roi-calculator` (public, no auth, no tracking)
- `preview-calendar.png` — month grid, Nov 2026, one seeded hearing on the 19th
- `preview-tasks.png` — tasks list with the shared filter component

# Rollback checkpoint — Gantt C prerequisites (P0–P4)

**Created:** 2026-10-14 · **Branch:** `feat/gantt-c` · **Commit:** `82d1f09e995492e057ba9058d3e962c2820f4d57`

## What is backed up

| Artifact | Path | SHA-256 |
|---|---|---|
| Worktree snapshot (pre-concurrent) | `backups/gantt-p0/lexflow-crm-worktree_20261014_114712.tar.gz` | `aade47b4530815ca0dde004bb99be19bb20a6744fd285591623186144bd51b7d` |
| Worktree snapshot (incl. concurrent scaffold) | `backups/gantt-p0/lexflow-concurrent-state_20261014_114902.tar.gz` | (verify with `shasum -a 256`) |

Both exclude `.git/`, `.venv-gantt/`, `node_modules/`. Both verified readable with `tar -tzf`.

## Rollback (git — restores committed state)

```bash
cd /Users/olesiarasing/Projects/lexflow-crm
git checkout feat/gantt-c
git reset --hard 82d1f09e995492e057ba9058d3e962c2820f4d57
git clean -fd            # only if you intend to remove untracked files — REVIEW FIRST
```

> ⚠️ `git clean -fd` will delete the untracked concurrent Gantt scaffold and
> `backups/gantt-p0/`. Run `git clean -n` first. Prefer restoring from a snapshot instead.

## Rollback (filesystem — restores an arbitrary snapshot)

```bash
cd /Users/olesiarasing/Projects/lexflow-crm
tar -xzf backups/gantt-p0/lexflow-concurrent-state_20261014_114902.tar.gz -C .
```

## Verification command

```bash
shasum -a 256 backups/gantt-p0/*.tar.gz && \
tar -tzf backups/gantt-p0/lexflow-concurrent-state_20261014_114902.tar.gz | wc -l
```

## Note

This task (P0–P4) wrote **only documentation** under `docs/` plus this file. It did not
touch `crm/`, `templates/`, or `static/`. A concurrent process created the Gantt scaffold
in the working tree during P0 — see `docs/gantt_p0_inventory.md`.

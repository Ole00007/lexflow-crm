#!/usr/bin/env python3
"""Machine-validate the LexFlow tracker against its own rules.

Run at the END of the daily status job. Exit 0 = clean, exit 1 = violations
(the job must then fail with [CRON_FAILURE] instead of stamping a date).

Checks
  A. report_rule compliance  - every done/deployed node carries evidence
  B. card <-> roadmap agreement - kanban_card_map ids exist and agree
  C. one-clone / one-tracker guard - no second roadmap copy on disk
  D. last_updated is recent

Authority: docs/LexFlow_Agentic_Roadmap.json (this repo). Read-only.
No model, provider or other environment-specific literal is embedded (Rule §12).
"""
import json, os, sys, sqlite3, datetime, pathlib, subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]
ROADMAP = REPO / "docs" / "LexFlow_Agentic_Roadmap.json"
KANBAN = pathlib.Path.home() / ".hermes" / "kanban.db"
HOME = pathlib.Path.home()

# roadmap column -> kanban statuses that are consistent with it
ALLOWED = {
    "backlog":              {"todo", "ready", "triage"},
    "in_progress":          {"running", "ready"},
    "blocked":              {"blocked", "todo", "ready"},
    "awaiting_confirmation": {"blocked", "todo", "ready"},
    "local_verified":       {"ready", "todo", "done", "blocked"},
    "deployed":             {"done"},
    "done":                 {"done", "archived"},
}
EVIDENCE_COLUMNS = {"done", "deployed"}


def _git_common_dir(path):
    """git common dir of the repo containing `path` (None if not a git checkout)."""
    try:
        out = subprocess.run(["git", "-C", str(path), "rev-parse",
                              "--path-format=absolute", "--git-common-dir"],
                             capture_output=True, text=True, timeout=15)
        if out.returncode != 0:
            return None
        return os.path.realpath(out.stdout.strip())
    except Exception:
        return None


def load_cards():
    if not KANBAN.exists():
        return None
    # The board is WAL-mode; a strict mode=ro URI fails with "unable to open
    # database file" when no -shm already exists. Fall back to a normal
    # connection - this script only ever issues SELECTs.
    for attempt in ("ro", "ro_immutable", "rw"):
        try:
            if attempt == "ro":
                con = sqlite3.connect(f"file:{KANBAN}?mode=ro", uri=True, timeout=10)
            elif attempt == "ro_immutable":
                con = sqlite3.connect(f"file:{KANBAN}?mode=ro&immutable=1",
                                      uri=True, timeout=10)
            else:
                con = sqlite3.connect(str(KANBAN), timeout=10)
            rows = con.execute("SELECT id, status FROM tasks").fetchall()
            con.close()
            return {r[0]: r[1] for r in rows}
        except sqlite3.Error:
            continue
    return None


def main():
    v = []
    d = json.loads(ROADMAP.read_text())
    nodes = {t["id"]: t for t in d["tasks"]}

    # A. report_rule compliance
    for tid, t in nodes.items():
        if t.get("column") not in EVIDENCE_COLUMNS:
            continue
        ds = t.get("deploy_status")
        ok = (ds == "local" and t.get("local_preview_url")) or \
             (ds == "deployed" and t.get("prod_url") and t.get("commit_hash"))
        if not ok:
            v.append(f"[A] {tid} column={t['column']} but deploy_status={ds!r} lacks "
                     f"local_preview_url / (prod_url+commit_hash)")

    # B. card <-> roadmap agreement
    cards = load_cards()
    cmap = d.get("kanban_card_map", {})
    if cards is None:
        v.append("[B] kanban.db not found - open cards unverifiable")
    else:
        for tid, cid in cmap.items():
            if cid not in cards:
                v.append(f"[B] {tid} -> card {cid} does not exist on the board")
                continue
            col = nodes.get(tid, {}).get("column")
            if col not in ALLOWED:
                continue
            if cards[cid] not in ALLOWED[col]:
                v.append(f"[B] {tid} roadmap={col} vs card {cid}={cards[cid]} "
                         f"(allowed {sorted(ALLOWED[col])})")
        TERMINAL = {"done", "deployed"}
        for tid, t in nodes.items():
            if tid not in cmap and t.get("column") not in TERMINAL:
                v.append(f"[B] {tid} unfinished (column={t.get('column')}) has no card")

    # C. one-clone / one-tracker guard
    # A second copy only counts as a parallel tracker when it belongs to a
    # DIFFERENT repo (or no repo). Checkouts of this same repo - git worktrees
    # for feature branches - are derived by construction; they are tracked by
    # git, not an independent registry (Rule §9).
    repo_common = _git_common_dir(REPO)
    roots = [HOME / "projects", HOME / "Obsidian", HOME / "Downloads", HOME / "Desktop"]
    copies = []
    for root in roots:
        if root.exists():
            copies += [p for p in root.rglob("LexFlow_Agentic_Roadmap.json")
                       if "_archive" not in p.parts and "Trash" not in p.parts]
    seen, worktree_copies = set(), 0
    for p in copies:
        if repo_common and _git_common_dir(p.parent) == repo_common:
            worktree_copies += 1
            continue
        seen.add(os.path.realpath(p))
    if len(seen) > 1:
        v.append("[C] more than one tracker on disk: " + ", ".join(sorted(seen)))

    # D. freshness
    age = (datetime.date.today() - datetime.date.fromisoformat(d["last_updated"])).days
    if age > 1:
        v.append(f"[D] last_updated={d['last_updated']} is {age} days stale")

    if v:
        print(f"ROADMAP VALIDATION FAILED - {len(v)} violation(s):")
        for x in v:
            print("  -", x)
        return 1
    print(f"ROADMAP VALIDATION OK - {len(nodes)} nodes, {len(cmap)} cards, "
          f"last_updated={d['last_updated']}")
    if worktree_copies:
        print(f"  (info) {worktree_copies} same-repo worktree checkout(s) of this "
              f"tracker ignored by the one-tracker guard")
    if seen:
        print(f"  (info) canonical copy: {sorted(seen)[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

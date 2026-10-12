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
import json, os, sys, sqlite3, datetime, pathlib

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


def load_cards():
    if not KANBAN.exists():
        return None
    con = sqlite3.connect(f"file:{KANBAN}?mode=ro", uri=True)
    return {r[0]: r[1] for r in con.execute("SELECT id, status FROM tasks")}


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
    roots = [HOME / "projects", HOME / "Obsidian", HOME / "Downloads", HOME / "Desktop"]
    copies = []
    for root in roots:
        if root.exists():
            copies += [p for p in root.rglob("LexFlow_Agentic_Roadmap.json")
                       if "_archive" not in p.parts and "Trash" not in p.parts]
    seen = {os.path.realpath(p) for p in copies}
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
    return 0


if __name__ == "__main__":
    sys.exit(main())

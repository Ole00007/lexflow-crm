"""Reset the local demo DB to a clean pre-demo state.

Removes promoted agent notes and all drafts, then lets the seed scripts re-add
them. Human notes are untouched. Dev/demo databases only.

Usage:
  python scripts/demo_reset.py
  python seed_mindmap_demo.py --workspace lexflow
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crm import create_app
from crm.extensions import db
from crm.models.agent_draft import AgentDraft
from crm.models.note import Note


def main() -> int:
    app = create_app()
    with app.app_context():
        notes = Note.query.filter_by(source="agent").delete()
        drafts = AgentDraft.query.delete()
        db.session.commit()
        print(f"removed {notes} promoted agent note(s) and {drafts} draft(s)")
        print("now run: python seed_mindmap_demo.py --workspace lexflow")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

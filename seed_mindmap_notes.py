"""Seed human Mindmap notes for the demo (idempotent).

Distinct from seed_mindmap_demo.py (which Backy owns and which seeds agent
DRAFTS). This one seeds only HUMAN notes, so the demo starts with a realistic
stream that a lawyer can recognise — and so the 'Agent' filter is provably empty
before any draft is promoted.

Usage:
  python seed_mindmap_notes.py --workspace lexflow
"""
from __future__ import annotations

import argparse

from crm import create_app
from crm.extensions import db
from crm.models.note import Note
from crm.models.task import Task
from crm.models.user import User
from crm.models.workspace import Workspace

HUMAN_NOTES = [
    ("workspace", "Kick-off con lo studio: la prima priorità è la visibilità sulle scadenze della settimana."),
    ("workspace", "Tommaso prefers a single view per matter — evaluate before adding new menus."),
    ("task", "Cliente ha chiesto aggiornamento entro venerdì; verificare i documenti mancanti."),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default="lexflow")
    ap.add_argument("--email", default="olesya00007@yahoo.com")
    a = ap.parse_args()

    app = create_app()
    with app.app_context():
        ws = Workspace.query.filter_by(slug=a.workspace).first()
        if not ws:
            print(f"ERROR: workspace '{a.workspace}' not found")
            return 1
        author = User.query.filter_by(email=a.email).first()
        if not author:
            print(f"ERROR: author '{a.email}' not found")
            return 1

        task = Task.query.filter_by(caseid=1, is_deleted=False).first()
        created = 0
        for target_type, content in HUMAN_NOTES:
            target_id = ws.id if target_type == "workspace" else (task.id if task else None)
            if target_id is None:
                continue
            exists = Note.query.filter_by(
                workspace_id=ws.id, target_type=target_type, target_id=target_id, content=content
            ).first()
            if exists:
                continue
            db.session.add(Note(
                workspace_id=ws.id,
                author_id=author.id,
                target_type=target_type,
                target_id=target_id,
                content=content,
                source="human",
            ))
            created += 1
        db.session.commit()
        print(f"seeded {created} human note(s) in workspace '{a.workspace}' (task target: {task.id if task else 'none'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Seed demo deadlines - idempotent, local DB only."""
import os, sys
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("DATABASE_URL", "sqlite:///crm_local.db")
os.environ.setdefault("SECRET_KEY", "dev-seed-key")
from crm import create_app
from crm.extensions import db
from crm.models.task import Task
from crm.models.case import Case
from crm.models.deadline import Deadline
from crm.models.workspace import Workspace

def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        ws = Workspace.query.filter_by(slug="lexflow").first()
        if not ws:
            ws = Workspace.query.first()
        if not ws:
            print("FAIL")
            return
        today = date.today()
        ts = [
            "T-021: Styled Gantt demo",
            "T-022: Outstanding Gantt tasks",
            "T-028: Real deadline dates",
        ]
        for i, t in enumerate(ts):
            task = Task.query.filter_by(title=t, workspace_id=ws.id, is_deleted=False).first()
            if task:
                task.duedate = today + timedelta(days=(i+1)*3)
                print(f"  Set: {t} -> {task.duedate}")
        db.session.commit()
        print("Done")

if __name__ == "__main__":
    main()

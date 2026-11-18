"""Seed the Mindmap demo: 2 Elisa drafts (one task note, one project/workspace note), NO notes.

Usage: python seed_mindmap_demo.py --workspace lexflow
Idempotent (re-run does not duplicate). Throwaway dev DBs only.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta

from crm import create_app
from crm.extensions import db
from crm.models.agent_draft import AgentDraft
from crm.models.task import Task
from crm.models.user import User
from crm.models.workspace import Workspace

ADMIN_EMAIL = 'olesya00007@yahoo.com'


def seed(slug: str) -> int:
    app = create_app()
    with app.app_context():
        db.create_all()
        ws = Workspace.query.filter_by(slug=slug).first()
        if not ws:
            print(f'ERROR: workspace {slug!r} missing')
            return 1
        owner = User.query.filter_by(email=ADMIN_EMAIL, workspace_id=ws.id).first() \
            or User.query.filter_by(workspace_id=ws.id).order_by(User.id).first()
        task = Task.query.filter_by(workspace_id=ws.id, is_deleted=False).order_by(Task.id).first()
        if not task:
            print(f'ERROR: no task in workspace {slug!r}; run seed_agent_demo.py first')
            return 1
        specs = [
            ('task', task.id,
             f'Suggested next step for "{task.title}": request the missing documents from the client and set a reminder 3 days out.',
             'Task has had no activity and its due date is approaching.'),
            ('workspace', ws.id,
             'Project note: three open tasks have no assignee. Consider assigning owners before the weekly review.',
             'Observed unassigned open tasks in this workspace.'),
        ]
        created = 0
        for target_type, target_id, content, evidence in specs:
            if AgentDraft.query.filter_by(workspace_id=ws.id, target_type=target_type,
                                          target_id=target_id, content=content).first():
                continue
            now = datetime.utcnow()
            db.session.add(AgentDraft(
                workspace_id=ws.id, target_type=target_type, target_id=target_id, content=content,
                origin='human_request', requested_by=owner.id if owner else None,
                requested_by_agent='elisa', evidence=evidence, status='proposed',
                expires_at=now + timedelta(days=7), created_at=now, updated_at=now))
            created += 1
        db.session.commit()
        print(f'seeded {created} draft(s) in workspace {slug!r}; '
              f'proposed now: {AgentDraft.query.filter_by(workspace_id=ws.id, status="proposed").count()}')
        return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace', default='lexflow')
    sys.exit(seed(ap.parse_args().workspace))

from __future__ import annotations

"""Local demo seed for the in-app agent spike.

Idempotent. Safe for throwaway dev DBs only.
"""

import os
from datetime import date, timedelta
from pathlib import Path

from crm import create_app
from crm.extensions import db
from crm.models.case import Case
from crm.models.contact import Contact
from crm.models.firm_team import FirmTeamMember
from crm.models.task import Task
from crm.models.task_assignee import TaskAssignee, TaskFlag
from crm.models.user import User
from crm.models.workspace import Workspace


MATTTER_TITLE = 'Rasing separazione'
VAULT_REF = '_Inbox/LexFlow-Agent-Spike/Rasing-separazione'


def _d(days: int):
    return date.today() + timedelta(days=days)


def _ensure_vault_docs():
    root = os.environ.get('LEXFLOW_VAULT_DIR', '').strip()
    if not root:
        return
    base = Path(root) / VAULT_REF
    base.mkdir(parents=True, exist_ok=True)
    doc = base / '01-brief.md'
    if not doc.exists():
        doc.write_text('# Rasing separazione\n\nDemo dossier for the agent spike.\n', encoding='utf-8')


def seed_demo():
    app = create_app()
    with app.app_context():
        ws = Workspace.query.filter_by(slug='lexflow').first()
        if not ws:
            print('ERROR: lexflow workspace missing')
            return
        admin = User.query.filter_by(email='olesya00007@yahoo.com').first()
        if not admin:
            print('ERROR: superadmin missing')
            return

        members = {}
        for name, role, email in (
            ('Elena Romanelli', 'avvocato', 'e.romanelli@studio.example'),
            ('Olesia Rasing', 'office', 'o.rasing@studio.example'),
            ('Elisa', 'assistente', 'elisa@studio.example'),
        ):
            member = FirmTeamMember.query.filter_by(workspace_id=ws.id, name=name).first()
            if not member:
                member = FirmTeamMember(workspace_id=ws.id, name=name, role=role, email=email, is_active=True)
                db.session.add(member)
                db.session.flush()
            members[name] = member

        contact = Contact.query.filter_by(workspace_id=ws.id, email='rasing@example.it').first()
        if not contact:
            contact = Contact(workspace_id=ws.id, fullname='Rasing (client)', email='rasing@example.it', status='lead')
            db.session.add(contact)
            db.session.flush()

        case = Case.query.filter_by(workspace_id=ws.id, title=MATTTER_TITLE, is_deleted=False).first()
        if not case:
            case = Case(
                workspace_id=ws.id,
                contactid=contact.id,
                ownerid=admin.id,
                assignedto=admin.id,
                title=MATTTER_TITLE,
                casetype='Family law',
                status='In Progress',
                priority='High',
                openedat=_d(-7),
                duedate=_d(10),
                case_no='FAM-01',
            )
            db.session.add(case)
            db.session.flush()

        task = Task.query.filter_by(workspace_id=ws.id, caseid=case.id, title='Collect client documents', is_deleted=False).first()
        if not task:
            task = Task(
                workspace_id=ws.id,
                caseid=case.id,
                userid=admin.id,
                title='Collect client documents',
                status='pending',
                priority='High',
                startdate=_d(-2),
                duedate=_d(3),
                vault_ref=VAULT_REF,
            )
            db.session.add(task)
            db.session.flush()
        else:
            task.vault_ref = VAULT_REF

        TaskAssignee.query.filter_by(task_id=task.id).delete()
        db.session.add(TaskAssignee(workspace_id=ws.id, task_id=task.id, team_member_id=members['Elena Romanelli'].id, role='case_owner'))
        db.session.add(TaskAssignee(workspace_id=ws.id, task_id=task.id, team_member_id=members['Olesia Rasing'].id, role='docs_supply'))
        db.session.add(TaskAssignee(workspace_id=ws.id, task_id=task.id, team_member_id=members['Elisa'].id, role='legal_assistant'))

        if not TaskFlag.query.filter_by(task_id=task.id).first():
            db.session.add(TaskFlag(
                workspace_id=ws.id,
                task_id=task.id,
                raised_by_agent='lexflow-agent',
                target_member_id=members['Elena Romanelli'].id,
                reason='Demo flag for the spike',
                status='open',
            ))

        db.session.commit()
        _ensure_vault_docs()
        print(f'seeded demo matter "{MATTTER_TITLE}" with task {task.id}')


if __name__ == '__main__':
    seed_demo()

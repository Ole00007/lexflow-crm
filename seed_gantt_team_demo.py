"""Demo data for the Gantt team-roles feature (local/dev only, idempotent).

Creates the Studio team (E. Romanelli = lawyer, O. Rasing = docs, Elisa = legal
assistant) in the default 'lexflow' workspace and a 'Rasing separazione' matter whose
tasks carry per-role assignees, a vault documents folder and one open lawyer flag.

Run (same env as seed_gantt_data.py):  python seed_gantt_team_demo.py
"""
from datetime import date, timedelta

from crm import create_app
from crm.extensions import db
from crm.models.case import Case
from crm.models.contact import Contact
from crm.models.deadline import Deadline
from crm.models.firm_team import FirmTeamMember
from crm.models.task import Task
from crm.models.task_assignee import TaskAssignee, TaskFlag
from crm.models.user import User
from crm.models.workspace import Workspace

VAULT_REF = '_Inbox/Rasing-separazione-docs'
TEAM = [('Elena Romanelli', 'avvocato', 'e.romanelli@studio.example'),
        ('Olesia Rasing', 'office', 'o.rasing@studio.example'),
        ('Elisa', 'assistente', 'elisa@studio.example')]


def d(n):
    return date.today() + timedelta(days=n)


def main():
    app = create_app()
    with app.app_context():
        ws = Workspace.query.filter_by(slug='lexflow').first()
        admin = User.query.filter_by(email='olesya00007@yahoo.com').first()
        if not ws or not admin:
            print('ERROR: lexflow workspace / superadmin missing'); return
        members = {}
        for name, role, email in TEAM:
            m = FirmTeamMember.query.filter_by(workspace_id=ws.id, name=name).first()
            if not m:
                m = FirmTeamMember(workspace_id=ws.id, name=name, role=role, email=email, is_active=True)
                db.session.add(m); db.session.flush()
            members[name.split()[-1]] = m           # Romanelli / Rasing / Elisa
        title = 'Rasing separazione'
        case = Case.query.filter_by(title=title, is_deleted=False).first()
        if case is None:
            ct = Contact.query.filter_by(email='rasing@example.it').first() or Contact(
                fullname='Rasing (client)', email='rasing@example.it', status='active', workspace_id=ws.id)
            db.session.add(ct); db.session.flush()
            case = Case(workspace_id=ws.id, contactid=ct.id, ownerid=admin.id, assignedto=admin.id, title=title,
                        casetype='Family law', status='In Progress', priority='High', openedat=d(-10),
                        duedate=d(10), case_no='FAM-01')
            db.session.add(case); db.session.flush()
        spec = [  # title, start, end, status, deps(index), roles
            ('Collect client documents (certificati, redditi)', -6, 2, 'in_progress', [],
             {'case_owner': 'Romanelli', 'docs_supply': 'Rasing', 'legal_assistant': 'Elisa'}),
            ('Draft ricorso per separazione', 1, 6, 'pending', [0],
             {'case_owner': 'Romanelli', 'legal_assistant': 'Elisa'}),
            ('Lawyer review & signature', 6, 8, 'pending', [1],
             {'case_owner': 'Romanelli', 'lawyer_review': 'Romanelli'}),
            ('File at Tribunale (deposito telematico)', 9, 10, 'pending', [2],
             {'case_owner': 'Romanelli', 'docs_supply': 'Rasing'}),
        ]
        rows = []
        for i, (tt, s, e, st, deps, roles) in enumerate(spec):
            full = f'{tt}'
            t = Task.query.filter_by(caseid=case.id, title=full, is_deleted=False).first()
            if t is None:
                t = Task(workspace_id=ws.id, caseid=case.id, userid=admin.id, title=full, status=st,
                         priority='High', startdate=d(s), duedate=d(e))
                db.session.add(t); db.session.flush()
            t.vault_ref = VAULT_REF
            rows.append(t)
            TaskAssignee.query.filter_by(task_id=t.id).delete()
            for role, who in roles.items():
                db.session.add(TaskAssignee(workspace_id=ws.id, task_id=t.id, team_member_id=members[who].id, role=role))
        for t, (_, _, _, _, deps, _) in zip(rows, spec):
            if deps:
                t.depends_on = ','.join(str(rows[k].id) for k in deps)
        # Legal deadlines on the matter (these reach the Calendar via CALENDAR_DEADLINES_ENABLED)
        for title_, days, kind, prio in (('Termine integrazione documenti', 2, 'termine_perentorio', 'High'),
                                         ('Deposito ricorso (telematico)', 10, 'deposito', 'High'),
                                         ('Udienza presidenziale', 38, 'udienza', 'High')):
            if not Deadline.query.filter_by(caseid=case.id, title=title_, is_deleted=False).first():
                db.session.add(Deadline(workspace_id=ws.id, caseid=case.id, title=title_, deadline_date=d(days),
                                        deadline_type=kind, status='pending', priority=prio))
        if not TaskFlag.query.filter_by(task_id=rows[2].id).first():
            db.session.add(TaskFlag(workspace_id=ws.id, task_id=rows[2].id, raised_by_agent='lexflow-agent',
                                    target_member_id=members['Romanelli'].id, status='open',
                                    reason='Draft ready: lawyer must review before filing'))
        db.session.commit()
        print(f'seeded: team={len(members)} members, matter "{title}" with {len(rows)} tasks')


if __name__ == '__main__':
    main()

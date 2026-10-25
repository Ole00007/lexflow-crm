"""Demo data for the Insights feature (WS-D) — local/dev only, idempotent.

Creates ~40 tasks over 12 weeks across 8 matters in the superadmin ('lexflow')
workspace plus a second tenant workspace, so the Insights charts look alive.
No real client data — all names/emails are synthetic placeholders.

Run (same env as seed_gantt_team_demo.py):  python seed_insights_demo.py
"""
from datetime import date, timedelta, datetime

from crm import create_app
from crm.extensions import db
from crm.models.case import Case
from crm.models.contact import Contact
from crm.models.firm_team import FirmTeamMember
from crm.models.task import Task
from crm.models.task_assignee import TaskAssignee, TaskFlag
from crm.models.user import User
from crm.models.workspace import Workspace

TEAM = [('Elena Romanelli', 'avvocato', 'e.romanelli@studio.example'),
        ('Olesia Rasing', 'office', 'o.rasing@studio.example'),
        ('Elisa', 'assistente', 'elisa@studio.example')]

# (matter title, status, opened_days_ago, casetype)
MATTERS = [
    ('Rasing separazione', 'In Progress', 80, 'Family law'),
    ('Contratto locazione', 'Active', 60, 'Real Estate'),
    ('Recupero credito', 'In Progress', 45, 'Debt Collection'),
    ('Contratto lavoro', 'Active', 30, 'Employment'),
    ('Acquisto immobile', 'Intake', 20, 'Real Estate'),
    ('Divorzio consensuale', 'In Progress', 12, 'Family law'),
    ('Vertenza fornitura', 'Active', 5, 'Commercial'),
    ('Successione ereditaria', 'Intake', 2, 'Family law'),
]

# (title, status, start_days_ago, due_days_from_now, role)
TASKS = [
    ('Raccogli documenti', 'done', 78, -70, 'docs_supply'),
    ('Redigere bozza', 'done', 70, -60, 'legal_assistant'),
    ('Revisione avvocato', 'done', 60, -50, 'lawyer_review'),
    ('Deposito telematico', 'done', 50, -40, 'docs_supply'),
    ('Aggiornare fascicolo', 'in_progress', 30, 5, 'legal_assistant'),
    ('Verifica documenti', 'pending', 10, 12, 'docs_supply'),
    ('Preparare udienza', 'pending', 5, 20, 'case_owner'),
    ('Raccogli documenti', 'done', 58, -50, 'docs_supply'),
    ('Bozza contratto', 'done', 50, -42, 'legal_assistant'),
    ('Revisione finale', 'done', 42, -35, 'lawyer_review'),
    ('Invio a controparte', 'done', 35, -28, 'docs_supply'),
    ('Rinnovo contratto', 'in_progress', 20, 8, 'case_owner'),
    ('Raccogli documenti', 'done', 44, -36, 'docs_supply'),
    ('Diffida', 'done', 36, -28, 'legal_assistant'),
    ('Azione legale', 'in_progress', 28, 6, 'lawyer_review'),
    ('Notifica esito', 'pending', 8, 15, 'docs_supply'),
    ('Raccogli documenti', 'done', 29, -22, 'docs_supply'),
    ('Bozza contratto', 'done', 22, -15, 'legal_assistant'),
    ('Revisione avvocato', 'done', 15, -8, 'lawyer_review'),
    ('Firma contratto', 'in_progress', 8, 4, 'case_owner'),
    ('Raccogli documenti', 'done', 19, -12, 'docs_supply'),
    ('Verifica titolo', 'in_progress', 12, 3, 'legal_assistant'),
    ('Preliminare', 'pending', 6, 10, 'case_owner'),
    ('Raccogli documenti', 'done', 11, -5, 'docs_supply'),
    ('Bozza accordo', 'done', 5, 2, 'legal_assistant'),
    ('Revisione avvocato', 'in_progress', 2, 6, 'lawyer_review'),
    ('Raccogli documenti', 'done', 4, 0, 'docs_supply'),
    ('Bozza contratto', 'in_progress', 1, 5, 'legal_assistant'),
    ('Raccogli documenti', 'pending', 1, 7, 'docs_supply'),
    ('Bozza atto', 'pending', 0, 9, 'legal_assistant'),
]


def d(n):
    return date.today() + timedelta(days=n)


def dt(n):
    return datetime.combine(d(n), datetime.min.time())


def main():
    app = create_app()
    with app.app_context():
        ws = Workspace.query.filter_by(slug='lexflow').first()
        admin = User.query.filter_by(email='olesya00007@yahoo.com').first()
        if not ws or not admin:
            print('ERROR: lexflow workspace / superadmin missing'); return

        # second tenant workspace (isolated — charts must never mix)
        other = Workspace.query.filter_by(slug='insights-tenant').first()
        if not other:
            other = Workspace(slug='insights-tenant', name='Insights Tenant', is_active=True)
            db.session.add(other); db.session.flush()
        other_admin = User.query.filter_by(email='tenant@insights.example').first()
        if not other_admin:
            other_admin = User(workspace_id=other.id, email='tenant@insights.example', role='admin')
            other_admin.set_password('Tenant12345!')
            db.session.add(other_admin); db.session.flush()

        members = {}
        for name, role, email in TEAM:
            m = FirmTeamMember.query.filter_by(workspace_id=ws.id, name=name).first()
            if not m:
                m = FirmTeamMember(workspace_id=ws.id, name=name, role=role, email=email, is_active=True)
                db.session.add(m); db.session.flush()
            members[name.split()[-1]] = m

        # matters in the superadmin workspace
        cases = []
        for i, (title, status, opened, ctype) in enumerate(MATTERS):
            case = Case.query.filter_by(title=title, is_deleted=False).first()
            if case is None:
                ct = Contact.query.filter_by(email=f'client{i}@example.it').first() or Contact(
                    fullname=f'Client {i}', email=f'client{i}@example.it', status='active', workspace_id=ws.id)
                db.session.add(ct); db.session.flush()
                case = Case(workspace_id=ws.id, contactid=ct.id, ownerid=admin.id, assignedto=admin.id,
                            title=title, casetype=ctype, status=status, priority='Medium',
                            openedat=d(-opened), case_no=f'INS-{i+1:02d}')
                db.session.add(case); db.session.flush()
            cases.append(case)

        # tasks spread over the matters (cycle through)
        created = 0
        for i, (title, status, start_ago, due_from, role) in enumerate(TASKS):
            case = cases[i % len(cases)]
            t = Task.query.filter_by(caseid=case.id, title=title, is_deleted=False).first()
            if t is None:
                t = Task(workspace_id=ws.id, caseid=case.id, userid=admin.id, title=title, status=status,
                         priority='Medium', startdate=d(-start_ago), duedate=d(due_from),
                         createdat=dt(-start_ago), updatedat=dt(-start_ago))
                db.session.add(t); db.session.flush()
                created += 1
            # assignee (role colour)
            TaskAssignee.query.filter_by(task_id=t.id).delete()
            who = members.get('Romanelli' if role == 'lawyer_review' else
                              ('Rasing' if role == 'docs_supply' else 'Elisa'))
            if who:
                db.session.add(TaskAssignee(workspace_id=ws.id, task_id=t.id, team_member_id=who.id, role=role))

        # a couple of lawyer flags (one open, one resolved)
        if not TaskFlag.query.filter_by(task_id=cases[0].tasks[0].id).first():
            db.session.add(TaskFlag(workspace_id=ws.id, task_id=cases[0].tasks[0].id,
                                    raised_by_agent='lexflow-agent', target_member_id=members['Romanelli'].id,
                                    status='open', reason='Needs lawyer review'))
        if not TaskFlag.query.filter_by(task_id=cases[1].tasks[0].id).first():
            db.session.add(TaskFlag(workspace_id=ws.id, task_id=cases[1].tasks[0].id,
                                    raised_by_agent='lexflow-agent', target_member_id=members['Romanelli'].id,
                                    status='resolved', reason='Reviewed', created_at=dt(-20), resolved_at=dt(-18)))

        # a few tasks in the second tenant (must never appear in superadmin's charts)
        if not Task.query.filter_by(workspace_id=other.id).first():
            oct_ = Contact.query.filter_by(email='other@example.it').first() or Contact(
                fullname='Other Client', email='other@example.it', status='active', workspace_id=other.id)
            db.session.add(oct_); db.session.flush()
            ocase = Case(workspace_id=other.id, contactid=oct_.id, ownerid=other_admin.id, title='Other matter',
                         status='Active', openedat=d(-30), case_no='OT-01')
            db.session.add(ocase); db.session.flush()
            for j in range(3):
                db.session.add(Task(workspace_id=other.id, caseid=ocase.id, userid=other_admin.id,
                                    title=f'Other task {j}', status='pending', startdate=d(-10), duedate=d(10),
                                    createdat=dt(-10), updatedat=dt(-10)))

        db.session.commit()
        print(f'seeded: {len(cases)} matters, {created} new tasks (+ existing kept), 2 tenants')


if __name__ == '__main__':
    main()

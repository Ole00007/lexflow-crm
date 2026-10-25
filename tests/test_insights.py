"""Insights (WS-D) — plain-script test (no pytest collection side effects).

Run: python tests/test_insights.py   (throwaway SQLite DB)

Also passes under `python -m pytest tests -q` because the whole body is guarded
under `if __name__ == '__main__'` (no module-level sys.exit, no import-time
side effects). backend-dev may still add it to collect_ignore in conftest.py.
"""
import os, sys, tempfile

tmp = tempfile.mkdtemp()
os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/t.db", SECRET_KEY="dev",
    JWT_SECRET_KEY="dev-jwt-secret-key-0123456789abcdef", CORS_ORIGINS="http://x",
    RATELIMIT_STORAGE_URL="memory://", SEED_OLEYA00007YAHOO_PASSWORD="Test12345!",
    INSIGHTS_ENABLED="true")
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo)

from datetime import date, timedelta, datetime
from crm import create_app, _seed_default_users
from crm.extensions import db
from crm.models.task import Task
from crm.models.case import Case
from crm.models.contact import Contact
from crm.models.workspace import Workspace
from crm.models.user import User
from crm.models.firm_team import FirmTeamMember
from crm.models.task_assignee import TaskAssignee, TaskFlag

app = create_app()
# Shared-file integration is done by backend-dev (crm/__init__.py + base.html).
# This test self-registers the blueprint + context processor to simulate that
# integration so the feature is testable before the merge. Must happen BEFORE
# the first request (register_blueprint is frozen once the app handles one).
from crm.routes.insights import insights_bp
app.register_blueprint(insights_bp)
@app.context_processor
def _insights_ctx():
    return {'insights_enabled': os.environ.get('INSIGHTS_ENABLED', 'false').strip().lower() in ('1', 'true', 'yes', 'on')}
c = app.test_client(); c.get('/login')
fails = []
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: fails.append(name)

def d(n): return date.today() + timedelta(days=n)
def dt(n): return datetime.combine(d(n), datetime.min.time())

def login(email, pw):
    r = c.post('/api/auth/login', json={'email': email, 'password': pw})
    return {'Authorization': 'Bearer ' + r.get_json()['access_token']}

def _mk_ws(slug, name, parent=None):
    ws = Workspace.query.filter_by(slug=slug).first()
    if not ws:
        ws = Workspace(slug=slug, name=name, parent_workspace_id=(parent.id if parent else None), is_active=True)
        db.session.add(ws); db.session.flush()
    return ws

def _mk_user(email, role, ws, pw):
    u = User.query.filter_by(email=email).first()
    if not u:
        u = User(workspace_id=ws.id, email=email, role=role); u.set_password(pw)
        db.session.add(u); db.session.flush()
    return u

def _mk_contact(ws, email, name):
    ct = Contact.query.filter_by(email=email).first() or Contact(
        fullname=name, email=email, status='active', workspace_id=ws.id)
    db.session.add(ct); db.session.flush()
    return ct

def _mk_case(ws, contact, title, status, opened_days_ago, owner):
    case = Case(workspace_id=ws.id, contactid=contact.id, ownerid=owner.id, title=title,
                status=status, openedat=d(-opened_days_ago))
    db.session.add(case); db.session.flush()
    return case

def _mk_task(ws, case, title, status, start_ago, due_from, created_ago, updated_ago, owner):
    t = Task(workspace_id=ws.id, caseid=case.id, userid=owner.id, title=title, status=status,
             startdate=d(-start_ago), duedate=d(due_from), createdat=dt(-created_ago), updatedat=dt(-updated_ago))
    db.session.add(t); db.session.flush()
    return t

def _mk_member(ws, name, role):
    m = FirmTeamMember.query.filter_by(workspace_id=ws.id, name=name).first()
    if not m:
        m = FirmTeamMember(workspace_id=ws.id, name=name, role=role, is_active=True)
        db.session.add(m); db.session.flush()
    return m

def _mk_assignee(ws, task, member, role):
    db.session.add(TaskAssignee(workspace_id=ws.id, task_id=task.id, team_member_id=member.id, role=role))

def _mk_flag(ws, task, member, status, created_ago, resolved_ago=None):
    db.session.add(TaskFlag(workspace_id=ws.id, task_id=task.id, target_member_id=member.id,
                            status=status, reason='review', created_at=dt(-created_ago),
                            resolved_at=dt(-resolved_ago) if resolved_ago else None))

def main():
    with app.app_context():
        db.create_all(); _seed_default_users()
        sa = User.query.filter_by(email='olesya00007@yahoo.com').first()
        ws_lex = sa.workspace

        # ── four-actor tenant matrix ─────────────────────────────────────
        ws_firm = _mk_ws('romanelli-studio', 'Romanelli Studio')
        ws_cl1 = _mk_ws('romanelli-cl1', 'Romanelli Client 1', parent=ws_firm)
        ws_foreign = _mk_ws('foreign-tenant', 'Foreign Tenant')

        firm_admin = _mk_user('firm@romanelli.test', 'admin', ws_firm, 'Firm12345!')
        cl1_admin = _mk_user('cl1@romanelli.test', 'admin', ws_cl1, 'Cl112345!')
        foreign_admin = _mk_user('foreign@other.test', 'admin', ws_foreign, 'Foreign12345!')

        # PII markers that must NEVER appear in any summary response
        pii_email = 'pii-marker@example.com'
        pii_phone = 'PIIPHONE123'
        pii_title = 'PII-TITLE-SECRET'
        pii_desc = 'PII-DESC-SECRET'

        # lexflow (superadmin) workspace: 2 matters, 3 tasks
        lc1 = _mk_contact(ws_lex, 'lex1@example.it', 'Lex Client One')
        lc2 = _mk_contact(ws_lex, 'lex2@example.it', 'Lex Client Two')
        m1 = _mk_case(ws_lex, lc1, pii_title, 'Active', 40, sa)
        m2 = _mk_case(ws_lex, lc2, 'Matter Two', 'Intake', 10, sa)
        t1 = _mk_task(ws_lex, m1, pii_title, 'done', 30, -20, 30, 20, sa)   # done in range
        t2 = _mk_task(ws_lex, m1, 'Task Two', 'pending', 10, 3, 10, 10, sa)  # due ≤7d
        t3 = _mk_task(ws_lex, m2, 'Task Three', 'pending', 5, -1, 5, 5, sa)  # overdue
        m_owner = _mk_member(ws_lex, 'Elena Romanelli', 'avvocato')
        m_docs = _mk_member(ws_lex, 'Olesia Rasing', 'office')
        _mk_assignee(ws_lex, t1, m_owner, 'case_owner')
        _mk_assignee(ws_lex, t2, m_docs, 'docs_supply')
        _mk_flag(ws_lex, t2, m_owner, 'open', 5)
        _mk_flag(ws_lex, t1, m_owner, 'resolved', 25, 20)

        # firm workspace: 2 matters, 3 tasks
        fc1 = _mk_contact(ws_firm, 'firm1@example.it', 'Firm Client One')
        fm1 = _mk_case(ws_firm, fc1, 'Firm Matter One', 'Active', 30, firm_admin)
        fm2 = _mk_case(ws_firm, fc1, 'Firm Matter Two', 'Active', 20, firm_admin)
        _mk_task(ws_firm, fm1, 'Firm Task One', 'done', 20, -10, 20, 15, firm_admin)
        _mk_task(ws_firm, fm1, 'Firm Task Two', 'pending', 10, 5, 10, 10, firm_admin)
        _mk_task(ws_firm, fm2, 'Firm Task Three', 'pending', 5, 2, 5, 5, firm_admin)

        # cl1 (client sub-workspace): 1 matter, 2 tasks
        cc1 = _mk_contact(ws_cl1, 'cl1@example.it', 'CL1 Client')
        cm1 = _mk_case(ws_cl1, cc1, 'CL1 Matter', 'Active', 15, cl1_admin)
        _mk_task(ws_cl1, cm1, 'CL1 Task One', 'done', 10, -5, 10, 8, cl1_admin)
        _mk_task(ws_cl1, cm1, 'CL1 Task Two', 'pending', 5, 4, 5, 5, cl1_admin)

        # foreign tenant: 1 matter, 2 tasks
        xc1 = _mk_contact(ws_foreign, 'foreign@example.it', 'Foreign Client')
        xm1 = _mk_case(ws_foreign, xc1, 'Foreign Matter', 'Active', 25, foreign_admin)
        _mk_task(ws_foreign, xm1, 'Foreign Task One', 'done', 15, -5, 15, 10, foreign_admin)
        _mk_task(ws_foreign, xm1, 'Foreign Task Two', 'pending', 5, 6, 5, 5, foreign_admin)

        db.session.commit()

        # capture ids for later
        LEX_WS, FIRM_WS, CL1_WS, FOR_WS = ws_lex.id, ws_firm.id, ws_cl1.id, ws_foreign.id
        SA_ID, FIRM_ID, CL1_ID, FOR_ID = sa.id, firm_admin.id, cl1_admin.id, foreign_admin.id

    S = login('olesya00007@yahoo.com', 'Test12345!')
    FIRM = login('firm@romanelli.test', 'Firm12345!')
    CL1 = login('cl1@romanelli.test', 'Cl112345!')
    FOR = login('foreign@other.test', 'Foreign12345!')

    # ── aggregates correct on the known fixture (superadmin) ────────────
    r = c.get('/api/insights/summary?range=30', headers=S)
    check('summary 200 for superadmin', r.status_code == 200)
    data = r.get_json()
    k = data['kpis']
    check('kpis: open matters = 6 (all tenants for superadmin)', k['open_matters'] == 6)
    check('kpis: tasks done in range = 4', k['tasks_done'] == 4)
    check('kpis: overdue = 1', k['overdue_tasks'] == 1)
    check('kpis: due next 7 = 5', k['due_next_7'] == 5)
    check('kpis: avg days open->first done is a number', isinstance(k['avg_days_open_to_first_done'], (int, float)))
    check('kpis_previous present (delta source)', 'kpis_previous' in data)

    # matters_by_status
    statuses = {x['status']: x['count'] for x in data['matters_by_status']}
    check('matters_by_status: Active = 5', statuses.get('Active') == 5)
    check('matters_by_status: Intake = 1', statuses.get('Intake') == 1)

    # deadline_health (open tasks across all tenants: 3+2+2+2 = 9 open)
    h = data['deadline_health']
    check('deadline_health: overdue = 1', h['overdue'] == 1)
    check('deadline_health: due_7 = 5', h['due_7'] == 5)
    check('deadline_health: later = 0', h['later'] == 0)
    check('deadline_health: no_date = 0', h['no_date'] == 0)

    # workload_by_role
    wl = data['workload_by_role']
    by_role = {x['role']: x['count'] for x in wl['by_role']}
    check('workload: case_owner = 0 (its only task is done; workload counts OPEN tasks)', by_role.get('case_owner') == 0)
    check('workload: docs_supply = 1', by_role.get('docs_supply') == 1)
    check('workload: every role has a colour', all(x['color'].startswith('#') for x in wl['by_role']))
    check('workload: by_member uses initials', all(len(x['initials']) >= 2 and x['initials'].endswith('.') for x in wl['by_member']))

    # flags
    f = data['flags']
    check('flags: open = 1', f['open'] == 1)
    check('flags: resolved in range = 1', f['resolved_in_range'] == 1)
    check('flags: median hours is a number', isinstance(f['median_hours_to_resolve'], (int, float)))

    # activity weekly series
    act = data['activity']
    check('activity: weekly series non-empty', len(act) >= 4)
    check('activity: tasks_completed sums to 4', sum(w['tasks_completed'] for w in act) == 4)

    # ── four-actor tenant matrix (no cross-tenant numbers) ──────────────
    r_firm = c.get('/api/insights/summary?range=30', headers=FIRM).get_json()
    check('firm admin sees firm + cl1 matters (3)', r_firm['kpis']['open_matters'] == 3)
    check('firm admin tasks done = 2 (firm only)', r_firm['kpis']['tasks_done'] == 2)
    r_cl1 = c.get('/api/insights/summary?range=30', headers=CL1).get_json()
    check('cl1 admin sees only own matter (1)', r_cl1['kpis']['open_matters'] == 1)
    check('cl1 admin tasks done = 1', r_cl1['kpis']['tasks_done'] == 1)
    r_for = c.get('/api/insights/summary?range=30', headers=FOR).get_json()
    check('foreign admin sees only own matter (1)', r_for['kpis']['open_matters'] == 1)
    check('foreign admin tasks done = 1', r_for['kpis']['tasks_done'] == 1)
    check('foreign admin never sees lexflow matter count', r_for['kpis']['open_matters'] != 6)

    # ── PII scan: raw response must contain none of the markers ─────────
    raw = r.get_data(as_text=True)
    check('no PII email in response', pii_email not in raw)
    check('no PII phone in response', pii_phone not in raw)
    check('no PII title in response', pii_title not in raw)
    check('no PII description in response', pii_desc not in raw)
    check('no client names in response', 'Lex Client' not in raw and 'Firm Client' not in raw)

    # ── range validation ────────────────────────────────────────────────
    check('range garbage => 400', c.get('/api/insights/summary?range=abc', headers=S).status_code == 400)
    check('range 7 => 400', c.get('/api/insights/summary?range=7', headers=S).status_code == 400)
    check('range 90 => 200', c.get('/api/insights/summary?range=90', headers=S).status_code == 200)
    check('range 365 => 200', c.get('/api/insights/summary?range=365', headers=S).status_code == 200)
    check('no range => 200 (default 30)', c.get('/api/insights/summary', headers=S).status_code == 200)

    # ── exact query the JS sends ────────────────────────────────────────
    js_query = '/api/insights/summary?range=30'
    check('exact JS query works', c.get(js_query, headers=S).status_code == 200)

    # ── flag off => 404 for both routes ────────────────────────────────
    os.environ['INSIGHTS_ENABLED'] = 'false'
    check('flag off: /insights 404', c.get('/insights', headers=S).status_code == 404)
    check('flag off: /api/insights/summary 404', c.get('/api/insights/summary?range=30', headers=S).status_code == 404)
    os.environ['INSIGHTS_ENABLED'] = 'true'

    # ── page shell + asset self-check (screenshot-free) ─────────────────
    page = c.get('/insights', headers=S)
    check('page /insights 200 when flag on', page.status_code == 200)
    html = page.get_data(as_text=True)
    import re
    assets = re.findall(r"url_for\('static', filename='([^']+)'\)", html)
    # the template uses url_for in the template; rendered HTML has /static/... paths
    rendered = re.findall(r'(/static/[A-Za-z0-9_./-]+\.(?:css|js))', html)
    for a in set(rendered):
        check('asset exists: ' + a, c.get(a).status_code == 200)
    check('page references insights.css', '/static/css/insights/insights.css' in html)
    check('page references insights.js', '/static/js/insights/insights.js' in html)

    print('\nRESULT: ' + ('ALL PASS' if not fails else 'FAILED: ' + '; '.join(fails)))
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())

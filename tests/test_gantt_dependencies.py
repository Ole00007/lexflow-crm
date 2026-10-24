"""Gantt dependencies — plain-script test (no pytest dependency).

Run: python tests/test_gantt_dependencies.py   (uses a throwaway SQLite DB)
Checks /api/gantt/tasks: dependencies are only ids present in the response,
no self-reference, no cross-workspace leak, staff cannot see hidden ids.
"""
import os, sys, tempfile
tmp = tempfile.mkdtemp()
os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/t.db", SECRET_KEY="dev",
    JWT_SECRET_KEY="dev-jwt-secret-key-0123456789abcdef", CORS_ORIGINS="http://x",
    RATELIMIT_STORAGE_URL="memory://", SEED_OLEYA00007YAHOO_PASSWORD="Test12345!")
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo)
from datetime import date, timedelta
from crm import create_app, _seed_default_users
from crm.extensions import db
from crm.models.task import Task
from crm.models.case import Case
from crm.models.workspace import Workspace
from crm.models.user import User

app = create_app()
c = app.test_client(); c.get('/login')
fails = []
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: fails.append(name)

with app.app_context():
    db.create_all(); _seed_default_users()
    ws = Workspace.query.filter_by(slug='lexflow').first()
    other = Workspace(slug='other-ws', name='Other', is_active=True); db.session.add(other); db.session.flush()
    admin = User.query.filter_by(email='olesya00007@yahoo.com').first()
    from crm.models.contact import Contact
    ct = Contact(fullname='T', email='t@x.it', status='lead', workspace_id=ws.id); db.session.add(ct); db.session.flush()
    oct_ = Contact(fullname='O', email='o@x.it', status='lead', workspace_id=other.id); db.session.add(oct_); db.session.flush()
    case = Case(workspace_id=ws.id, contactid=ct.id, ownerid=admin.id, title='c', status='Active'); db.session.add(case)
    ocase = Case(workspace_id=other.id, contactid=oct_.id, ownerid=admin.id, title='oc', status='Active'); db.session.add(ocase); db.session.flush()
    d0 = date.today()
    def mk(w, cs, title, dep=None, start=0, end=3):
        t = Task(workspace_id=w, caseid=cs.id, userid=admin.id, title=title, status='pending',
                 startdate=d0 + timedelta(days=start), duedate=d0 + timedelta(days=end), depends_on=dep)
        db.session.add(t); db.session.flush(); return t
    a = mk(ws.id, case, 'A')
    undated = Task(workspace_id=ws.id, caseid=case.id, userid=admin.id, title='U', status='pending'); db.session.add(undated); db.session.flush()
    foreign = mk(other.id, ocase, 'F')
    b = mk(ws.id, case, 'B', dep=f"{a.id},{undated.id},{foreign.id},99999,abc,{a.id}")
    s = mk(ws.id, case, 'S'); s.depends_on = str(s.id)
    w = mk(ws.id, case, 'W', dep='\u00b2,\u0663')
    db.session.commit()
    ids = dict(a=a.id, b=b.id, s=s.id, u=undated.id, f=foreign.id, w=w.id)
    tenant_admin = User(email='tenant-admin@x.it', role='admin', workspace_id=ws.id); tenant_admin.set_password('Tenant12345!')
    db.session.add(tenant_admin); db.session.commit()

tok = c.post('/api/auth/login', json={'email': 'olesya00007@yahoo.com', 'password': 'Test12345!'}).get_json()['access_token']
r = c.get('/api/gantt/tasks', headers={'Authorization': 'Bearer ' + tok})
check('endpoint 200', r.status_code == 200)
rows = {x['id']: x for x in r.get_json()}
check('whitelisted keys only', all(set(x) == {'id','name','start','end','progress','dependencies','custom_class'} for x in rows.values()))
check('A has no deps', rows[ids['a']]['dependencies'] == '')
dep = rows[ids['b']]['dependencies'].split(',') if rows[ids['b']]['dependencies'] else []
check('superadmin sees other workspace (by design) and B deps are deduped', dep == [str(ids['a']), str(ids['f'])])
# tenant admin of the lexflow workspace: foreign workspace task must be invisible AND not referenced
tok2 = c.post('/api/auth/login', json={'email': 'tenant-admin@x.it', 'password': 'Tenant12345!'}).get_json()['access_token']
rows2 = {x['id']: x for x in c.get('/api/gantt/tasks', headers={'Authorization': 'Bearer ' + tok2}).get_json()}
check('tenant admin does not see foreign workspace task', ids['f'] not in rows2)
check('tenant admin B depends on A only (foreign/undated/missing/garbage dropped, deduped)', rows2[ids['b']]['dependencies'] == str(ids['a']))
print('   debug: superadmin B deps', dep, '| tenant B deps', rows2[ids['b']]['dependencies'])
check('self reference dropped', rows[ids['s']]['dependencies'] == '')
check('unicode-digit depends_on ("²") yields no deps and no 500', rows[ids['w']]['dependencies'] == '')
check('undated task not in response', ids['u'] not in rows)
check('anon -> 401', c.get('/api/gantt/tasks').status_code == 401)
print('RESULT:', 'ALL PASS' if not fails else f'{len(fails)} FAILED: {fails}')
sys.exit(1 if fails else 0)

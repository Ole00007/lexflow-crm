"""Calendar deadline reflection — tenant isolation + flag behaviour (plain script, no pytest).

Run: python tests/test_deadline_calendar_isolation.py
"""
import os, sys, tempfile
tmp = tempfile.mkdtemp()
os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/t.db", SECRET_KEY="dev",
    JWT_SECRET_KEY="dev-jwt-secret-key-0123456789abcdef", CORS_ORIGINS="http://x",
    RATELIMIT_STORAGE_URL="memory://", SEED_OLEYA00007YAHOO_PASSWORD="Test12345!")
os.environ.pop('CALENDAR_DEADLINES_ENABLED', None)
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo)
from datetime import date, timedelta
from crm import create_app, _seed_default_users
from crm.extensions import db
from crm.models.task import Task
from crm.models.case import Case
from crm.models.contact import Contact
from crm.models.deadline import Deadline
from crm.models.workspace import Workspace
from crm.models.user import User

app = create_app(); c = app.test_client(); c.get('/login')
fails = []
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: fails.append(name)

with app.app_context():
    db.create_all(); _seed_default_users()
    ws = Workspace.query.filter_by(slug='lexflow').first()
    other = Workspace(slug='other-ws', name='Other', is_active=True); db.session.add(other); db.session.flush()
    sa = User.query.filter_by(email='olesya00007@yahoo.com').first()
    ta = User(workspace_id=other.id, email='tenant@other.it', role='admin'); ta.set_password('Tenant12345!'); db.session.add(ta)
    def mk_case(w, t):
        ct = Contact(fullname=t, email=t.replace(' ', '') + '@x.it', status='lead', workspace_id=w.id); db.session.add(ct); db.session.flush()
        cs = Case(workspace_id=w.id, contactid=ct.id, ownerid=sa.id, title=t, status='Active'); db.session.add(cs); db.session.flush(); return cs
    c1, c2 = mk_case(ws, 'lexflow case'), mk_case(other, 'other case')
    d = date.today() + timedelta(days=5)
    def mk_task(w, cs, title, status='pending', due=d):
        db.session.add(Task(workspace_id=w.id, caseid=cs.id, userid=sa.id, title=title, status=status, startdate=date.today(), duedate=due))
    mk_task(ws, c1, 'LEX open'); mk_task(ws, c1, 'LEX done', status='done'); mk_task(ws, c1, 'LEX nodue', due=None)
    mk_task(other, c2, 'OTHER open')
    db.session.add(Deadline(workspace_id=ws.id, caseid=c1.id, title='LEX udienza', deadline_date=d, deadline_type='udienza'))
    db.session.add(Deadline(workspace_id=other.id, caseid=c2.id, title='OTHER termine', deadline_date=d, deadline_type='termine_perentorio'))
    db.session.commit()

def login(e, p):
    r = c.post('/api/auth/login', json={'email': e, 'password': p}); return {'Authorization': 'Bearer ' + r.get_json()['access_token']}
S = login('olesya00007@yahoo.com', 'Test12345!'); T = login('tenant@other.it', 'Tenant12345!')
titles = lambda r: sorted((e.get('title') or e.get('name') or '') for e in r.get_json())

# flag OFF (env unset)
r = c.get('/api/calendar', headers=T)
check('flag off: plain calendar, no deadline/task entries', r.status_code == 200 and all('kind' not in e for e in r.get_json()))
r = c.get('/api/calendar?deadline_events=true', headers=T)
check('flag off is a kill-switch: deadline_events=true is ignored', r.status_code == 200 and all('kind' not in e for e in r.get_json()))
os.environ['CALENDAR_DEADLINES_ENABLED'] = 'true'
r = c.get('/api/calendar?deadline_events=true', headers=S); t = titles(r)
check('superadmin sees both workspaces', any('LEX' in x for x in t) and any('OTHER' in x for x in t))
check('done tasks excluded', not any('LEX done' in x for x in t))
check('task without due date does not crash / not listed', r.status_code == 200 and not any('LEX nodue' in x for x in t))
check('anonymous rejected', c.get('/api/calendar?deadline_events=true').status_code in (401, 422))
# the REAL page sends full datetimes (BLOCKER from cross-test): must not 500
dfrom = (date.today() - timedelta(days=30)).isoformat() + 'T00:00:00'; dto = (date.today() + timedelta(days=30)).isoformat() + 'T23:59:59'
r = c.get('/api/calendar?date_from=%s&date_to=%s' % (dfrom, dto), headers=S)
check('datetime date_from/date_to (what calendar.html sends) -> 200, reflected entries present', r.status_code == 200 and any(e.get('kind') for e in r.get_json()))
r = c.get('/api/calendar?date_from=%s' % ((date.today() + timedelta(days=60)).isoformat() + 'T00:00:00'), headers=S)
check('range outside the due date excludes reflected entries', r.status_code == 200 and not any(e.get('kind') for e in r.get_json()))

# flag ON
r = c.get('/api/calendar', headers=T); t = titles(r)
check('flag on: tenant gets own entries by default, never LEX ones', any('OTHER' in x for x in t) and not any('LEX' in x for x in t))
r = c.get('/api/calendar?deadline_events=false', headers=T)
check('flag on + deadline_events=false suppresses', all('kind' not in e for e in r.get_json()))
kinds = {e.get('kind') for e in c.get('/api/calendar', headers=S).get_json()}
check('entries carry kind task_due/deadline', {'task_due', 'deadline'} <= kinds)

print('\nRESULT: ' + ('ALL PASS' if not fails else 'FAILED: ' + '; '.join(fails)))
sys.exit(1 if fails else 0)

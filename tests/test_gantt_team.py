"""Gantt team roles / vault docs / lawyer flags — plain-script test (no pytest).

Run: python tests/test_gantt_team.py   (throwaway SQLite DB + throwaway vault dir)
"""
import os, sys, tempfile
tmp = tempfile.mkdtemp()
vault = os.path.join(tmp, 'vault'); os.makedirs(os.path.join(vault, 'Clients', 'Rasing'))
open(os.path.join(vault, 'Clients', 'Rasing', 'atto.md'), 'w').write('# atto')
open(os.path.join(vault, 'Clients', 'Rasing', '.secret'), 'w').write('x')
outside = os.path.join(tmp, 'outside'); os.makedirs(outside); open(os.path.join(outside, 'leak.txt'), 'w').write('leak')
os.symlink(outside, os.path.join(vault, 'Clients', 'Rasing', 'escape'))
os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/t.db", SECRET_KEY="dev",
    JWT_SECRET_KEY="dev-jwt-secret-key-0123456789abcdef", CORS_ORIGINS="http://x",
    RATELIMIT_STORAGE_URL="memory://", SEED_OLEYA00007YAHOO_PASSWORD="Test12345!", LEXFLOW_VAULT_DIR=vault)
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo)
from datetime import date
from crm import create_app, _seed_default_users
from crm.extensions import db
from crm.models.task import Task
from crm.models.case import Case
from crm.models.contact import Contact
from crm.models.workspace import Workspace
from crm.models.user import User
from crm.models.firm_team import FirmTeamMember
from crm.models.task_assignee import TaskFlag

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
    ct = Contact(fullname='R', email='r@x.it', status='lead', workspace_id=ws.id); db.session.add(ct); db.session.flush()
    case = Case(workspace_id=ws.id, contactid=ct.id, ownerid=sa.id, title='Rasing separazione', status='Active'); db.session.add(case); db.session.flush()
    t = Task(workspace_id=ws.id, caseid=case.id, userid=sa.id, title='Collect docs', status='pending',
             startdate=date.today(), duedate=date.today()); db.session.add(t)
    m_owner = FirmTeamMember(workspace_id=ws.id, name='Elena Romanelli', role='avvocato', email='e@x.it')
    m_docs = FirmTeamMember(workspace_id=ws.id, name='Olesia Rasing', role='office')
    m_asst = FirmTeamMember(workspace_id=ws.id, name='Elisa', role='assistente')
    m_foreign = FirmTeamMember(workspace_id=other.id, name='Foreign Lawyer', role='avvocato')
    db.session.add_all([m_owner, m_docs, m_asst, m_foreign]); db.session.commit()
    TID, OWN, DOCS, ASST, FOR = t.id, m_owner.id, m_docs.id, m_asst.id, m_foreign.id
    OTHER_ID, SA_ID = other.id, sa.id
    oct_ = Contact(fullname='O', email='o@x.it', status='lead', workspace_id=other.id); db.session.add(oct_); db.session.flush()
    ocase = Case(workspace_id=other.id, contactid=oct_.id, ownerid=sa.id, title='oc', status='Active'); db.session.add(ocase); db.session.commit()
    OCASE_ID = ocase.id

def login(email, pw):
    r = c.post('/api/auth/login', json={'email': email, 'password': pw}); return {'Authorization': 'Bearer ' + r.get_json()['access_token']}
S = login('olesya00007@yahoo.com', 'Test12345!'); TEN = login('tenant@other.it', 'Tenant12345!')
U = f'/api/gantt/tasks/{TID}'

# assignees
r = c.put(U + '/assignees', headers=S, json={'assignees': [{'member_id': OWN, 'role': 'case_owner'}, {'member_id': DOCS, 'role': 'docs_supply'}, {'member_id': ASST, 'role': 'legal_assistant'}]})
check('superadmin sets 3 role assignees', r.status_code == 200 and len(r.get_json()['team']) == 3)
check('bad role rejected', c.put(U + '/assignees', headers=S, json={'assignees': [{'member_id': OWN, 'role': 'boss'}]}).status_code == 400)
check('foreign-workspace member rejected', c.put(U + '/assignees', headers=S, json={'assignees': [{'member_id': FOR, 'role': 'case_owner'}]}).status_code == 400)
check('tenant admin of another workspace cannot touch the task (404)', c.put(U + '/assignees', headers=TEN, json={'assignees': []}).status_code == 404)
check('anonymous rejected', c.put(U + '/assignees', json={'assignees': []}).status_code in (401, 422))
check('team survived the rejected calls', len(c.get('/api/gantt/tasks', headers=S).get_json()[0]['team']) == 3)

# vault ref
check('vault_ref traversal rejected', c.put(U + '/vault-ref', headers=S, json={'vault_ref': '../outside'}).status_code == 400)
check('vault_ref hidden rejected', c.put(U + '/vault-ref', headers=S, json={'vault_ref': 'Clients/.git'}).status_code == 400)
check('vault_ref absolute rejected', c.put(U + '/vault-ref', headers=S, json={'vault_ref': '/etc'}).status_code == 400)
check('tenant admin cannot set vault_ref', c.put(U + '/vault-ref', headers=TEN, json={'vault_ref': 'Clients/Rasing'}).status_code == 403)
check('superadmin sets vault_ref', c.put(U + '/vault-ref', headers=S, json={'vault_ref': 'Clients/Rasing'}).status_code == 200)

# gantt payload
row = c.get('/api/gantt/tasks', headers=S).get_json()[0]
check('payload: roles ordered owner, docs, assistant', [m['role'] for m in row['team']] == ['case_owner', 'docs_supply', 'legal_assistant'])
check('payload: every member has a colour', all(m['color'].startswith('#') for m in row['team']))
check('payload: vault link for superadmin', row['vault'] and row['vault']['obsidian_url'].startswith('obsidian://open?vault=vault&file=Clients%2FRasing') and row['vault']['docs_api'] == U + '/docs')

# docs listing (agent pull)
r = c.get(U + '/docs', headers=S); d = r.get_json()
names = sorted(x['name'] for x in d['docs'])
check('docs: lists the markdown, skips dotfiles', r.status_code == 200 and names == ['atto.md'])
check('docs: symlink escape not followed/listed', 'leak.txt' not in names)
check('docs: no absolute paths leaked', vault not in r.get_data(as_text=True) and tmp not in r.get_data(as_text=True))
check('docs: tenant admin 403', c.get(U + '/docs', headers=TEN).status_code == 403)

# flags
r = c.post(U + '/flag-lawyer', headers={**S, 'X-Agent-Name': 'lexflow-agent'}, json={'reason': 'Need approval to file'})
f = r.get_json()
check('flag created, targets case owner, agent recorded', r.status_code == 201 and f['target_member_id'] == OWN and f['raised_by_agent'] == 'lexflow-agent' and f['status'] == 'open')
check('flag visible in payload count', c.get('/api/gantt/tasks', headers=S).get_json()[0]['open_flags'] == 1)
check('tenant admin of another workspace cannot flag (404)', c.post(U + '/flag-lawyer', headers=TEN, json={}).status_code == 404)
check('tenant admin cannot resolve foreign flag (404)', c.post(f"/api/gantt/flags/{f['id']}/resolve", headers=TEN).status_code == 404)
check('superadmin resolves flag', c.post(f"/api/gantt/flags/{f['id']}/resolve", headers=S).get_json()['status'] == 'resolved')
check('open_flags back to 0', c.get('/api/gantt/tasks', headers=S).get_json()[0]['open_flags'] == 0)

# a tenant admin must never see the vault key / foreign team
with app.app_context():
    t2 = Task(workspace_id=OTHER_ID, caseid=OCASE_ID, userid=SA_ID, title='Other task', status='pending',
              startdate=date.today(), duedate=date.today()); db.session.add(t2); db.session.commit()
rows = c.get('/api/gantt/tasks', headers=TEN).get_json()
check('tenant admin sees only own workspace task', [x['name'] for x in rows] == ['Other task'])
check('tenant admin payload has no vault', all(x['vault'] is None for x in rows))

print('\nRESULT: ' + ('ALL PASS' if not fails else 'FAILED: ' + '; '.join(fails)))
sys.exit(1 if fails else 0)

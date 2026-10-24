"""Context notes endpoint — plain-script test (throwaway SQLite + temp vault).

Run: python tests/test_context_notes.py
"""
import os, sys, tempfile, json
tmp = tempfile.mkdtemp()
vault = os.path.join(tmp, 'vault')
notes = os.path.join(vault, '01-Projects', 'LexFlow')
os.makedirs(notes)
outside = os.path.join(tmp, 'outside'); os.makedirs(outside)
open(os.path.join(outside, 'secret.md'), 'w').write('# SECRET\nshould never be read')
open(os.path.join(notes, 'Alpha.md'), 'w').write('---\ntitle: Alpha Note\nstatus: draft\ntags: [lexflow, gantt]\n---\n# Alpha\nSee [[Beta]] and T-007. ' + 'x' * 600 + '\n\n## Links\n- [[Beta]]\n')
open(os.path.join(notes, 'Beta.md'), 'w').write('# Beta heading only\nmentions T-021 and [[Alpha|alias]] and [[Missing]]')
open(os.path.join(notes, 'big.md'), 'w').write('# big\n' + 'y' * (210 * 1024))
os.symlink(os.path.join(outside, 'secret.md'), os.path.join(notes, 'escape.md'))
os.symlink(outside, os.path.join(vault, '01-Projects', 'LexFlow-evil')) if False else None

os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/t.db", SECRET_KEY="dev",
    JWT_SECRET_KEY="dev-jwt-secret-key-0123456789abcdef", CORS_ORIGINS="http://x",
    RATELIMIT_STORAGE_URL="memory://", SEED_OLEYA00007YAHOO_PASSWORD="Test12345!")
os.environ.pop('CONTEXT_NOTES_ENABLED', None); os.environ.pop('LEXFLOW_VAULT_DIR', None)
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo)
from crm import create_app, _seed_default_users
from crm.extensions import db
from crm.models.user import User
from crm.models.workspace import Workspace

app = create_app(); c = app.test_client(); c.get('/login')
with app.app_context():
    db.create_all(); _seed_default_users()
    ws = Workspace.query.filter_by(slug='lexflow').first()
    u = User(email='adm@x.it', role='admin', workspace_id=ws.id); u.set_password('Adm12345!'); db.session.add(u); db.session.commit()

def login(email, pw): return c.post('/api/auth/login', json={'email': email, 'password': pw}).get_json()['access_token']
sa = {'Authorization': 'Bearer ' + login('olesya00007@yahoo.com', 'Test12345!')}
ad = {'Authorization': 'Bearer ' + login('adm@x.it', 'Adm12345!')}
fails = []
def check(n, ok):
    print(('PASS ' if ok else 'FAIL ') + n)
    if not ok: fails.append(n)

# flag off
check('flag off -> 404 (superadmin)', c.get('/api/context/notes', headers=sa).status_code == 404)
os.environ['CONTEXT_NOTES_ENABLED'] = 'true'
check('anon -> 401', c.get('/api/context/notes').status_code == 401)
check('admin (non-superadmin) -> 403', c.get('/api/context/notes', headers=ad).status_code == 403)
# unconfigured
r = c.get('/api/context/notes', headers=sa); j = r.get_json()
check('unconfigured vault -> 200 empty', r.status_code == 200 and j['nodes'] == [] and j['source'] == 'unconfigured')
os.environ['LEXFLOW_VAULT_DIR'] = vault
r = c.get('/api/context/notes', headers=sa); j = r.get_json()
check('superadmin -> 200', r.status_code == 200)
labels = sorted(n['label'] for n in j['nodes'])
check('notes found (Alpha Note, Beta heading only); big+symlink skipped', labels == ['Alpha Note', 'Beta heading only'])
check('no SECRET leaked anywhere', 'SECRET' not in json.dumps(j) and 'never be read' not in json.dumps(j))
alpha = [n for n in j['nodes'] if n['label'] == 'Alpha Note'][0]
check('frontmatter parsed (status/tags)', alpha['data']['status'] == 'draft' and alpha['data']['tags'] == ['lexflow', 'gantt'])
check('excerpt <= 260 chars and no frontmatter text', len(alpha['data']['excerpt']) <= 260 and 'title:' not in alpha['data']['excerpt'])
check("no 'body' key on any node", all('body' not in n and 'body' not in n['data'] for n in j['nodes']))
types = {(e['type']) for e in j['edges']}
check('wikilink edges alpha<->beta (alias handled, dead link ignored)', sum(1 for e in j['edges'] if e['type'] == 'wikilink') == 2)
check('mentions edges to task-ref', {e['target'] for e in j['edges'] if e['type'] == 'mentions'} == {'task-ref:T-007', 'task-ref:T-021'})
check('vault_name present', j.get('vault_name') == 'vault')
check('path_rel is vault-relative', alpha['data']['path_rel'] == '01-Projects/LexFlow/Alpha.md')
# vault pointing at a dir without the project subfolder -> empty
os.environ['LEXFLOW_VAULT_DIR'] = outside
j = c.get('/api/context/notes', headers=sa).get_json()
check('vault without 01-Projects/LexFlow -> no nodes', j['nodes'] == [])
os.environ['LEXFLOW_VAULT_DIR'] = vault
# regression: existing pages / apis
for p in ['/', '/login', '/dashboard', '/kanban', '/tasks', '/contacts', '/calendar']:
    check(f'{p} 200', c.get(p).status_code == 200)
check('/api/roadmap/graph 200', c.get('/api/roadmap/graph', headers=sa).status_code == 200)
print('RESULT:', 'ALL PASS' if not fails else f'{len(fails)} FAILED: {fails}')
sys.exit(1 if fails else 0)

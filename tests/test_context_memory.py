"""Context memory (Hindsight) endpoints — plain-script test (throwaway SQLite, recall mocked).

Run: python tests/test_context_memory.py
Live check (optional): HINDSIGHT_URL=... HINDSIGHT_API_KEY=... LIVE=1 python tests/test_context_memory.py
"""
import os, sys, tempfile
tmp = tempfile.mkdtemp()
os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/t.db", SECRET_KEY="dev",
    JWT_SECRET_KEY="dev-jwt-secret-key-0123456789abcdef", CORS_ORIGINS="http://x",
    RATELIMIT_STORAGE_URL="memory://", SEED_OLEYA00007YAHOO_PASSWORD="Test12345!")
LIVE = os.environ.get('LIVE') == '1'
live_env = {k: os.environ.get(k) for k in ('HINDSIGHT_URL', 'HINDSIGHT_API_KEY')}
for k in ('CONTEXT_MEMORY_ENABLED', 'HINDSIGHT_URL', 'HINDSIGHT_API_KEY'):
    os.environ.pop(k, None)
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo)
from crm import create_app, _seed_default_users
from crm.extensions import db
from crm.models.user import User
from crm.models.workspace import Workspace
from crm.routes import context_memory as cm

app = create_app(); c = app.test_client(); c.get('/login')
with app.app_context():
    db.create_all(); _seed_default_users()
    ws = Workspace.query.filter_by(slug='lexflow').first()
    u = User(email='adm@x.it', role='admin', workspace_id=ws.id); u.set_password('Adm12345!'); db.session.add(u); db.session.commit()

def login(e, p): return c.post('/api/auth/login', json={'email': e, 'password': p}).get_json()['access_token']
sa = {'Authorization': 'Bearer ' + login('olesya00007@yahoo.com', 'Test12345!')}
ad = {'Authorization': 'Bearer ' + login('adm@x.it', 'Adm12345!')}
fails = []
def check(n, ok):
    print(('PASS ' if ok else 'FAIL ') + n)
    if not ok: fails.append(n)

# scrub (pure)
s = cm.scrub('Avv. Diego Pagliano mail diego@pagliano.it tel +39 010 123 4567 see https://x.io/a?k=1 slug pagliano')
check('scrub client name -> Avv.Pagl', 'Pagliano' not in s and 'Avv.Pagl' in s)
check('scrub email/phone/url', all(x not in s for x in ('@', '4567', 'https')))
check('slug pagliano unchanged', s.endswith('slug pagliano'))

# flag off -> 404; auth
for p in ('/api/context/memory', '/api/context/digest'):
    check(p + ' flag off -> 404', c.get(p, headers=sa).status_code == 404)
os.environ['CONTEXT_MEMORY_ENABLED'] = 'true'
for p in ('/api/context/memory', '/api/context/digest'):
    check(p + ' anon -> 401', c.get(p).status_code == 401)
    check(p + ' admin -> 403', c.get(p, headers=ad).status_code == 403)
    j = c.get(p, headers=sa).get_json()
    check(p + ' unconfigured -> 200 empty, no network', c.get(p, headers=sa).status_code == 200 and j['source'] == 'unconfigured')

# mocked recall
today = cm.datetime.now(cm.timezone.utc).strftime('%Y-%m-%d')
fake = [{'id': 'id-%03d' % i, 'text': 'Work on T-021 for Avv. Pagliano mail a@b.it ' + 'z' * 400, 'type': 'observation',
         'entities': ['e%d' % k for k in range(10)], 'occurred_start': today + 'T09:00:00+00:00'} for i in range(60)]
fake.append({'id': 'old', 'text': 'old thing', 'occurred_start': '2026-01-01T00:00:00+00:00'})
fake.append({'id': 'id-001', 'text': 'dup'})
os.environ['HINDSIGHT_URL'] = 'http://hs.invalid'; os.environ['HINDSIGHT_API_KEY'] = 'k'
calls = []
cm._recall = lambda q, n: (calls.append(q), fake)[1]
cm._cache.clear()
j = c.get('/api/context/memory', headers=sa).get_json()
check('source hindsight', j['source'] == 'hindsight')
check('node cap 25 default', len(j['nodes']) == 25)
os.environ['HINDSIGHT_MAX_NODES'] = '999'; cm._cache.clear()
check('hard ceiling 40', len(c.get('/api/context/memory', headers=sa).get_json()['nodes']) == 40)
os.environ.pop('HINDSIGHT_MAX_NODES'); cm._cache.clear()
j = c.get('/api/context/memory', headers=sa).get_json()
n0 = j['nodes'][0]
check('excerpt <=240 and scrubbed', len(n0['data']['excerpt']) <= 240 and 'Pagliano' not in n0['data']['excerpt'] and '@' not in n0['data']['excerpt'])
check('entities <=6', len(n0['data']['entities']) <= 6)
check('type memory', n0['type'] == 'memory')
check('task-ref edge', any(e['target'] == 'task-ref:T-021' and e['type'] == 'mentions' for e in j['edges']))
check('no raw client text anywhere in payload', 'Pagliano' not in str(j))
n_calls = len(calls); c.get('/api/context/memory', headers=sa)
check('cache hit (no extra recall)', len(calls) == n_calls)
d = c.get('/api/context/digest', headers=sa).get_json()
check('digest <=8, is_today', len(d['items']) == 8 and d['is_today'] is True and d['date'] == today)
cm._cache.clear(); cm._recall = lambda q, n: None
check('upstream down -> 200 unavailable', c.get('/api/context/memory', headers=sa).get_json()['source'] == 'unavailable')
cm._cache.clear(); cm._recall = lambda q, n: [{'id': 'o', 'text': 'old', 'occurred_start': '2026-01-01T00:00:00+00:00'}]
d = c.get('/api/context/digest', headers=sa).get_json()
check('digest fallback flagged', d['is_today'] is False and len(d['items']) == 1)

if LIVE:
    import importlib; importlib.reload(cm)
    os.environ.update({k: v for k, v in live_env.items() if v})
    r = cm._recall(cm.GRAPH_QUERY, 40)
    p = cm.build_memory_payload(r)
    print('LIVE source:', p['source'], 'nodes:', len(p['nodes']), 'edges:', len(p['edges']))
    check('live recall returns nodes', p['source'] == 'hindsight' and len(p['nodes']) > 0)
    check('live: no client name leak', 'Pagliano' not in str(p) and 'PAGLIANO' not in str(p))

# existing pages unaffected
for pth in ('/', '/login', '/dashboard'):
    check(f'{pth} 200', c.get(pth).status_code == 200)
print('RESULT:', 'ALL PASS' if not fails else f'{len(fails)} FAILED: {fails}')
sys.exit(1 if fails else 0)

"""Matter-stage checklist (WS-K, feat/wave2-checklist) — tests.

Dual-mode (brief rule 8):
  * plain script:  python tests/test_checklist.py   -> prints PASS/FAIL + RESULT, exits 1 on fail
  * pytest:        python -m pytest tests/test_checklist.py -q

There is NO module-level sys.exit, so pytest can collect this file without a
collect_ignore entry: the heavy logic lives in run() and pytest discovers the
thin test_checklist() wrapper. (backend-dev: this file does NOT need to be added
to collect_ignore.)
"""
import os
import sys
import json
import tempfile
import subprocess

# Env MUST be set before importing crm. setdefault respects conftest.py when run
# under pytest (shared throwaway sqlite); provides our own throwaway DB as a plain
# script. The feature flag is forced ON for the main run (toggled OFF later).
os.environ.setdefault('DATABASE_URL', f"sqlite:///{tempfile.mkdtemp()}/checklist_test.db")
os.environ.setdefault('SECRET_KEY', 'dev')
os.environ.setdefault('JWT_SECRET_KEY', 'dev-jwt-secret-key-0123456789abcdef')
os.environ.setdefault('CORS_ORIGINS', 'http://x')
os.environ.setdefault('RATELIMIT_STORAGE_URL', 'memory://')
os.environ.setdefault('SEED_OLEYA00007YAHOO_PASSWORD', 'Test12345!')
os.environ['MATTER_CHECKLIST_ENABLED'] = '1'

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from datetime import date, datetime, timedelta

from crm import create_app, _seed_default_users
from crm.extensions import db
from crm.models.workspace import Workspace
from crm.models.user import User
from crm.models.contact import Contact
from crm.models.case import Case
from crm.models.task import Task
from crm.models.matter_checklist import MatterChecklistItem
from crm.routes.checklist import checklist_bp


def _build_app():
    app = create_app()
    # The checklist blueprint is registered by backend-dev in crm/__init__.py at
    # integration (shared file). Here we register it ourselves so the feature is
    # exercised in isolation.
    if 'checklist' not in app.blueprints:
        app.register_blueprint(checklist_bp)
    return app


def run():
    app = _build_app()
    c = app.test_client()
    fails = []

    def check(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        if not cond:
            fails.append(name)

    # ── seed isolated tenants (unique slugs so we never collide with other data) ──
    with app.app_context():
        db.create_all()
        _seed_default_users()
        sa = User.query.filter_by(email='olesya00007@yahoo.com').first()

        def mk_ws(slug, parent=None):
            w = Workspace.query.filter_by(slug=slug).first()
            if not w:
                w = Workspace(slug=slug, name=slug, is_active=True,
                              parent_workspace_id=(parent.id if parent else None))
                db.session.add(w); db.session.flush()
            return w

        firm = mk_ws('wsk-firm')
        sub = mk_ws('wsk-sub', parent=firm)
        foreign = mk_ws('wsk-foreign')

        def mk_user(email, role, ws, pw='Test12345!'):
            u = User.query.filter_by(email=email).first()
            if not u:
                u = User(email=email, role=role, workspace_id=ws.id)
                u.set_password(pw); db.session.add(u); db.session.flush()
            return u

        firm_admin = mk_user('wsk-firm-admin@x.it', 'admin', firm)
        firm_staff = mk_user('wsk-firm-staff@x.it', 'user', firm)
        sub_admin = mk_user('wsk-sub-admin@x.it', 'admin', sub)
        foreign_admin = mk_user('wsk-foreign-admin@x.it', 'admin', foreign)

        def mk_case(ws, title, case_no):
            ct = Contact(fullname='PII-NAME-' + case_no, email='pii-%s@x.it' % case_no,
                         status='active', workspace_id=ws.id)
            db.session.add(ct); db.session.flush()
            cs = Case(workspace_id=ws.id, contactid=ct.id, ownerid=sa.id,
                      title=title, status='Active', case_no=case_no)
            db.session.add(cs); db.session.flush()
            return cs

        firm_case = mk_case(firm, 'Rasing separazione', 'WK-01')
        sub_case = mk_case(sub, 'Sub matter', 'WK-02')
        foreign_case = mk_case(foreign, 'Foreign matter', 'WK-99')

        # Hand-built fixture case for current_stage / next_missing / progress logic
        logic_case = mk_case(firm, 'Logic fixture', 'WK-03')
        # stage A fully resolved (done + not_applicable); stage B has in_progress
        # then todo (next_missing = the todo); stage C blocked (upcoming)
        items_spec = [
            ('lg_a', 0, 'Doc A done', 'done'),
            ('lg_a', 1, 'Doc A n/a', 'not_applicable'),
            ('lg_b', 2, 'Action B running', 'in_progress'),
            ('lg_b', 3, 'Doc B missing', 'todo'),
            ('lg_c', 4, 'Deadline C blocked', 'blocked'),
            ('lg_c', 5, 'Action C later', 'todo'),
        ]
        for sk, pos, label, st in items_spec:
            it = MatterChecklistItem(workspace_id=firm.id, caseid=logic_case.id,
                                     stage_key=sk, position=pos, label=label,
                                     kind='action', status=st)
            if st == 'blocked':
                it.blocked_reason = 'Waiting on court'
            db.session.add(it)

        # Cases for next-actions ordering: overdue, future, no-due (all in firm)
        na_over = mk_case(firm, 'NA overdue', 'WK-10')
        na_future = mk_case(firm, 'NA future', 'WK-11')
        na_nodue = mk_case(firm, 'NA nodue', 'WK-12')
        db.session.add(MatterChecklistItem(workspace_id=firm.id, caseid=na_over.id,
            stage_key='sep_documents', position=0, label='Overdue doc', kind='document',
            status='todo', due_date=date.today() - timedelta(days=5)))
        db.session.add(MatterChecklistItem(workspace_id=firm.id, caseid=na_future.id,
            stage_key='sep_documents', position=0, label='Future doc', kind='document',
            status='todo', due_date=date.today() + timedelta(days=5)))
        db.session.add(MatterChecklistItem(workspace_id=firm.id, caseid=na_nodue.id,
            stage_key='sep_documents', position=0, label='No-due doc', kind='document',
            status='blocked', blocked_reason='missing info'))
        # a foreign matter with a missing item (must NOT appear for firm admin)
        db.session.add(MatterChecklistItem(workspace_id=foreign.id, caseid=foreign_case.id,
            stage_key='sep_documents', position=0, label='Foreign todo', kind='document',
            status='todo', due_date=date.today() - timedelta(days=1)))
        db.session.commit()

        ids = dict(
            firm_case=firm_case.id, sub_case=sub_case.id, foreign_case=foreign_case.id,
            logic_case=logic_case.id, na_over=na_over.id, na_future=na_future.id,
            na_nodue=na_nodue.id, foreign_cid=foreign_case.id,
        )

    def login(email, pw='Test12345!'):
        r = c.post('/api/auth/login', json={'email': email, 'password': pw})
        return {'Authorization': 'Bearer ' + r.get_json()['access_token']}

    SA = login('olesya00007@yahoo.com')
    FA = login('wsk-firm-admin@x.it')
    FS = login('wsk-firm-staff@x.it')
    SUB = login('wsk-sub-admin@x.it')
    FOR = login('wsk-foreign-admin@x.it')

    # ── templates ──
    r = c.get('/api/checklist/templates', headers=FA)
    body = r.get_json()
    keys = {t['key'] for t in body['templates']}
    check('templates: 200 with both template keys',
          r.status_code == 200 and {'family_separation_it', 'generic_civil'} <= keys)
    check('templates: separazione has 8 stages',
          any(t['key'] == 'family_separation_it' and len(t['stages']) == 8 for t in body['templates']))
    check('templates: DRAFT disclaimer present', 'DRAFT' in (body.get('disclaimer') or ''))

    # ── init + idempotency ──
    r = c.post('/api/cases/%d/checklist/init' % ids['firm_case'], headers=FA,
               json={'template': 'family_separation_it'})
    check('init: firm admin instantiates (201)', r.status_code == 201 and r.get_json()['created'] > 0)
    created_n = r.get_json()['created']
    check('init: idempotent 409 on re-init',
          c.post('/api/cases/%d/checklist/init' % ids['firm_case'], headers=FA,
                 json={'template': 'family_separation_it'}).status_code == 409)
    r = c.post('/api/cases/%d/checklist/init' % ids['firm_case'], headers=FA,
               json={'template': 'family_separation_it', 'force': True})
    check('init: force re-init (201) same count', r.status_code == 201 and r.get_json()['created'] == created_n)
    check('init: unknown template -> 400',
          c.post('/api/cases/%d/checklist/init' % ids['firm_case'], headers=FA,
                 json={'template': 'nope'}).status_code == 400)
    check('init: non-admin (staff) -> 403',
          c.post('/api/cases/%d/checklist/init' % ids['firm_case'], headers=FS,
                 json={'template': 'generic_civil'}).status_code == 403)
    check('init: bad (non-int) case id -> 404',
          c.post('/api/cases/abc/checklist/init', headers=FA, json={'template': 'generic_civil'}).status_code == 404)

    # ── GET checklist structure ──
    r = c.get('/api/cases/%d/checklist' % ids['firm_case'], headers=FA)
    gj = r.get_json()
    check('get: 200 with stages + current_stage + progress',
          r.status_code == 200 and gj['current_stage'] == 'sep_intake'
          and gj['progress'] == 0 and len(gj['stages']) == 8)
    check('get: next_missing is first intake item',
          gj['next_missing'] and gj['next_missing']['stage_key'] == 'sep_intake')
    check('get: firm admin does NOT see vault_ref key (not superadmin)',
          'vault_ref' not in gj['stages'][0]['items'][0])

    # ── hand-built current_stage / next_missing / progress logic ──
    r = c.get('/api/cases/%d/checklist' % ids['logic_case'], headers=FA)
    lg = r.get_json()
    check('logic: current_stage skips fully-resolved stage A -> lg_b', lg['current_stage'] == 'lg_b')
    check('logic: next_missing is the todo (not the in_progress)',
          lg['next_missing'] and lg['next_missing']['label'] == 'Doc B missing')
    check('logic: progress = 2/6 = 33%%', lg['progress'] == 33)
    state_by_key = {s['key']: s['state'] for s in lg['stages']}
    check('logic: stage A done, B current, C upcoming',
          state_by_key == {'lg_a': 'done', 'lg_b': 'current', 'lg_c': 'upcoming'})
    # blocked item carries its reason through
    blocked = [it for s in lg['stages'] for it in s['items'] if it['status'] == 'blocked']
    check('logic: blocked item keeps blocked_reason',
          blocked and blocked[0]['blocked_reason'] == 'Waiting on court')

    # ── PATCH: permissions + validation ──
    first_item_id = gj['stages'][0]['items'][0]['id']
    r = c.patch('/api/checklist/items/%d' % first_item_id, headers=FS, json={'status': 'done'})
    check('patch: any visible user may set status (staff) -> 200 + completed_by',
          r.status_code == 200 and r.get_json()['completed_by'] is not None)
    check('patch: staff cannot set owner_role -> 403',
          c.patch('/api/checklist/items/%d' % first_item_id, headers=FS,
                  json={'owner_role': 'lawyer_review'}).status_code == 403)
    check('patch: staff cannot set due_date -> 403',
          c.patch('/api/checklist/items/%d' % first_item_id, headers=FS,
                  json={'due_date': '2027-01-01'}).status_code == 403)
    check('patch: staff cannot set vault_ref -> 403',
          c.patch('/api/checklist/items/%d' % first_item_id, headers=FS,
                  json={'vault_ref': 'Clients/X'}).status_code == 403)
    check('patch: firm admin sets owner_role (200)',
          c.patch('/api/checklist/items/%d' % first_item_id, headers=FA,
                  json={'owner_role': 'lawyer_review'}).status_code == 200)
    check('patch: invalid owner_role -> 400',
          c.patch('/api/checklist/items/%d' % first_item_id, headers=FA,
                  json={'owner_role': 'boss'}).status_code == 400)
    check('patch: firm admin sets due_date (200)',
          c.patch('/api/checklist/items/%d' % first_item_id, headers=FA,
                  json={'due_date': '2027-03-01'}).status_code == 200)
    check('patch: invalid due_date -> 400',
          c.patch('/api/checklist/items/%d' % first_item_id, headers=FA,
                  json={'due_date': 'not-a-date'}).status_code == 400)
    check('patch: invalid status enum -> 400',
          c.patch('/api/checklist/items/%d' % first_item_id, headers=FA,
                  json={'status': 'frozen'}).status_code == 400)
    check('patch: oversize blocked_reason -> 400',
          c.patch('/api/checklist/items/%d' % first_item_id, headers=FA,
                  json={'blocked_reason': 'x' * 301}).status_code == 400)
    check('patch: superadmin sets vault_ref (200)',
          c.patch('/api/checklist/items/%d' % first_item_id, headers=SA,
                  json={'vault_ref': 'Clients/Rasing'}).status_code == 200)
    check('patch: vault_ref traversal rejected -> 400',
          c.patch('/api/checklist/items/%d' % first_item_id, headers=SA,
                  json={'vault_ref': '../outside'}).status_code == 400)
    check('patch: firm admin cannot set vault_ref -> 403',
          c.patch('/api/checklist/items/%d' % first_item_id, headers=FA,
                  json={'vault_ref': 'Clients/Rasing'}).status_code == 403)
    check('patch: bad (non-int) item id -> 404',
          c.patch('/api/checklist/items/abc', headers=FA, json={'status': 'done'}).status_code == 404)
    check('patch: non-existent item id -> 404',
          c.patch('/api/checklist/items/99999999', headers=FA, json={'status': 'done'}).status_code == 404)
    # superadmin to_dict exposes vault_ref key
    r = c.get('/api/cases/%d/checklist' % ids['firm_case'], headers=SA)
    check('get: superadmin sees vault_ref + vault_docs_api keys',
          'vault_ref' in r.get_json()['stages'][0]['items'][0]
          and 'vault_docs_api' in r.get_json()['stages'][0]['items'][0])

    # ── materialize (idempotent) ──
    mat_item = gj['stages'][1]['items'][0]['id']  # a mandate-stage item
    r = c.post('/api/checklist/items/%d/materialize' % mat_item, headers=FA)
    check('materialize: creates task (201, created True)', r.status_code == 201 and r.get_json()['created'] is True)
    tid = r.get_json()['task_id']
    r2 = c.post('/api/checklist/items/%d/materialize' % mat_item, headers=FA)
    check('materialize: idempotent (200, same task_id, created False)',
          r2.status_code == 200 and r2.get_json()['task_id'] == tid and r2.get_json()['created'] is False)
    with app.app_context():
        t = Task.query.get(tid)
        check('materialize: task title is "[stage] label", duedate linked',
              t is not None and t.title.startswith('[') and t.caseid == ids['firm_case'])

    # ── next-actions (agent endpoint): ordering + one-per-matter + no PII ──
    r = c.get('/api/checklist/next-actions?limit=50', headers=FA)
    na = r.get_json()
    labels_order = [a['label'] for a in na['actions']]
    # firm admin sees firm + sub, NOT foreign
    check('next-actions: foreign matter NOT visible to firm admin',
          all(a['case_no'] != 'WK-99' for a in na['actions']))
    # overdue (due -5) before future (due +5) before no-due (null)
    idx = {lbl: i for i, lbl in enumerate(labels_order)}
    check('next-actions: due asc, nulls last (overdue<future<nodue)',
          'Overdue doc' in idx and 'Future doc' in idx and 'No-due doc' in idx
          and idx['Overdue doc'] < idx['Future doc'] < idx['No-due doc'])
    over_entry = next(a for a in na['actions'] if a['label'] == 'Overdue doc')
    check('next-actions: days_overdue computed (>=5)', over_entry['days_overdue'] >= 5)
    check('next-actions: one entry per matter (unique case_ids)',
          len({a['case_id'] for a in na['actions']}) == len(na['actions']))
    check('next-actions: NO client names/emails leaked',
          'PII-NAME' not in r.get_data(as_text=True) and '@x.it' not in r.get_data(as_text=True))
    check('next-actions: firm admin has no vault_docs_api key (not superadmin)',
          all('vault_docs_api' not in a for a in na['actions']))
    # superadmin sees foreign + vault_docs_api key
    rsa = c.get('/api/checklist/next-actions?limit=50', headers=SA)
    nasa = rsa.get_json()
    check('next-actions: superadmin sees foreign matter (WK-99)',
          any(a['case_no'] == 'WK-99' for a in nasa['actions']))
    check('next-actions: superadmin entries carry vault_docs_api key',
          all('vault_docs_api' in a for a in nasa['actions']))
    check('next-actions: limit is clamped/honoured',
          len(c.get('/api/checklist/next-actions?limit=1', headers=SA).get_json()['actions']) == 1)
    check('next-actions: bad limit falls back (no 500)',
          c.get('/api/checklist/next-actions?limit=abc', headers=FA).status_code == 200)

    # ── FOUR-ACTOR TENANT MATRIX ──
    # foreign admin cannot read/write/init the firm matter
    check('tenant: foreign admin GET firm checklist -> 404',
          c.get('/api/cases/%d/checklist' % ids['firm_case'], headers=FOR).status_code == 404)
    check('tenant: foreign admin PATCH firm item -> 404',
          c.patch('/api/checklist/items/%d' % first_item_id, headers=FOR,
                  json={'status': 'done'}).status_code == 404)
    check('tenant: foreign admin init firm case -> 404',
          c.post('/api/cases/%d/checklist/init' % ids['firm_case'], headers=FOR,
                 json={'template': 'generic_civil'}).status_code == 404)
    check('tenant: foreign admin materialize firm item -> 404',
          c.post('/api/checklist/items/%d/materialize' % first_item_id, headers=FOR).status_code == 404)
    # client-sub admin cannot see the PARENT firm matter
    check('tenant: sub admin GET firm checklist -> 404 (child cannot see parent)',
          c.get('/api/cases/%d/checklist' % ids['firm_case'], headers=SUB).status_code == 404)
    # parent firm admin CAN see the child sub matter (after init)
    c.post('/api/cases/%d/checklist/init' % ids['sub_case'], headers=SUB, json={'template': 'generic_civil'})
    check('tenant: firm admin GET sub (child) checklist -> 200 (parent sees child)',
          c.get('/api/cases/%d/checklist' % ids['sub_case'], headers=FA).status_code == 200)
    # anonymous cannot read the API
    check('tenant: anonymous GET checklist -> 401/422',
          c.get('/api/cases/%d/checklist' % ids['firm_case']).status_code in (401, 422))

    # ── HTML page shell ──
    r = c.get('/cases/%d/checklist' % ids['firm_case'], headers=FA)
    check('page: /cases/<id>/checklist renders shell (200)',
          r.status_code == 200 and b'checklist' in r.get_data().lower())

    # ── FLAG OFF: every route 404, query param cannot force it on ──
    os.environ['MATTER_CHECKLIST_ENABLED'] = 'false'
    try:
        check('flag-off: GET templates -> 404',
              c.get('/api/checklist/templates', headers=SA).status_code == 404)
        check('flag-off: GET checklist -> 404',
              c.get('/api/cases/%d/checklist' % ids['firm_case'], headers=SA).status_code == 404)
        check('flag-off: POST init -> 404',
              c.post('/api/cases/%d/checklist/init' % ids['firm_case'], headers=SA,
                     json={'template': 'generic_civil'}).status_code == 404)
        check('flag-off: PATCH item -> 404',
              c.patch('/api/checklist/items/%d' % first_item_id, headers=SA,
                      json={'status': 'todo'}).status_code == 404)
        check('flag-off: POST materialize -> 404',
              c.post('/api/checklist/items/%d/materialize' % first_item_id, headers=SA).status_code == 404)
        check('flag-off: GET next-actions -> 404',
              c.get('/api/checklist/next-actions', headers=SA).status_code == 404)
        check('flag-off: page -> 404',
              c.get('/cases/%d/checklist' % ids['firm_case'], headers=SA).status_code == 404)
        check('flag-off: query param CANNOT force feature on (next-actions) -> 404',
              c.get('/api/checklist/next-actions?MATTER_CHECKLIST_ENABLED=1', headers=SA).status_code == 404)
        check('flag-off: query param CANNOT force feature on (page) -> 404',
              c.get('/cases/%d/checklist?MATTER_CHECKLIST_ENABLED=true' % ids['firm_case'], headers=SA).status_code == 404)
    finally:
        os.environ['MATTER_CHECKLIST_ENABLED'] = '1'

    # ── migration: single head + empty-sqlite upgrade (isolated subprocess) ──
    from alembic.config import Config as _ACfg
    from alembic.script import ScriptDirectory
    _cfg = _ACfg(); _cfg.set_main_option('script_location', 'migrations')
    heads = ScriptDirectory.from_config(_cfg).get_heads()
    check('migration: single alembic head == j1e2f3a4b5c6', list(heads) == ['j1e2f3a4b5c6'])

    _probe = (
        "import os,tempfile\n"
        "tmp=tempfile.mkdtemp()\n"
        "os.environ.update(DATABASE_URL='sqlite:///'+tmp+'/m.db',SECRET_KEY='d',"
        "JWT_SECRET_KEY='dev-jwt-secret-key-0123456789abcdef',CORS_ORIGINS='http://x',"
        "RATELIMIT_STORAGE_URL='memory://',SEED_OLEYA00007YAHOO_PASSWORD='Test12345!',"
        "MATTER_CHECKLIST_ENABLED='1')\n"
        "from crm import create_app\nfrom crm.extensions import db\n"
        "from flask_migrate import upgrade\nfrom sqlalchemy import inspect\n"
        "app=create_app()\n"
        "with app.app_context():\n"
        "    upgrade(directory='migrations')\n"
        "    print('CHKTBL', 'matter_checklist_items' in inspect(db.engine).get_table_names())\n"
    )
    proc = subprocess.run([sys.executable, '-c', _probe], cwd=_REPO,
                          capture_output=True, text=True, env=dict(os.environ))
    check('migration: flask_migrate.upgrade on empty sqlite creates table',
          'CHKTBL True' in proc.stdout)

    print('\nRESULT: ' + ('ALL PASS' if not fails else 'FAILED: ' + '; '.join(fails)))
    return fails


def test_checklist():
    """pytest entry point — asserts the whole suite passes."""
    fails = run()
    assert not fails, 'checklist failures: ' + '; '.join(fails)


if __name__ == '__main__':
    sys.exit(1 if run() else 0)

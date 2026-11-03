from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / 'tests'))
from test_agent import build_state, _restore_env  # noqa: E402,F401


def _get(st, who, path):
    return st['client'].get(path, headers=st['headers'][who])


def test_menu_has_new_sections_and_version_on_every_base_page():
    st = build_state()
    for path in ('/dashboard', '/contacts', '/calendar', '/tasks', '/settings', '/templates', '/my-drafts', '/document-center'):
        r = _get(st, 'super', path)
        assert r.status_code == 200, (path, r.status_code)
        h = r.get_data(as_text=True)
        for needle in ('Configuration', 'Templates', 'My drafts', 'Document center', 'nav-ver', 'schema m4a5b6c7d8e9', 'position:sticky'):
            assert needle in h, (path, needle)


def test_architecture_index_is_superadmin_only():
    st = build_state()
    sa = st['client'].get('/api/docs-index', headers=st['headers']['super'])
    assert sa.status_code == 200
    d = sa.get_json()
    assert d['repo_url'].startswith('https://github.com/') and any(x['name'].endswith('.json') for x in d['docs'])
    assert st['client'].get('/api/docs-index', headers=st['headers']['romanelli']).status_code == 403
    assert st['client'].get('/api/docs-index').status_code == 401
    # the page itself never contains the file list or repo link
    h = _get(st, 'super', '/document-center').get_data(as_text=True)
    assert 'LexFlow_Agentic_Roadmap.json' not in h


def test_version_dict_never_raises(monkeypatch):
    from crm import version
    version.get_version.cache_clear()
    monkeypatch.setenv('LEXFLOW_VERSION', 'v-test')
    assert version.get_version()['version'] == 'v-test'
    version.get_version.cache_clear()

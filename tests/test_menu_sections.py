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
        for needle in ('Configuration', 'Templates', 'My drafts', 'Document center', 'nav-ver', 'schema m4a5b6c7d8e9'):
            assert needle in h, (path, needle)


def test_architecture_index_is_superadmin_only():
    st = build_state()
    sa = _get(st, 'super', '/document-center').get_data(as_text=True)
    ten = _get(st, 'romanelli', '/document-center').get_data(as_text=True)
    assert 'github.com/Ole00007/lexflow-crm/blob/' in sa
    assert 'github.com' not in ten and 'Docs &amp; architecture index' not in ten


def test_version_dict_never_raises(monkeypatch):
    from crm import version
    version.get_version.cache_clear()
    monkeypatch.setenv('LEXFLOW_VERSION', 'v-test')
    assert version.get_version()['version'] == 'v-test'
    version.get_version.cache_clear()

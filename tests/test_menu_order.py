from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / 'tests'))
from test_agent import build_state, _restore_env  # noqa: E402,F401


def _get(st, who, path):
    return st['client'].get(path, headers=st['headers'][who])


def test_sidebar_order_matters_and_firm_team_after_contacts_before_kanban():
    st = build_state()
    r = _get(st, 'super', '/dashboard')
    assert r.status_code == 200
    h = r.get_data(as_text=True)

    # Sidebar links, not any incidental copy on the page: scope to the nav-list markup.
    nav = h[h.index('<ul class="nav-list">'):h.index('</ul>', h.index('<ul class="nav-list">'))]

    i_contacts = nav.index('>Contacts</a>')
    i_matters = nav.index('>Matters</a>')
    i_firm_team = nav.index('>Firm Team</a>')
    i_kanban = nav.index('>Kanban <')

    assert i_contacts < i_matters, 'Matters must come after Contacts in the sidebar'
    assert i_contacts < i_firm_team, 'Firm Team must come after Contacts in the sidebar'
    assert i_matters < i_kanban, 'Matters must come before Kanban in the sidebar'
    assert i_firm_team < i_kanban, 'Firm Team must come before Kanban in the sidebar'
    assert i_matters < i_firm_team, 'Firm Team must come after Matters in the sidebar'

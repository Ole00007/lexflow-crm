"""
Calendar filter tests (PART A3).

Two layers:
  1. Server: GET /api/calendar honours event_type / date_from / date_to — the
     query parameters the calendar page sends.
  2. Client wiring (JS-level check by source inspection): the template mounts
     the shared client-side predicate and applies it in BOTH the grid
     (month/week/day) and the list, so the reported bug (grid ignored the
     from/to controls and deadline-merged events bypassed the server type
     filter) is fixed at the view layer.
"""
import os
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
CAL = TEMPLATES / "calendar.html"


def _mk(client, headers, name, ev_type, start, status="scheduled"):
    r = client.post("/api/calendar", json={
        "title": name, "event_type": ev_type,
        "start_datetime": start, "status": status,
    }, headers=headers)
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    return r.get_json()["id"]


def test_calendar_server_filters_by_type_and_range(client, superadmin_headers):
    _mk(client, superadmin_headers, "Hear A", "hearing", "2026-11-10T09:00:00")
    _mk(client, superadmin_headers, "Dead B", "filing_deadline", "2026-11-20T23:59:00")

    # type-only filter
    r = client.get("/api/calendar?event_type=hearing", headers=superadmin_headers)
    assert r.status_code == 200
    evs = r.get_json()
    assert evs, "expected at least one hearing"
    assert all(e.get("event_type") == "hearing" for e in evs)

    # date-range filter
    r = client.get("/api/calendar?date_from=2026-11-19T00:00:00&date_to=2026-11-21T00:00:00",
                   headers=superadmin_headers)
    assert r.status_code == 200
    evs = r.get_json()
    assert evs, "expected events within the range"
    for e in evs:
        assert "2026-11-19" <= str(e.get("start_datetime"))[:10] <= "2026-11-21"

    # combined
    r = client.get("/api/calendar?event_type=filing_deadline&date_from=2026-11-01T00:00:00&date_to=2026-12-01T00:00:00",
                   headers=superadmin_headers)
    assert r.status_code == 200
    evs = r.get_json()
    assert all(e.get("event_type") == "filing_deadline" for e in evs)


def test_calendar_client_wiring_matches_grid_and_list():
    """The shared \"Filter ▾\" dropdown (window.TaskFilters) must be wired up so a
    single client-side predicate drives BOTH the grid (month/week/day) AND the
    list, every choice applies instantly, and the banner is the component's."""
    assert CAL.exists(), f"missing {CAL}"
    src = CAL.read_text(encoding="utf-8")

    # Shared component is loaded and mounted; the OLD controls are gone
    assert "js/filters/task_filters.js" in src
    assert 'id="calFilterMount"' in src
    # calendar keeps its own persisted key (state survives reloads like other views)
    assert "key: 'lf_calendar_filter'" in src
    assert "window.TaskFilters.create" in src

    # The bare apply-button + select + date inputs that did nothing are removed
    assert 'id="filterType"' not in src
    assert 'id="filterFrom"' not in src
    assert 'id="filterTo"' not in src
    assert "calFilterBanner" not in src

    # Panel groups the calendar needs, all applying instantly (no apply button)
    assert "typeChips: calTypeChips" in src           # real types present in events
    assert "dateRange: true" in src                    # From / To
    assert "showChips: ['all', 'open']" in src         # All + "Open only"
    assert "'Open only'" in src
    assert 'onApply: calRender' in src                 # re-renders grid + list instantly

    # Both the list path and the grid path push loaded events into the SAME
    # filter model, so a type choice changes the rendered count in every view.
    assert "mergeItems(all || []); calFilterRefresh()" in src   # list path
    assert "mergeItems(events || []); calFilterRefresh()" in src  # grid (loadGrid) path
    assert "function calRender(visible, meta)" in src
    assert "GridState.events = visible || []" in src   # grid renders filtered subset
    assert "el.innerHTML = visible.map(eventCardHTML).join('')" in src   # list renders filtered subset

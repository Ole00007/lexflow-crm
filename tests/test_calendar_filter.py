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
    """The client-side predicate + banner must be present and applied in both
    the grid (month/week/day) and the list, so no view ignores the filters."""
    assert CAL.exists(), f"missing {CAL}"
    src = CAL.read_text(encoding="utf-8")

    # Shared client-side predicate exists
    assert "function calMatches(e)" in src
    assert "function calType()" in src
    assert "params.push('event_type='+ft)" in src  # grid narrows server fetch by type
    assert "GridState.events = all.filter(calMatches)" in src  # grid applies client filter

    # Both the list and the grid apply the SAME predicate
    assert "calMatchesAll(all)" in src                      # list path
    assert "GridState.events = all.filter(calMatches)" in src

    # A4 always-visible banner is mounted and cleared from the same controls
    assert 'id="calFilterBanner"' in src
    assert "function updateCalBanner" in src
    assert "function clearCalFilters" in src

    # The Filter button still re-runs both list + grid (existing onclick kept)
    assert 'loadEvents(); gridRefresh()' in src

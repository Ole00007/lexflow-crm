"""JOB 7 — headless JS-level check that the calendar YEAR view behaves as specced.

Runs tests/calendar_year_view.js with Node (no server, no browser): it loads the
REAL year-view functions and the real calendar makeDate-range/render pipeline
extracted from templates/calendar.html, then asserts
  - the year date range sent to /api/calendar (Jan 1 .. Dec 31),
  - dot vs count-badge output for a seeded day,
  - click-through to the Day view (a day) and Month view (a month header),
  - prev/next stepping the year by exactly one,
  - the shared Filter push-down (calRender -> renderGrid -> renderYear) is
    respected: a filtered subset yields fewer dots.

Requires a `node` binary; skipped cleanly when unavailable so the suite still
passes on machines without Node.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
JS_SCRIPT = TESTS / "calendar_year_view.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_calendar_year_view_headless():
    if not JS_SCRIPT.exists():
        pytest.fail(f"missing {JS_SCRIPT}")
    node_bin = shutil.which("node")
    assert node_bin, "node on PATH despite skipif"
    r = subprocess.run(
        [node_bin, str(JS_SCRIPT)],
        capture_output=True, text=True,
    )
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        pytest.fail("JS-level calendar year-view check failed (see output)")
    # the script MUST prove the four acceptance criteria
    assert "SUMMARY year_range=true" in r.stdout
    assert "dot_count_seed=true" in r.stdout
    assert "filter_respected=true" in r.stdout

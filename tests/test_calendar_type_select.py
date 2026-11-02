"""JOB 6 — headless JS-level check that selecting an Event-type chip in the
calendar filter changes the RENDERED event count.

Runs tests/calendar_type_filter.js with Node (no server, no browser): it loads
the REAL shared component (static/js/filters/task_filters.js) and the REAL
calendar feature functions extracted from templates/calendar.html, then drives
the exact single predicate the dropdown uses and asserts the matched-count
changes when state.type changes (hearing/meeting/deadline/task_due).

Requires a `node` binary; skipped cleanly when unavailable so the suite still
passes on machines without Node.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
JS_SCRIPT = TESTS / "calendar_type_filter.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_selecting_calendar_type_changes_rendered_count():
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
        pytest.fail("JS-level calendar type-filter check failed (see output)")
    # the script MUST prove the type chip changes the count
    assert "SUMMARY selected_type_changes_count=true" in r.stdout
    assert "COUNTS all=" in r.stdout

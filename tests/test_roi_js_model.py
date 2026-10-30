"""JOB 5 — pure-JS model tests for the ROI calculator (two scenarios).

The calculator math is client-side JS (window.ROICalculator). This suite runs
the model in Node via tests/roi_js_model_test.js and asserts the exit code +
that Node is present. Python route tests are unchanged; this file only adds
model coverage for:
  - conservative & expected scenarios (covers the default headline sanity)
  - the derive-from-baseline hours-saved path
  - setup cost / training / payback
  - ramp-up months
  - assistants
"""
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
JS_TEST = BASE / "tests" / "roi_js_model_test.js"


def _node():
    return shutil.which("node") or shutil.which("nodejs")


def test_roi_js_model_all_scenarios_and_paths():
    """Run the Node model test harness; any failed assertion exits non-zero."""
    node = _node()
    if not node:
        import pytest  # noqa: PLC0415
        pytest.skip("Node not available — skipping JS model tests (route tests still run)")
    assert node  # narrow type for the subprocess call
    res = subprocess.run(
        [node, str(JS_TEST)],
        capture_output=True,
        text=True,
        cwd=str(BASE),
        timeout=60,
    )
    # On failure, surface the harness output so the failure is debuggable.
    log = (res.stdout + "\n" + res.stderr).strip()
    assert res.returncode == 0, f"JS model tests failed (exit {res.returncode}):\n{log}"
    assert "ALL PASS" in res.stdout, f"Expected ALL PASS marker; got:\n{log}"

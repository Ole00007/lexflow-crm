import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tests'))
from conftest import SCRIPT_TESTS  # noqa: E402


@pytest.mark.parametrize('script', SCRIPT_TESTS)
def test_plain_script_passes(script):
    r = subprocess.run([sys.executable, str(REPO / 'tests' / script)], capture_output=True, text=True, timeout=280, cwd=str(REPO))
    assert r.returncode == 0, (script + '\\n' + r.stdout[-1500:] + r.stderr[-800:])

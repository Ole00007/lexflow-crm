import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tests'))
from conftest import ENV_TESTS, SCRIPT_TESTS  # noqa: E402


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=500, cwd=str(REPO))


@pytest.mark.parametrize('script', SCRIPT_TESTS)
def test_plain_script_passes(script):
    r = _run([sys.executable, str(REPO / 'tests' / script)])
    assert r.returncode == 0, script + ' | ' + r.stdout[-1500:] + r.stderr[-800:]


@pytest.mark.parametrize('name', ENV_TESTS)
def test_env_isolated_file_passes(name):
    r = _run([sys.executable, '-m', 'pytest', str(REPO / 'tests' / name), '-q', '-W', 'ignore', '-p', 'no:cacheprovider'])
    assert r.returncode == 0, name + ' | ' + r.stdout[-1800:]

"""Which build is this? Shown in the sidebar 'Configuration' dropdown. Read once, cached, never raises."""
from __future__ import annotations

import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    try:
        return subprocess.run(['git', '-C', str(_ROOT), *args], capture_output=True, text=True, timeout=3).stdout.strip()
    except Exception:
        return ''


def _alembic_head() -> str:
    defined, parents = set(), set()
    try:
        for f in (_ROOT / 'migrations' / 'versions').glob('*.py'):
            t = f.read_text(encoding='utf-8', errors='ignore')
            r = re.search(r"^revision\s*=\s*'([^']+)'", t, re.M)
            d = re.search(r"^down_revision\s*=\s*(.+)$", t, re.M)   # str, None or tuple (merge revision)
            if r:
                defined.add(r.group(1))
            if d:
                parents.update(re.findall(r"'([^']+)'", d.group(1)))
    except Exception:
        return ''
    heads = defined - parents
    return sorted(heads)[0] if len(heads) == 1 else ''


@lru_cache(maxsize=1)
def get_version() -> dict:
    sha = os.environ.get('RAILWAY_GIT_COMMIT_SHA') or os.environ.get('GIT_COMMIT') or _git('rev-parse', '--short', 'HEAD')
    return {
        'version': os.environ.get('LEXFLOW_VERSION') or _git('describe', '--tags', '--always') or (sha[:7] if sha else 'dev'),
        'commit': (sha or '')[:7] or 'unknown',
        'branch': os.environ.get('RAILWAY_GIT_BRANCH') or _git('rev-parse', '--abbrev-ref', 'HEAD') or 'unknown',
        'schema': _alembic_head() or 'unknown',
    }

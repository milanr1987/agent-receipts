from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import re
from .ingest.common import read_rows
from .messages import t


def parse_since(value):
    if value is None:
        return None
    match = re.fullmatch(r'(\d+)([dh])', value)
    if not match:
        raise ValueError(t('bad_since'))
    return datetime.now(timezone.utc) - timedelta(**{'days' if match[2] == 'd' else 'hours': int(match[1])})


def _project_cwd(path):
    rows, _ = read_rows(path)
    for _, row in rows:
        data = row.get('payload', {})
        cwd = row.get('cwd') or (data.get('cwd') if isinstance(data, dict) else None)
        if cwd:
            return os.path.normcase(os.path.abspath(cwd))
    return None


def discover(home, source='all', since=None, profile=None, project=None):
    home = Path(home)
    roots = []
    if source in ('all', 'codex') and not profile:
        codex_home = Path(os.environ.get('CODEX_HOME', str(home / '.codex')))
        roots.append(codex_home / 'sessions')
    if source in ('all', 'claude'):
        if profile and profile not in ('.claude', '.claude-max', '.claude-pro'):
            raise ValueError(t('unknown_profile', name=profile))
        roots.extend(home / name / 'projects' for name in ([profile] if profile else ['.claude', '.claude-max', '.claude-pro']))
        if not profile and os.environ.get('CLAUDE_CONFIG_DIR'):
            roots.append(Path(os.environ['CLAUDE_CONFIG_DIR']) / 'projects')
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob('*.jsonl'):
            try:
                if path.is_symlink():
                    continue
                if since and path.stat().st_mtime < since.timestamp():
                    continue
                if project and _project_cwd(path) != os.path.normcase(os.path.abspath(project)):
                    continue
                found.append(path)
            except OSError:
                continue
    return tuple(sorted(set(found), key=str))

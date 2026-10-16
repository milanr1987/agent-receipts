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


PROFILE_RE = re.compile(r'\.claude[\w.-]*')


def _claude_roots(home, profile, env):
    if profile is not None:
        if not PROFILE_RE.fullmatch(profile) or not (home / profile).is_dir():
            raise ValueError(t('unknown_profile', name=profile))
        return [home / profile / 'projects']
    roots = [p / 'projects' for p in sorted(home.glob('.claude*'))
             if PROFILE_RE.fullmatch(p.name) and p.is_dir()]
    if env.get('CLAUDE_CONFIG_DIR'):
        roots.append(Path(env['CLAUDE_CONFIG_DIR']).expanduser() / 'projects')
    return roots


def discover(home, source='all', since=None, profile=None, project=None, env=None, include_subagents=False):
    home = Path(home)
    env = os.environ if env is None else env
    roots = []
    if source in ('all', 'codex') and not profile:
        roots.append(Path(env.get('CODEX_HOME') or home / '.codex') / 'sessions')
    if source in ('all', 'claude'):
        roots.extend(_claude_roots(home, profile, env))
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob('*.jsonl'):
            try:
                if path.is_symlink():
                    continue
                # Subagent reports already appear in the parent session as Agent tool results.
                if not include_subagents and 'subagents' in path.relative_to(root).parts:
                    continue
                if since and path.stat().st_mtime < since.timestamp():
                    continue
                if project and _project_cwd(path) != os.path.normcase(os.path.abspath(project)):
                    continue
                found.append(path)
            except OSError:
                continue
    return tuple(sorted(set(found), key=str))

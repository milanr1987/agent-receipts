from .common import read_rows
from ..messages import t

FATAL_DIAGNOSTICS = {'file_limit', 'line_limit', 'read_error'}


class UnreadableSession(ValueError):
    """A session that exists but could not be read; the audit must report itself incomplete."""


def detect(path):
    rows, diagnostics = read_rows(path)
    fatal = [d for d in diagnostics if d.code in FATAL_DIAGNOSTICS]
    if fatal and not rows:
        raise UnreadableSession(fatal[0].message)
    for _, row in rows[:100]:
        kind = row.get('type')
        if kind in ('session_meta', 'turn_context', 'response_item'):
            return 'codex'
        if kind == 'event_msg' and isinstance(row.get('payload'), dict):
            return 'codex'
        if kind in ('assistant', 'user') and isinstance(row.get('message'), dict):
            return 'claude'
    raise ValueError(t('unknown_format'))

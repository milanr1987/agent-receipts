from .common import read_rows
from ..messages import t


def detect(path):
    rows, _ = read_rows(path)
    for _, row in rows[:100]:
        kind = row.get('type')
        if kind in ('session_meta', 'turn_context', 'response_item'):
            return 'codex'
        if kind == 'event_msg' and isinstance(row.get('payload'), dict):
            return 'codex'
        if kind in ('assistant', 'user') and isinstance(row.get('message'), dict):
            return 'claude'
    raise ValueError(t('unknown_format'))

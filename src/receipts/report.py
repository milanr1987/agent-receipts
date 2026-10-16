from collections import Counter
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from .messages import t
from .redaction import redact

REPORTS_DIR = None  # Explicit override (tests); see reports_dir().
STATUSES = ('CONFIRMED', 'NO_EVIDENCE', 'CONTRADICTED')


def _checkout_root():
    """Source checkout root when running from src/receipts, None when installed."""
    here = Path(__file__).resolve()
    return here.parents[2] if here.parents[1].name == 'src' else None


def reports_dir(out=None, env=None):
    env = os.environ if env is None else env
    if out:
        return Path(out).expanduser()
    if REPORTS_DIR is not None:
        return REPORTS_DIR
    if env.get('RECEIPTS_HOME'):
        return Path(env['RECEIPTS_HOME']).expanduser() / 'reports'
    root = _checkout_root()
    if root is not None:
        return root / 'reports'
    if os.name == 'nt':
        base = Path(env.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    else:
        base = Path(env.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state')
    return base / 'agent-receipts' / 'reports'


def cell(value):
    return redact(str(value)).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '\\|').replace('\n', ' ')


def render_report(results, skipped=0):
    lines = ['# Agent Receipts', '', t('report_note'), '']
    counts = Counter((session.source, verdict.status) for session, verdicts in results for verdict in verdicts)
    for source in ('codex', 'claude'):
        lines.append(f'- {source}: ' + ', '.join(f'{s}={counts[source, s]}' for s in STATUSES))
    if skipped:
        lines += ['', t('report_skipped', n=skipped)]
    if not results:
        lines += ['', t('report_empty')]
    lines += ['', t('report_header'), '|---|---:|---|---|---|']
    for session, verdicts in results:
        label = session.source + ' / ' + session.session_id + (t('subagent_label') if session.subagent else '')
        for verdict in verdicts:
            lines.append('| ' + ' | '.join(cell(x) for x in [label, verdict.claim.event.line, verdict.claim.quote,
                                                               verdict.status, '; '.join(verdict.evidence)]) + ' |')
        for diagnostic in session.diagnostics:
            lines.append('\n' + t('report_diagnostic', source=cell(session.source), line=diagnostic.line,
                                  code=cell(diagnostic.code), message=cell(diagnostic.message)))
        if not verdicts:
            lines.append('\n' + t('report_no_claims', source=cell(session.source), session=cell(session.session_id)))
    return redact('\n'.join(lines) + '\n')


def render_json(results, skipped=0):
    """Field-level redaction keeps the document valid JSON."""
    from . import __version__
    summary = {source: dict.fromkeys(STATUSES, 0) for source in ('codex', 'claude')}
    sessions = []
    for session, verdicts in results:
        for verdict in verdicts:
            summary[session.source][verdict.status] += 1
        sessions.append({
            'source': session.source, 'session_id': redact(session.session_id), 'subagent': session.subagent,
            'verdicts': [{'type': v.claim.type, 'status': v.status, 'line': v.claim.event.line,
                          'quote': redact(v.claim.quote), 'evidence': [redact(e) for e in v.evidence]} for v in verdicts],
            'diagnostics': [{'code': d.code, 'line': d.line, 'message': redact(d.message)} for d in session.diagnostics],
        })
    data = {'schema_version': 1, 'tool_version': __version__,
            'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'summary': summary, 'skipped_files': skipped, 'sessions': sessions}
    return json.dumps(data, ensure_ascii=False, indent=2)


def save_report(text, name=None, out=None, already_redacted=False):
    directory = reports_dir(out)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (name or (date.today().isoformat() + '.md'))
    path.write_text(text if already_redacted else redact(text), encoding='utf-8')
    return path

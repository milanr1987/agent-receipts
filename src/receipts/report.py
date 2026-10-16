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


def session_label(session):
    when = (session.started_at or '')[:16].replace('T', ' ')
    parts = [p for p in (session.project, when) if p]
    tail = f'{session.source} {session.session_id[:8]}' + (t('subagent_label') if session.subagent else '')
    return ' · '.join(parts + [tail])


def render_report(results, skipped=0):
    lines = ['# Agent Receipts', '', t('report_note'), '']
    counts = Counter((session.source, verdict.status) for session, verdicts in results for verdict in verdicts)
    for source in ('codex', 'claude'):
        lines.append(f'- {source}: ' + ', '.join(f'{s}={counts[source, s]}' for s in STATUSES))
    empty = sum(1 for _, verdicts in results if not verdicts)
    lines += ['', t('report_counts', skipped=skipped, empty=empty)]
    if not results:
        lines += ['', t('report_empty')]
    order = {'CONTRADICTED': 0, 'NO_EVIDENCE': 1}
    review, conversation, confirmed = [], [], []
    for session, verdicts in results:
        flagged = sorted((v for v in verdicts if v.status != 'CONFIRMED' and not v.conversation_only),
                         key=lambda v: (order[v.status], v.claim.event.line))
        if flagged or session.diagnostics:
            review.append((session, flagged))
        conversation += [(session, v) for v in verdicts if v.status == 'NO_EVIDENCE' and v.conversation_only]
        ok = sum(1 for v in verdicts if v.status == 'CONFIRMED')
        if ok:
            confirmed.append((session, ok))
    if review:
        lines += ['', '## ' + t('section_review')]
        for session, flagged in review:
            lines += ['', '### ' + cell(session_label(session))]
            if flagged:
                lines += ['', t('table_review'), '|---:|---|---|---|']
                lines += ['| ' + ' | '.join(cell(x) for x in [v.claim.event.line, v.claim.quote, v.status,
                                                               '; '.join(v.evidence)]) + ' |' for v in flagged]
            for diagnostic in session.diagnostics:
                lines.append('\n' + t('report_diagnostic', source=cell(session.source), line=diagnostic.line,
                                      code=cell(diagnostic.code), message=cell(diagnostic.message)))
    if conversation:
        lines += ['', '## ' + t('section_conversation', n=len(conversation)), '', t('table_conversation'), '|---|---:|---|']
        lines += ['| ' + ' | '.join(cell(x) for x in [session_label(s), v.claim.event.line, v.claim.quote]) + ' |'
                  for s, v in conversation]
    if confirmed:
        lines += ['', '## ' + t('section_confirmed', n=sum(n for _, n in confirmed)), '']
        lines += ['- ' + cell(t('confirmed_row', label=session_label(s), n=n)) for s, n in confirmed]
    return redact('\n'.join(lines) + '\n')


def render_json(results, skipped=0):
    """Field-level redaction keeps the document valid JSON."""
    from . import __version__
    summary = {source: dict.fromkeys(STATUSES, 0) for source in ('codex', 'claude')}
    summary['sessions_without_claims'] = sum(1 for _, verdicts in results if not verdicts)
    sessions = []
    for session, verdicts in results:
        for verdict in verdicts:
            summary[session.source][verdict.status] += 1
        sessions.append({
            'source': session.source, 'session_id': redact(session.session_id), 'subagent': session.subagent,
            'project': redact(session.project), 'started_at': session.started_at,
            'verdicts': [{'type': v.claim.type, 'status': v.status, 'line': v.claim.event.line,
                          'quote': redact(v.claim.quote), 'evidence': [redact(e) for e in v.evidence],
                          'conversation_only': v.conversation_only} for v in verdicts],
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

from collections import Counter
from datetime import date
from pathlib import Path
from .redaction import redact

REPORTS_DIR = Path(__file__).resolve().parents[2] / 'reports'


def cell(value):
    return redact(str(value)).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '\\|').replace('\n', ' ')


def render_report(results):
    lines = ['# Agent Receipts', '', 'Offline pregled prethodnih dokaza; NO_EVIDENCE nije dokaz neistine.', '']
    counts = Counter((session.source, verdict.status) for session, verdicts in results for verdict in verdicts)
    for source in ('codex', 'claude'):
        lines.append(f'- {source}: CONFIRMED={counts[source,"CONFIRMED"]}, NO_EVIDENCE={counts[source,"NO_EVIDENCE"]}, CONTRADICTED={counts[source,"CONTRADICTED"]}')
    if not results:
        lines += ['', 'Nema pronađenih sesija. Nije izvršena provjera tvrdnji.']
    lines += ['', '| Alat / sesija | Red | Tvrdnja | Status | Dokaz |', '|---|---:|---|---|---|']
    for session, verdicts in results:
        for verdict in verdicts:
            lines.append('| ' + ' | '.join(cell(x) for x in [session.source + ' / ' + session.session_id,
                verdict.claim.event.line, verdict.claim.quote, verdict.status, '; '.join(verdict.evidence)]) + ' |')
        for diagnostic in session.diagnostics:
            lines.append(f'\nDijagnostika ({cell(session.source)}, red {diagnostic.line}): {cell(diagnostic.code)} — {cell(diagnostic.message)}')
        if not verdicts:
            lines.append(f'\n{cell(session.source)}: nema prepoznatih tvrdnji u sesiji {cell(session.session_id)}.')
    return redact('\n'.join(lines) + '\n')


def save_report(text, name=None):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / (name or (date.today().isoformat() + '.md'))
    path.write_text(redact(text), encoding='utf-8')
    return path

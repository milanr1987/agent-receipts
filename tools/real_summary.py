"""Aggregate verdict counts over local sessions for one receipts source tree.

Usage: python tools/real_summary.py [--src DIR] [--since 30d] [--show STATUS]
Prints counts only. --show prints claim quotes of one status to this terminal;
never redirect that output into the repository.
"""
import argparse
from collections import Counter
import os
from pathlib import Path
import sys
import time

DEFAULT_SRC = Path(__file__).resolve().parents[1] / 'src'


def session_files(days):
    """Own file listing, so 0.1 and 0.2 are measured on exactly the same sessions."""
    home = Path.home()
    roots = [Path(os.environ.get('CODEX_HOME') or home / '.codex') / 'sessions']
    roots += [p / 'projects' for p in home.glob('.claude*') if p.is_dir()]
    if os.environ.get('CLAUDE_CONFIG_DIR'):
        roots.append(Path(os.environ['CLAUDE_CONFIG_DIR']) / 'projects')
    cutoff = time.time() - days * 86400
    found = set()
    for root in roots:
        if root.is_dir():
            found.update(p for p in root.rglob('*.jsonl') if 'subagents' not in p.relative_to(root).parts
                         and not p.is_symlink() and p.stat().st_mtime >= cutoff)
    return sorted(found, key=str)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--src', type=Path, default=DEFAULT_SRC)
    parser.add_argument('--since', default='30d', help='Nd, days only')
    parser.add_argument('--show', choices=['CONFIRMED', 'NO_EVIDENCE', 'CONTRADICTED'])
    args = parser.parse_args(argv)
    sys.path.insert(0, str(args.src.resolve()))
    from receipts.ingest.detect import detect
    from receipts.ingest import claude, codex
    from receipts.claims import extract_claims
    from receipts.evidence import evaluate

    verdicts, diagnostics, sessions, skipped = Counter(), Counter(), Counter(), 0
    shown = []
    for path in session_files(int(args.since.rstrip('d'))):
        try:
            source = detect(path)
        except ValueError:
            skipped += 1
            continue
        session = (codex if source == 'codex' else claude).parse(path)
        sessions[source] += 1
        for code in {d.code for d in session.diagnostics}:
            diagnostics[source, code] += 1
        for v in evaluate(session, extract_claims(session.events)):
            verdicts[source, v.claim.type, v.status] += 1
            if v.status == args.show:
                shown.append(f'{source} {v.claim.type}: {v.claim.quote[:160]}')
    print('sessions', dict(sessions), 'skipped', skipped)
    for (source, typ, status), n in sorted(verdicts.items()):
        print(source, typ, status, n)
    for (source, code), n in sorted(diagnostics.items()):
        print('sessions_with_diagnostic', source, code, n)
    for line in shown:
        print('  -', line)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Sample recognized claims from local sessions into a CSV for manual labelling.

Writes eval/labels.csv (git-ignored) with an empty truth column. Fill truth=true
when the claim was actually true, false when it was not, judged from the session
itself and not from any tool verdict. Then run: receipts eval eval/labels.csv
"""
import argparse
import csv
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['source', 'session_path', 'line', 'claim_type', 'quote', 'truth']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--since', default='30d')
    parser.add_argument('--size', type=int, default=60)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--out', type=Path, default=ROOT / 'eval' / 'labels.csv')
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT / 'src'))
    from receipts.discovery import discover, parse_since
    from receipts.ingest.detect import detect
    from receipts.ingest import claude, codex
    from receipts.claims import extract_claims

    rows = []
    for path in discover(Path.home(), 'all', parse_since(args.since)):
        try:
            source = detect(path)
        except ValueError:
            continue
        session = (codex if source == 'codex' else claude).parse(path)
        for claim in extract_claims(session.events):
            rows.append(dict(source=source, session_path=str(path), line=claim.event.line,
                             claim_type=claim.type, quote=claim.quote, truth=''))
    random.Random(args.seed).shuffle(rows)
    rows = rows[:args.size]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f'{len(rows)} claims written to {args.out}; fill truth=true/false manually.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

import csv
from pathlib import Path
from .claims import extract_claims
from .evidence import evaluate
from .ingest.detect import detect
from .ingest import claude, codex
from .messages import t


def evaluate_labels(path):
    groups, cache = {}, {}
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            if row.get('truth') not in ('true', 'false'):
                raise ValueError(t('eval_truth'))
            file = Path(row['session_path']).expanduser()
            if not file.is_absolute():
                file = Path(path).resolve().parent / file
            key = str(file.resolve())
            if key not in cache:
                source = detect(file)
                session = (codex if source == 'codex' else claude).parse(file)
                cache[key] = (source, evaluate(session, extract_claims(session.events)))
            source, verdicts = cache[key]
            if source != row.get('source'):
                raise ValueError(t('eval_source'))
            matched = [v for v in verdicts if v.claim.type == row['claim_type'] and v.claim.event.line == int(row['line'])]
            flagged = any(v.status != 'CONFIRMED' for v in matched)
            actual = row['truth'] == 'false'
            g = groups.setdefault(source + '/' + row['claim_type'], dict(TP=0, FP=0, FN=0, TN=0, unrecognized=0))
            if not matched:
                g['unrecognized'] += 1
            g['TP' if flagged and actual else 'FP' if flagged else 'FN' if actual else 'TN'] += 1
    for g in groups.values():
        g['precision'] = g['TP'] / (g['TP'] + g['FP']) if g['TP'] + g['FP'] else None
        g['recall'] = g['TP'] / (g['TP'] + g['FN']) if g['TP'] + g['FN'] else None
    return groups

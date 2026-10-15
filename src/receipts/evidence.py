import re
from pathlib import PurePosixPath
from .claims import runner, git_operation
from .models import Verdict


def _failed(result):
    if result.is_error or (result.exit_code is not None and result.exit_code != 0):
        return True
    return bool(re.search(r'(?im)\b[1-9]\d*\s+(?:failed|failures?|errors?)\b|FAILED\s*\([^)]*(?:failures|errors)=[1-9]|^FAIL\s*$|test result: FAILED', result.text))


def _successful(result, tests=False):
    if _failed(result) or result.status not in ('completed', 'success'):
        return False
    if result.exit_code == 0:
        return True
    if tests:
        return bool(re.search(r'(?im)^OK(?:\s|$)|\b\d+\s+passed\b|test result: ok', result.text))
    # Successful edit/write tool_result (not Bash) has a reliable tool success flag.
    return result.tool_name in ('Write', 'Edit', 'MultiEdit') and result.is_error is False


def evaluate(session, claims):
    verdicts = []
    for claim in claims:
        preceding = [e for e in session.events if e.line < claim.event.line]
        # Events can share a JSONL line (Claude blocks). Earlier block order still matters.
        try:
            at = session.events.index(claim.event)
            preceding = list(session.events[:at])
        except ValueError:
            pass
        calls = {e.tool_id: e for e in preceding if e.kind == 'tool_call'}
        results = [e for e in preceding if e.kind == 'tool_result']
        status, proof = 'NO_EVIDENCE', ('Nema dovoljnog prethodnog dokaza.',)
        if claim.type == 'tests_pass':
            test_calls = [e for e in preceding if e.kind == 'tool_call' and e.turn == claim.event.turn and runner(e.text)]
            scopes = re.findall(r'(?i)\b(?:backend|frontend)\b', claim.quote)
            if scopes:
                test_calls = [e for e in test_calls if all(re.search(r'(?i)\b' + scope + r'\b', e.text) for scope in scopes)]
            if test_calls:
                call = test_calls[-1]
                result = next((e for e in reversed(results) if e.tool_id == call.tool_id and e.turn == claim.event.turn), None)
                if result:
                    if _failed(result):
                        status = 'CONTRADICTED'
                    elif _successful(result, tests=True):
                        status = 'CONFIRMED'
                        requested = re.search(r'(?i)\b(\d+)\s+(?:tests?|testova|testa|testovi)\b', claim.quote)
                        actual = re.search(r'(?i)Ran\s+(\d+)\s+tests|\b(\d+)\s+passed', result.text)
                        skips = re.search(r'(?i)skipped[=: ]+(\d+)', result.text)
                        if requested and actual:
                            count = int(actual[1] or actual[2])
                            if skips and 'Ran ' in actual[0]:
                                count -= int(skips[1])
                            if count != int(requested[1]):
                                status = 'CONTRADICTED'
                        if skips and int(skips[1]) and re.search(r'(?i)without skips|no skips|bez preskakanja', claim.quote):
                            status = 'CONTRADICTED'
                    proof = (f'line {call.line}: runner {runner(call.text)}; line {result.line}: exit={result.exit_code}, status={result.status}',)
        elif claim.type in ('committed', 'pushed'):
            operation = 'commit' if claim.type == 'committed' else 'push'
            for result in reversed(results):
                call = calls.get(result.tool_id)
                if not call or not git_operation(call.text, operation):
                    continue
                proof = (f'line {call.line}: git {operation}; line {result.line}: exit={result.exit_code}. Istorijski rezultat; trenutno stanje nije provjereno.',)
                if _failed(result):
                    status = 'CONTRADICTED'
                elif result.exit_code == 0 and result.status == 'completed':
                    if operation == 'commit' and re.search(r'\[[^\]\n]+\s+[0-9a-f]{7,40}\]', result.text):
                        status = 'CONFIRMED'
                    elif operation == 'push' and re.search(r'(?im)\S+\s+->\s+\S+|Everything up-to-date', result.text):
                        status = 'CONFIRMED'
                break
        elif claim.type in ('files_changed', 'file_created'):
            successful = [e for e in results if _successful(e) or
                          (e.tool_name == 'file_change' and e.status == 'completed' and not e.is_error)]
            paths = set(p.replace('\\', '/') for e in successful for p in e.files)
            if claim.type == 'files_changed':
                if len(paths) >= int(claim.value or 0) and paths:
                    status = 'CONFIRMED'
                proof = (f'Zabilježeno {len(paths)} različitih uspješno izmijenjenih putanja; nepotpun inventar nije dokaz neistine.',)
            else:
                wanted = (claim.value or '').replace('\\', '/')
                for result in successful:
                    for path, action in result.file_actions:
                        path = path.replace('\\', '/')
                        if (path == wanted or path.endswith('/' + wanted)) and action == 'add':
                            status, proof = 'CONFIRMED', (f'line {result.line}: uspješno kreiranje fajla.',)
        verdicts.append(Verdict(claim, status, proof))
    return tuple(verdicts)

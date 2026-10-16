import re
from .claims import runner, git_operation, command_segments
from .messages import t
from .models import Verdict

FAIL_RE = re.compile(r'(?im)\b[1-9]\d*\s+(?:failed|failures?|errors?)\b|FAILED\s*\([^)]*(?:failures|errors)=[1-9]|^FAIL\s*$|test result: FAILED')
PASS_RE = re.compile(r'(?im)^OK(?:\s|$)|\b\d+\s+passed\b|test result: ok')
# Jest "Tests: 1 failed, 94 passed, 95 total"; Vitest "Tests  95 passed (95)". Never "Test Files"/"Test Suites".
JS_TESTS_RE = re.compile(r'(?im)^\s*Tests:?\s+(?:\d+\s+\w+,\s*)*(\d+)\s+passed\b[^\n]*')
SUMMARY_RE = {
    'unittest': re.compile(r'Ran \d+ tests? in [\d.]+s\s+(?:OK|FAILED)[^\n]*'),
    # Banner "=== 3 passed in 0.1s ===", or the bare "3 passed in 0.1s" line printed by pytest -q.
    'pytest': re.compile(r'(?m)^=+ [^\n]*\b(?:passed|failed|errors?)\b[^\n]*=+\s*$'
                         r'|^\s*(?:\d+ \w+, )*\d+ (?:passed|failed|errors?)\b[^\n]* in [\d.]+s\b[^\n]*$'),
    'vitest': JS_TESTS_RE, 'jest': JS_TESTS_RE, 'npm': JS_TESTS_RE,
}
SETUP_SEGMENT = re.compile(r'(?i)^(?:(?:cd|pushd|set-location|export|set|source)\s|\.\s+\S*activate|\$env:\w+\s*=|\w+=\S*$)')


def _exit_failed(result):
    return bool(result.is_error) or (result.exit_code is not None and result.exit_code != 0)


def _failed(result):
    return _exit_failed(result) or bool(FAIL_RE.search(result.text))


def _successful(result, tests=False):
    if _failed(result) or result.status not in ('completed', 'success'):
        return False
    # The host success flag proves the shell exited 0, not that a runner reported a pass.
    if result.exit_code == 0 and not (tests and result.exit_source == 'host_success_flag'):
        return True
    if tests:
        return bool(PASS_RE.search(result.text))
    # Successful edit/write tool_result (not Bash) has a reliable tool success flag.
    return result.tool_name in ('Write', 'Edit', 'MultiEdit') and result.is_error is False


def _source(result):
    return f' [{result.exit_source}]' if result.exit_source else ''


def is_compound(command):
    """True when a runner shares the command with steps other than cd/env setup."""
    return any(not SETUP_SEGMENT.match(s) and not runner(s) for s in command_segments(command))


def runner_summary(name, text):
    pattern = SUMMARY_RE.get(name)
    matches = list(pattern.finditer(text)) if pattern else []
    return matches[-1].group(0) if matches else None


def test_count(name, text):
    if name == 'unittest':
        found = re.findall(r'\bRan\s+(\d+)\s+tests?\b', text)
    elif name in ('vitest', 'jest', 'npm'):
        # npm workspaces print one "Tests" line per package; the claim counts all of them.
        found = JS_TESTS_RE.findall(text)
        return sum(int(n) for n in found) if found else None
    elif name == 'pytest':
        found = re.findall(r'\b(\d+)\s+passed\b', text)
    else:
        found = []
    return int(found[-1]) if found else None


def _commit_proven(command, output):
    """Commit summary line, or for `commit -q` a following `git log --oneline` line with the same subject."""
    if re.search(r'\[[^\]\n]+\s+[0-9a-f]{7,40}\]', output):
        return True
    message = re.search(r'''\bcommit\b[^\n]*?\s-[a-zA-Z]*m\s*(["'])([^"'\n$]+)''', command)
    if not message:
        return False
    subject = message[2].strip()[:60]
    return bool(subject) and bool(re.search(r'(?m)^[0-9a-f]{7,40} ' + re.escape(subject), output))


def _check_counts(claim, name, text):
    requested = re.search(r'(?i)\b(\d+)\s+(?:tests?|testova|testa|testovi)\b', claim.quote)
    actual = test_count(name, text)
    if requested and actual is not None and actual != int(requested[1]):
        return 'CONTRADICTED'
    skipped = re.search(r'(?i)skipped[=: ]+(\d+)', text)
    if skipped and int(skipped[1]) and re.search(r'(?i)without skips|no skips|bez preskakanja', claim.quote):
        return 'CONTRADICTED'
    return 'CONFIRMED'


def _test_verdict(claim, call, result):
    name = runner(call.text)
    proof = (t('proof_runner', call=call.line, runner=name, result=result.line,
               exit=result.exit_code, source=_source(result), status=result.status),)
    if is_compound(call.text):
        # Exit code and stray numbers belong to the other steps; judge the runner summary only.
        text = runner_summary(name, result.text)
        if text is None:
            return 'NO_EVIDENCE', (t('proof_compound', call=call.line),)
        if FAIL_RE.search(text):
            return 'CONTRADICTED', proof
        if not PASS_RE.search(text):
            return 'NO_EVIDENCE', proof
    else:
        text = result.text
        if _failed(result):
            return 'CONTRADICTED', proof
        if not _successful(result, tests=True):
            return 'NO_EVIDENCE', proof
    return _check_counts(claim, name, text), proof


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
        status, proof = 'NO_EVIDENCE', (t('no_evidence'),)
        if claim.type == 'tests_pass':
            test_calls = [e for e in preceding if e.kind == 'tool_call' and e.turn == claim.event.turn and runner(e.text)]
            scopes = re.findall(r'(?i)\b(?:backend|frontend)\b', claim.quote)
            if scopes:
                test_calls = [e for e in test_calls if all(re.search(r'(?i)\b' + scope + r'\b', e.text) for scope in scopes)]
            if test_calls:
                call = test_calls[-1]
                result = next((e for e in reversed(results) if e.tool_id == call.tool_id and e.turn == claim.event.turn), None)
                if result:
                    status, proof = _test_verdict(claim, call, result)
        elif claim.type in ('committed', 'pushed'):
            operation = 'commit' if claim.type == 'committed' else 'push'
            for result in reversed(results):
                call = calls.get(result.tool_id)
                if not call or not git_operation(call.text, operation):
                    continue
                proof = (t('proof_git', call=call.line, op=operation, result=result.line,
                           exit=result.exit_code, source=_source(result)),)
                # Git output text (commit messages) is not a failure signal; only the exit is.
                if _exit_failed(result):
                    status = 'CONTRADICTED'
                elif result.exit_code == 0 and result.status == 'completed':
                    if operation == 'commit' and _commit_proven(call.text, result.text):
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
                proof = (t('proof_files', n=len(paths)),)
            else:
                wanted = (claim.value or '').replace('\\', '/')
                for result in successful:
                    for path, action in result.file_actions:
                        path = path.replace('\\', '/')
                        if (path == wanted or path.endswith('/' + wanted)) and action == 'add':
                            status, proof = 'CONFIRMED', (t('proof_created', line=result.line),)
        verdicts.append(Verdict(claim, status, proof))
    return tuple(verdicts)

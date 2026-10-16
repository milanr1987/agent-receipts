from pathlib import Path
import unittest
from receipts.models import Event, Session
from receipts.claims import extract_claims, runner
from receipts.evidence import evaluate
from receipts.ingest import claude

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def event(kind, text, line, **kwargs):
    return Event('codex', 's', '/project', line, kwargs.pop('turn', 't'), kind, text, **kwargs)


def verdict(command, output, claim='All tests pass', exit_code=0, result_turn='t', exit_source=None, **kwargs):
    events = (event('tool_call', command, 1, tool_id='x', tool_name='command'),
              event('tool_result', output, 2, tool_id='x', tool_name='command', exit_code=exit_code,
                    status='completed', turn=result_turn, exit_source=exit_source),
              event('assistant_text', claim, 3, **kwargs))
    session = Session('codex', 's', events)
    return evaluate(session, extract_claims(events))[0]


class ClaimsTests(unittest.TestCase):
    def test_positive_en_bcs(self):
        for text, typ in [('All tests pass', 'tests_pass'), ('182 testa prolaze', 'tests_pass'),
                          ('Commitovao sam izmjene', 'committed'), ('I pushed the changes', 'pushed'),
                          ('Updated 12 files', 'files_changed'), ('Created `src/new.py`', 'file_created')]:
            with self.subTest(text=text):
                claims = extract_claims([event('assistant_text', text, 1)])
                self.assertIn(typ, [c.type for c in claims])

    def test_negation_quotes_intent_not_claims(self):
        for text in ['Tests do not pass', 'I will run tests', 'Make sure all tests pass',
                     'The agent claims "all tests pass"', 'Izmjene nisu commitovane',
                     'If all tests pass, commit', 'committed cleanup is missing']:
            with self.subTest(text=text):
                self.assertEqual(extract_claims([event('assistant_text', text, 1)]), ())

    def test_document_read_not_runner(self):
        self.assertIsNone(runner('Get-Content README.md # python -m unittest'))
        self.assertIsNone(runner('echo "pytest -q"'))
        self.assertIsNone(runner('git diff -- tests/test_pytest.py'))

    def test_powershell_runner(self):
        self.assertEqual(runner('powershell.exe -Command $env:PYTHONUTF8="1"; .\\.venv\\Scripts\\python.exe -m unittest discover -s tests'), 'unittest')
        self.assertEqual(runner('npx vitest run'), 'vitest')


class EvidenceTests(unittest.TestCase):
    def test_pass_fail_and_unknown(self):
        self.assertEqual(verdict('python -m unittest', 'Ran 2 tests\nOK').status, 'CONFIRMED')
        self.assertEqual(verdict('pytest', '1 failed', exit_code=1).status, 'CONTRADICTED')
        self.assertEqual(verdict('pytest', 'unknown', exit_code=None).status, 'NO_EVIDENCE')

    def test_claude_result_needs_recognizable_output(self):
        self.assertEqual(verdict('pytest', '2 passed', exit_code=None).status, 'CONFIRMED')

    def test_no_future_or_other_turn_evidence(self):
        self.assertEqual(verdict('pytest', '2 passed', result_turn='old').status, 'NO_EVIDENCE')
        claim = event('assistant_text', 'All tests pass', 1)
        session = Session('codex', 's', (claim, event('tool_result', '2 passed', 2, exit_code=0)))
        self.assertEqual(evaluate(session, extract_claims(session.events))[0].status, 'NO_EVIDENCE')

    def test_last_failed_run_wins(self):
        events = [event('tool_call', 'pytest', 1, tool_id='a'),
                  event('tool_result', '2 passed', 2, tool_id='a', exit_code=0, status='completed'),
                  event('tool_call', 'pytest', 3, tool_id='b'),
                  event('tool_result', '1 failed', 4, tool_id='b', exit_code=1, status='completed'),
                  event('assistant_text', 'All tests pass', 5)]
        self.assertEqual(evaluate(Session('codex','s',tuple(events)),extract_claims(events))[0].status, 'CONTRADICTED')

    def test_frontend_pass_does_not_override_explicit_backend_failure(self):
        events=[event('tool_call','pytest backend',1,tool_id='a'),
                event('tool_result','1 failed',2,tool_id='a',exit_code=1,status='completed'),
                event('tool_call','npm test -- frontend',3,tool_id='b'),
                event('tool_result','2 passed',4,tool_id='b',exit_code=0,status='completed'),
                event('assistant_text','Backend tests pass',5)]
        self.assertEqual(evaluate(Session('codex','s',tuple(events)),extract_claims(events))[0].status,'CONTRADICTED')

    def test_test_count_and_skips(self):
        self.assertEqual(verdict('python -m unittest', 'Ran 2 tests\nOK', 'All 14 tests pass').status, 'CONTRADICTED')
        self.assertEqual(verdict('python -m unittest', 'Ran 2 tests\nOK (skipped=1)',
                                 'All tests pass without skips').status, 'CONTRADICTED')

    def test_failed_file_changes_and_distinct_count(self):
        changes = [event('tool_result', '', 1, tool_name='file_change', files=('a.py',),
                         file_actions=(('a.py','add'),), status='failed', is_error=True),
                   event('assistant_text', 'Created `a.py`', 2)]
        self.assertEqual(evaluate(Session('codex','s',tuple(changes)),extract_claims(changes))[0].status, 'NO_EVIDENCE')
        changes[0] = event('tool_result','',1,tool_name='file_change',files=('a.py',),
                           file_actions=(('a.py','add'),),status='completed')
        self.assertEqual(evaluate(Session('codex','s',tuple(changes)),extract_claims(changes))[0].status, 'CONFIRMED')

    def test_git_output_required_and_no_network(self):
        self.assertEqual(verdict('git push origin main', 'main -> main', 'I pushed the changes').status, 'CONFIRMED')
        self.assertEqual(verdict('git push origin main; echo done', 'done', 'I pushed the changes').status, 'NO_EVIDENCE')
        self.assertEqual(verdict('git commit -m fix', '[main abc1234] fix', 'I committed the fix').status, 'CONFIRMED')
        self.assertEqual(verdict('echo "git commit"', '[main abc1234] fake', 'I committed the fix').status, 'NO_EVIDENCE')

    def test_incomplete_log_cannot_contradict_file_count(self):
        events = (event('assistant_text','Updated 12 files',1),)
        self.assertEqual(evaluate(Session('codex','s',events),extract_claims(events))[0].status, 'NO_EVIDENCE')

    def test_help_collect_only_and_dry_run_not_execution(self):
        for cmd in ['pytest --help','pytest --collect-only','python -m unittest --help','go test -list .']:
            with self.subTest(cmd=cmd):
                self.assertEqual(verdict(cmd,'',exit_code=0).status,'NO_EVIDENCE')
        self.assertEqual(verdict('git push --dry-run origin main','main -> main','I pushed the changes').status,'NO_EVIDENCE')
        self.assertEqual(verdict('git push -nv origin main','main -> main','I pushed the changes').status,'NO_EVIDENCE')


class ClaudeFixtureTests(unittest.TestCase):
    def test_claude_commit_and_tests_confirmed(self):
        session = claude.parse(FIXTURES / 'claude-2.1.300.jsonl')
        verdicts = evaluate(session, extract_claims(session.events))
        statuses = {v.claim.type: v.status for v in verdicts}
        self.assertEqual(statuses['committed'], 'CONFIRMED')
        self.assertEqual(statuses['tests_pass'], 'CONFIRMED')
        self.assertIn('host_success_flag', ' '.join(next(v for v in verdicts if v.claim.type == 'committed').evidence))

    def test_host_flag_alone_does_not_prove_tests(self):
        self.assertEqual(verdict('pytest', 'collected 0 items', exit_code=0, exit_source='host_success_flag').status, 'NO_EVIDENCE')
        self.assertEqual(verdict('pytest', '2 passed', exit_code=0, exit_source='host_success_flag').status, 'CONFIRMED')

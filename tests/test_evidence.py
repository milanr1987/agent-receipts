import os
from pathlib import Path
import unittest
from unittest.mock import patch
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

    def test_markdown_and_intent_are_not_claims(self):
        for text in ['| 1 | Scroll | Test je commitovan i poslan |',
                     '- `pushed`: "pushao sam"',
                     '```\nI committed the fix\n```',
                     '> All tests pass',
                     'Cilj je da testovi prolaze',
                     'Kad testovi prolaze, commitujem',
                     'Testovi će proći i tada commitovano',
                     'staging ograničavam, commitujem, pa pregledam committed diff',
                     "I'm going to push once tests pass",
                     'Nothing is committed.',
                     "I didn't open the emails in the preview, and nothing is committed.",
                     'Your changes pushed: none (nothing local to commit).']:
            with self.subTest(text=text):
                self.assertEqual(extract_claims([event('assistant_text', text, 1)]), ())

    def test_real_claims_survive_stripping(self):
        for text, typ in [('Created `src/new.py`', 'file_created'),
                          ('Izmjene su commitovane i poslane u granu main.', 'committed'),
                          ('Svih 213 testova prolazi', 'tests_pass'),
                          ('Testovi prolaze (56).', 'tests_pass')]:
            with self.subTest(text=text):
                self.assertIn(typ, [c.type for c in extract_claims([event('assistant_text', text, 1)])])

    def test_sentence_split_after_number(self):
        text = 'Route boundary je GREEN: 25/25 fokusiranih testova prolazi, a oba daju 502. Prelazim dalje: testovi će koristiti limite.'
        self.assertEqual([c.type for c in extract_claims([event('assistant_text', text, 1)])], ['tests_pass'])

    def test_git_dash_c_recognised(self):
        from receipts.claims import git_operation
        self.assertTrue(git_operation('git -C "/p q" push origin main', 'push'))
        self.assertTrue(git_operation('git -C /p --no-optional-locks commit -m x', 'commit'))

    def test_claude_fixture_claim_types(self):
        session = claude.parse(FIXTURES / 'claude-2.1.300.jsonl')
        self.assertEqual([c.type for c in extract_claims(session.events)], ['committed', 'pushed', 'tests_pass'])
        verdicts = evaluate(session, extract_claims(session.events))
        self.assertEqual({v.claim.type: v.status for v in verdicts}['pushed'], 'CONFIRMED')

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

    def test_vitest_jest_counts_tests_not_files(self):
        out = ' Test Files  17 passed (17)\n      Tests  95 passed (95)\n'
        self.assertEqual(verdict('npx vitest run', out, 'Full suite: 17 passed, 95 tests passed').status, 'CONFIRMED')
        self.assertEqual(verdict('npx jest', 'Tests:       95 passed, 95 total', 'All 95 tests pass').status, 'CONFIRMED')
        self.assertEqual(verdict('npx jest', 'Tests:       94 passed, 94 total', 'All 95 tests pass').status, 'CONTRADICTED')

    def test_skips_only_contradict_when_claim_says_no_skips(self):
        out = 'Ran 213 tests in 1.000s\n\nOK (skipped=2)'
        self.assertEqual(verdict('python -m unittest', out, 'All 213 tests pass').status, 'CONFIRMED')
        self.assertEqual(verdict('python -m unittest', out, 'All 213 tests pass without skips').status, 'CONTRADICTED')

    def test_count_mismatch_still_contradicted(self):
        self.assertEqual(verdict('python -m unittest', 'Ran 212 tests in 22.947s\n\nOK', 'Svih 213 testova prolazi').status, 'CONTRADICTED')

    @patch.dict(os.environ, {'RECEIPTS_LANG': ''})
    def test_compound_command_uses_runner_summary(self):
        out = 'Ran 212 tests in 22.900s\n\nOK\nscan: 3 errors in plugin metadata\n'
        self.assertEqual(verdict('python -m unittest discover && python tools/scan.py', out,
                                 'Svi testovi prolaze (212)', exit_code=1).status, 'CONFIRMED')
        no_summary = verdict('python -m unittest && python tools/scan.py', 'scan finished', 'All tests pass')
        self.assertEqual(no_summary.status, 'NO_EVIDENCE')
        self.assertIn('compound', no_summary.evidence[0])
        self.assertEqual(verdict('python -m unittest && python tools/scan.py', 'Ran 3 tests in 0.1s\n\nFAILED (failures=1)',
                                 'All tests pass', exit_code=1).status, 'CONTRADICTED')

    def test_setup_prefix_is_not_compound(self):
        self.assertEqual(verdict('cd "/p" && python -m unittest', 'Ran 2 tests\nOK').status, 'CONFIRMED')
        self.assertEqual(verdict('cd /p && pytest -q', '1 failed', exit_code=1).status, 'CONTRADICTED')
        self.assertEqual(verdict('export X=1; source .venv/bin/activate && pytest', '3 passed').status, 'CONFIRMED')

    def test_compound_pytest_quiet_summary(self):
        out = '........ [100%]\r\n153 passed in 0.39s\r\n2\n'
        self.assertEqual(verdict('python -m pytest -q && grep -c x f.py', out, 'Svi testovi prolaze, ukupno 153').status, 'CONFIRMED')
        self.assertEqual(verdict('pytest -q && echo done', '1 failed, 2 passed in 0.30s\ndone', 'All tests pass').status, 'CONTRADICTED')

    def test_npm_workspaces_sum_test_lines(self):
        out = '      Tests  121 passed (121)\n...\n      Tests  31 passed (31)\n'
        self.assertEqual(verdict('npm test', out, 'Svih 152 testa prolaze').status, 'CONFIRMED')
        self.assertEqual(verdict('npm test', out, 'Svih 160 testa prolaze').status, 'CONTRADICTED')

    def test_quiet_commit_proven_by_log_subject(self):
        cmd = 'git add a.md && git commit -q -m "docs: plan for atlas" && git log --oneline -2'
        out = 'warning: LF will be replaced\n40bfb5b docs: plan for atlas\n40efd5f docs: older work\n'
        self.assertEqual(verdict(cmd, out, 'I committed the plan').status, 'CONFIRMED')
        self.assertEqual(verdict(cmd, 'warning: LF\n40efd5f docs: older work\n', 'I committed the plan').status, 'NO_EVIDENCE')

    def test_git_output_numbers_do_not_contradict_commit(self):
        self.assertEqual(verdict('git commit -m "fix 2 errors"', '[main abc1234] fix 2 errors', 'I committed the fix').status, 'CONFIRMED')


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

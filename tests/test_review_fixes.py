"""Regression tests for the final branch review findings (Important 1-6)."""
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from receipts.claims import extract_claims, runner
from receipts.evidence import evaluate
from receipts.models import Diagnostic, Session
from test_evidence import event, verdict
from test_cli_integration import fixture
from test_packaging import posix

ROOT = Path(__file__).resolve().parents[1]


def claim_types(text):
    return [c.type for c in extract_claims([event('assistant_text', text, 1)])]


class ReviewFixTests(unittest.TestCase):
    def test_env_prefixed_and_wrapped_runners_recognised(self):
        self.assertEqual(runner('PYTHONPATH=src python -m unittest discover -s tests'), 'unittest')
        self.assertEqual(runner('uv run pytest -q'), 'pytest')
        self.assertEqual(runner('poetry run pytest'), 'pytest')
        events = [event('tool_call', 'python -m unittest', 1, tool_id='a'),
                  event('tool_result', 'Ran 2 tests in 0.1s\n\nFAILED (errors=2)', 2, tool_id='a', exit_code=1, status='completed'),
                  event('tool_call', 'PYTHONPATH=src python -m unittest', 3, tool_id='b'),
                  event('tool_result', 'Ran 2 tests in 0.1s\n\nOK', 4, tool_id='b', exit_code=0, status='completed'),
                  event('assistant_text', 'All tests pass.', 5)]
        self.assertEqual(evaluate(Session('codex', 's', tuple(events)), extract_claims(events))[0].status, 'CONFIRMED')

    def test_several_runs_in_one_command_can_add_up(self):
        out = 'Ran 100 tests in 1.0s\n\nOK\nRan 112 tests in 1.0s\n\nOK\n'
        cmd = 'python -m unittest discover -s a; python -m unittest discover -s b'
        self.assertEqual(verdict(cmd, out, 'All 212 tests pass.').status, 'CONFIRMED')
        self.assertEqual(verdict(cmd, out, 'All 112 tests pass.').status, 'CONFIRMED')
        self.assertEqual(verdict(cmd, out, 'All 250 tests pass.').status, 'CONTRADICTED')

    def test_quiet_commit_needs_exact_subject_on_newest_log_line(self):
        cmd = 'git commit -q -m "fix"; git log --oneline -5'
        old = 'abc1234 fix typo in README\nbcd2345 older\n'
        self.assertEqual(verdict(cmd, old, 'I committed the fix').status, 'NO_EVIDENCE')
        buried = 'abc1234 other change\nbcd2345 fix\n'
        self.assertEqual(verdict(cmd, buried, 'I committed the fix').status, 'NO_EVIDENCE')
        self.assertEqual(verdict(cmd, 'abc1234 fix\nbcd2345 older\n', 'I committed the fix').status, 'CONFIRMED')

    def test_exclusions_apply_per_clause(self):
        for text, expected in [('All 95 tests pass, none skipped.', ['tests_pass']),
                               ('I committed the fix and pushed it, so nothing is left.', ['committed', 'pushed']),
                               ("All tests pass, which wasn't the case before.", ['tests_pass']),
                               ('Kada sam pokrenuo, svi testovi prolaze.', ['tests_pass']),
                               ('Tests pass once more after the fix.', ['tests_pass']),
                               ('Ran it twice: 1,234 tests pass.', ['tests_pass'])]:
            with self.subTest(text=text):
                self.assertEqual(claim_types(text), expected)

    @unittest.skipUnless(shutil.which('sh'), 'POSIX sh not available')
    def test_launchers_ignore_modules_in_current_directory(self):
        with tempfile.TemporaryDirectory() as d:
            marker = Path(d) / 'imported.txt'
            (Path(d) / 'argparse.py').write_text(
                f'open({str(marker)!r}, "w").write("x")\nraise SystemExit(9)\n', encoding='utf-8')
            env = dict(os.environ, RECEIPTS_PYTHON=posix(sys.executable))
            run = subprocess.run(['sh', (ROOT / 'receipts.sh').as_posix(), '--help'], cwd=d, env=env,
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            if os.name == 'nt':
                env['RECEIPTS_PYTHON'] = sys.executable
                run = subprocess.run(['cmd', '/d', '/c', str(ROOT / 'receipts.cmd'), '--help'], cwd=d, env=env,
                                     capture_output=True, text=True, timeout=30)
                self.assertEqual(run.returncode, 0, run.stderr)
            self.assertFalse(marker.exists())

    def test_unreadable_discovered_session_makes_audit_incomplete(self):
        from receipts import report
        from receipts.cli import main
        from receipts.ingest import detect as detect_module
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            good = home / '.codex/sessions/2026/10/16/s.jsonl'; good.parent.mkdir(parents=True); fixture(good)
            huge = home / '.codex/sessions/2026/10/16/huge.jsonl'; huge.write_text('{}', encoding='utf-8')
            real = detect_module.read_rows

            def fake_rows(path, *args, **kwargs):
                if Path(path).name == 'huge.jsonl':
                    return [], [Diagnostic('file_limit', 0, 'too big')]
                return real(path, *args, **kwargs)
            env = {'CODEX_HOME': str(home / '.codex'), 'CLAUDE_CONFIG_DIR': str(home / '.claude')}
            with patch.object(detect_module, 'read_rows', fake_rows), patch('pathlib.Path.home', return_value=home), \
                    patch.dict(os.environ, env), patch.object(report, 'REPORTS_DIR', home / 'r'), redirect_stdout(io.StringIO()):
                self.assertEqual(main(['audit', '--since', '1d']), 2)

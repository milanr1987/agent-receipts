import io
import os
import subprocess
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from receipts.hook import handle_hook, run_hook
from test_cli_integration import fixture


class HookTests(unittest.TestCase):
    def test_stop_hook_active_silent(self):
        self.assertIsNone(handle_hook('codex',{'stop_hook_active':True}))

    def test_missing_and_ambiguous_input_fail_open(self):
        with tempfile.TemporaryDirectory() as d:
            from receipts import report
            with patch.object(report,'REPORTS_DIR',Path(d)/'reports'):
                self.assertIsNone(handle_hook('codex',{}))
                self.assertIsNone(handle_hook('codex',{'transcript_path':'Z:/not-present','session_id':'wrong'}))

    def test_warns_only_missing_runner(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'session.jsonl'
            p.write_text(json.dumps({'type':'session_meta','payload':{'id':'s','cwd':d}})+'\n'+
                json.dumps({'type':'event_msg','payload':{'type':'task_complete','turn_id':'t','last_agent_message':'All tests pass'}}))
            from receipts import report
            with patch.object(report,'REPORTS_DIR',Path(d)/'reports'):
                warning=handle_hook('codex',{'transcript_path':str(p),'session_id':'s','cwd':d,'turn_id':'t'})
            self.assertIn('test',warning.lower())

    def test_identity_mismatch_not_audited(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'session.jsonl';fixture(p)
            from receipts import report
            with patch.object(report,'REPORTS_DIR',Path(d)/'reports'):
                self.assertIsNone(handle_hook('codex',{'transcript_path':str(p),'session_id':'other','cwd':d}))

    def test_json_stdout_exit_zero_on_malformed(self):
        from receipts import report
        with tempfile.TemporaryDirectory() as d,patch.object(report,'REPORTS_DIR',Path(d)/'reports'):
            with patch('sys.stdin',io.StringIO('{broken')),redirect_stdout(io.StringIO()) as output:
                self.assertEqual(run_hook('codex'),0)
                self.assertEqual(output.getvalue(),'')

    def test_good_verification_silent(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'session.jsonl';fixture(p)
            from receipts import report
            with patch.object(report,'REPORTS_DIR',Path(d)/'reports'):
                self.assertIsNone(handle_hook('codex',{'transcript_path':str(p),'session_id':'s',
                    'cwd':'C:/Users/Example/project','turn_id':'t'}))


def git_repo_with_two_weakened_tests(d):
    root = Path(d)
    git = lambda *a: subprocess.run(['git', '-C', str(root), *a], check=True, capture_output=True)
    git('init', '-q'); git('config', 'user.email', 'a@b.c'); git('config', 'user.name', 'a')
    (root / 'tests').mkdir()
    for name in ('test_a.py', 'test_b.py'):
        (root / 'tests' / name).write_text('def test_x():\n assert 1\n assert 2\n', encoding='utf-8')
    git('add', '.'); git('commit', '-qm', 'init')
    for name in ('test_a.py', 'test_b.py'):
        (root / 'tests' / name).write_text('def test_x():\n assert 1\n', encoding='utf-8')
    return root


def claude_turn(path, cwd, edited=None, padding=0):
    rows = [{'type': 'user', 'sessionId': 's', 'cwd': cwd, 'message': {'content': 'old ' + 'p' * padding}},
            {'type': 'assistant', 'sessionId': 's', 'cwd': cwd, 'message': {'content': [{'type': 'text', 'text': 'ok'}]}},
            {'type': 'user', 'sessionId': 's', 'cwd': cwd, 'message': {'content': 'now edit'}}]
    if edited:
        rows += [{'type': 'assistant', 'sessionId': 's', 'cwd': cwd, 'message': {'content': [
                     {'type': 'tool_use', 'id': 'e', 'name': 'Edit', 'input': {'file_path': edited}}]}},
                 {'type': 'user', 'sessionId': 's', 'cwd': cwd, 'message': {'content': [
                     {'type': 'tool_result', 'tool_use_id': 'e', 'content': 'ok', 'is_error': False}]}}]
    rows.append({'type': 'assistant', 'sessionId': 's', 'cwd': cwd, 'message': {'content': [{'type': 'text', 'text': 'Done.'}]}})
    path.write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf-8')


class TouchedFilesHookTests(unittest.TestCase):
    def run_hook_on(self, d, edited, padding=0):
        from receipts import report
        root = git_repo_with_two_weakened_tests(d)
        transcript = Path(d) / 't.jsonl'
        claude_turn(transcript, str(root), edited, padding)
        with patch.object(report, 'REPORTS_DIR', Path(d) / 'r'), patch.dict(os.environ, {'RECEIPTS_LANG': ''}):
            return handle_hook('claude', {'transcript_path': str(transcript), 'session_id': 's', 'cwd': str(root)})

    def test_hook_counts_only_files_touched_this_turn(self):
        with tempfile.TemporaryDirectory() as d:
            warning = self.run_hook_on(d, str(Path(d) / 'tests' / 'test_b.py'))
            self.assertIn('signals: 1', warning)

    def test_hook_ignores_untouched_changes(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(self.run_hook_on(d, None))

    def test_hook_matches_windows_paths_case_insensitively(self):
        if os.name != 'nt':
            self.skipTest('Windows path case folding')
        with tempfile.TemporaryDirectory() as d:
            edited = str(Path(d) / 'tests' / 'TEST_B.py').upper()
            self.assertIn('signals: 1', self.run_hook_on(d, edited))

    def test_hook_tail_window_and_fallback(self):
        from receipts import hook
        with tempfile.TemporaryDirectory() as d, patch.object(hook, 'HOOK_TAIL_BYTES', 600):
            # Old turn is large, current turn fits in the window.
            self.assertIn('signals: 1', self.run_hook_on(d, str(Path(d) / 'tests' / 'test_b.py'), padding=5000))
        with tempfile.TemporaryDirectory() as d, patch.object(hook, 'HOOK_TAIL_BYTES', 50):
            # Window too small to contain the turn start: falls back to the full read.
            self.assertIn('signals: 1', self.run_hook_on(d, str(Path(d) / 'tests' / 'test_b.py'), padding=5000))

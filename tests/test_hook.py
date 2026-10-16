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

    def spy_hook(self, d, edited, padding=0, window=None, cwd_sub=None):
        from receipts import hook, report
        root = git_repo_with_two_weakened_tests(d)
        transcript = Path(d) / 't.jsonl'
        cwd = root / cwd_sub if cwd_sub else root
        claude_turn(transcript, str(cwd), edited(root) if callable(edited) else edited, padding)
        calls = []
        real = hook.read_rows

        def spy(*a, **k):
            calls.append(k.get('tail_bytes'))
            return real(*a, **k)

        with patch.object(report, 'REPORTS_DIR', Path(d) / 'r'), patch.dict(os.environ, {'RECEIPTS_LANG': ''}),                 patch.object(hook, 'read_rows', spy), patch.object(hook, 'HOOK_TAIL_BYTES', window or 8 * 1024 * 1024):
            warning = handle_hook('claude', {'transcript_path': str(transcript), 'session_id': 's', 'cwd': str(cwd)})
        return warning, calls

    def test_hook_tail_window_is_used_when_turn_fits(self):
        with tempfile.TemporaryDirectory() as d:
            warning, calls = self.spy_hook(d, lambda r: str(r / 'tests' / 'test_b.py'), padding=5000, window=2500)
            self.assertIn('signals: 1', warning)
            self.assertEqual(calls, [2500])  # no full read

    def test_hook_falls_back_to_full_read_when_turn_starts_before_window(self):
        with tempfile.TemporaryDirectory() as d:
            warning, calls = self.spy_hook(d, lambda r: str(r / 'tests' / 'test_b.py'), padding=5000, window=50)
            self.assertIn('signals: 1', warning)
            self.assertEqual(calls[0], 50)
            self.assertIn(None, calls)

    def test_hook_ignores_same_named_file_outside_repo(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as other:
            self.assertIsNone(self.run_hook_on(d, str(Path(other) / 'tests' / 'test_b.py')))

    def test_hook_does_not_match_nested_path_by_suffix(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(self.run_hook_on(d, str(Path(d) / 'pkg' / 'tests' / 'test_b.py')))

    def test_hook_from_repo_subdirectory_matches_repo_root_file(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'sub').mkdir()
            (Path(d) / 'sub' / 'keep.txt').write_text('x', encoding='utf-8')
            warning, _ = self.spy_hook(d, lambda r: str(r / 'tests' / 'test_b.py'), cwd_sub='sub')
            self.assertIn('signals: 1', warning)

    def test_codex_tail_is_accepted_with_head_session_meta(self):
        from receipts import hook, report
        with tempfile.TemporaryDirectory() as d:
            root = git_repo_with_two_weakened_tests(d)
            cwd = str(root)
            item = lambda turn, v: {'type': 'event_msg', 'payload': {'type': 'item_completed', 'turn_id': turn, 'item': v}}
            rows = [{'type': 'session_meta', 'payload': {'id': 's', 'cwd': cwd}},
                    item('t1', {'type': 'UserMessage', 'id': 'u1', 'content': [{'type': 'text', 'text': 'old ' + 'p' * 5000}]}),
                    item('t1', {'type': 'AgentMessage', 'id': 'a1', 'content': [{'type': 'text', 'text': 'ok'}]}),
                    item('t2', {'type': 'UserMessage', 'id': 'u2', 'content': [{'type': 'text', 'text': 'now edit'}]}),
                    item('t2', {'type': 'FileChange', 'id': 'f', 'status': 'completed',
                                'changes': {str(root / 'tests' / 'test_b.py'): {'type': 'update'}}}),
                    item('t2', {'type': 'AgentMessage', 'id': 'a2', 'content': [{'type': 'text', 'text': 'Done.'}]})]
            transcript = Path(d) / 'c.jsonl'
            transcript.write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf-8')
            calls = []
            real = hook.read_rows

            def spy(*a, **k):
                calls.append((k.get('tail_bytes'), k.get('max_rows')))
                return real(*a, **k)

            with patch.object(report, 'REPORTS_DIR', Path(d) / 'r'), patch.dict(os.environ, {'RECEIPTS_LANG': ''}),                     patch.object(hook, 'read_rows', spy), patch.object(hook, 'HOOK_TAIL_BYTES', 2500):
                warning = handle_hook('codex', {'transcript_path': str(transcript), 'session_id': 's', 'cwd': cwd})
            self.assertIn('signals: 1', warning)
            self.assertNotIn((None, None), calls)  # never a full read

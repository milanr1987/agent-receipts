import io
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

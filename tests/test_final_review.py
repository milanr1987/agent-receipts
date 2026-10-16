"""Regression tests for the final whole-branch review findings."""
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr

from receipts import report
from receipts.cli import main
from receipts.claims import extract_claims
from receipts.evidence import evaluate
from receipts.git_read import changed_versions
from receipts.messages import t
from receipts.models import Session
from test_evidence import event


class ContradictedConversationTests(unittest.TestCase):
    def test_contradicted_from_a_no_tool_turn_is_listed_under_review(self):
        events = (event('tool_call', 'git push origin main', 1, tool_id='p', turn='t1'),
                  event('tool_result', 'error: failed to push', 2, tool_id='p', exit_code=1, status='completed', turn='t1'),
                  event('assistant_text', 'I pushed the branch.', 3, turn='t2'))
        session = Session('codex', 'abcdef123456', events)
        verdicts = evaluate(session, extract_claims(events))
        self.assertEqual([(v.status, v.conversation_only) for v in verdicts], [('CONTRADICTED', True)])
        text = report.render_report([(session, verdicts)])
        self.assertIn('CONTRADICTED=1', text)
        heading = '## ' + t('section_review')
        self.assertIn(heading, text)
        row = text.index('I pushed the branch.')
        self.assertGreater(row, text.index(heading))
        self.assertNotIn('## ' + t('section_conversation', n=1), text)


class ProjectRedactionTests(unittest.TestCase):
    def run_audit(self, cwd):
        rows = [{'type': 'session_meta', 'payload': {'id': 's', 'cwd': cwd}},
                {'type': 'event_msg', 'payload': {'type': 'item_completed', 'turn_id': 't', 'item': {
                    'type': 'AgentMessage', 'id': 'm', 'content': [{'type': 'text', 'text': 'All tests pass'}]}}}]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / 's.jsonl'
            path.write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf-8')
            saved = ''
            for fmt in ('md', 'json'):
                with patch.object(report, 'REPORTS_DIR', root / 'r'), redirect_stdout(io.StringIO()) as out, \
                        redirect_stderr(io.StringIO()):
                    main(['audit', str(path)] + (['--format', 'json'] if fmt == 'json' else []))
                saved += out.getvalue() + ''.join(p.read_text(encoding='utf-8') for p in (root / 'r').iterdir())
            return saved

    def test_home_folder_name_is_not_persisted(self):
        for cwd in ('C:/Users/Private', 'C:\\Users\\Private', '/home/private'):
            with self.subTest(cwd=cwd):
                self.assertNotIn('rivate', self.run_audit(cwd))


class ChangedVersionsEmptyPathsTests(unittest.TestCase):
    def test_empty_list_means_no_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git = lambda *a: subprocess.run(['git', '-C', str(root), *a], check=True, capture_output=True)
            git('init', '-q'); git('config', 'user.email', 'a@b.c'); git('config', 'user.name', 'a')
            (root / 'tests').mkdir()
            (root / 'tests/test_a.py').write_text('def test_x():\n assert 1\n assert 2\n', encoding='utf-8')
            git('add', '.'); git('commit', '-qm', 'init')
            (root / 'tests/test_a.py').write_text('def test_x():\n assert 1\n', encoding='utf-8')
            self.assertEqual(changed_versions(root, paths=[]), [])
            self.assertEqual([v.path for v in changed_versions(root, paths=None)], ['tests/test_a.py'])


if __name__ == '__main__':
    unittest.main()

import dataclasses
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from receipts.models import Event
from receipts.redaction import redact


class CoreTests(unittest.TestCase):
    def test_redacts_multiline_private_key(self):
        text = 'before\n-----BEGIN PRIVATE KEY-----\nSUPERSECRET\n-----END PRIVATE KEY-----\nafter'
        result = redact(text)
        self.assertNotIn('SUPERSECRET', result)
        self.assertIn('after', result)

    def test_redacts_token_email_user_path(self):
        result = redact('sk-abcdefghijklmnop foo@example.org C:\\Users\\Private\\proj api_key=sentinel-secret')
        for private in ['abcdefghijklmnop', 'foo@example.org', 'Private', 'sentinel-secret']:
            self.assertNotIn(private, result)

    def test_preserves_command_structure(self):
        self.assertEqual(redact('python -m unittest -v; Exit code 1'), 'python -m unittest -v; Exit code 1')

    def test_event_immutable(self):
        event = Event('codex', 's', '.', 1, 't', 'assistant_text', 'hello')
        with self.assertRaises(dataclasses.FrozenInstanceError):
            event.text = 'changed'

    def test_launcher_from_other_cwd_with_spaces(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='receipts launch ') as other:
            env = dict(os.environ, RECEIPTS_PYTHON=sys.executable)
            run = subprocess.run(['cmd.exe', '/d', '/c', str(root / 'receipts.cmd'), '--help'],
                                 cwd=other, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn('audit', run.stdout)

    def test_missing_interpreter_clear_failure(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, RECEIPTS_PYTHON='Z:\\missing\\python.exe')
        run = subprocess.run(['cmd.exe', '/d', '/c', str(root / 'receipts.cmd'), '--help'],
                             env=env, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('Python', run.stdout + run.stderr)

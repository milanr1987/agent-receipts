import csv
import io
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from test_cli_integration import fixture

TOOLS = Path(__file__).resolve().parents[1] / 'tools'


class ToolsTests(unittest.TestCase):
    def home(self, d):
        home = Path(d)
        path = home / '.codex/sessions/2026/10/16/s.jsonl'
        path.parent.mkdir(parents=True)
        fixture(path)
        return home, {'CODEX_HOME': str(home / '.codex'), 'CLAUDE_CONFIG_DIR': str(home / '.claude')}

    def test_real_summary_prints_counts_only(self):
        with tempfile.TemporaryDirectory() as d:
            home, env = self.home(d)
            module = runpy.run_path(str(TOOLS / 'real_summary.py'))
            with patch('pathlib.Path.home', return_value=home), patch.dict(os.environ, env), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(module['main'](['--since', '1d']), 0)
            self.assertIn('codex tests_pass CONFIRMED 1', out.getvalue())
            self.assertNotIn('All tests pass', out.getvalue())

    def test_real_sample_writes_unlabelled_csv(self):
        with tempfile.TemporaryDirectory() as d:
            home, env = self.home(d)
            target = Path(d) / 'labels.csv'
            module = runpy.run_path(str(TOOLS / 'real_sample.py'))
            with patch('pathlib.Path.home', return_value=home), patch.dict(os.environ, env), redirect_stdout(io.StringIO()):
                self.assertEqual(module['main'](['--since', '1d', '--out', str(target)]), 0)
            with target.open(encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([r['claim_type'] for r in rows], ['tests_pass'])
            self.assertEqual(rows[0]['truth'], '')
            self.assertNotIn('predicted', rows[0])

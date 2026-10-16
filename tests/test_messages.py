import io
import os
from pathlib import Path
import string
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from receipts.messages import MESSAGES, set_lang, t, lang
from test_cli_integration import fixture


def fields(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


class MessagesTests(unittest.TestCase):
    def tearDown(self):
        set_lang(None)

    def test_languages_have_same_keys_and_placeholders(self):
        self.assertEqual(set(MESSAGES['en']), set(MESSAGES['bs']))
        for key, text in MESSAGES['en'].items():
            with self.subTest(key=key):
                self.assertEqual(fields(text), fields(MESSAGES['bs'][key]))

    def test_default_env_and_fallback(self):
        with patch.dict(os.environ, {'RECEIPTS_LANG': ''}):
            self.assertEqual(lang(), 'en')
        with patch.dict(os.environ, {'RECEIPTS_LANG': 'bs'}):
            self.assertEqual(lang(), 'bs')
        with patch.dict(os.environ, {'RECEIPTS_LANG': 'xx'}):
            self.assertEqual(lang(), 'en')
        with patch.dict(os.environ, {'RECEIPTS_LANG': 'en'}):
            set_lang('bs')
            self.assertEqual(t('no_evidence'), MESSAGES['bs']['no_evidence'])
        with self.assertRaises(ValueError):
            set_lang('xx')

    def test_cli_lang_after_subcommand(self):
        from receipts import report
        from receipts.cli import main
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); path = root / 'session.jsonl'; fixture(path)
            with patch.object(report, 'REPORTS_DIR', root / 'bs'), redirect_stdout(io.StringIO()):
                self.assertEqual(main(['audit', str(path), '--lang', 'bs']), 0)
            with patch.object(report, 'REPORTS_DIR', root / 'en'), redirect_stdout(io.StringIO()), \
                    patch.dict(os.environ, {'RECEIPTS_LANG': ''}):
                self.assertEqual(main(['audit', str(path)]), 0)
            bs = ''.join(p.read_text(encoding='utf-8') for p in (root / 'bs').glob('*.md'))
            en = ''.join(p.read_text(encoding='utf-8') for p in (root / 'en').glob('*.md'))
            self.assertIn('Potvrđeno', bs)
            self.assertIn('Confirmed', en)
            self.assertEqual(lang(), 'en')

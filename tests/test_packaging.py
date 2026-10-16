import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
import unittest

import receipts

ROOT = Path(__file__).resolve().parents[1]


def posix(path):
    """Git Bash needs /c/... style paths for arguments it reads itself."""
    if os.name == 'nt' and shutil.which('cygpath'):
        return subprocess.check_output(['cygpath', '-u', str(path)], text=True).strip()
    return str(path)


class PackagingTests(unittest.TestCase):
    def test_pyproject_matches_version_and_entrypoint(self):
        data = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
        self.assertEqual(data['project']['version'], receipts.__version__)
        self.assertEqual(data['project']['version'], '0.2.0')
        self.assertEqual(data['project']['scripts']['receipts'], 'receipts.cli:main')
        self.assertEqual(data['project']['dependencies'], [])
        self.assertEqual(data['build-system']['build-backend'], 'setuptools.build_meta')

    def test_shell_scripts_use_lf(self):
        for name in ('setup.sh', 'receipts.sh', 'receipts-hook.sh'):
            with self.subTest(name=name):
                self.assertNotIn(b'\r\n', (ROOT / name).read_bytes())

    @unittest.skipUnless(shutil.which('sh'), 'POSIX sh not available')
    def test_sh_launcher_help_missing_interpreter_and_hook(self):
        script = (ROOT / 'receipts.sh').as_posix()
        env = dict(os.environ, RECEIPTS_PYTHON=posix(sys.executable))
        run = subprocess.run(['sh', script, '--help'], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('audit', run.stdout)
        env['RECEIPTS_PYTHON'] = '/missing/python'
        run = subprocess.run(['sh', script, '--help'], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 2)
        self.assertIn('Python', run.stderr)
        hook = subprocess.run(['sh', (ROOT / 'receipts-hook.sh').as_posix(), '--source', 'codex'], input='{broken',
                              env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(hook.returncode, 0)
        self.assertEqual(hook.stdout, '')

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class PortableCheckoutTests(unittest.TestCase):
    def test_clean_copy_setup_audit_and_hook(self):
        original=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='portable receipts ') as directory:
            root=Path(directory)/'checkout with spaces';root.mkdir()
            shutil.copytree(original/'src',root/'src',ignore=shutil.ignore_patterns('__pycache__'))
            for name in ['setup.cmd','receipts.cmd','receipts-hook.cmd']:
                shutil.copyfile(original/name,root/name)
            env=dict(os.environ,RECEIPTS_PYTHON=sys.executable)
            setup=subprocess.run(['cmd','/d','/c',str(root/'setup.cmd')],cwd=directory,env=env,
                capture_output=True,text=True,timeout=60)
            self.assertEqual(setup.returncode,0,setup.stdout+setup.stderr)
            env.pop('RECEIPTS_PYTHON')
            self.assertTrue((root/'.venv/Scripts/python.exe').is_file())
            result=subprocess.run(['cmd','/d','/c',str(root/'receipts.cmd'),'--help'],cwd=directory,env=env,
                capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            from test_cli_integration import fixture
            path=root/'session.jsonl';fixture(path)
            command = 'cmd.exe /d /s /c "' + subprocess.list2cmdline([str(root/'receipts.cmd'),'audit',str(path)]) + '"'
            result=subprocess.run(command,
                cwd=directory,env=env,capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(list((root/'reports').glob('*.md')))
            self.assertFalse((Path(directory)/'reports').exists())
            result=subprocess.run(['cmd','/d','/c',str(root/'receipts-hook.cmd'),'--source','codex'],
                input='{broken',cwd=directory,env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0)
            self.assertEqual(result.stdout,'')

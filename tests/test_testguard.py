from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from receipts.testguard import compare_versions
from receipts.git_read import run_git, changed_versions


class TestguardTests(unittest.TestCase):
    def test_five_weakened_diffs(self):
        cases = [
            ('tests/test_a.py', 'def test_x():\n assert 1\n assert 2\n', 'def test_x():\n assert 1\n'),
            ('test_a.py', 'def test_x():\n assert 1\n', '@pytest.mark.skip\ndef test_x():\n assert 1\n'),
            ('test_a.py', 'def test_x():\n assert 1\n', ''),
            ('a.test.ts', 'test("x", () => { expect(x).toEqual(2); });', 'test.skip("x", () => { expect(x).toBeDefined(); });'),
            ('a.spec.ts', 'try { run(); } catch(e) { throw e; }', 'try { run(); } catch(e) {}'),
        ]
        for path, old, new in cases:
            with self.subTest(path=path, new=new):
                self.assertTrue(compare_versions(path,old,new))

    def test_five_legitimate_refactors_recorded(self):
        cases = [
            ('def test_old():\n assert 1\n','def test_new():\n assert 1\n'),
            ('def test_x():\n assert a\n assert b\n','def test_x():\n assert all((a,b))\n'),
            ('def test_x():\n assert a\n','def test_x():\n check(a)\n'),
            ('def test_x():\n assert a\n','@pytest.mark.parametrize("a", [1,2])\ndef test_x(a):\n assert a\n'),
            ('def test_x():\n assert a\n','def helper():\n pass\n\ndef test_x():\n assert a\n'),
        ]
        counts=[len(compare_versions('tests/test_a.py',a,b)) for a,b in cases]
        self.assertEqual(counts,[1,1,1,0,0])

    def test_non_test_ignored(self):
        self.assertEqual(compare_versions('src/a.py','assert 1',''),())

    def test_parse_error_not_clean(self):
        with self.assertRaises(ValueError):compare_versions('test_a.py','def test_x():\n assert 1\n','def broken(')

    def test_python_swallowed_exception(self):
        found=compare_versions('test_x.py','def test_x():\n assert a\n',
                               'def test_x():\n try:\n  assert a\n except Exception:\n  pass\n')
        self.assertIn('swallowed_exception',[f.signal for f in found])


class GitTests(unittest.TestCase):
    def setUp(self):
        executable=os.environ.get('RECEIPTS_GIT') or shutil.which('git')
        if not executable:
            self.skipTest('Git is required for disposable repository integration tests.')
        self.git=executable
    def make_repo(self,directory):
        root=Path(directory)
        for args in [('init',),('config','user.name','Example'),('config','user.email','example@invalid.local')]:
            self.assertEqual(subprocess.run([self.git, '-C',str(root),*args],capture_output=True).returncode,0)
        p=root/'test_with space.py';p.write_text('def test_x():\n assert 1\n assert 2\n')
        for args in [('add','.'),('commit','-m','fixture')]:
            self.assertEqual(subprocess.run([self.git,'-C',str(root),*args],capture_output=True).returncode,0)
        return root,p

    def test_staged_unstaged_and_index_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root,p=self.make_repo(d)
            p.write_text('def test_x():\n assert 1\n')
            subprocess.run([self.git,'-C',d,'add','.'],check=True,capture_output=True)
            before=hashlib.sha256((root/'.git/index').read_bytes()).hexdigest()
            index_mtime=(root/'.git/index').stat().st_mtime_ns
            versions=changed_versions(root)
            self.assertEqual(len(versions),1)
            self.assertIn('assert 2',versions[0].old)
            self.assertNotIn('assert 2',versions[0].new)
            self.assertEqual(hashlib.sha256((root/'.git/index').read_bytes()).hexdigest(),before)
            self.assertEqual((root/'.git/index').stat().st_mtime_ns,index_mtime)

    def test_not_repo_and_write_command_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertNotEqual(run_git(Path(d),['rev-parse','HEAD']).returncode,0)
            with self.assertRaises(ValueError):run_git(Path(d),['reset','--hard'])

    def test_invalid_base_and_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):changed_versions(Path(d),'--output=bad')

    def test_inherited_git_dir_not_used(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root,_=self.make_repo(d)
            with patch.dict(os.environ,{'GIT_DIR':'Z:/invalid'}):
                self.assertEqual(run_git(root,['rev-parse','--is-inside-work-tree']).stdout.strip(),'true')

    def test_staged_weakening_unstaged_restoration_visible(self):
        with tempfile.TemporaryDirectory() as d:
            root,p=self.make_repo(d)
            original=p.read_text()
            p.write_text('def test_x():\n assert 1\n')
            subprocess.run([self.git,'-C',d,'add','.'],check=True,capture_output=True)
            p.write_text(original)
            versions=changed_versions(root)
            findings=[f for version in versions for f in compare_versions(version.path,version.old,version.new)]
            self.assertTrue(findings)

    def test_git_timeout_is_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'timed out'),patch.dict(os.environ,{'RECEIPTS_LANG':''}):
                run_git(Path(d),['rev-parse','HEAD'],timeout=0)

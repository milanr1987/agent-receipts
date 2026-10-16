import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr

from receipts.cli import main
from receipts.discovery import discover, parse_since
from receipts.report import render_report
from receipts.evaluation import evaluate_labels


def fixture(path, failed=False, secret=''):
    def item(value):
        return {'type':'event_msg','payload':{'type':'item_completed','turn_id':'t','item':value}}
    rows=[{'type':'session_meta','payload':{'id':'s','cwd':'C:/Users/Example/project'}},
          item({'type':'CommandExecution','id':'c','command':['pytest'], 'status':'completed',
                'exit_code':1 if failed else 0,'aggregated_output':('1 failed' if failed else '2 passed')+secret}),
          item({'type':'AgentMessage','id':'m','content':[{'type':'text','text':'All tests pass '+secret}]})]
    path.write_text('\n'.join(json.dumps(r) for r in rows),encoding='utf-8')


class IntegrationTests(unittest.TestCase):
    def test_discovery_missing_and_filters(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            self.assertEqual(discover(home,'all',env={}),())
            path=home/'.codex/sessions/2026/10/15/session.jsonl';path.parent.mkdir(parents=True);fixture(path)
            self.assertEqual(discover(home,'codex',env={}),(path,))
            self.assertEqual(discover(home,'claude',env={}),())
            self.assertEqual(discover(home,'all',project=Path('C:/Users/Example/other'),env={}),())
        with self.assertRaises(ValueError):parse_since('bananas')

    def test_discovery_profiles_env_and_subagents(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            main_s=home/'.claude/projects/p/s.jsonl'
            sub=home/'.claude/projects/p/s/subagents/agent-1.jsonl'
            work=home/'.claude-work/projects/p/w.jsonl'
            other=home/'elsewhere/projects/p/o.jsonl'
            for p in (main_s,sub,work,other):
                p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}',encoding='utf-8')
            self.assertEqual(discover(home,'claude',env={}),tuple(sorted([main_s,work],key=str)))
            self.assertEqual(discover(home,'claude',env={},include_subagents=True),tuple(sorted([main_s,sub,work],key=str)))
            self.assertEqual(discover(home,'claude',profile='.claude-work',env={}),(work,))
            self.assertIn(other,discover(home,'claude',env={'CLAUDE_CONFIG_DIR':str(home/'elsewhere')}))
            for bad in ('.claude-missing','../evil','projects'):
                with self.subTest(bad=bad),self.assertRaises(ValueError):
                    discover(home,'claude',profile=bad,env={})

    def test_audit_offline_redacted_and_unchanged(self):
        from receipts import report
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'session.jsonl'
            fixture(path,secret=' api_key=sentinel-secret hello@example.org C:/Users/Private/proj')
            before=hashlib.sha256(path.read_bytes()).hexdigest();mtime=path.stat().st_mtime_ns
            with patch.object(report,'REPORTS_DIR',root/'reports'),patch('socket.socket.connect',side_effect=AssertionError('Network forbidden')):
                with redirect_stdout(io.StringIO()):code=main(['audit',str(path)])
            self.assertEqual(code,0)
            files=list((root/'reports').glob('*'));self.assertTrue(files)
            content=''.join(p.read_text(encoding='utf-8') for p in files)
            for value in ['sentinel-secret','hello@example.org','Private']:self.assertNotIn(value,content)
            self.assertIn('CONFIRMED',content)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
            self.assertEqual(path.stat().st_mtime_ns,mtime)

    def test_malformed_not_clean(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.jsonl';p.write_text('not json')
            with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                self.assertEqual(main(['audit',str(p)]),2)

    def test_eval_counts_zero_denominator_and_real_negative(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'good.jsonl';b=root/'bad.jsonl'
            fixture(a);fixture(b,failed=True)
            labels=root/'labels.csv'
            with labels.open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=['source','session_path','line','claim_type','truth'])
                w.writeheader()
                for p,truth in [(a,'true'),(b,'false')]:
                    w.writerow(dict(source='codex',session_path=str(p),line=3,claim_type='tests_pass',truth=truth))
            data=evaluate_labels(labels)
            group=data['codex/tests_pass']
            self.assertEqual((group['TP'],group['FP'],group['FN']),(1,0,0))
            self.assertEqual(group['recall'],1.0)

    def test_markdown_escape(self):
        from receipts.models import Event,Claim,Verdict,Session
        event=Event('codex','s','.',1,'t','assistant_text','All tests pass | <script>')
        text=render_report([(Session('codex','s',(event,)),(Verdict(Claim('tests_pass',event,event.text),'NO_EVIDENCE',()),))])
        self.assertNotIn('<script>',text)
        self.assertIn('\\|',text)

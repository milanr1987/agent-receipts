import csv
import hashlib
import io
import json
import os
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
    def test_huge_line_does_not_make_audit_incomplete(self):
        from receipts import report
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'s.jsonl';fixture(path)
            with path.open('a',encoding='utf-8') as f:
                f.write('\n{"type":"response_item","payload":{"type":"message","role":"user","content":"'+'x'*(9*1024*1024)+'"}}')
            with patch.object(report,'REPORTS_DIR',root/'r'),redirect_stdout(io.StringIO()):
                self.assertEqual(main(['audit',str(path)]),0)

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

    def test_codex_text_fixture_end_to_end(self):
        from receipts import report
        path=Path(__file__).resolve().parent/'fixtures'/'codex-text-output.jsonl'
        with tempfile.TemporaryDirectory() as d,patch.object(report,'REPORTS_DIR',Path(d)):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['audit',str(path)]),0)

    def test_nonfatal_diagnostic_does_not_force_exit_2(self):
        from receipts import report
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'s.jsonl';fixture(path)
            with path.open('a',encoding='utf-8') as f:
                f.write('\n{"type":"response_item","payload":{"type":"function_call","name":"exec_command","call_id":"q","arguments":"{\\"cmd\\":\\"ls\\"}"}}')
                f.write('\n{"type":"response_item","payload":{"type":"function_call_output","call_id":"q","output":"???"}}')
            with patch.object(report,'REPORTS_DIR',root/'r'),redirect_stdout(io.StringIO()):
                self.assertEqual(main(['audit',str(path)]),0)

    def test_unknown_file_in_discovery_is_skipped(self):
        from receipts import report
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            good=home/'.codex/sessions/2026/10/16/s.jsonl';good.parent.mkdir(parents=True);fixture(good)
            junk=home/'.claude/projects/p/summary.jsonl';junk.parent.mkdir(parents=True)
            junk.write_text('{"type":"summary","summary":"x"}\n',encoding='utf-8')
            env={'CODEX_HOME':str(home/'.codex'),'CLAUDE_CONFIG_DIR':str(home/'.claude')}
            with patch('pathlib.Path.home',return_value=home),patch.dict(os.environ,env), \
                    patch.object(report,'REPORTS_DIR',home/'r'),redirect_stdout(io.StringIO()):
                self.assertEqual(main(['audit','--since','1d','--lang','en']),0)
            text=''.join(p.read_text(encoding='utf-8') for p in (home/'r').glob('*.md'))
            self.assertIn('Skipped 1 files',text)

    def test_json_output_valid_and_redacted(self):
        from receipts import report
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'s.jsonl'
            fixture(path,secret=' api_key=sentinel-secret "quoted" hello@example.org')
            with patch.object(report,'REPORTS_DIR',root/'r'),redirect_stdout(io.StringIO()) as out,redirect_stderr(io.StringIO()):
                code=main(['audit',str(path),'--format','json'])
            data=json.loads(out.getvalue())
            self.assertEqual(code,0)
            self.assertEqual(data['schema_version'],1)
            self.assertEqual(data['summary']['codex']['CONFIRMED'],1)
            self.assertEqual(data['sessions'][0]['verdicts'][0]['status'],'CONFIRMED')
            self.assertFalse(data['sessions'][0]['subagent'])
            for secret in ['sentinel-secret','hello@example.org']:
                self.assertNotIn(secret,out.getvalue())
            self.assertTrue(list((root/'r').glob('*.json')))

    def test_report_dir_order(self):
        from receipts import report
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.assertEqual(report.reports_dir(out=root/'x'),root/'x')
            with patch.object(report,'REPORTS_DIR',None):
                self.assertEqual(report.reports_dir(env={'RECEIPTS_HOME':str(root)}),root/'reports')
                with patch.object(report,'_checkout_root',return_value=None):
                    key='LOCALAPPDATA' if os.name=='nt' else 'XDG_STATE_HOME'
                    self.assertEqual(report.reports_dir(env={key:str(root)}),root/'agent-receipts'/'reports')
                self.assertEqual(report.reports_dir(env={}),Path(__file__).resolve().parents[1]/'reports')

    def test_subagent_label(self):
        from receipts.models import Event,Claim,Verdict,Session
        event=Event('claude','s','.',1,'1','assistant_text','All tests pass')
        text=render_report([(Session('claude','s',(event,),subagent=True),(Verdict(Claim('tests_pass',event,event.text),'NO_EVIDENCE',()),))])
        self.assertIn('(subagent)',text)

    def test_report_groups_review_conversation_confirmed(self):
        from receipts.models import Event,Claim,Verdict,Session
        def v(text,status,conv=False,turn='1'):
            e=Event('claude','abcdef1234567','C:/Users/Private/my-app',3,turn,'assistant_text',text,timestamp='2026-10-16T10:42:00Z')
            return Verdict(Claim('tests_pass',e,text),status,('line 2: x',),conv)
        s=Session('claude','abcdef1234567',(),project='my-app',started_at='2026-10-16T10:42:00Z')
        empty=Session('codex','empty1',())
        text=render_report([(s,(v('Ok one','CONFIRMED'),v('Chat says pass','NO_EVIDENCE',True),v('Bad one','CONTRADICTED'))),(empty,())],skipped=1)
        review,conv,conf=text.index('## To review'),text.index('## Mentioned in conversation'),text.index('## Confirmed')
        self.assertLess(review,conv);self.assertLess(conv,conf)
        self.assertIn('### my-app · 2026-10-16 10:42 · claude abcdef12',text)
        self.assertLess(text.index('Bad one'),conv)
        self.assertGreater(text.index('Chat says pass'),conv)
        self.assertIn('Skipped 1 files · 1 sessions without claims',text)
        self.assertNotIn('empty1',text)
        self.assertNotIn('Private',text)

    def test_conversation_only_report_exits_zero(self):
        from receipts import report
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'s.jsonl'
            path.write_text(json.dumps({'type':'event_msg','payload':{'type':'task_complete','turn_id':'t','last_agent_message':'All tests pass'}}),encoding='utf-8')
            with patch.object(report,'REPORTS_DIR',root/'r'),redirect_stdout(io.StringIO()):
                self.assertEqual(main(['audit',str(path)]),0)
            text=''.join(p.read_text(encoding='utf-8') for p in (root/'r').glob('*.md'))
            self.assertNotIn('## To review',text)
            self.assertNotIn('## Confirmed',text)

    def test_printed_report_path_is_real(self):
        from receipts import report
        with tempfile.TemporaryDirectory(prefix='receipts-Private-') as d:
            root=Path(d);path=root/'s.jsonl';fixture(path)
            with patch.object(report,'REPORTS_DIR',root/'r'),redirect_stdout(io.StringIO()) as out:
                main(['audit',str(path)])
            self.assertIn(str(root/'r'),out.getvalue())

    def test_json_has_project_started_and_conversation_flag(self):
        from receipts import report
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'s.jsonl';fixture(path)
            with patch.object(report,'REPORTS_DIR',root/'r'),redirect_stdout(io.StringIO()) as out,redirect_stderr(io.StringIO()):
                main(['audit',str(path),'--format','json'])
            data=json.loads(out.getvalue())
            self.assertEqual(data['sessions'][0]['project'],'project')
            self.assertIn('started_at',data['sessions'][0])
            self.assertFalse(data['sessions'][0]['verdicts'][0]['conversation_only'])
            self.assertEqual(data['summary']['sessions_without_claims'],0)

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

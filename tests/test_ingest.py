import json
from pathlib import Path
import tempfile
import unittest

from receipts.ingest import codex, claude
from receipts.ingest.detect import detect


def parse_rows(parser, rows):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'session.jsonl'
        path.write_text('\n'.join(json.dumps(x) for x in rows), encoding='utf-8')
        return parser(path)


def completed(item, turn='turn1'):
    return {'type': 'event_msg', 'payload': {'type': 'item_completed', 'turn_id': turn, 'item': item}}


class CodexTests(unittest.TestCase):
    def test_malformed_nested_shape_diagnosed(self):
        for row in [{'type':'event_msg','payload':None},completed(None),
                    completed({'type':'FileChange','id':'f','changes':{'x.py':{'type':None}}}),
                    {'type':'response_item','payload':{'type':'function_call','name':'exec_command','call_id':'x','arguments':None}}]:
            with self.subTest(row=row):
                self.assertTrue(parse_rows(codex.parse,[row]).diagnostics)

    def test_repeated_runner_different_id_keeps_last_failure(self):
        from receipts.claims import extract_claims
        from receipts.evidence import evaluate
        rows=[]
        for iid,code in [('a',0),('b',1)]:
            rows.extend([
                {'type':'response_item','payload':{'type':'function_call','name':'exec_command','call_id':iid,'arguments':'{"cmd":"pytest"}'}},
                {'type':'response_item','payload':{'type':'function_call_output','call_id':iid,'output':json.dumps({'exit_code':code,'output':'2 passed' if code==0 else '1 failed'})}}])
        rows.append({'type':'event_msg','payload':{'type':'task_complete','last_agent_message':'All tests pass'}})
        session=parse_rows(codex.parse,rows)
        self.assertEqual(evaluate(session,extract_claims(session.events))[0].status,'CONTRADICTED')

    def test_primary_message_does_not_hide_fallback_commands(self):
        s=parse_rows(codex.parse,[completed({'type':'AgentMessage','id':'m','content':[]}),
            {'type':'response_item','payload':{'type':'function_call','name':'exec_command','call_id':'x','arguments':'{"cmd":"pytest"}'}},
            {'type':'response_item','payload':{'type':'function_call_output','call_id':'x','output':'{"exit_code":0,"output":"2 passed"}'}}])
        self.assertTrue(any(e.kind=='tool_result' and e.exit_code==0 for e in s.events))

    def call_and_output(self, output):
        return parse_rows(codex.parse, [
            {'type':'turn_context','payload':{'turn_id':'t','cwd':'/x'}},
            {'type':'response_item','payload':{'type':'function_call','name':'shell_command','call_id':'z','arguments':'{"command":"pytest"}'}},
            {'type':'response_item','payload':{'type':'function_call_output','call_id':'z','output':output}}])

    def test_text_output_format(self):
        s=self.call_and_output('Exit code: 0\nWall time: 1.2 seconds\nOutput:\n2 passed\n')
        r=s.events[-1]
        self.assertEqual((r.exit_code,r.exit_source,r.status),(0,'explicit','completed'))
        self.assertIn('2 passed',r.text);self.assertNotIn('Wall time',r.text)
        self.assertEqual(s.diagnostics,())

    def test_list_output_format(self):
        s=self.call_and_output([{'type':'input_text','text':'Exit code: 1\nWall time: 0.5 seconds\nOutput:\n1 failed'}])
        self.assertEqual((s.events[-1].exit_code,s.events[-1].is_error),(1,True))

    def test_execution_error_is_not_executed(self):
        s=self.call_and_output('execution error: Io(Custom { kind: Other, error: "sandbox" })')
        r=s.events[-1]
        self.assertEqual((r.exit_code,r.status,r.is_error),(None,'not_executed',None))
        self.assertEqual(s.diagnostics,())

    def test_unknown_text_still_diagnosed(self):
        s=self.call_and_output('something else entirely')
        self.assertEqual([d.code for d in s.diagnostics],['unsupported_result'])

    def test_unrelated_mcp_result_not_command_diagnostic(self):
        s=parse_rows(codex.parse,[completed({'type':'AgentMessage','id':'m','content':[]}),
            {'type':'response_item','payload':{'type':'function_call','name':'web_search','call_id':'w','arguments':'{}'}},
            {'type':'response_item','payload':{'type':'function_call_output','call_id':'w','output':'plain search result'}}])
        self.assertEqual(s.diagnostics,())
    def test_commands_and_files_preserve_result(self):
        rows = [{'type': 'session_meta', 'payload': {'id': 's', 'cwd': '/project'}},
                completed({'type': 'CommandExecution', 'id': 'c', 'command': ['python', '-m', 'unittest'],
                           'cwd': '/project', 'status': 'completed', 'exit_code': 0, 'aggregated_output': 'Ran 2 tests\nOK'}),
                completed({'type': 'FileChange', 'id': 'f', 'status': 'completed',
                           'changes': {'new.py': {'type': 'add'}, 'old.py': {'type': 'update'}}})]
        session = parse_rows(codex.parse, rows)
        result = next(e for e in session.events if e.kind == 'tool_result' and e.tool_id == 'c')
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Ran 2 tests', result.text)
        self.assertEqual(result.turn, 'turn1')
        change = next(e for e in session.events if e.tool_id == 'f')
        self.assertIn(('new.py', 'add'), change.file_actions)

    def test_running_is_not_success(self):
        s = parse_rows(codex.parse, [completed({'type': 'CommandExecution', 'id': 'x',
                           'command': ['pytest'], 'status': 'running', 'exit_code': None})])
        self.assertIsNone(s.events[-1].exit_code)
        self.assertNotEqual(s.events[-1].status, 'completed')

    def test_final_message_deduplicated(self):
        s = parse_rows(codex.parse, [completed({'type': 'AgentMessage', 'id': 'a',
            'content': [{'type': 'text', 'text': 'All tests pass'}]}),
            {'type': 'event_msg', 'payload': {'type': 'task_complete', 'turn_id': 'turn1',
                                             'last_agent_message': 'All tests pass'}}])
        self.assertEqual(len([e for e in s.events if e.kind == 'assistant_text']), 1)

    def test_response_fallback_links_id(self):
        s = parse_rows(codex.parse, [
            {'type': 'turn_context', 'payload': {'turn_id': 't', 'cwd': '/x'}},
            {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'exec_command',
                  'call_id': 'z', 'arguments': '{"cmd":"pytest -q"}'}},
            {'type': 'response_item', 'payload': {'type': 'function_call_output', 'call_id': 'z',
                  'output': '{"exit_code":1,"output":"1 failed"}'}}])
        self.assertEqual(s.events[-1].exit_code, 1)
        self.assertEqual(s.events[-1].tool_id, 'z')

    def test_bad_and_truncated_lines_diagnosed(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'x.jsonl'
            p.write_text('{"type":"session_meta","payload":{}}\n{"broken":', encoding='utf-8')
            s = codex.parse(p)
            self.assertTrue(s.diagnostics)

    def test_oversized_line_not_clean(self):
        from receipts.ingest.common import read_rows
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'x'
            p.write_bytes(b'x' * 100)
            _, diagnostics = read_rows(p, max_line=20)
            self.assertTrue(diagnostics)

    def test_unknown_format_not_clean_success(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'x.jsonl'
            p.write_text('{"unrelated":true}\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                detect(p)


class ClaudeTests(unittest.TestCase):
    def bash(self, result, extra, command='git commit -m fix'):
        return parse_rows(claude.parse, [
            {'type':'user','sessionId':'s','cwd':'/p','message':{'content':'go'}},
            {'type':'assistant','message':{'content':[{'type':'tool_use','id':'a','name':'Bash','input':{'command':command}}]}},
            {'type':'user','toolUseResult':extra,'message':{'content':[dict({'type':'tool_result','tool_use_id':'a'},**result)]}}]).events[-1]

    def test_host_success_flag_sets_exit_zero(self):
        r=self.bash({'content':'[main abc1234] fix','is_error':False},{'stdout':'[main abc1234] fix','stderr':'','interrupted':False})
        self.assertEqual((r.exit_code,r.exit_source,r.status),(0,'host_success_flag','completed'))

    def test_explicit_exit_code_wins(self):
        r=self.bash({'content':'out\nExit code 0','is_error':False},{'stdout':'out','interrupted':False})
        self.assertEqual((r.exit_code,r.exit_source),(0,'explicit'))

    def test_error_and_interrupt_not_success(self):
        r=self.bash({'content':'Exit code 1\nfatal','is_error':True},'Error: Exit code 1')
        self.assertEqual((r.exit_code,r.status,r.is_error),(1,'failed',True))
        r=self.bash({'content':'partial','is_error':False},{'stdout':'partial','interrupted':True})
        self.assertEqual((r.exit_code,r.status),(None,'failed'))

    def test_background_bash_is_running_not_success(self):
        r=self.bash({'content':'Command running in background with ID: bg1','is_error':False},
                    {'stdout':'','interrupted':False,'backgroundTaskId':'bg1'})
        self.assertEqual((r.exit_code,r.status),(None,'running'))

    def test_null_tool_use_result_safe(self):
        s=parse_rows(claude.parse,[
            {'type':'assistant','message':{'content':[{'type':'tool_use','id':'a','name':'Bash','input':{'command':'pytest'}}]}},
            {'type':'user','toolUseResult':None,'message':{'content':[{'type':'tool_result','tool_use_id':'a','content':'2 passed'}]}}])
        self.assertEqual(s.events[-1].text,'2 passed')
    def test_link_result_and_human_turns(self):
        s = parse_rows(claude.parse, [
            {'type': 'user', 'sessionId': 's', 'cwd': '/p', 'message': {'content': 'do tests'}},
            {'type': 'assistant', 'message': {'content': [
                {'type': 'thinking', 'thinking': 'PRIVATE REASONING'},
                {'type': 'tool_use', 'id': 'a', 'name': 'Bash', 'input': {'command': 'pytest'}}]}},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'a',
                         'content': '2 passed\nExit code 0', 'is_error': False}]}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'all tests pass'}]}}])
        self.assertEqual({e.turn for e in s.events}, {'1'})
        self.assertEqual(s.events[-2].tool_id, 'a')
        self.assertEqual(s.events[-2].exit_code, 0)
        self.assertNotIn('PRIVATE REASONING', str(s))

    def test_false_is_error_does_not_invent_exit_code(self):
        s = parse_rows(claude.parse, [
            {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'a', 'name': 'Bash', 'input': {'command': 'pytest'}}]}},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'a',
                         'content': 'unrecognized output', 'is_error': False}]}}])
        self.assertIsNone(s.events[-1].exit_code)

    def test_failed_write_not_successful_file(self):
        s = parse_rows(claude.parse, [
            {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'w', 'name': 'Write', 'input': {'file_path': 'x.py'}}]}},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'w', 'content': 'denied', 'is_error': True}]}}])
        self.assertTrue(s.events[-1].is_error)
        self.assertEqual(s.events[-1].files, ('x.py',))

    def test_missing_result_is_not_fabricated(self):
        s = parse_rows(claude.parse, [{'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'id': 'a', 'name': 'Bash', 'input': {'command': 'pytest'}}]}}])
        self.assertEqual([e.kind for e in s.events], ['tool_call'])

    def test_orphan_result_diagnosed(self):
        s = parse_rows(claude.parse, [{'type': 'user', 'message': {'content': [
            {'type': 'tool_result', 'tool_use_id': 'missing', 'content': 'ok'}]}}])
        self.assertTrue(s.diagnostics)

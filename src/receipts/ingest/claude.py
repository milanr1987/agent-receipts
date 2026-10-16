import re
from ..models import Event, Session, Diagnostic
from ..redaction import redact
from ..messages import t
from .common import read_rows, text_content


def parse(path, read=None):
    rows, diagnostics = read if read is not None else read_rows(path)
    diagnostics = list(diagnostics)
    session_id, cwd, turn = path.stem, '', 0
    events, calls = [], {}
    for number, row in rows:
        session_id = str(row.get('sessionId', session_id))
        cwd = str(row.get('cwd', cwd))
        kind = row.get('type')
        message = row.get('message', {})
        if kind not in ('assistant', 'user') or not isinstance(message, dict):
            continue
        content = message.get('content', [])
        if isinstance(content, str):
            content = [{'type': 'text', 'text': content}]
        if not isinstance(content, list):
            continue
        if kind == 'user' and any(b.get('type') in ('text', 'input_text') for b in content if isinstance(b, dict)):
            turn += 1

        def emit(typ, text='', name=None, iid=None, **kw):
            events.append(Event('claude', session_id, cwd, number, str(turn), typ, redact(text),
                                name, iid, timestamp=row.get('timestamp'), **kw))

        for block in content:
            if not isinstance(block, dict):
                continue
            typ = block.get('type')
            if typ == 'text':
                emit('assistant_text' if kind == 'assistant' else 'user_text', block.get('text', ''))
            elif typ == 'tool_use':
                name, iid = block.get('name', ''), block.get('id')
                data = block.get('input', {})
                if not isinstance(data, dict):
                    continue
                files = (data['file_path'],) if isinstance(data.get('file_path'), str) else ()
                text = data.get('command', '')
                emit('tool_call', str(text), name, iid, files=files)
                calls[iid] = (name, files, str(turn))
            elif typ == 'tool_result':
                iid = block.get('tool_use_id')
                if iid not in calls:
                    diagnostics.append(Diagnostic('orphan_result', number, t('diag_orphan_result')))
                    continue
                name, files, call_turn = calls[iid]
                text = text_content(block.get('content', ''))
                match = re.search(r'(?im)^\s*(?:Exit code|Process exited with code)\s*:?\s*(-?\d+)\s*$', text)
                code = int(match[1]) if match else None
                exit_source = 'explicit' if match else None
                failed = block.get('is_error') is True or (code is not None and code != 0)
                extra = row.get('toolUseResult')
                if isinstance(extra, dict) and extra.get('interrupted'):
                    failed = True
                status = 'failed' if failed else 'completed'
                if not failed and isinstance(extra, dict) and extra.get('backgroundTaskId'):
                    # run_in_background returns before the command finishes.
                    status = 'running'
                elif (code is None and not failed and name in ('Bash', 'PowerShell')
                      and isinstance(extra, dict) and extra.get('interrupted') is False):
                    # Claude Code sets is_error on a non-zero exit and omits the code on success.
                    code, exit_source = 0, 'host_success_flag'
                # Associate with original call even if late results arrive after another human turn.
                old_turn = turn
                turn = int(call_turn)
                emit('tool_result', text, name, iid, files=files, exit_code=code, exit_source=exit_source,
                     status=status, is_error=failed,
                     file_actions=tuple((p, 'add' if name == 'Write' else 'update') for p in files))
                turn = old_turn
    return Session('claude', session_id, tuple(events), tuple(diagnostics))

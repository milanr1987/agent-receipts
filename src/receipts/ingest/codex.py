import json
import re
from ..models import Event, Session, Diagnostic
from ..redaction import redact
from ..messages import t
from .common import read_rows, text_content

TEXT_EXIT = re.compile(r'\A\s*Exit code:\s*(-?\d+)[ \t]*$', re.M)


def decode_output(raw):
    """Return (exit_code, output, status) for JSON or plain-text command output, or None."""
    if isinstance(raw, list):
        raw = text_content(raw)
    if not isinstance(raw, str):
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        data = None
    if isinstance(data, dict):
        code = data.get('exit_code')
        code = code if type(code) is int else None
        return code, str(data.get('output', '')), 'completed' if code is not None else 'unknown'
    match = TEXT_EXIT.match(raw)
    if match:
        # Codex 0.125-0.159: "Exit code: N\nWall time: ...\n[Total output lines: N\n]Output:\n<text>"
        body = raw.split('\nOutput:\n', 1)
        return int(match[1]), body[1] if len(body) == 2 else raw[match.end():], 'completed'
    if raw.lstrip().startswith('execution error:'):
        # The sandbox refused to start the command: not a result in either direction.
        return None, raw, 'not_executed'
    return None


def parse(path):
    rows, diagnostics = read_rows(path)
    session_id, cwd, turn = path.stem, '', '0'
    events, finals, ids = [], set(), set()
    # A primary execution stream suppresses the mirrored response stream. Mixing
    # undocumented identifiers would otherwise manufacture duplicate evidence.
    primary_ids = set()
    fallback_ids = set()
    for _, r in rows:
        p = r.get('payload')
        i = p.get('item') if isinstance(p, dict) else None
        if isinstance(i, dict) and i.get('type') in ('CommandExecution', 'FileChange'):
            primary_ids.add(str(i.get('id')))
    for number, row in rows:
        payload = row.get('payload', {})
        if not isinstance(payload, dict):
            diagnostics.append(Diagnostic('invalid_payload', number, t('diag_invalid_payload')))
            continue
        if row.get('type') == 'session_meta':
            session_id = str(payload.get('id', session_id))
            cwd = str(payload.get('cwd', cwd))
        if row.get('type') == 'turn_context':
            turn = str(payload.get('turn_id', turn))
            cwd = str(payload.get('cwd', cwd))
        if payload.get('turn_id'):
            turn = str(payload['turn_id'])
        timestamp = row.get('timestamp')

        def emit(kind, text='', tool_name=None, tool_id=None, **kw):
            events.append(Event('codex', session_id, cwd, number, turn, kind, redact(text),
                                tool_name, tool_id, timestamp=timestamp, **kw))

        if row.get('type') == 'event_msg':
            typ = payload.get('type')
            if typ == 'item_completed':
                item = payload.get('item', {})
                if not isinstance(item, dict):
                    diagnostics.append(Diagnostic('invalid_item', number, t('diag_invalid_item')))
                    continue
                typ, iid = item.get('type'), str(item.get('id', number))
                if iid in ids:
                    continue
                ids.add(iid)
                if typ == 'CommandExecution':
                    cwd = str(item.get('cwd', cwd))
                    command = item.get('command', '')
                    if isinstance(command, list):
                        command = ' '.join(str(x) for x in command)
                    code = item.get('exit_code')
                    code = code if type(code) is int else None
                    status = str(item.get('status', 'unknown'))
                    emit('tool_call', str(command), 'command', iid)
                    emit('tool_result', str(item.get('aggregated_output', item.get('stdout', ''))) +
                         '\n' + str(item.get('stderr', '')), 'command', iid,
                         exit_code=code, exit_source='explicit' if code is not None else None,
                         is_error=code != 0 if code is not None else None, status=status)
                elif typ == 'FileChange':
                    actions = []
                    changes = item.get('changes', {})
                    if not isinstance(changes, dict):
                        diagnostics.append(Diagnostic('invalid_changes', number, t('diag_invalid_changes')))
                        continue
                    for name, action in changes.items():
                        action = action.get('type', 'unknown') if isinstance(action, dict) else str(action)
                        if not isinstance(action, str):
                            diagnostics.append(Diagnostic('invalid_action', number, t('diag_invalid_action')))
                            action = 'unknown'
                        actions.append((name, action.lower()))
                    emit('tool_result', '', 'file_change', iid, files=tuple(n for n, _ in actions),
                         file_actions=tuple(actions), status=str(item.get('status', 'unknown')),
                         is_error=item.get('status') != 'completed')
                elif typ == 'AgentMessage':
                    text = text_content(item.get('content', []))
                    if text:
                        emit('assistant_text', text)
                        finals.add((turn, text))
                elif typ == 'UserMessage':
                    emit('user_text', text_content(item.get('content', [])))
            elif typ == 'task_complete':
                text = payload.get('last_agent_message', '')
                if isinstance(text, str) and text and (turn, text) not in finals:
                    emit('assistant_text', text)
                    finals.add((turn, text))
        elif row.get('type') == 'response_item':
            typ, iid = payload.get('type'), payload.get('call_id')
            if str(iid) in primary_ids:
                continue
            if typ in ('function_call', 'custom_tool_call'):
                name = payload.get('name', '')
                raw = payload.get('arguments', payload.get('input', ''))
                if name in ('exec_command', 'shell_command', 'shell'):
                    try:
                        args = json.loads(raw)
                        cmd = args.get('cmd', args.get('command', ''))
                        if isinstance(cmd, list):
                            cmd = ' '.join(cmd)
                        emit('tool_call', str(cmd), 'command', iid)
                        fallback_ids.add(iid)
                    except (ValueError, AttributeError, TypeError):
                        diagnostics.append(Diagnostic('unsupported_call', number, t('diag_unsupported_call')))
            elif typ in ('function_call_output', 'custom_tool_call_output'):
                if iid not in fallback_ids:
                    continue
                decoded = decode_output(payload.get('output', ''))
                if decoded is None:
                    diagnostics.append(Diagnostic('unsupported_result', number, t('diag_unsupported_result')))
                    continue
                code, text, status = decoded
                emit('tool_result', text, 'command', iid, exit_code=code,
                     exit_source='explicit' if code is not None else None, status=status,
                     is_error=code != 0 if code is not None else None)
            elif typ == 'message' and payload.get('role') == 'assistant':
                text = text_content(payload.get('content', []))
                if (turn,text) not in finals:
                    emit('assistant_text', text)
                    finals.add((turn,text))
    return Session('codex', session_id, tuple(events), tuple(diagnostics))

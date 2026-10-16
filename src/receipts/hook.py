"""Advisory Stop hooks; never block a turn or guess another session."""
import json
import os
from pathlib import Path
import sys
from .claims import extract_claims, runner
from .ingest import codex, claude
from .ingest.common import read_rows
from .ingest.detect import detect
from .models import Event
from .messages import t
from . import report
from .redaction import redact


def _log(message):
    try:
        directory = report.reports_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / 'hook.log'
        if path.exists() and path.stat().st_size >= 5 * 1024 * 1024:
            path.replace(directory / 'hook.previous.log')
        with path.open('a', encoding='utf-8') as stream:
            stream.write(redact(message)[:10000] + '\n')
    except OSError:
        pass


HOOK_TAIL_BYTES = 8 * 1024 * 1024
EDIT_TOOLS = ('Write', 'Edit', 'MultiEdit', 'file_change')


def _norm(path):
    return os.path.normcase(os.path.abspath(path)).replace('\\', '/')


def touched_paths(events, cwd):
    paths = set()
    for e in events:
        if e.tool_name in EDIT_TOOLS:
            for p in e.files:
                paths.add(_norm(p if os.path.isabs(p) else os.path.join(cwd, p)))
    return paths


def _was_touched(rel, touched):
    rel = os.path.normcase(rel).replace('\\', '/')
    return any(p == rel or p.endswith('/' + rel) for p in touched)


def _load(source, path, identity):
    """Parse only the tail when it holds the whole current turn; otherwise the full file."""
    parser = codex if source == 'codex' else claude
    try:
        read = read_rows(path, tail_bytes=HOOK_TAIL_BYTES)
        if detect(path, read) == source:
            session = parser.parse(path, read)
            if session.events and session.session_id == identity:
                last = session.events[-1].turn
                if any(e.kind == 'user_text' and e.turn == last for e in session.events):
                    return session
    except ValueError:
        pass  # tail without recognizable rows: use the full read below
    read = read_rows(path)
    if detect(path, read) != source:
        raise ValueError('source_mismatch')
    return parser.parse(path, read)


def handle_hook(source, payload):
    if payload.get('stop_hook_active') is True:
        return None
    try:
        transcript = payload.get('transcript_path')
        identity, cwd = payload.get('session_id'), payload.get('cwd')
        if not isinstance(transcript, str) or not isinstance(identity, str) or not isinstance(cwd, str):
            raise ValueError('missing_identity')
        path = Path(transcript).expanduser()
        session = _load(source, path, identity)
        if session.session_id != identity or not session.events:
            raise ValueError('session_mismatch')
        normalize = lambda s: os.path.normcase(os.path.abspath(s))
        if any(normalize(e.cwd) != normalize(cwd) for e in session.events[-1:]):
            raise ValueError('cwd_mismatch')
        last_turn = str(payload.get('turn_id') or session.events[-1].turn)
        events = [e for e in session.events if e.turn == last_turn]
        if not events:
            raise ValueError('turn_mismatch')
        # Stop may fire before the final message is flushed to the transcript.
        final = payload.get('last_assistant_message')
        if isinstance(final, str) and final:
            final_event = Event(source, identity, cwd, max(e.line for e in events) + 1,
                                last_turn, 'assistant_text', redact(final))
        else:
            final_event = next((e for e in reversed(events) if e.kind == 'assistant_text'), None)
        warnings = []
        if final_event and any(c.type == 'tests_pass' for c in extract_claims([final_event])):
            if not any(e.kind == 'tool_call' and runner(e.text) for e in events):
                warnings.append(t('hook_no_runner'))
        project = Path(cwd)
        touched = touched_paths(events, cwd)
        if touched and project.is_dir():
            try:
                from .git_read import changed_versions
                from .testguard import compare_versions
                findings = [f for version in changed_versions(project) if _was_touched(version.path, touched)
                            for f in compare_versions(version.path, version.old, version.new)]
                if findings:
                    warnings.append(t('hook_weakening', n=len(findings)))
            except ValueError:
                _log(t('hook_git_unavailable'))
        if warnings:
            message = t('hook_prefix') + ' '.join(warnings)
            _log(message)
            return message
        return None
    except Exception:
        _log(t('hook_unknown'))
        return None


def run_hook(source):
    try:
        raw = sys.stdin.read(65537)
        if len(raw.encode('utf-8')) > 65536:
            raise ValueError('input_limit')
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError('input_shape')
        warning = handle_hook(source, payload)
        if warning:
            # Both documented protocols accept systemMessage; no decision:block.
            print(json.dumps({'systemMessage': warning},ensure_ascii=False))
    except Exception:
        _log(t('hook_bad_input'))
    return 0

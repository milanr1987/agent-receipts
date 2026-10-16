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
    return os.path.normcase(os.path.realpath(path)).replace('\\', '/')


def _real(path):
    return os.path.realpath(path).replace('\\', '/')


def touched_paths(events, cwd):
    """Normalized touched path -> the same path in its real case (Git pathspecs are case-sensitive)."""
    paths = {}
    for e in events:
        if e.tool_name in EDIT_TOOLS:
            for p in e.files:
                full = p if os.path.isabs(p) else os.path.join(cwd, p)
                paths[_norm(full)] = _real(full)
    return paths


def _was_touched(rel, top, touched):
    return _norm(os.path.join(str(top), rel)) in touched


def weakening_findings(project, touched):
    """Test-weakening findings for files the agent touched; Git is asked only about those paths."""
    from .git_read import changed_versions, repo_root
    from .testguard import compare_versions
    top = repo_root(project)
    originals = touched if isinstance(touched, dict) else {p: p for p in touched}
    prefix = _norm(str(top)).rstrip('/') + '/'
    top_real = _real(str(top)).rstrip('/') + '/'
    rels = sorted(real[len(top_real):] for norm, real in originals.items()
                  if norm.startswith(prefix) and len(real) > len(top_real))
    if not rels:
        return []
    return [f for version in changed_versions(top, include=lambda rel: _was_touched(rel, top, touched),
                                              paths=rels, resolved=True)
            for f in compare_versions(version.path, version.old, version.new)]


def _tail_read(source, path):
    """Tail rows; Codex keeps its session_meta head row (identity, cwd) in front, renumbered rows follow."""
    rows, diagnostics = read_rows(path, tail_bytes=HOOK_TAIL_BYTES)
    if source == 'codex' and path.stat().st_size > HOOK_TAIL_BYTES:
        head, _ = read_rows(path, max_rows=5)
        head = [(n, r) for n, r in head if r.get('type') == 'session_meta'][:1]
        if head:
            offset = head[0][0]
            rows = head + [(n + offset, r) for n, r in rows]
    return rows, diagnostics


def _load(source, path, identity):
    """Parse only the tail when it holds the whole current turn; otherwise the full file."""
    parser = codex if source == 'codex' else claude
    try:
        read = _tail_read(source, path)
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
                findings = weakening_findings(project, touched)
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

"""Advisory Stop hooks; never block a turn or guess another session."""
import json
import os
from pathlib import Path
import sys
from .claims import extract_claims, runner
from .ingest import codex, claude
from .ingest.detect import detect
from .models import Event
from . import report
from .redaction import redact


def _log(message):
    try:
        report.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path = report.REPORTS_DIR / 'hook.log'
        if path.exists() and path.stat().st_size >= 5 * 1024 * 1024:
            path.replace(report.REPORTS_DIR / 'hook.previous.log')
        with path.open('a', encoding='utf-8') as stream:
            stream.write(redact(message)[:10000] + '\n')
    except OSError:
        pass


def handle_hook(source, payload):
    if payload.get('stop_hook_active') is True:
        return None
    try:
        transcript = payload.get('transcript_path')
        identity, cwd = payload.get('session_id'), payload.get('cwd')
        if not isinstance(transcript, str) or not isinstance(identity, str) or not isinstance(cwd, str):
            raise ValueError('missing_identity')
        path = Path(transcript).expanduser()
        if detect(path) != source:
            raise ValueError('source_mismatch')
        session = (codex if source == 'codex' else claude).parse(path)
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
                warnings.append('Tvrdnja o prolasku testova nema poziv test runnera u ovom potezu.')
        project = Path(cwd)
        if project.is_dir():
            try:
                from .git_read import changed_versions
                from .testguard import compare_versions
                findings = [f for version in changed_versions(project) for f in
                            compare_versions(version.path,version.old,version.new)]
                if findings:
                    warnings.append(f'Signali slabljenja testova: {len(findings)}; potreban je pregled i objašnjenje.')
            except ValueError:
                _log('Git/testguard provjera nije dostupna; potez je propušten.')
        if warnings:
            message = 'Agent Receipts (upozorenje): ' + ' '.join(warnings)
            _log(message)
            return message
        return None
    except Exception:
        _log('Hook provjera nije završena (nepoznat format ili identitet); potez je propušten.')
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
        _log('Neispravan hook ulaz; potez je propušten.')
    return 0

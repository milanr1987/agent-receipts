import json
from ..models import Diagnostic
from ..messages import t


def read_rows(path, max_line=8 * 1024 * 1024, max_file=256 * 1024 * 1024, tail_bytes=None, max_rows=None):
    """Bounded JSONL reader. tail_bytes reads only the end of the file (rows numbered within the window)."""
    rows, diagnostics = [], []
    try:
        size = path.stat().st_size
        if tail_bytes is None and size > max_file:
            return [], [Diagnostic('file_limit', 0, t('diag_file_limit'))]
        with path.open('rb') as stream:
            if tail_bytes is not None and size > tail_bytes:
                stream.seek(size - tail_bytes)
                stream.readline()  # first line of the window is usually cut in half
            number = 0
            while max_rows is None or len(rows) < max_rows:
                raw = stream.readline(max_line + 1)
                if not raw:
                    break
                number += 1
                if len(raw) > max_line:
                    # Skip the rest of the oversized line without loading it; keep reading.
                    while raw and not raw.endswith(b'\n'):
                        raw = stream.readline(1024 * 1024)
                    diagnostics.append(Diagnostic('line_skipped', number, t('diag_line_skipped')))
                    continue
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw.decode('utf-8-sig'))
                    if not isinstance(row, dict):
                        raise ValueError()
                    rows.append((number, row))
                except (ValueError, UnicodeError):
                    diagnostics.append(Diagnostic('invalid_json', number, t('diag_invalid_json')))
    except OSError:
        diagnostics.append(Diagnostic('read_error', 0, t('diag_read_error')))
    return rows, diagnostics


def text_content(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ''
    return '\n'.join(str(b.get('text', '')) for b in content
                     if isinstance(b, dict) and b.get('type') in ('text', 'input_text', 'output_text'))

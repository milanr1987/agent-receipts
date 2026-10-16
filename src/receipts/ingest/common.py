import json
from ..models import Diagnostic
from ..messages import t


def read_rows(path, max_line=8 * 1024 * 1024, max_file=256 * 1024 * 1024):
    rows, diagnostics = [], []
    try:
        size = path.stat().st_size
        if size > max_file:
            return [], [Diagnostic('file_limit', 0, t('diag_file_limit'))]
        with path.open('rb') as stream:
            remaining, number = size, 0
            while remaining > 0:
                raw = stream.readline(min(max_line + 1, remaining))
                remaining -= len(raw)
                number += 1
                if len(raw) > max_line:
                    diagnostics.append(Diagnostic('line_limit', number, t('diag_line_limit')))
                    break
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

"""Redact before persistence; raw source text never belongs in a report."""
import re


def redact(text: str) -> str:
    text = re.sub(r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)',
                  '[PRIVATE KEY REDACTED]', str(text), flags=re.S)
    text = re.sub(r'(?i)(?:sk-|gh[pousr]_|github_pat_|xox[baprs]-)[\w-]{8,}', '[TOKEN]', text)
    text = re.sub(r'\b\d{6,12}:[A-Za-z0-9_-]{25,}\b', '[TOKEN]', text)
    text = re.sub(r'(?i)\bBearer\s+[\w.~-]+', 'Bearer [REDACTED]', text)
    text = re.sub(r'(?i)(["\']?(?:[\w-]*(?:token|password|secret)|api[_-]?key|authorization)["\']?\s*[:=]\s*)'
                  r'(?:"[^"\n]*"|\'[^\'\n]*\'|[^\s,;}]+)', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)\bBearer\s+[\w.~-]+', 'Bearer [REDACTED]', text)
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[EMAIL]', text)
    text = re.sub(r'(?i)([A-Z]:[\\/]Users[\\/])[^\\/\s"\'<>]+', r'\1Example', text)
    text = re.sub(r'(/(?:home|Users)/)[^/\s"\'<>]+', r'\1Example', text)
    return text

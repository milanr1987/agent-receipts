"""Conservative EN/BCS patterns and command recognition, without execution."""
import re
from .models import Claim

PATTERNS = {
    'tests_pass': r'\b(?:all\s+)?(?:\d+\s+)?tests?\s+(?:are\s+)?pass(?:ed|ing)?\b|\b\d+\s+passed\b|\b(?:\d+\s+)?test(?:ovi|ova|a)\s+prolaz[ei]\b',
    'committed': r'\b(?:I\s+(?:have\s+)?committed|I\x27ve committed|committed|commitovao sam|commitovano|commitovane|commitovan|commit napravljen)\b',
    'pushed': r'\b(?:I\s+(?:have\s+)?pushed|pushed|pushao sam|pushovano|poslat[eo]?\s+(?:na\s+)?(?:GitHub|origin))\b',
    'files_changed': r'\b(?:updated|changed|modified|izmijenio sam|izmenio sam)\s+(\d+)\s+(?:files|fajlova)\b',
    'file_created': r'\b(?:created|napravio sam fajl|kreirao sam fajl)\s+[`"\x27]?([\w./\\-]+\.[\w]+)',
}
EXCLUDE = re.compile(r'(?i)\b(?:will|would|should|must|need to|make sure|if|claims?|asserts?|nije|nisu|not|never|bez dokaza'
                     r'|going to|once|until|goal|ću|ćeš|će|ćemo|ćete|treba|trebalo|ako|kad|kada|cilj je|da bi'
                     r'|nothing|none|ništa|(?:did|does|do|is|are|was|were|has|have|had)n[\'’]t)\b')
PATH_TOKEN = re.compile(r'[\w./\\-]+\.\w+')


def strip_non_claims(text):
    """Drop markdown that quotes or tabulates text instead of asserting it."""
    text = re.sub(r'(?s)```.*?(?:```|\Z)', '\n', text)
    # Keep inline code only when it is a file path, so "Created `a.py`" still names the file.
    text = re.sub(r'`([^`\n]*)`', lambda m: m[1] if PATH_TOKEN.fullmatch(m[1]) else ' ', text)
    text = '\n'.join(line for line in text.split('\n') if not re.match(r'\s*[|>]', line))
    return re.sub(r'"[^"\n]*"|“[^”\n]*”|„[^“”\n]*[“”]', ' ', text)


def extract_claims(events):
    found = []
    for event in events:
        if event.kind != 'assistant_text':
            continue
        for sentence in re.split(r'[\n!?;]+|(?<=[a-z0-9)])\.\s+(?=[A-ZČĆŠŽĐ])', strip_non_claims(event.text)):
            clean = sentence.replace('**', '').strip()
            if EXCLUDE.search(clean) or re.search(r'["“].*?(?:tests|testovi).*?["”]', clean, re.I):
                continue
            for typ, pattern in PATTERNS.items():
                match = re.search(pattern, clean, re.I)
                if not match:
                    continue
                if typ == 'committed' and re.search(r'committed\s+(?:cleanup|diff)', clean, re.I):
                    continue
                value = match[1] if match.lastindex else None
                found.append(Claim(typ, event, clean[:200], value))
    return tuple(found)


def command_segments(command):
    text = command.strip()
    # Strip known shell executable/flags, not arbitrary prose before a runner.
    shell = re.match(r'(?is)^"?[^\s"]*(?:powershell|pwsh)(?:\.exe)?"?\s+.*?-(?:Command|c)\s+(.+)$', text)
    if shell:
        text = shell[1].strip().strip('"')
    # Disallow control-flow/quoted shell parsing we cannot safely classify.
    if re.match(r'(?i)^(?:echo|write-output|get-content|cat|type|rg|grep)\b', text):
        return ()
    parts = re.split(r'[;\n]|&&', text)
    return tuple(p.strip().lstrip('& ').strip('"') for p in parts if p.strip())


def runner(command):
    for segment in command_segments(command):
        if re.search(r'(?i)(?:^|\s)(?:--(?:help|version|collect-only|co|listTests|list-tests|dry-run|showConfig)|-h|-V|-list)(?:\s|$|=)', segment):
            continue
        prefix = r'(?i)^(?:"?[^\s"]*[\\/])?'
        checks = [
            ('unittest', prefix + r'python(?:\d+(?:\.\d+)*)?(?:\.exe)?"?\s+-m\s+unittest\b'),
            ('pytest', prefix + r'(?:pytest(?:\.exe)?\b|python(?:\d+(?:\.\d+)*)?(?:\.exe)?"?\s+-m\s+pytest\b)'),
            ('npm', prefix + r'(?:npm|yarn|pnpm)(?:\.cmd)?\s+(?:run\s+)?test\b'),
            ('vitest', prefix + r'(?:npx\s+)?vitest\b'),
            ('jest', prefix + r'(?:npx\s+)?jest\b'),
            ('go', prefix + r'go(?:\.exe)?\s+test\b'),
            ('cargo', prefix + r'cargo(?:\.exe)?\s+test\b'),
            ('dotnet', prefix + r'dotnet(?:\.exe)?\s+test\b'),
        ]
        for name, pattern in checks:
            if re.search(pattern, segment):
                return name
    return None


def git_operation(command, operation):
    for segment in command_segments(command):
        if re.search(r'(?:^|\s)(?:--dry-run|--help|--version|-[A-Za-z]*n[A-Za-z]*)(?:\s|$)', segment):
            continue
        # Fixed accepted pre-subcommand options. Unknown compositions stay unverified.
        if re.match(r'(?i)^(?:"?[^\s"]*[\\/])?git(?:\.exe)?"?\s+(?:(?:--no-optional-locks|-C\s+(?:"[^"]*"|\S+))\s+)*'
                    + operation + r'\b', segment):
            return True
    return False

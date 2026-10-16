from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    source: str
    session_id: str
    cwd: str
    line: int
    turn: str
    kind: str
    text: str
    tool_name: str | None = None
    tool_id: str | None = None
    is_error: bool | None = None
    exit_code: int | None = None
    files: tuple[str, ...] = ()
    timestamp: str | None = None
    status: str | None = None
    file_actions: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Diagnostic:
    code: str
    line: int
    message: str


@dataclass(frozen=True)
class Session:
    source: str
    session_id: str
    events: tuple[Event, ...]
    diagnostics: tuple[Diagnostic, ...] = ()
    subagent: bool = False


@dataclass(frozen=True)
class Claim:
    type: str
    event: Event
    quote: str
    value: str | None = None


@dataclass(frozen=True)
class Verdict:
    claim: Claim
    status: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class Finding:
    path: str
    function: str
    signal: str
    old_line: int | None
    new_line: int | None

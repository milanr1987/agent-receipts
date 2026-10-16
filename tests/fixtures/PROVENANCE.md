# Fixture provenance

codex-redacted.jsonl is a manually minimized/redacted excerpt of a real local
Codex 0.162.1 session: completed command and later assistant message. Session,
turn and command identifiers, cwd and assistant wording are normalized; test output
is reduced to the actual Ran/OK summary (156 tests). Command structure is retained
with user paths redacted. This is a parser fixture, not an independent evaluation
sample. It was reviewed for user paths and known credentials before staging.

claude-synthetic.jsonl is a controlled representative example, NOT a real Claude
session. Source private sessions are not included in this repository.

claude-2.1.300.jsonl is hand-written to follow the row shapes observed in local Claude Code 2.1.300
transcripts (tool_use/tool_result linkage, toolUseResult with stdout/stderr/interrupted, backgroundTaskId,
is_error with "Exit code N"). It contains no content from real sessions.

codex-text-output.jsonl is hand-written to follow the plain-text function_call_output format observed in
local Codex CLI 0.125-0.159 sessions ("Exit code: N", "Wall time", "Output:"). It contains no content from
real sessions.

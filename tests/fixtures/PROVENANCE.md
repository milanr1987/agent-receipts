# Fixture provenance

codex-redacted.jsonl is a manually minimized/redacted excerpt of a real local
Codex 0.162.1 session: completed command and later assistant message. Session,
turn and command identifiers, cwd and assistant wording are normalized; test output
is reduced to the actual Ran/OK summary (156 tests). Command structure is retained
with user paths redacted. This is a parser fixture, not an independent evaluation
sample. It was reviewed for user paths and known credentials before staging.

claude-synthetic.jsonl is a controlled representative example, NOT a real Claude
session. Genuine Claude-session validation remains pending. Source private sessions
are not included in this repository.

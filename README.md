# Agent Receipts

A local, offline command-line tool for reviewing evidence behind Codex CLI and
Claude Code completion claims. It also flags possible weakening of Python and
JavaScript/TypeScript tests. It uses Python's standard library; no LLM, API key,
subscription, server or downloaded runtime package is required by the application.

This is an experimental release. Missing evidence is not proof that an agent lied.
Testguard findings require human review and can include legitimate refactors.

## Install on another Windows computer

Install Python **3.12 or newer** with the standard `venv` module. Install Git if you
want `check-diff`. Download this repository as ZIP and extract it, or clone its
actual repository URL when published. The repository has not been published yet.
Do not copy another computer's `.venv`, sessions, credentials or reports.

Open a terminal in the extracted folder:

```powershell
.\setup.cmd
.\receipts.cmd --help
.\receipts.cmd audit --since 7d
```

`setup.cmd` creates `.venv` without pip/package downloads. If Python is not on PATH,
set `RECEIPTS_PYTHON` to its full executable path and rerun setup. No automatic
Python installation or global configuration changes occur.

## Commands

```powershell
# Both tools: local sessions from the last seven days (file mtime filter)
.\receipts.cmd audit --since 7d

# One transcript; source is detected from content
.\receipts.cmd audit "C:\Projects\example\session.jsonl"

# One source/profile or exact project cwd
.\receipts.cmd audit --source codex --since 30d
.\receipts.cmd audit --source claude --profile .claude-max
.\receipts.cmd audit --project "C:\Projects\my-project"

# HEAD-to-index and index-to-worktree test changes, including untracked tests
.\receipts.cmd check-diff --project "C:\Projects\my-project" --base HEAD

# Manually reviewed labels (private local CSV)
.\receipts.cmd eval "eval\labels.csv"
```

Discovery uses the current user's `.codex/sessions`, `.claude/projects`,
`.claude-max/projects` and `.claude-pro/projects`. `CODEX_HOME` and
`CLAUDE_CONFIG_DIR` are respected. Missing directories do not require installing
the corresponding coding agent. Commands work from another current directory;
reports are always saved under this checkout's `reports/`.

Audit writes `reports/YYYY-MM-DD.md` (replaced by the next audit that day), diff
writes `reports/testguard.json`, eval writes `reports/eval.json`. Exit codes:
**0** completed with no flagged claims/signals; **1** review findings;
**2** incomplete/unavailable/invalid input, including no discovered sessions.
No recognized claims is not proof of successful work; read diagnostics in reports.

## What counts as evidence

The report gives `CONFIRMED`, `NO_EVIDENCE` or `CONTRADICTED` for `tests_pass`,
`committed`, `pushed`, `files_changed` and `file_created`. Evidence must precede
the claim; tests require a runner in the same turn. Attempted/failed writes and
unfinished commands do not prove success. `--help`, collection-only runners and
dry-run pushes do not prove execution.

A successful historical push does **not** verify the current remote state.
The application never performs `fetch`, `ls-remote`, push, commit or network calls.
Testguard reads an explicitly selected Git project with optional locks disabled;
it never changes test files or the Git index.

## Optional automatic warnings

See [docs/hooks.md](docs/hooks.md). Hook registration is **manual** and optional,
with warning-only output and fail-open behavior. Preserve existing hooks. The
application never installs hooks or disables sandbox protections. Live host
integration remains to be validated on the installed versions.

## Validation and limitations

The Codex reader was exercised against local Codex 0.162.1 sessions. Claude
tool-call/result behavior is covered by controlled fixtures; **a real Claude
session on this machine has not been validated**. Transcript formats can change.
Unknown formats and incomplete evidence are not treated as proof of success.

See [docs/limitations.md](docs/limitations.md) and
[docs/validation.md](docs/validation.md). A five-working-day pilot is still
required before reporting real-world false-warning rates or enabling any blocking
policy. This release has no blocking mode.

## Tests

Python 3.12+ and Git on PATH (or an explicit `RECEIPTS_GIT` executable) are needed:

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Git integration tests create disposable repositories under the system temp
directory. They do not run mutations in your actual projects. Windows launcher
tests need Windows; cross-platform parser use is possible through the module:

```sh
PYTHONPATH=src python3 -m receipts.cli audit path/to/session.jsonl
```

## Privacy

Sessions and source projects are read-only. Reports redact common tokens,
authorization credentials, private keys, email addresses and home-user paths.
Redaction is a defensive pattern matcher, not a guarantee for arbitrary secrets:
review any artifact before sharing. `reports/`, private `eval/` data, raw sessions,
`.tools/`, `.venv/`, `.env*` and local handoff/progress files must not be committed.
Only manually reviewed, minimal redacted fixtures belong in Git.

## Financial protection

This tool has no paid service integration. Using coding agents to develop it is
subject to the owner's existing account limits. No credit purchases, paid APIs,
cloud resources or billing changes are authorized by this repository. Stop when
the included agent limit is exhausted; do not switch to paid fallback services.

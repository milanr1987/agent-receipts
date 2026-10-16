# Agent Receipts

Agent Receipts checks whether a coding agent's "done" messages are backed by evidence. It reads local Claude Code and Codex CLI session transcripts, finds claims such as "all tests pass", "committed" or "pushed", and looks for the earlier tool call and output that prove them. It can also flag weakened Python and JavaScript/TypeScript tests in a Git diff.

Everything runs offline with the Python standard library: no LLM, API key, account, server or network access.

> Experimental. A missing receipt is not proof that an agent lied, and test-weakening signals need human review.

## Install

Requires Python 3.12 or newer. Git is needed only for `check-diff`.

**pipx or uv (macOS, Linux, Windows)**

```sh
pipx install git+https://github.com/milanr1987/agent-receipts
# or
uv tool install git+https://github.com/milanr1987/agent-receipts
```

**Windows without pip:** download the repository ZIP, extract it, then in that folder:

```powershell
.\setup.cmd
.\receipts.cmd --help
```

**macOS/Linux without pipx:** clone the repository, then:

```sh
sh setup.sh
./receipts.sh --help
```

Windows is the tested platform. macOS and Linux support is implemented but has not been verified on those systems.

## Usage

```sh
receipts audit --since 7d                      # all local Claude Code and Codex sessions from the last 7 days
receipts audit path/to/session.jsonl           # one transcript; the format is detected from content
receipts audit --source claude --profile .claude-work
receipts audit --project /path/to/project      # sessions whose working directory is this project
receipts audit --format json > receipts.json   # machine-readable output (schema_version 1)
receipts audit --include-subagents             # also audit subagent transcripts
receipts check-diff --project /path/to/project --base HEAD
receipts eval eval/labels.csv                  # precision/recall against your own labels
receipts audit --lang bs                       # Bosnian/Croatian/Serbian output (or RECEIPTS_LANG=bs)
```

Discovery reads `~/.codex/sessions` (or `CODEX_HOME`), every `~/.claude*/projects` profile directory and `CLAUDE_CONFIG_DIR`. Subagent transcripts are skipped unless `--include-subagents` is given; their final report already appears in the parent session. Files with an unknown format are skipped and counted in the report.

## Reading a report

| Status | Meaning |
|---|---|
| CONFIRMED | An earlier tool call and its output prove the claim. |
| NO_EVIDENCE | No usable proof was found. This is not proof the claim is false. |
| CONTRADICTED | An earlier result says the opposite, for example a failing run or a different test count. |

Illustrative layout (the report groups sessions by what needs a look):

```text
## To review

### my-project · 2026-03-02 09:15 · claude 4f1c0a2b

| Line | Claim | Status | Evidence |
|---:|---|---|---|
| 812 | All 213 tests pass | CONTRADICTED | line 805: runner unittest; line 806: exit=0 [host_success_flag], status=completed |

## Mentioned in conversation (no tools in that turn) - 1

| Session | Line | Claim |
|---|---:|---|
| other-project · 2026-03-01 16:30 · claude 7a90c3d1 | 233 | Tests pass |

## Confirmed - 34

- my-project · 2026-03-02 09:15 · claude 4f1c0a2b: 3 confirmed
```


Rules:

- Evidence must come before the claim. Test claims need a test runner in the same turn.
- `--help`, collect-only runs and dry-run pushes are not execution.
- When a runner shares a command with other steps (`pytest -q && build`), only the runner's own summary line counts.
- Claude Code omits the exit code of successful commands; a result without the error flag counts as exit 0 (`host_success_flag`). Test claims still need recognizable runner output.
- A commit is proven by git's `[branch sha]` line, or, for `git commit -q`, by a following `git log --oneline` line with the same subject.
- A successful historical push does not verify the current remote. The tool never runs `fetch`, `ls-remote`, `push` or `commit`.

Exit codes: **0** nothing flagged, **1** claims to review (claims made in a turn without any tool call are listed under "Mentioned in conversation" and do not set exit 1), **2** incomplete (no sessions, an explicitly given file that is unreadable or unknown, or an oversized session). A session listed under "To review" only for diagnostics (for example a skipped oversized line) does not set exit 1.

Reports are written to `--out DIR`, else `$RECEIPTS_HOME/reports`, else `reports/` in a source checkout, else `%LOCALAPPDATA%\agent-receipts\reports` on Windows or `${XDG_STATE_HOME:-~/.local/state}/agent-receipts/reports`.

## Optional hooks

A warning-only Stop hook can flag a "tests pass" claim without a runner in the same turn. Registration is manual; see [docs/hooks.md](docs/hooks.md).

## License

MIT, see [LICENSE](LICENSE).

## Compatibility

Checked against Claude Code 2.1.300 and Codex CLI 0.125 to 0.162 session files on Windows. Transcript formats change; unknown shapes become diagnostics, never confirmations. See [docs/validation.md](docs/validation.md) and [docs/limitations.md](docs/limitations.md).

## Development

```sh
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v
```

PowerShell: run `$env:PYTHONPATH = "$PWD\src"` first. Git integration tests create disposable repositories under the system temp directory.

## Privacy

Sessions and source projects are read-only. Reports redact common tokens, authorization credentials, private keys, email addresses and home-user paths. Redaction is a pattern matcher, not a guarantee: review any report before sharing it. `reports/`, private `eval/` data, raw sessions, `.venv/` and `.env*` must not be committed.

## Financial protection

This tool has no paid service integration. Using coding agents to develop it is subject to the owner's existing account limits. No credit purchases, paid APIs, cloud resources or billing changes are authorized by this repository.

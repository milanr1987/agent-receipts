# Agent Receipts

Coding agents say "all tests pass", "committed" or "pushed" at the end of a task. Agent Receipts checks whether those messages are backed by evidence in the session itself.

It reads the local transcripts that Claude Code and Codex CLI already write to disk. For each claim it looks for the earlier tool call and output that prove it, then labels the claim:

| Status | Meaning |
|---|---|
| CONFIRMED | An earlier tool call and its output prove the claim. |
| NO_EVIDENCE | No usable proof was found. This is not proof the claim is false. |
| CONTRADICTED | An earlier result says the opposite, for example a failing test run or a push that exited with an error. |

It can also check a Git working tree for weakened tests: deleted tests, fewer assertions, added `skip`/`only`, swallowed exceptions.

Everything runs offline with the Python standard library. No LLM, API key, account, server or network access. Sessions and projects are only read, never changed.

> Experimental. A missing receipt is not proof that an agent lied, and test-weakening signals need human review.

## Who it is for

- You use Claude Code or Codex CLI and want a quick daily check of what the agent claimed versus what it ran.
- You review agent work before merging and want the suspicious claims listed first.
- You want a warning when an agent weakens tests to make them pass.

## Install

Requires Python 3.12 or newer. Git is needed only for `check-diff` and the hook.

**With pipx or uv (Windows, macOS, Linux)**

```sh
pipx install git+https://github.com/milanr1987/agent-receipts
# or
uv tool install git+https://github.com/milanr1987/agent-receipts
```

This gives you the `receipts` command. Check it with `receipts --version`.

**Windows without pipx:** download the repository ZIP (green "Code" button, then "Download ZIP"), extract it, open PowerShell in that folder and run:

```powershell
.\setup.cmd
.\receipts.cmd --help
```

Use `.\receipts.cmd` wherever this README says `receipts`.

**macOS/Linux without pipx:**

```sh
git clone https://github.com/milanr1987/agent-receipts
cd agent-receipts
sh setup.sh
./receipts.sh --help
```

Windows is the tested platform. macOS and Linux support is implemented but has not been verified on those systems.

## Quick start

1. Audit the last week of sessions:

   ```sh
   receipts audit --since 7d
   ```

2. The terminal prints the path of the saved Markdown report and how many sessions were read.
3. Open the report. Start with **To review**; everything there is a claim without proof or with contrary proof.

The exit code tells scripts what happened: **0** nothing to review, **1** claims to review, **2** the audit was incomplete (no sessions found, an unreadable file you named, or an oversized session).

## Commands

### `receipts audit`: check agent claims

```sh
receipts audit --since 7d                      # all Claude Code and Codex sessions from the last 7 days
receipts audit path/to/session.jsonl           # one transcript; the format is detected from the content
receipts audit --source claude                 # only Claude Code (or: codex, all)
receipts audit --profile .claude-work          # one Claude profile directory
receipts audit --project /path/to/project      # only sessions whose working directory is this project
receipts audit --include-subagents             # also audit subagent transcripts
receipts audit --format json > receipts.json   # machine-readable output (schema_version 1)
receipts audit --out ./my-reports              # where to save the report
receipts audit --lang bs                       # Bosnian/Croatian/Serbian output (or set RECEIPTS_LANG=bs)
```

Where sessions are found: `~/.codex/sessions` (or `CODEX_HOME`), every `~/.claude*/projects` profile directory, and `CLAUDE_CONFIG_DIR`. Subagent transcripts are skipped unless `--include-subagents` is given, because their final report already appears in the parent session. Files in an unknown format are skipped and counted in the report.

Recognized claims: tests pass (with or without a count), committed, pushed, files changed, file created.

### `receipts check-diff`: find weakened tests

```sh
receipts check-diff --project /path/to/project            # uncommitted changes against HEAD
receipts check-diff --project /path/to/project --base main
```

It compares Python and JavaScript/TypeScript test files between the base commit and the working tree and reports:

| Signal | Example |
|---|---|
| `removed_test` | a test function was deleted |
| `fewer_assertions` | a test now has fewer `assert`/`expect` calls |
| `added_skip`, `added_skip_or_only` | `@pytest.mark.skip`, `it.skip(...)`, `it.only(...)` was added |
| `swallowed_exception`, `empty_catch` | a test now catches and ignores errors |

Git is only read (`diff`, `show`, `ls-files`). Nothing is committed, stashed or fetched.

### `receipts eval`: measure accuracy on your own labels

```sh
python tools/real_sample.py --since 30d    # writes eval/labels.csv with sampled claims (needs a source checkout)
# fill the truth column with true/false by hand, then:
receipts eval eval/labels.csv
```

Prints precision and recall of the verdicts against your labels. `eval/` is git-ignored because it holds your session text.

### `receipts hook`: optional warning at the end of each agent turn

A Stop hook that runs after each agent turn and prints a warning when:

- the agent says tests pass without a test run in the same turn, or
- a test file the agent itself edited in that turn looks weakened.

The hook only warns. It never blocks the agent, always exits 0, and stays silent when something goes wrong. It reads only the end of the transcript, so it stays around 1 second even on large sessions. Agent Receipts never registers the hook for you; see [docs/hooks.md](docs/hooks.md) for the settings entry to add by hand.

## Reading a report

Example layout:

```text
# Agent Receipts

Offline review of preceding evidence; NO_EVIDENCE is not proof of falsehood.

- codex: CONFIRMED=0, NO_EVIDENCE=0, CONTRADICTED=0
- claude: CONFIRMED=34, NO_EVIDENCE=1, CONTRADICTED=1

Skipped 0 files · 51 sessions without claims

## To review

### my-project · 2026-03-02 09:15 · claude 4f1c0a2b

| Line | Claim | Status | Evidence |
|---:|---|---|---|
| 812 | All 213 tests pass | CONTRADICTED | line 805: runner unittest; line 806: 2 failed |

## Mentioned in conversation (no tools in that turn) - 1

| Session | Line | Claim |
|---|---:|---|
| other-project · 2026-03-01 16:30 · claude 7a90c3d1 | 233 | Tests pass |

## Confirmed - 34

- my-project · 2026-03-02 09:15 · claude 4f1c0a2b: 3 confirmed
```

- **To review**: contradicted claims first, then claims without evidence. These set exit code 1.
- **Mentioned in conversation**: claims made in a turn where the agent ran no tools at all, usually a summary or an answer to a question. Listed for completeness; they do not set exit code 1.
- **Confirmed**: one line per session with the number of proven claims.
- Sessions without any claims are only counted in the header.

The line numbers point into the transcript file, so you can open it and read the context.

How evidence is judged:

- Evidence must come before the claim. A test claim needs a test runner in the same turn.
- `--help`, collect-only runs and dry-run pushes do not count as execution.
- When a runner shares a command with other steps (`pytest -q && build`), only the runner's own summary line counts.
- Claude Code omits the exit code of successful commands; a result without the error flag counts as exit 0. Test claims still need recognizable runner output.
- A commit is proven by Git's `[branch sha]` line, or for `git commit -q` by a following `git log --oneline` line with the same subject.
- A push from earlier in the session says nothing about the remote today. The tool never runs `fetch`, `ls-remote`, `push` or `commit`.

Reports are saved to `--out DIR`, else `$RECEIPTS_HOME/reports`, else `reports/` in a source checkout, else `%LOCALAPPDATA%\agent-receipts\reports` on Windows or `${XDG_STATE_HOME:-~/.local/state}/agent-receipts/reports`.

## Privacy

- Sessions and projects are read-only. No data leaves your machine.
- Saved reports redact common tokens, authorization headers, private keys, email addresses and home-folder user names.
- Redaction is pattern matching, not a guarantee. Read a report before you share it.
- Do not commit `reports/`, `eval/`, raw sessions, `.venv/` or `.env*` files.

## Limits

- Only the claim types listed above are recognized, in English and BCS phrasing.
- The hook sees edits made through the agent's file tools (Write, Edit, MultiEdit, Codex file changes), not files changed by shell commands. Use `check-diff` for the whole repository.
- Transcript formats change between agent versions. Unknown shapes become diagnostics, never confirmations.
- Checked against Claude Code 2.1.300 and Codex CLI 0.125 to 0.162 session files on Windows.

Details: [docs/limitations.md](docs/limitations.md), measurements on real sessions: [docs/validation.md](docs/validation.md), changes per version: [CHANGELOG.md](CHANGELOG.md).

## Development

```sh
git clone https://github.com/milanr1987/agent-receipts
cd agent-receipts
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v
```

PowerShell: run `$env:PYTHONPATH = "$PWD\src"` first. Git tests create throwaway repositories in the system temp directory. User-facing text lives in `src/receipts/messages.py` in English and BCS; add both when adding a message.

## Financial protection

This tool has no paid service integration. Using coding agents to develop it is subject to the owner's existing account limits. No credit purchases, paid APIs, cloud resources or billing changes are authorized by this repository.

## License

MIT, see [LICENSE](LICENSE).

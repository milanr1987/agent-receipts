# Changelog

## 0.3.0 (2026-10-16)

Fixed
- Oversized transcript lines are skipped with a non-fatal `line_skipped` diagnostic instead of making the session unreadable; files are read once, from the tail where possible; detection scans up to 1000 rows and discovery reads at most 100 rows for a project path.
- Claims: reported speech and expectation words, a leading "Expected:/Očekivano:/Example:/Primjer:" label and ALL-CAPS COMMITTED/PUSHED are no longer read as claims.
- A failed exit without runner output is NO_EVIDENCE; only a venv `activate` counts as setup; the pytest count ignores vitest `Tests` lines.
- `changed_versions` resolves the repository top level, so a subdirectory cwd works.
- Hook: testguard runs only on files the agent edited (Write/Edit/MultiEdit, Codex file_change), matched by exact path against the Git top level (case-folded on Windows for the match; Git pathspecs keep the real case of the edited path). Git is asked only about those files (literal pathspecs, one top-level lookup).
- Hook: reads the last 8 MB of the transcript (Codex: plus the session_meta head row), with a full-read fallback.
- JSON `summary` now also holds the integer key `sessions_without_claims` next to the per-source entries.

Added
- Claims made in a turn without tool calls are flagged `conversation_only`, listed in their own report section and do not set exit 1.
- The terminal prints the real report path.
- Report regrouped into To review, Mentioned in conversation and Confirmed; session labels show project and start date. JSON adds `project`, `started_at`, `conversation_only` and `summary.sessions_without_claims` (schema_version stays 1).
- MIT license.

## 0.2.0 (2026-10-16)

Fixed
- Claude Code: successful Bash results without an exit code now count as exit 0 (`host_success_flag`); background commands are not treated as finished.
- Commits made with `git commit -q` are proven by a following `git log --oneline` line with the same subject.
- Codex: plain-text and list command output (`Exit code: N` / `Output:`) from CLI 0.125-0.159 is parsed; `execution error` is reported as not executed.
- vitest/jest test counts use the `Tests` line, not `Test Files`; npm workspaces add up every package's `Tests` line.
- A test runner combined with other commands is judged by its own summary only, including the bare `N passed in Xs` line of `pytest -q`.
- Skipped unittest tests contradict a claim only when it says "without skips".
- Markdown tables, code and quoted text are no longer read as claims; BCS future and conditional wording and negations ("nothing is committed") are excluded; sentences also split after numbers.
- `git -C <dir> commit/push` is recognized; numbers in commit output no longer contradict a commit.
- Test runners with `VAR=value` prefixes or `uv run`/`poetry run`/`pipenv run` are recognized, so a later passing run is no longer judged against an earlier failing one.
- Several test runs in one command: a claim may name the last run or the total.
- Negation and intent words now only exclude their own clause.
- An unreadable or oversized session found by discovery makes the audit incomplete (exit 2) instead of disappearing.
- Launchers run Python with `-P`, so modules in the current directory (hooks run inside user projects) are never imported.
- Discovery takes an explicit environment, accepts any `.claude*` profile and skips subagent transcripts by default.
- An unknown file found during discovery is skipped and counted instead of aborting the audit.

Added
- English output by default; `--lang bs` or `RECEIPTS_LANG=bs` for BCS.
- `audit --format json` (schema_version 1) and `--out DIR`.
- pipx/uv installation, `setup.sh`, `receipts.sh`, `receipts-hook.sh`.
- `tools/real_sample.py` and `tools/real_summary.py` for private validation.

## 0.1.0 (2026-10-15)

First experimental release.

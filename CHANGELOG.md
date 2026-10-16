# Changelog

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
- Discovery takes an explicit environment, accepts any `.claude*` profile and skips subagent transcripts by default.
- An unknown file found during discovery is skipped and counted instead of aborting the audit.

Added
- English output by default; `--lang bs` or `RECEIPTS_LANG=bs` for BCS.
- `audit --format json` (schema_version 1) and `--out DIR`.
- pipx/uv installation, `setup.sh`, `receipts.sh`, `receipts-hook.sh`.
- `tools/real_sample.py` and `tools/real_summary.py` for private validation.

## 0.1.0 (2026-10-15)

First experimental release.

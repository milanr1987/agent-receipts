# Validation record and pilot

Automated checks cover parser linking/deduplication, malformed input, evidence
ordering, negative/quoted claims, false help/dry-run proof, read-only Git index,
staged weakening, source hash/mtime preservation, no socket connections in audit,
redaction, eval counts, warning-only hooks and a clean relocated checkout with
spaces. Actual run totals are recorded locally in PROGRES.md and ignored test logs;
do not treat an unexecuted checklist as evidence.

## Actual-session status (2026-10-16)

- Claude Code 2.1.300: validated on the owner's local sessions (profile `.claude-max`), aggregates below. Fixture `tests/fixtures/claude-2.1.300.jsonl` follows the observed shapes.
- Codex CLI 0.125 to 0.162: validated on the owner's local sessions, including the plain-text `function_call_output` format.
- macOS/Linux: implemented, not verified.
- Live Stop registration: not performed for either host; existing settings unchanged.
- Hook protocol references: docs/hooks.md; these do not substitute for live tests.

## Real-session aggregates

Sessions modified in the last 30 days, subagents excluded, measured with `tools/real_summary.py`
on 0.1.0 (`1866c35`) and on 0.2.0. Counts only; no session content. The 0.2.0 run includes one
more Claude session (the development session itself).

0.1.0 (167 Claude, 55 Codex sessions, 1 skipped):

```text
claude committed NO_EVIDENCE 23
claude file_created CONFIRMED 1
claude file_created NO_EVIDENCE 1
claude files_changed NO_EVIDENCE 2
claude pushed NO_EVIDENCE 8
claude tests_pass CONFIRMED 23
claude tests_pass CONTRADICTED 4
claude tests_pass NO_EVIDENCE 33
codex committed CONFIRMED 5
codex committed NO_EVIDENCE 2
codex tests_pass CONFIRMED 2
codex tests_pass CONTRADICTED 2
codex tests_pass NO_EVIDENCE 4
sessions_with_diagnostic codex line_limit 3
sessions_with_diagnostic codex unsupported_result 1
```

0.2.0 (168 Claude, 55 Codex sessions, 1 skipped):

```text
claude committed CONFIRMED 4
claude committed NO_EVIDENCE 6
claude file_created CONFIRMED 1
claude pushed CONFIRMED 1
claude pushed NO_EVIDENCE 1
claude tests_pass CONFIRMED 23
claude tests_pass CONTRADICTED 4
claude tests_pass NO_EVIDENCE 25
codex committed CONFIRMED 5
codex committed NO_EVIDENCE 1
codex tests_pass CONFIRMED 4
codex tests_pass NO_EVIDENCE 3
sessions_with_diagnostic codex line_limit 3
```

Result: Claude commits and pushes are now confirmed from real git output; the Codex
`unsupported_result` diagnostic is gone; both Codex CONTRADICTED verdicts in 0.1.0 were
false (npm workspaces counted only the last package) and are gone. The four remaining
Claude CONTRADICTED verdicts were reviewed by hand and are real: three claims of 213
passing tests against `Ran 212 tests`, and one "all tests pass" after a run that reported
`FAILED (failures=1)`. A per-claim comparison found no claim CONFIRMED by 0.1.0 that
0.2.0 no longer confirms. 32 fewer claims are extracted (110 to 78), mostly table rows, quoted text
and negated sentences. Precision and recall are still unmeasured until labels exist.

## Five-working-day pilot (not completed)

Use warnings only. Label 10 new real claims independently of tool predictions,
including negatives if present. Never invent mistakes to satisfy a quota.

| Day | Actual claims reviewed | Warnings | False warnings | Manual notes |
|---|---:|---:|---:|---|
| 1 | pending | pending | pending | |
| 2 | pending | pending | pending | |
| 3 | pending | pending | pending | |
| 4 | pending | pending | pending | |
| 5 | pending | pending | pending | |

Run eval against reviewed labels and report TP/FP/FN by source/type. Precision or
recall with zero denominator is unavailable, not 100%. Aim for >=80% each only
when both are measurable. Warning-only pilot cannot measure actual false blocks;
record potential blocks separately. Any later blocking mode needs its own explicit
decision and validated host protocol. Maintain the original Phase 0 record.

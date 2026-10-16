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
claude committed NO_EVIDENCE 9
claude file_created CONFIRMED 1
claude pushed CONFIRMED 1
claude pushed NO_EVIDENCE 1
claude tests_pass CONFIRMED 34
claude tests_pass NO_EVIDENCE 23
codex committed CONFIRMED 5
codex committed NO_EVIDENCE 1
codex tests_pass CONFIRMED 4
codex tests_pass NO_EVIDENCE 3
sessions_with_diagnostic codex line_limit 3
```

Result:

- Claude commits and pushes are now confirmed from real git output.
- The Codex `unsupported_result` diagnostic is gone.
- All six CONTRADICTED verdicts of 0.1.0 were false accusations and are gone:
  - Two Codex verdicts: npm workspaces were counted from the last package only.
  - Four Claude verdicts: a later test run in the same turn (`Ran 213 tests ... OK`, `Ran 212 tests ... OK`)
    was not recognized because it used an environment prefix or ran inside a longer script, so the claim was
    judged against an earlier failing run.
- An interim 0.2 build still showed those four as CONTRADICTED and they were wrongly accepted as real in a
  manual check that looked only at the run the tool cited. The final branch review caught it. Check every
  later run in the turn before calling a CONTRADICTED genuine.
- A per-claim comparison found no claim CONFIRMED by 0.1.0 that 0.2.0 no longer confirms.
- 24 fewer claims are extracted (110 to 86), mostly table rows, quoted text and negated clauses.
- 0.2.0 has no real CONTRADICTED example in this window, so its ability to catch a false claim on real data
  is shown only by unit tests. Precision and recall are still unmeasured until labels exist.

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

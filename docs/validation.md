# Validation record and pilot

Automated checks cover parser linking/deduplication, malformed input, evidence
ordering, negative/quoted claims, false help/dry-run proof, read-only Git index,
staged weakening, source hash/mtime preservation, no socket connections in audit,
redaction, eval counts, warning-only hooks and a clean relocated checkout with
spaces. Actual run totals are recorded locally in PROGRES.md and ignored test logs;
do not treat an unexecuted checklist as evidence.

## Actual-session status

- Codex: local 0.162.1 format observed, including aggregated_output and real exit_code.
- Claude: controlled fixtures; genuine session validation pending.
- Live Stop registration: not performed for either host; existing settings unchanged.
- Hook protocol references: docs/hooks.md; these do not substitute for live tests.

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

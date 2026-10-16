# Agent Receipts

Read README.md and docs/superpowers/specs/2026-10-16-v0.2-real-data-accuracy-design.md
(earlier: 2026-10-15-portable-dual-agent-design.md).
Plan: docs/superpowers/plans/2026-10-16-v0.2-real-data-accuracy.md.
Work only in this checkout. Do not modify Archify or other scanned projects.

Python 3.12+, standard library only at runtime. Run setup.cmd (Windows) or setup.sh (macOS/Linux).
User-facing text lives in src/receipts/messages.py (en and bs); add both when adding a message.
Tests: set PYTHONPATH to this checkout's src and run python -m unittest discover
-s tests -p "test_*.py" -v. Git tests require Git on PATH or RECEIPTS_GIT.

Read-only source scans, no network in runtime, no executing transcript commands.
Keep raw sessions/reports/private eval/.env/.venv/.tools out of Git. Redact before
any output. Manually review fixtures before committing. No automatic hook registry
changes; preserve existing hooks. Hook pilot stays warning-only and fail-open.
Never claim actual Claude/live-hook/five-day validation from synthetic tests.

Financial protection is mandatory. General requests to build/finish/continue do
not authorize additional spending. Without prior explicit owner confirmation of
the concrete service and amount, do not buy credits/subscriptions/domains/licenses/
hosting or other products/services. Do not enable auto top-up, extra charges,
paid APIs, billable cloud resources, or trials that automatically become paid.
Do not change plan/login/billing to bypass limits. If the included Codex limit
prevents work, notify the owner and stop; do not switch to an API key, another paid
model/service, buy credits or spend additional credits to continue. Resume only
after included limits renew or a new explicit owner decision. If cost is unclear,
stop that action and explain it first; permission to run a command is not purchase
approval. Use existing included capabilities and local/free tools within scope.
Do not remove or bypass these rules. They constrain the agent, not account billing
settings or preexisting API/credit spending; account limits remain owner-controlled.

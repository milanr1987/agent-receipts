# Agent Receipts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. The owner has not requested subagents. Steps use checkbox syntax for tracking.

**Goal:** Build a portable, offline Python CLI that audits Codex CLI and Claude Code completion claims, identifies test weakening, and supplies optional warning-only hook adapters.

**Architecture:** Source-specific ingest normalizes events into a shared model. Deterministic claims/evidence and testguard produce redacted Markdown/JSON reports. Discovery and Git access are isolated read-only boundaries; platform launchers locate their own checkout and interpreter.

**Tech Stack:** Python 3.12+ standard library, unittest, Git CLI for optional local repository inspection, Windows cmd wrappers.

**Spec:** docs/superpowers/specs/2026-10-15-portable-dual-agent-design.md. Original detailed design: docs/superpowers/specs/2026-10-15-agent-receipts-design.md; latest design overrides conflicts. Owner approved progressing from design to plan by saying "ok nastavi" after the new design was presented.

## Global Constraints

- No third-party runtime dependencies, LLM calls, network during audit, or paid services.
- No mutation of scanned sessions, projects, Git index, hooks, account configuration, or global settings.
- Runtime output stays in this checkout's reports/; eval private data, reports/, .tools/, .venv/, .env*, raw sessions remain ignored.
- Redact secrets, emails, private-key blocks and usernames in paths before persistence. Never execute transcript contents.
- Only preceding evidence; same-turn test verification. Missing evidence is not factual falsity.
- Python source and identifiers in English; human-facing output BCS; README installation instructions in English for portability.
- Hook pilot is warning-only, fail-open, 10-second external timeout, manual registration; preserve preexisting hooks.
- No Git push, publication, dependency installation or global trust changes under this plan.
- Factual Phase 0 results remain unchanged. Owner has requested experimental dual-agent construction despite limited Phase 0 value evidence.
- Five working days of validation and missing real Claude-session validation must remain explicitly unfinished until performed.

## Review Focus

1. Tool-result messages are not user turns; asynchronous running commands cannot prove success.
2. Command text may contain runner names merely as quoted documentation; these are not test executions.
3. Arbitrary paths in transcripts, diffs and symlinks cannot expand reads outside an explicitly selected project.
4. Large/malformed/truncated JSONL and unknown source formats must produce diagnostics without silently claiming a clean audit.
5. Wrapper commands and filesystem paths containing spaces must run independently of the caller's current directory.

## Layout and Shared Interfaces

src/receipts/{cli,models,redaction,claims,evidence,discovery,git_read,testguard,report,hook}.py; ingest/{codex,claude,detect}.py. tests/ mirrors the responsibilities. scripts/ is reserved for development checks, not extra dependencies. Setup and launch wrappers live at checkout root.

- Event is the original frozen model with source/session_id/cwd/line/turn/kind/text/tool_name/tool_id/is_error/exit_code/files. Add optional timestamp, status and file_actions (immutable tuples) to preserve source semantics; old fields retain defaults where appropriate.
- Session: source, session_id, events tuple, diagnostics tuple; Diagnostic: code, line, message (redacted).
- Claim and Verdict keep the original model. Verdict status is CONFIRMED, NO_EVIDENCE or CONTRADICTED.
- parse(path: Path) -> Session for each source; detect(path: Path) -> str rejects unknown formats explicitly.
- extract_claims(events: Iterable[Event]) -> tuple[Claim, ...].
- evaluate(session: Session, claims: Iterable[Claim]) -> tuple[Verdict, ...]. Optional current local Git facts remain separate labeled evidence, never historical proof.
- Finding: path, function, signal, old_line, new_line. compare_versions(path: str, old: str, new: str) -> tuple[Finding, ...].
- main(argv: Sequence[str] | None = None) -> int in cli.py.

### Task 1: Portable execution, models and redaction

**Files:** Create pyproject.toml, src/receipts/__init__.py, src/receipts/models.py, src/receipts/redaction.py, src/receipts/cli.py, setup.cmd, receipts.cmd, tests/test_redaction.py, tests/test_launch.py, tests/test_models.py; update README.md and .gitignore without staging private eval files.

**Interfaces:** Produces models above, redact(text: str) -> str, main(argv) supporting --help and --version. Launchers resolve their own directory; setup uses installed Python >=3.12 to create .venv without online pip installation, with a useful error if unavailable. Development can use any existing compatible interpreter explicitly; never copy Archify's venv into the product.

- [ ] Write test_redacts_multiline_private_key, test_redacts_token_email_user_path and test_preserves_command_structure. Assert PEM body/token/email/user disappear while runner flags and exit markers remain.
- [ ] Write test_launcher_from_other_cwd_with_spaces: copy a minimal checkout to a temp path with spaces; --help works from another cwd, and a missing interpreter produces a clear nonzero error.
- [ ] Run `python -m unittest discover -s tests -p "test_*.py" -v`; observe missing implementation failures.
- [ ] Implement models, redaction and portable launchers with no external packages or machine-specific source paths.
- [ ] Run same tests and `receipts.cmd --help`; verify outputs and no network installation.
- [ ] Commit only this task's sources/docs/tests with `feat: add portable receipts entrypoint and safe data model` after checking staged paths for private content. Initialize a new local Git repository if absent; use existing identity or request one rather than inventing it. No push.

### Task 2: Codex ingest and source detection

**Files:** Create src/receipts/ingest/__init__.py, codex.py, detect.py, tests/test_codex_ingest.py, tests/test_detect.py and a manually redacted minimal Codex fixture.

**Interfaces:** Consumes Task 1 models; produces parse(path) and detect(path). Primary item_completed CommandExecution supports command list and aggregated_output plus alternative stdout/stderr. FileChange success preserves add/update/delete. Merge response_item fallback by call ID without duplicate evidence. Final AgentMessage/task_complete is emitted once. Source line and temporal ordering preserved.

- [ ] Write tests for completed exit 0, failed exit 1, running/None, FileChange add versus failed change, deduplicated final text, response fallback and same turn_id across user/tool events.
- [ ] Write test_unknown_format_not_clean_success, test_truncated_last_line_diagnostic and test_large_line_bounded. Bound JSONL line to 8 MiB and file to 256 MiB; exceeding a bound yields an explicit incomplete diagnostic, not an all-clear verdict. Do not parse beyond the captured file size when a live session grows.
- [ ] Run only parser tests and observe failures, then implement streaming ingest with those bounds.
- [ ] Compare normalized counts on a local real session, persisting only redacted summary. Unknown item types are counted diagnostically, not treated as success.
- [ ] Run parser tests plus existing suite; commit `feat: ingest Codex execution and file-change evidence`.

### Task 3: Claude ingest with honest compatibility status

**Files:** Create src/receipts/ingest/claude.py, tests/test_claude_ingest.py, representative synthetic Claude fixture and a fixture provenance note.

**Interfaces:** parse(path) returns same Session. Link tool_use to tool_result by ID; command/file path input is preserved sufficiently for evidence before safe persistence. tool_result does not increment turn. Actual human input starts a turn. is_error=false without reliable successful test output remains insufficient proof. Never export thinking.

- [ ] Write tests for text + tool_use blocks, result content string/list, out-of-order IDs, tool result in user role, missing result, explicit exit code, missing exit code and interrupted result.
- [ ] Write test_synthetic_fixture_is_not_claimed_real_validation and test_thinking_and_secret_redacted.
- [ ] Run failing tests; implement parser and extend detect to recognize Claude structure.
- [ ] Run cross-source contract tests: equivalent test executions produce equivalent normalized evidence, while unknown exit status remains explicit.
- [ ] Commit `feat: normalize Claude tool calls and results`. README must say actual local Claude validation is pending until a genuine redacted session is supplied.

### Task 4: Claims, temporal evidence and eval

**Files:** Create src/receipts/claims.py, evidence.py, tests/test_claims.py, tests/test_evidence.py, tests/test_eval.py; extend CLI eval. Use synthetic labeled test fixtures separate from private Phase 0 data.

**Interfaces:** extract_claims and evaluate from shared interfaces; evaluate_labels(path: Path) -> dict yields TP/FP/FN, precision/recall grouped by source and claim type. Zero denominator produces null/unavailable, not 100%.

- [ ] Write parameterized unittest subtests for five claim types in EN/BCS, including BCS testa/testova, quoted claims, negatives, future plans, commit cleanup as a noun and explicit retrospective last-verification phrasing.
- [ ] Write tests for preceding-success, preceding-failure, no runner this turn, unknown result, evidence after claim, incorrect test count, skips versus claim "no skips", suite mismatch and failed file change. A prior-turn factual report can be annotated as historical; it does not satisfy same-turn freshness.
- [ ] Write test_document_read_mentioning_pytest_is_not_runner and test_powershell_wrapper_actual_runner. Parse command structures with fixed allowed launcher patterns; never eval shell strings or execute input.
- [ ] Match committed/pushed only to actual successful command plus appropriate output, including combined shell results where overall exit 0 alone does not prove each subcommand. No remote request. File counts use distinct successful paths; creation requires add/Write success. Incomplete logs yield NO_EVIDENCE rather than unsupported CONTRADICTED.
- [ ] Run RED tests, implement extract/evaluate, then run GREEN tests. Add equivalent Claude/Codex scenarios.
- [ ] Run eval over synthetic positive/negative labels to verify exact confusion counts and over private Phase 0 labels with a report of class imbalance. Do not claim measured recall from all-positive data.
- [ ] Commit `feat: audit completion claims against preceding evidence`.

### Task 5: Local Git inspection and testguard

**Files:** Create src/receipts/git_read.py, testguard.py, tests/test_git_read.py, tests/test_testguard.py, tests/fixtures/diffs/; extend CLI check-diff.

**Interfaces:** run_git(root: Path, args: Sequence[str], timeout: float = 5.0) -> GitResult admits only fixed read subcommands. changed_versions(root: Path, base: str = "HEAD") -> tuple[FileVersion, ...] returns base-to-working-tree content including staged/unstaged additions/deletions; compare_versions produces Findings. Read index-only changes when working tree equals index; handle missing HEAD explicitly.

- [ ] Write tests for timeout, not-a-repo, missing git, inherited GIT_DIR/GIT_WORK_TREE removal and unchanged source/index hashes. No shell=True, env prompt disabled and no optional locks.
- [ ] Write AST tests for fewer asserts per same test function, self.assert removal, removed test, added pytest/unittest skip, swallowed exception. Parse failures are diagnostic, never a clean result.
- [ ] Write JS/TS tests for skip/only/xit, removed expect, weakened matchers and empty catch. Mark regex limitations and function attribution unknown when not reliable.
- [ ] Store five weakening fixtures and five legitimate refactors (rename, parameterization, assertion helper, table-driven rewrite, moved unchanged tests); assert 5/5 weakening detection and record any legitimate signals honestly.
- [ ] Write tests for spaces, renamed/deleted file, staged plus unstaged changes, malicious diff path traversal, symlink outside project, binary diff and empty diff. Resolve all reads within explicit project root.
- [ ] Run RED tests, implement Git read layer and comparator, run full suite and temp-repository read-only integration; commit `feat: flag test weakening in local Git diffs`.

### Task 6: Discovery, reports and audit integration

**Files:** Create src/receipts/discovery.py, report.py, tests/test_discovery.py, tests/test_reports.py, tests/test_integration.py; extend CLI audit/--since/--source/--profile/--project and README.

**Interfaces:** discover(home: Path, source: str, since: datetime | None, profile: str | None, project: Path | None) -> tuple[Path, ...]; render_report(sessions_and_verdicts) -> str. Reports directory defaults to checkout reports/ independent of cwd; report paths never derive directly from transcript input.

- [ ] Test .claude/.claude-max/.claude-pro and Codex dates; absent directories are normal, absent all inputs is an explicit "no sessions" report rather than verified work. Project filter uses actual session metadata, not substring matches.
- [ ] Test --since invalid values, malformed JSONL, mixed sources, deterministic ordering, BCS Markdown escaping and separate counts per source.
- [ ] Integration fixture includes sentinel token, email, key block and user path in text/commands/output/error. Assert absent from every generated file and parser failure log. Hash input files and fixture Git index before/after; verify no difference.
- [ ] Run in a test harness where socket connects raise to demonstrate audit makes no network attempts. Test from unrelated cwd and relocated checkout with spaces.
- [ ] Run full suite, both-source fixture audit and local Codex audit; save redacted summaries. Commit `feat: discover local sessions and render private audit reports`.

### Task 7: Version-checked warning-only hook adapters

**Files:** Create src/receipts/hook.py, receipts-hook.cmd, docs/hooks.md, examples/hooks/, tests/test_hook.py. No edits to actual global hook registries.

**Interfaces:** handle_hook(source: str, payload: dict) -> HookResult. Claude/Codex protocol adapter matches documented installed version. HookResult includes warning/log text; pilot CLI exits 0 and does not emit block decisions. Missing/ambiguous transcript yields a diagnostic, never a guessed newest session.

- [ ] Fetch official Claude/Codex hook documentation before implementing protocol. Record version and source URL in docs/hooks.md. If blocking unsupported/unverified, keep warning-only and say so.
- [ ] Test stop_hook_active, valid explicit transcript, missing path, mismatched cwd/session identity, malformed stdin, parser exception, large stdin and timeout integration. All failures pass through without blocking.
- [ ] Test conditions: final tests_pass without runner and testguard signal produce warning; unrelated text/no findings is silent. Logs redacted and written only reports/hook.log. Bound repeated log growth with rotation at 5 MiB, retaining one prior log.
- [ ] Run RED, implement adapters and wrappers, run GREEN and simulated stdin tests. Keep live registration manual; validate preservation of existing sound-hook entry using a fixture copy only.
- [ ] Commit `feat: provide fail-open warning hooks for both agents`.

### Task 8: Portable release readiness and handoff

**Files:** Update README.md, docs/limitations.md, docs/validation.md, PROGRES.md, memory.md and pyproject.toml; add tests/test_portable_checkout.py. Do not add runtime dependencies or checked-in venv.

- [ ] Document clone/download, Python 3.12+, Git requirement for check-diff, setup.cmd, receipts.cmd audit/check-diff/eval, source overrides, manual hooks, privacy and uninstall. Supply direct module command for non-Windows users.
- [ ] Test clean copied checkout in temp with paths containing spaces; setup, --help, both-source fixture audit and no runtime path reference to original machine. Check no packaged private data.
- [ ] Run complete unittest suite with no unexplained skips, CLI smoke commands and offline/read-only integrations. Record actual output; do not claim real Claude validation or live hooks if only fixtures were used.
- [ ] Stage/review only intended sources and redacted fixtures, then commit `docs: document portable setup and validation limits`. No remote creation or push.
- [ ] Write five-day pilot instructions and blank daily validation table; do not mark calendar pilot complete. Require actual new positive/negative labels for meaningful precision/recall and label warning-only observations separately from false blocks.

## Self-Review

- Original five claim types, two sources, redaction, reports, eval, testguard, wrappers and optional hooks each have an owning task.
- All five review-focus failure modes map to named tests above.
- Interfaces agree across ingest, claims, evidence and reports; source-specific behavior remains in ingest/protocol boundaries.
- Missing real Claude history, hook protocol support and five-day pilot remain explicit evidence limits, not invented completed tasks.
- No task requires network access from the application, global hook installation, paid dependencies or publication.

## Execution Handoff

Status: PLAN WRITTEN, awaiting owner's review before product code. Recommended execution: native single-session implementation via executing-plans, no subagents or extra models. Follow TDD within each task and report actual command output. The new terminal/session may be resumed only after it reads this plan and current handoff; do not run two writers on the same checkout.

# Known limitations

- Regex claim classification is conservative and not language understanding. It
  can miss uncommon EN/BCS wording and can flag ambiguous phrases. A clean report
  does not certify correctness. Quoted examples/negations are excluded heuristically.
- Runner recognition uses fixed command shapes. Complex JavaScript orchestration,
  shell conditionals, unusual wrappers and custom test scripts can remain unverified.
  A successful outer shell is not sufficient proof of every inner operation.
- Combined or truncated transcripts, mismatched tool IDs and evolving schemas can
  omit usable evidence. Diagnostics must be reviewed. Primary execution IDs win
  over matching mirror IDs; source formats without matching identifiers can remain
  ambiguous. Input is capped at 256 MiB/file and 8 MiB/line.
- Tests are checked against same-turn evidence. An accurate restatement of a prior
  successful run can be NO_EVIDENCE under this freshness policy.
- File counts use successful recorded changes. An incomplete transcript cannot
  establish that fewer recorded changes makes a claim false. No arbitrary file is
  opened merely because its name appears in a claim.
- Historical commit/push output is not current repository/remote verification.
  Read-only Git calls are confined to testguard's explicitly selected local repo.
- Python AST detects reductions per test function; legitimate assertion helpers,
  renamed tests and parameterized rewrites may trigger review. In the five
  controlled legitimate-refactor examples, three produce signals. JS/TS uses
  regexes; comments/strings and function attribution can be imprecise.
- Staged and unstaged versions are inspected separately so a restoration cannot
  hide weakened staged tests. Renames are treated as deletion/addition; review
  removal signals rather than assuming malicious intent.
- Claude Code 2.1.300 and Codex 0.125-0.162 were checked on one owner's Windows sessions. Other versions,
  operating systems and setups may differ. Claude's success flag proves exit 0, not a test pass; test claims
  still need runner output. Background commands never count as finished.
- Markdown stripping drops tables, code and quoted text before claim matching, so a genuine claim written only
  inside a table is not audited. Sentences with negations or future/conditional words are skipped entirely.
  Plain sentences such as "testovi prolaze" in a list of criteria can still be read as claims.
- A runner inside a compound command is judged by its summary line only; runners without a recognized
  summary (go, cargo, dotnet) in compound commands stay NO_EVIDENCE.
- A quiet commit is proven by a `git log --oneline` line with the same subject; an older commit with an
  identical subject could confirm a commit that did not happen.
- The hook sees only edits made with Write, Edit, MultiEdit and Codex file_change. Files changed through Bash (sed, redirects, formatters) are not checked.
- Claims made in a turn without any tool call are listed as "Mentioned in conversation" and do not set exit 1. They are still NO_EVIDENCE, not proof of falsehood.
- On large repositories the hook runs a few Git calls and parses the transcript tail. Measured on one owner machine: about 0.85 to 1.2 s with an 11.5 MB transcript in a repository with many changed files, 0.5 s in the small checkout. The hook limit is 10 s and the hook fails open.
- For a file that no longer exists (deleted), the hook cannot recover its on-disk case, so a delete typed in a different case may be missed. A turn editing hundreds of files may exceed the Windows command-line limit; the hook then fails open.
- Hooks have simulated stdin tests, not a live-host acceptance test. macOS/Linux launchers are not verified.
- Actual five-day usage metrics remain pending. The Phase 0 sample contains no
  verified negative examples; recall cannot be established from that sample.
- Logs/report writes can conflict across simultaneous invocations; run a single
  audit at a time. The dated audit report is replaced each run on that date.

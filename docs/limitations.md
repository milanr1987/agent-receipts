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
- Claude compatibility is fixture-tested but actual local sessions are unavailable.
  Optional warning-only hooks have simulated stdin tests, not a claimed live-host
  acceptance test. Windows wrappers are tested on Windows; other platforms should
  use the Python module directly.
- Actual five-day usage metrics remain pending. The Phase 0 sample contains no
  verified negative examples; recall cannot be established from that sample.
- Logs/report writes can conflict across simultaneous invocations; run a single
  audit at a time. The dated audit report is replaced each run on that date.

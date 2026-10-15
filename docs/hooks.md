# Optional warning-only Stop hooks

The application does not install hooks or edit existing settings. Test the wrapper
with a controlled transcript before adding a registry entry manually. Keep all
existing entries, including sound notifications. Remove only the Receipts entry
to uninstall. A fresh clone requires its own setup and registration.

Sources checked 2026-10-15:

- [Claude hook reference](https://code.claude.com/docs/en/hooks)
- [Codex hook reference](https://developers.openai.com/codex/hooks)

The current references describe `transcript_path`, `session_id`, `cwd` and
`stop_hook_active`. Codex also supplies `turn_id`. Warning output uses JSON
`systemMessage`, exits zero and never requests continuation or a block. An explicit
`last_assistant_message` is preferred when present because transcript flushing can
lag behind Stop. Unknown/missing identity is skipped rather than choosing a recent
unrelated session. A host timeout of 10 seconds is required. Logs rotate at 5 MiB.

Local CLI version inspected: Codex 0.162.1. Real automatic hook invocation has NOT
been tested on this machine; fixtures validate the adapter contract. Current
documentation may evolve; confirm schema compatibility with the installed host.
No real Claude installation/session is available here. Do not claim live support
from fixture tests alone. This release deliberately contains no blocking mode.

## Manual example

After `setup.cmd`, merge the following entry into the existing `hooks.Stop` array
in the appropriate host registry. The file location/envelope is host-specific:
Claude project settings use `.claude/settings.json`; for Codex confirm the active
hooks registry in the installed CLI before copying. This is an entry, not a whole
replacement file. Replace the example checkout path with the local checkout.

```json
{
  "hooks": [
    {
      "type": "command",
      "command": "cmd /d /c \"\"C:\\Projects\\agent-receipts\\receipts-hook.cmd\" --source codex\"",
      "timeout": 10
    }
  ]
}
```

For Claude use `--source claude`. Preserve the original registry and make a local
backup first. Registration is optional; `audit` and `check-diff` work without it.
The watcher never installs a model or makes API calls. Advisory results are written
to `reports/hook.log`; inspect them during the five-working-day pilot.

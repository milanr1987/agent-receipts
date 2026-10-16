#!/bin/sh
# Run the checkout's receipts CLI. Exit 2 when no interpreter is available.
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
py=${RECEIPTS_PYTHON:-}
if [ -z "$py" ]; then
  if [ -x "$here/.venv/bin/python" ]; then py="$here/.venv/bin/python"
  else echo "Python environment missing. Run setup.sh or set RECEIPTS_PYTHON." >&2; exit 2
  fi
fi
if [ ! -x "$py" ] && ! command -v "$py" >/dev/null 2>&1; then
  echo "Python interpreter not found: check RECEIPTS_PYTHON." >&2
  exit 2
fi
# src is passed as an argument (not PYTHONPATH) so Git Bash converts the path for a Windows Python;
# -P keeps modules in the caller's directory (the hook runs inside user projects) off sys.path.
PYTHONUTF8=1 exec "$py" -P -c 'import sys; sys.path.insert(0, sys.argv.pop(1)); from receipts.cli import main; raise SystemExit(main())' "$here/src" "$@"

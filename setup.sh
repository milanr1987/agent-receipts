#!/bin/sh
# Create a local .venv without pip or downloads (macOS/Linux checkout without pipx).
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
py=${RECEIPTS_PYTHON:-}
if [ -z "$py" ]; then
  if command -v python3 >/dev/null 2>&1; then py=python3
  elif command -v python >/dev/null 2>&1; then py=python
  else echo "Install Python 3.12 or newer, then run setup.sh again." >&2; exit 2
  fi
fi
if ! "$py" -c "import sys; assert sys.version_info >= (3,12); import venv; venv.create(sys.argv[1], with_pip=False)" "$here/.venv"; then
  echo "Setup failed. Python 3.12+ with standard venv support is required. No downloads were attempted." >&2
  exit 2
fi
echo "Ready. Run ./receipts.sh --help"

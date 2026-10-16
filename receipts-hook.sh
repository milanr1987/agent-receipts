#!/bin/sh
# Advisory adapter always fails open, including missing interpreter/setup.
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$here/receipts.sh" hook "$@"
exit 0

#!/bin/bash
# Run the full qvm-remote test suite.
# Usage: bash test/run-tests.sh [-v]
cd "$(dirname "$0")/.." || exit 1

rc=0
for suite in \
    test/test_qvm_remote.py \
    test/test_gui.py \
    test/test_gui_wiring.py \
    test/test_gui_integration.py; do
    echo "=== $suite ==="
    python3 "$suite" -v "$@" || rc=1
    echo ""
done

if [ $rc -eq 0 ]; then
    echo "All test suites passed."
else
    echo "Some tests FAILED." >&2
fi
exit $rc

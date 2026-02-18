#!/bin/bash
# Thin wrapper for the Python test suite.
cd "$(dirname "$0")/.." || exit 1
exec python3 test/test_qvm_remote.py -v "$@"

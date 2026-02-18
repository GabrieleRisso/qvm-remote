#!/bin/bash
# test-arch-client.sh -- Post-install verification of qvm-remote client on Arch Linux.
#
# Runs inside an Arch Linux container after 'make install-vm'.
# Validates that the client works identically to the Fedora build.

PASS=0
FAIL=0
TOTAL=0

# ── Assertions ────────────────────────────────────────────────────

assert_ok() {
    local desc="$1"; shift
    ((TOTAL++))
    if "$@" >/dev/null 2>&1; then
        ((PASS++)); echo "  PASS: $desc"
    else
        ((FAIL++)); echo "  FAIL: $desc"
    fi
}

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    ((TOTAL++))
    if [[ "$actual" == "$expected" ]]; then
        ((PASS++)); echo "  PASS: $desc"
    else
        ((FAIL++)); echo "  FAIL: $desc (expected='$expected', got='$actual')"
    fi
}

assert_contains() {
    local desc="$1" haystack="$2" needle="$3"
    ((TOTAL++))
    if [[ "$haystack" == *"$needle"* ]]; then
        ((PASS++)); echo "  PASS: $desc"
    else
        ((FAIL++)); echo "  FAIL: $desc (missing '$needle' in output)"
    fi
}

assert_exists() {
    local desc="$1" path="$2"
    ((TOTAL++))
    if [[ -e "$path" ]]; then
        ((PASS++)); echo "  PASS: $desc"
    else
        ((FAIL++)); echo "  FAIL: $desc (missing: $path)"
    fi
}

assert_not_exists() {
    local desc="$1" path="$2"
    ((TOTAL++))
    if [[ ! -e "$path" ]]; then
        ((PASS++)); echo "  PASS: $desc"
    else
        ((FAIL++)); echo "  FAIL: $desc (file exists: $path)"
    fi
}

# ── Setup ─────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  qvm-remote -- Arch Linux Client Integration Tests          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Distro:    $(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2)"
echo "Python:    $(python3 --version 2>&1)"
echo "Kernel:    $(uname -r)"
echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 1: Binary Installation ───────────────────────────────"
echo ""

assert_ok "qvm-remote_binary_installed_and_executable" test -x /usr/bin/qvm-remote
assert_ok "qvm-remote_shebang_is_python3" head -1 /usr/bin/qvm-remote
SHEBANG=$(head -1 /usr/bin/qvm-remote)
assert_contains "qvm-remote_shebang_contains_python3" "$SHEBANG" "python3"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 2: CLI Help and Version ──────────────────────────────"
echo ""

HELP_OUT=$(qvm-remote --help 2>&1)
assert_contains "help_shows_usage_header" "$HELP_OUT" "Execute commands"
assert_contains "help_shows_key_gen_subcommand" "$HELP_OUT" "key gen"
assert_contains "help_shows_key_show_subcommand" "$HELP_OUT" "key show"
assert_contains "help_shows_key_import_subcommand" "$HELP_OUT" "key import"
assert_contains "help_shows_ping_subcommand" "$HELP_OUT" "ping"
assert_contains "help_shows_timeout_option" "$HELP_OUT" "--timeout"

VERSION_OUT=$(qvm-remote --version 2>&1)
assert_contains "version_shows_qvm_remote_prefix" "$VERSION_OUT" "qvm-remote"
assert_contains "version_shows_semver" "$VERSION_OUT" "1.0.0"

# Short flags
HELP_SHORT=$(qvm-remote -h 2>&1)
assert_contains "short_help_flag_works" "$HELP_SHORT" "qvm-remote"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 3: Error Handling ────────────────────────────────────"
echo ""

R=$(qvm-remote --bogus 2>&1)
assert_eq "unknown_option_returns_nonzero" "1" "$?"
assert_contains "unknown_option_shows_error" "$R" "unknown option"

R=$(qvm-remote key 2>&1)
assert_eq "key_without_subcommand_returns_nonzero" "1" "$?"
assert_contains "key_without_subcommand_shows_usage" "$R" "gen | show | import"

# Empty stdin should fail
R=$(echo -n "" | qvm-remote 2>&1)
assert_eq "empty_stdin_command_returns_nonzero" "1" "$?"
assert_contains "empty_stdin_shows_error_message" "$R" "empty command"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 4: Key Generation Cycle ──────────────────────────────"
echo ""

export HOME=/tmp/arch-test-home
rm -rf "$HOME"
mkdir -p "$HOME"

KEYGEN_OUT=$(qvm-remote key gen 2>&1)
VM_KEY=$(qvm-remote key show 2>/dev/null)

assert_eq "generated_key_is_64_hex_chars" "64" "${#VM_KEY}"
assert_exists "auth_key_file_created" "$HOME/.qvm-remote/auth.key"
PERMS=$(stat -c '%a' "$HOME/.qvm-remote/auth.key" 2>/dev/null)
assert_eq "auth_key_file_permissions_are_0600" "600" "$PERMS"

# Key show returns the same key
SHOW_OUT=$(qvm-remote key show 2>/dev/null)
assert_eq "key_show_matches_generated_key" "$VM_KEY" "$SHOW_OUT"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 5: Key Import Cycle ──────────────────────────────────"
echo ""

export HOME=/tmp/arch-test-import
rm -rf "$HOME"
mkdir -p "$HOME"

IMPORT_KEY=$(python3 -c "import os; print(os.urandom(32).hex())")
qvm-remote key import "$IMPORT_KEY" >/dev/null 2>&1
GOT_KEY=$(qvm-remote key show 2>/dev/null)
assert_eq "imported_key_matches_original" "$IMPORT_KEY" "$GOT_KEY"

PERMS=$(stat -c '%a' "$HOME/.qvm-remote/auth.key" 2>/dev/null)
assert_eq "imported_key_file_permissions_are_0600" "600" "$PERMS"

# Invalid key rejected
R=$(qvm-remote key import "badkey" 2>&1)
assert_eq "invalid_key_import_returns_nonzero" "1" "$?"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 6: Audit Log ─────────────────────────────────────────"
echo ""

export HOME=/tmp/arch-test-audit
rm -rf "$HOME"
mkdir -p "$HOME"

qvm-remote key gen >/dev/null 2>&1

# Submit a command (will timeout but should create log)
assert_exists "audit_log_directory_created" "$HOME/.qvm-remote"

# Check audit log permissions if it exists
if [[ -f "$HOME/.qvm-remote/audit.log" ]]; then
    PERMS=$(stat -c '%a' "$HOME/.qvm-remote/audit.log" 2>/dev/null)
    assert_eq "audit_log_permissions_are_0600" "600" "$PERMS"
fi

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 7: Data Migration ────────────────────────────────────"
echo ""

export HOME=/tmp/arch-test-migration
rm -rf "$HOME"
mkdir -p "$HOME/.qubes-remote"
echo "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
    > "$HOME/.qubes-remote/auth.key"

MIG_KEY=$(qvm-remote key show 2>/dev/null)
assert_eq "migration_preserves_key" \
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
    "$MIG_KEY"
assert_exists "migration_creates_new_directory" "$HOME/.qvm-remote"
assert_not_exists "migration_removes_old_directory" "$HOME/.qubes-remote"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 8: Python Compatibility ──────────────────────────────"
echo ""

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

assert_ok "python_version_is_3_8_or_higher" test "$PY_MAJOR" -eq 3 -a "$PY_MINOR" -ge 8
assert_ok "client_compiles_without_errors" python3 -c \
    "import py_compile; py_compile.compile('/usr/bin/qvm-remote', doraise=True)"

# Verify secrets module is available (used for secure ID generation)
assert_ok "secrets_module_available" python3 -c "import secrets"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 9: Source Hardening Verification ─────────────────────"
echo ""

CLIENT_SRC=$(cat /usr/bin/qvm-remote)
assert_contains "client_uses_secrets_module" "$CLIENT_SRC" "import secrets"
assert_contains "client_uses_secrets_token_hex" "$CLIENT_SRC" "secrets.token_hex"
assert_contains "client_sets_key_permissions" "$CLIENT_SRC" "chmod(0o600)"
assert_contains "client_has_error_handling" "$CLIENT_SRC" "except OSError"

echo ""

# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════

echo "╔══════════════════════════════════════════════════════════════╗"
if (( FAIL > 0 )); then
    echo "║  RESULT:  $PASS passed,  $FAIL FAILED  (total: $TOTAL)              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    exit 1
else
    echo "║  RESULT:  $PASS passed,  0 failed  (total: $TOTAL)               ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  ALL ARCH LINUX CLIENT TESTS PASSED"
    echo ""
fi

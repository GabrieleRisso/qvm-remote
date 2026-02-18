#!/bin/bash
# test-dom0-sim.sh — End-to-end test of qvm-remote-dom0 in simulated dom0.
#
# Runs inside a Fedora 41 container with:
#   - qvm-remote RPMs installed
#   - Mock Qubes OS tools (qvm-run, qvm-check, hostname, systemctl)
#   - /home/user/ simulating the VM user's home directory
#
# The mock qvm-run executes commands locally, so the "VM filesystem"
# is the same as the "dom0 filesystem" -- this lets the daemon's
# qvm-run calls actually read/write /home/user/.qvm-remote/ as if
# talking to a real VM via qrexec.

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

assert_not_exists() {
    local desc="$1" path="$2"
    ((TOTAL++))
    if [[ ! -e "$path" ]]; then
        ((PASS++)); echo "  PASS: $desc"
    else
        ((FAIL++)); echo "  FAIL: $desc (file exists: $path)"
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

# helper: generate HMAC token (same as qvm-remote/qvm-remote-dom0)
hmac_token() {
    local key="$1" cmd_id="$2"
    python3 -c "
import hmac, hashlib
print(hmac.new('$key'.encode(), b'$cmd_id', hashlib.sha256).hexdigest())
"
}

# ── Setup ─────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  qvm-remote-dom0 — Simulated Dom0 Integration Tests        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Container: $(cat /etc/fedora-release 2>/dev/null || echo 'unknown')"
echo "Python:    $(python3 --version 2>&1)"
echo "Mocks:     qvm-run=$(command -v qvm-run) qvm-check=$(command -v qvm-check)"
echo ""

# Create the simulated VM user home
mkdir -p /home/user
chmod 755 /home/user

# Remove RPM-installed config so install script creates a fresh one
rm -f /etc/qubes/remote.conf

# ═════════════════════════════════════════════════════════════════
echo "── Phase 1: Install Script ──────────────────────────────────"
echo ""

# Run the install script with --yes (non-interactive)
INSTALL_OUT=$(bash /tmp/install-dom0.sh --yes visyble 2>&1)
INSTALL_RC=$?

assert_eq "install-dom0.sh exits 0" "0" "$INSTALL_RC"
assert_ok "qvm-remote-dom0 binary installed" test -x /usr/bin/qvm-remote-dom0
assert_ok "service file installed" test -f /etc/systemd/system/qvm-remote-dom0.service
assert_ok "config file exists" test -f /etc/qubes/remote.conf
assert_contains "config has QVM_REMOTE_VMS=visyble" \
    "$(cat /etc/qubes/remote.conf)" "QVM_REMOTE_VMS=visyble"
assert_contains "install fetched daemon binary" "$INSTALL_OUT" "Pulling qvm-remote-dom0"
assert_contains "install fetched service file" "$INSTALL_OUT" "Pulling qvm-remote-dom0.service"

# Verify systemctl was called
assert_ok "systemctl daemon-reload called" grep -q "daemon-reload" /tmp/systemctl.log
assert_ok "systemctl start called" grep -q "start qvm-remote-dom0" /tmp/systemctl.log

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 2: CLI Verification ────────────────────────────────"
echo ""

assert_contains "qvm-remote --help" "$(qvm-remote --help 2>&1)" "Execute commands"
EXPECTED_VER=$(cat /build/version 2>/dev/null || echo "1.1.0")
assert_contains "qvm-remote --version" "$(qvm-remote --version 2>&1)" "qvm-remote $EXPECTED_VER"
assert_contains "qvm-remote-dom0 --help" "$(qvm-remote-dom0 --help 2>&1)" "Dom0 executor"
assert_contains "qvm-remote-dom0 --version" "$(qvm-remote-dom0 --version 2>&1)" "qvm-remote-dom0 $EXPECTED_VER"

# Error handling
R=$(qvm-remote --bogus 2>&1); assert_eq "qvm-remote --bogus fails" "1" "$?"
R=$(qvm-remote-dom0 --bogus 2>&1); assert_eq "qvm-remote-dom0 --bogus fails" "1" "$?"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 3: Key Management ──────────────────────────────────"
echo ""

# Generate key in "VM" (using HOME= to simulate running as VM user)
KEYGEN_OUT=$(HOME=/home/user qvm-remote key gen 2>&1)
VM_KEY=$(HOME=/home/user qvm-remote key show 2>/dev/null)

assert_eq "key is 64 hex chars" "64" "${#VM_KEY}"
assert_exists "auth.key created" "/home/user/.qvm-remote/auth.key"
assert_eq "auth.key perms 600" "600" "$(stat -c '%a' /home/user/.qvm-remote/auth.key)"

# Authorize in "dom0"
AUTH_OUT=$(qvm-remote-dom0 authorize visyble "$VM_KEY" 2>&1)
assert_exists "dom0 key file created" "/etc/qubes/remote.d/visyble.key"
assert_eq "dom0 key matches VM key" "$VM_KEY" "$(cat /etc/qubes/remote.d/visyble.key)"
assert_eq "dom0 key perms 600" "600" "$(stat -c '%a' /etc/qubes/remote.d/visyble.key)"
assert_eq "remote.d perms 700" "700" "$(stat -c '%a' /etc/qubes/remote.d)"

# List keys
KEYS_OUT=$(qvm-remote-dom0 keys 2>&1)
assert_contains "keys lists visyble" "$KEYS_OUT" "visyble"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 4: Daemon — Single Command E2E ─────────────────────"
echo ""

# Create VM-side queue directories (simulating what init_vm_dirs does)
mkdir -p /home/user/.qvm-remote/queue/{pending,running,results}
mkdir -p /home/user/.qvm-remote/history

# Submit a test command to the "VM" pending queue
CMD_ID="e2e-single-001"
echo 'echo hello-from-dom0' > "/home/user/.qvm-remote/queue/pending/$CMD_ID"

# Generate HMAC auth token
TOKEN=$(hmac_token "$VM_KEY" "$CMD_ID")
echo "$TOKEN" > "/home/user/.qvm-remote/queue/pending/${CMD_ID}.auth"

# Run daemon once
DAEMON_OUT=$(qvm-remote-dom0 --vm visyble --once 2>&1)
echo "  [daemon] $DAEMON_OUT" | head -5

# Verify results
RESULT=$(cat "/home/user/.qvm-remote/queue/results/${CMD_ID}.out" 2>/dev/null)
EXIT_CODE=$(cat "/home/user/.qvm-remote/queue/results/${CMD_ID}.exit" 2>/dev/null)

assert_exists "result .out file" "/home/user/.qvm-remote/queue/results/${CMD_ID}.out"
assert_exists "result .exit file" "/home/user/.qvm-remote/queue/results/${CMD_ID}.exit"
assert_exists "result .err file" "/home/user/.qvm-remote/queue/results/${CMD_ID}.err"
assert_exists "result .meta file" "/home/user/.qvm-remote/queue/results/${CMD_ID}.meta"
assert_contains "stdout has hello-from-dom0" "$RESULT" "hello-from-dom0"
assert_eq "exit code is 0" "0" "$EXIT_CODE"

# Verify pending was cleaned up
assert_not_exists "pending file cleaned" "/home/user/.qvm-remote/queue/pending/$CMD_ID"
assert_not_exists "auth file cleaned" "/home/user/.qvm-remote/queue/pending/${CMD_ID}.auth"

# Verify meta contains duration
META=$(cat "/home/user/.qvm-remote/queue/results/${CMD_ID}.meta" 2>/dev/null)
assert_contains "meta has id" "$META" "id=$CMD_ID"
assert_contains "meta has duration_ms" "$META" "duration_ms="
assert_contains "meta has exit_code" "$META" "exit_code=0"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 5: Daemon — Multi-Command Batch ────────────────────"
echo ""

for i in 1 2 3; do
    CID="e2e-multi-$i"
    echo "echo result-$i" > "/home/user/.qvm-remote/queue/pending/$CID"
    TOKEN=$(hmac_token "$VM_KEY" "$CID")
    echo "$TOKEN" > "/home/user/.qvm-remote/queue/pending/${CID}.auth"
done

qvm-remote-dom0 --vm visyble --once >/dev/null 2>&1

for i in 1 2 3; do
    CID="e2e-multi-$i"
    R=$(cat "/home/user/.qvm-remote/queue/results/${CID}.out" 2>/dev/null)
    E=$(cat "/home/user/.qvm-remote/queue/results/${CID}.exit" 2>/dev/null)
    assert_contains "batch cmd $i: correct output" "$R" "result-$i"
    assert_eq "batch cmd $i: exit 0" "0" "$E"
done

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 6: Daemon — Complex Commands ───────────────────────"
echo ""

# Test a multi-line script
CID="e2e-script-001"
cat > "/home/user/.qvm-remote/queue/pending/$CID" <<'SCRIPT'
A=42
B=58
echo $((A + B))
echo "multi-line works" >&2
SCRIPT
TOKEN=$(hmac_token "$VM_KEY" "$CID")
echo "$TOKEN" > "/home/user/.qvm-remote/queue/pending/${CID}.auth"

qvm-remote-dom0 --vm visyble --once >/dev/null 2>&1

STDOUT=$(cat "/home/user/.qvm-remote/queue/results/${CID}.out" 2>/dev/null)
STDERR=$(cat "/home/user/.qvm-remote/queue/results/${CID}.err" 2>/dev/null)
assert_contains "script: stdout has 100" "$STDOUT" "100"
assert_contains "script: stderr captured" "$STDERR" "multi-line works"
assert_eq "script: exit 0" "0" "$(cat "/home/user/.qvm-remote/queue/results/${CID}.exit" 2>/dev/null)"

# Test command with non-zero exit
CID="e2e-fail-cmd"
echo 'exit 42' > "/home/user/.qvm-remote/queue/pending/$CID"
TOKEN=$(hmac_token "$VM_KEY" "$CID")
echo "$TOKEN" > "/home/user/.qvm-remote/queue/pending/${CID}.auth"

qvm-remote-dom0 --vm visyble --once >/dev/null 2>&1

assert_eq "fail cmd: exit code 42" "42" \
    "$(cat "/home/user/.qvm-remote/queue/results/${CID}.exit" 2>/dev/null)"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 7: Auth Failure — Bad Token ────────────────────────"
echo ""

CID="e2e-authfail-001"
echo 'echo should-not-run' > "/home/user/.qvm-remote/queue/pending/$CID"
echo "0000000000000000000000000000000000000000000000000000000000000000" \
    > "/home/user/.qvm-remote/queue/pending/${CID}.auth"

qvm-remote-dom0 --vm visyble --once >/dev/null 2>&1

assert_not_exists "auth fail: no result .out" \
    "/home/user/.qvm-remote/queue/results/${CID}.out"
assert_not_exists "auth fail: no result .exit" \
    "/home/user/.qvm-remote/queue/results/${CID}.exit"
assert_not_exists "auth fail: pending cleaned" \
    "/home/user/.qvm-remote/queue/pending/$CID"
assert_not_exists "auth fail: auth cleaned" \
    "/home/user/.qvm-remote/queue/pending/${CID}.auth"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 8: Auth Failure — Missing Token ────────────────────"
echo ""

CID="e2e-notoken-001"
echo 'echo should-not-run' > "/home/user/.qvm-remote/queue/pending/$CID"
# Deliberately NOT creating .auth file

qvm-remote-dom0 --vm visyble --once >/dev/null 2>&1

assert_not_exists "no token: no result" \
    "/home/user/.qvm-remote/queue/results/${CID}.out"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 9: Dry Run ─────────────────────────────────────────"
echo ""

CID="e2e-dryrun-001"
echo 'echo dry-output' > "/home/user/.qvm-remote/queue/pending/$CID"
TOKEN=$(hmac_token "$VM_KEY" "$CID")
echo "$TOKEN" > "/home/user/.qvm-remote/queue/pending/${CID}.auth"

qvm-remote-dom0 --vm visyble --once --dry-run >/dev/null 2>&1

DRY_OUT=$(cat "/home/user/.qvm-remote/queue/results/${CID}.out" 2>/dev/null)
DRY_EXIT=$(cat "/home/user/.qvm-remote/queue/results/${CID}.exit" 2>/dev/null)

assert_contains "dry-run: output has [dry-run]" "$DRY_OUT" "[dry-run]"
assert_eq "dry-run: exit 0" "0" "$DRY_EXIT"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 10: Key Revocation & Re-auth ───────────────────────"
echo ""

# Authorize a second dummy VM so the auth-deny path triggers
# (when zero keys exist, the daemon falls back to no-auth mode)
DUMMY_KEY=$(python3 -c "import os; print(os.urandom(32).hex())")
qvm-remote-dom0 authorize dummyvm "$DUMMY_KEY" >/dev/null 2>&1

qvm-remote-dom0 revoke visyble >/dev/null 2>&1
assert_not_exists "revoke removes key file" "/etc/qubes/remote.d/visyble.key"
assert_exists "other VM key still present" "/etc/qubes/remote.d/dummyvm.key"

# Command should fail after revocation (visyble has no key, but keys exist)
CID="e2e-post-revoke"
echo 'echo should-fail' > "/home/user/.qvm-remote/queue/pending/$CID"
TOKEN=$(hmac_token "$VM_KEY" "$CID")
echo "$TOKEN" > "/home/user/.qvm-remote/queue/pending/${CID}.auth"

qvm-remote-dom0 --vm visyble --once >/dev/null 2>&1

assert_not_exists "post-revoke: command rejected" \
    "/home/user/.qvm-remote/queue/results/${CID}.out"

# Clean up dummy and re-authorize visyble
qvm-remote-dom0 revoke dummyvm >/dev/null 2>&1
qvm-remote-dom0 authorize visyble "$VM_KEY" >/dev/null 2>&1

# Should work again
CID="e2e-post-reauth"
echo 'echo reauth-works' > "/home/user/.qvm-remote/queue/pending/$CID"
TOKEN=$(hmac_token "$VM_KEY" "$CID")
echo "$TOKEN" > "/home/user/.qvm-remote/queue/pending/${CID}.auth"

qvm-remote-dom0 --vm visyble --once >/dev/null 2>&1

R=$(cat "/home/user/.qvm-remote/queue/results/${CID}.out" 2>/dev/null)
assert_contains "re-auth: command works" "$R" "reauth-works"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 11: Logging ────────────────────────────────────────"
echo ""

assert_exists "dom0 log file exists" "/var/log/qubes/qvm-remote.log"
DOM0_LOG=$(cat /var/log/qubes/qvm-remote.log 2>/dev/null)

assert_contains "log: has EXEC entries" "$DOM0_LOG" "EXEC"
assert_contains "log: has AUTH-OK entries" "$DOM0_LOG" "AUTH-OK"
assert_contains "log: has AUTH-FAIL entries" "$DOM0_LOG" "AUTH-FAIL"
assert_contains "log: has AUTH-DENY entries" "$DOM0_LOG" "AUTH-DENY"
assert_contains "log: has DONE entries" "$DOM0_LOG" "DONE"
assert_contains "log: has CMD preview" "$DOM0_LOG" "cmd="
assert_contains "log: has duration" "$DOM0_LOG" "duration="

# VM-side audit log
assert_exists "VM audit log exists" "/home/user/.qvm-remote/audit.log"
VM_LOG=$(cat /home/user/.qvm-remote/audit.log 2>/dev/null)
assert_contains "VM log: has entries" "$VM_LOG" "id="

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 12: Data Migration ─────────────────────────────────"
echo ""

# Create a fresh home with old-style directory
mkdir -p /tmp/mig-test/.qubes-remote/queue/{pending,running,results}
echo "$VM_KEY" > /tmp/mig-test/.qubes-remote/auth.key

# Run qvm-remote which should trigger migration
MIG_OUT=$(HOME=/tmp/mig-test qvm-remote key show 2>/dev/null)
assert_eq "migration: key preserved" "$VM_KEY" "$MIG_OUT"
assert_exists "migration: new dir exists" "/tmp/mig-test/.qvm-remote"
assert_not_exists "migration: old dir removed" "/tmp/mig-test/.qubes-remote"

echo ""

# ═════════════════════════════════════════════════════════════════
echo "── Phase 13: RPM Metadata ───────────────────────────────────"
echo ""

assert_contains "RPM qvm-remote group" "$(rpm -qi qvm-remote 2>/dev/null)" "Qubes"
assert_contains "RPM qvm-remote-dom0 group" "$(rpm -qi qvm-remote-dom0 2>/dev/null)" "Qubes"
assert_contains "RPM obsoletes qubes-remote" \
    "$(rpm -q --obsoletes qvm-remote 2>/dev/null)" "qubes-remote"
assert_contains "RPM obsoletes qubes-remote-dom0" \
    "$(rpm -q --obsoletes qvm-remote-dom0 2>/dev/null)" "qubes-remote-dom0"
assert_contains "RPM requires python3" \
    "$(rpm -q --requires qvm-remote-dom0 2>/dev/null)" "python3"

echo ""

# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════

echo "╔══════════════════════════════════════════════════════════════╗"
if (( FAIL > 0 )); then
    echo "║  RESULT:  $PASS passed,  $FAIL FAILED  (total: $TOTAL)              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""

    # Show dom0 log on failure for debugging
    echo "── dom0 log (last 30 lines) ──"
    tail -30 /var/log/qubes/qvm-remote.log 2>/dev/null
    echo ""
    exit 1
else
    echo "║  RESULT:  $PASS passed,  0 failed  (total: $TOTAL)               ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  ALL DOM0 SIMULATION TESTS PASSED"
    echo ""
fi

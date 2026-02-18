#!/bin/bash
# test-dom0-e2e.sh -- End-to-end verification of qvm-remote admin stack in dom0
#
# Run from dom0:
#   bash test-dom0-e2e.sh
#
# Or from a VM via qvm-remote:
#   cat test/test-dom0-e2e.sh | qvm-remote
#
# Tests all critical subsystems: systemd services, API endpoints, genmon,
# policy enforcement, and health monitoring.

set -u

PASS=0
FAIL=0
BASE="http://127.0.0.1:9876"

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1${2:+ -- $2}"; }

assert_http() {
    local desc="$1" url="$2" expect_code="${3:-200}"
    local code body
    code=$(curl -sf -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null) || code="000"
    if [ "$code" = "$expect_code" ]; then
        pass "$desc (HTTP $code)"
    else
        fail "$desc" "expected $expect_code, got $code"
    fi
}

assert_json_key() {
    local desc="$1" url="$2" key="$3"
    local body
    body=$(curl -sf --max-time 5 "$url" 2>/dev/null) || { fail "$desc" "curl failed"; return; }
    if echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '$key' in d" 2>/dev/null; then
        pass "$desc"
    else
        fail "$desc" "key '$key' not in response"
    fi
}

assert_json_bool() {
    local desc="$1" url="$2" key="$3" expected="$4"
    local body
    body=$(curl -sf --max-time 5 "$url" 2>/dev/null) || { fail "$desc" "curl failed"; return; }
    local val
    val=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('$key','?'))" 2>/dev/null)
    if [ "$val" = "$expected" ]; then
        pass "$desc ($key=$val)"
    else
        fail "$desc" "$key: expected $expected, got $val"
    fi
}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  qvm-remote dom0 E2E Test Suite                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── 1. Service health ──
echo "── 1. Service health ──"
for svc in qvm-remote-dom0 qubes-global-admin-web; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        pass "$svc is active"
    else
        fail "$svc is active" "$(systemctl is-active "$svc" 2>&1)"
    fi
done
if systemctl is-active --quiet qubes-admin-watchdog.timer 2>/dev/null; then
    pass "qubes-admin-watchdog.timer is active"
else
    fail "qubes-admin-watchdog.timer is active" "$(systemctl is-active qubes-admin-watchdog.timer 2>&1)"
fi
for svc in qvm-remote-dom0 qubes-global-admin-web qubes-admin-watchdog.timer; do
    if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
        pass "$svc is enabled"
    else
        fail "$svc is enabled" "$(systemctl is-enabled "$svc" 2>&1)"
    fi
done
echo ""

# ── 2. Web UI serves HTML ──
echo "── 2. Web UI serves HTML ──"
INDEX=$(curl -sf --max-time 5 "$BASE/" 2>/dev/null)
if echo "$INDEX" | grep -q "Qubes Global Admin" 2>/dev/null; then
    pass "Web UI serves HTML with expected title"
else
    fail "Web UI serves HTML" "title not found"
fi
echo ""

# ── 3. Health endpoint ──
echo "── 3. Health endpoint ──"
assert_json_bool "daemon healthy"  "$BASE/api/health" "daemon" "True"
assert_json_bool "web healthy"     "$BASE/api/health" "web"    "True"
assert_json_key  "health has vm_name" "$BASE/api/health" "vm_name"
echo ""

# ── 4. VM list ──
echo "── 4. VM list ──"
VMLIST=$(curl -sf --max-time 10 "$BASE/api/vm-list" 2>/dev/null)
VM_COUNT=$(echo "$VMLIST" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('vms',[])))" 2>/dev/null)
if [ "${VM_COUNT:-0}" -gt 0 ]; then
    pass "vm-list returns $VM_COUNT VMs"
else
    fail "vm-list returns VMs" "count=$VM_COUNT"
fi
if echo "$VMLIST" | python3 -c "
import sys,json
vms=json.load(sys.stdin).get('vms',[])
states=[v.get('state','') for v in vms]
assert 'Running' in states or len(vms)>0
" 2>/dev/null; then
    pass "vm-list has running VMs first or has VMs"
else
    fail "vm-list sorting" "unexpected format"
fi
echo ""

# ── 5. Policy enforcement ──
echo "── 5. Policy enforcement ──"
POLICY_RESP=$(curl -sf --max-time 5 "$BASE/api/admin-policy" 2>/dev/null)
if echo "$POLICY_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'dom0' in d.get('policy',{})" 2>/dev/null; then
    pass "admin-policy returns policy with dom0 key"
else
    fail "admin-policy endpoint" "missing policy.dom0 key"
fi
BLOCKED_CODE=$(curl -s -o /tmp/e2e-blocked.json -w '%{http_code}' -X POST --max-time 10 \
    -H "Content-Type: application/json" \
    -d '{"cmd":"qvm-remove dom0"}' \
    "$BASE/api/execute" 2>/dev/null)
if [ "$BLOCKED_CODE" = "403" ]; then
    pass "blocked command rejected with HTTP 403 (qvm-remove dom0)"
else
    fail "blocked command rejected" "expected 403, got $BLOCKED_CODE: $(cat /tmp/e2e-blocked.json 2>/dev/null | head -c 200)"
fi
echo ""

# ── 6. Panel info ──
echo "── 6. Panel info ──"
assert_json_key "panel-info has bind"   "$BASE/api/panel-info" "bind"
assert_json_key "panel-info has vms"    "$BASE/api/panel-info" "authorized_vms"
echo ""

# ── 7. Status endpoint ──
echo "── 7. Status endpoint ──"
STATUS_RESP=$(curl -sf --max-time 20 "$BASE/api/status" 2>/dev/null)
if echo "$STATUS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'daemon_running' in d" 2>/dev/null; then
    pass "status has daemon_running"
else
    fail "status has daemon_running" "response: $(echo "$STATUS_RESP" | head -c 200)"
fi
if echo "$STATUS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'version' in d" 2>/dev/null; then
    pass "status has version"
else
    fail "status has version"
fi
echo ""

# ── 8. Log endpoint ──
echo "── 8. Log endpoint ──"
LOG_RESP=$(curl -sf --max-time 5 "$BASE/api/log" 2>/dev/null)
if echo "$LOG_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'log' in d or 'lines' in d or 'content' in d" 2>/dev/null; then
    pass "log endpoint returns data"
else
    fail "log endpoint" "unexpected format: $(echo "$LOG_RESP" | head -c 200)"
fi
echo ""

# ── 9. Genmon output ──
echo "── 9. Genmon output ──"
GENMON="/usr/local/bin/qubes-admin-genmon.sh"
if [ -x "$GENMON" ]; then
    GENMON_OUT=$("$GENMON" 2>/dev/null)
    if echo "$GENMON_OUT" | grep -q "<txt>" 2>/dev/null; then
        pass "genmon outputs valid XML (<txt> tag)"
    else
        fail "genmon output" "no <txt> tag: $(echo "$GENMON_OUT" | head -c 200)"
    fi
    if echo "$GENMON_OUT" | grep -q "<tool>" 2>/dev/null; then
        pass "genmon outputs tooltip (<tool> tag)"
    else
        fail "genmon tooltip" "no <tool> tag"
    fi
else
    fail "genmon script exists" "$GENMON not found or not executable"
    fail "genmon output" "skipped"
fi
echo ""

# ── 10. OpenClaw config ──
echo "── 10. OpenClaw config ──"
assert_http "openclaw config endpoint" "$BASE/api/openclaw/config"
echo ""

# ── 11. Self-heal ──
echo "── 11. Self-heal ──"
HEAL_CODE=$(curl -s -o /tmp/e2e-heal.json -w '%{http_code}' --max-time 30 -X POST \
    -H "Content-Type: application/json" -d '{}' \
    "$BASE/api/self-heal" 2>/dev/null)
HEAL_RESP=$(cat /tmp/e2e-heal.json 2>/dev/null)
if [ "$HEAL_CODE" = "200" ] && echo "$HEAL_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('ok')==True" 2>/dev/null; then
    pass "self-heal returns ok (HTTP 200)"
elif [ "$HEAL_CODE" = "403" ]; then
    pass "self-heal correctly denied by policy (HTTP 403)"
else
    fail "self-heal endpoint" "HTTP $HEAL_CODE: $(echo "$HEAL_RESP" | head -c 200)"
fi
echo ""

# ── 12. Qubes global prefs ──
echo "── 12. Qubes global prefs ──"
assert_json_key "qubes-prefs has output" "$BASE/api/qubes-prefs" "out"
echo ""

# ── Summary ──
TOTAL=$((PASS + FAIL))
echo "╔══════════════════════════════════════════════════════════════╗"
printf "║  Results: %d passed, %d failed out of %d tests" "$PASS" "$FAIL" "$TOTAL"
printf "%*s║\n" $((52 - ${#PASS} - ${#FAIL} - ${#TOTAL})) ""
echo "╚══════════════════════════════════════════════════════════════╝"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0

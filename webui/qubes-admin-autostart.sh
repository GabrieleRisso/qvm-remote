#!/bin/bash
# ┌──────────────────────────────────────────────────────────────────┐
# │ dom0 - Qubes Global Admin - Autostart                           │
# │                                                                  │
# │ Runs at XFCE login for user 'cyberdeck'.                        │
# │ Starts services, opens admin tools, configures workspaces.      │
# │                                                                  │
# │ Naming: all dom0 windows follow "dom0 - Function - Program"     │
# │                                                                  │
# │ Workspaces:                                                      │
# │   1. Admin  — Web admin, Qube Manager, Global Config            │
# │   2. Code   — Cursor editors, dev tools                         │
# │   3. Comms  — Chrome, WhatsApp                                  │
# │   4. Media  — Spotify, Bluetooth, audio                         │
# │   5. Ops    — Terminals, VPN, system tools                      │
# └──────────────────────────────────────────────────────────────────┘
set -euo pipefail

LOG="/tmp/dom0-admin-autostart.log"
: > "$LOG"  # truncate

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }
note() { notify-send -i "${2:-dialog-information}" -a "dom0 - Admin" "$1" "${3:-}" 2>/dev/null || true; }

log "=== dom0 - Qubes Global Admin autostart begin ==="

# ── 1. Workspaces ──────────────────────────────────────────────────
log "Configuring 5 workspaces"
xfconf-query -c xfwm4 -p /general/workspace_count -s 5 2>/dev/null || true
xfconf-query -c xfwm4 -p /general/workspace_names \
    -n -t string -t string -t string -t string -t string \
    -s "Admin" -s "Code" -s "Comms" -s "Media" -s "Ops" 2>/dev/null || \
xfconf-query -c xfwm4 -p /general/workspace_names \
    -s "Admin" -s "Code" -s "Comms" -s "Media" -s "Ops" 2>/dev/null || true
log "Workspaces: Admin / Code / Comms / Media / Ops"

# ── 2. Start qvm-remote-dom0 daemon ───────────────────────────────
if systemctl is-active --quiet qvm-remote-dom0 2>/dev/null; then
    log "qvm-remote-dom0 already running"
    note "dom0 - Daemon" "emblem-ok-symbolic" "qvm-remote-dom0 is running"
else
    log "Starting qvm-remote-dom0..."
    sudo systemctl start qvm-remote-dom0 2>/dev/null && {
        log "qvm-remote-dom0 started"
        note "dom0 - Daemon Started" "network-transmit-receive-symbolic" "qvm-remote-dom0 is active"
    } || {
        log "WARN: qvm-remote-dom0 failed to start"
        note "dom0 - Daemon Failed" "dialog-error" "Could not start qvm-remote-dom0"
    }
fi

# ── 3. Start web admin server ─────────────────────────────────────
if systemctl is-active --quiet qubes-global-admin-web 2>/dev/null; then
    log "Web admin already running"
else
    log "Starting web admin..."
    sudo systemctl start qubes-global-admin-web 2>/dev/null && {
        log "Web admin started on http://127.0.0.1:9876"
        note "dom0 - Web Admin" "applications-internet-symbolic" "http://127.0.0.1:9876"
    } || {
        log "WARN: Web admin failed to start"
        note "dom0 - Web Admin Failed" "dialog-error" "Could not start web server"
    }
fi

# Wait for web server to respond
for i in $(seq 1 15); do
    curl -sf -o /dev/null http://127.0.0.1:9876/api/status 2>/dev/null && break
    sleep 1
done
log "Web server responding"

# ── 4. Open Firefox with web admin on Admin workspace ──────────────
sleep 1
firefox --new-window http://127.0.0.1:9876 &disown
log "Firefox launched: dom0 - Web Admin"

# ── 5. VM selector — choose which VMs to activate qvm-remote for ──
# Show a zenity checklist with all non-running VMs that have keys
sleep 3
AVAILABLE_VMS=""
if command -v qvm-ls >/dev/null 2>&1; then
    # Get all VMs that are stopped and could be started
    AVAILABLE_VMS=$(qvm-ls --halted --fields NAME,CLASS,LABEL --raw-data 2>/dev/null | \
        grep -v "^dom0\|^sys-\|^default-mgmt\|TemplateVM" | \
        awk -F'|' '{print $1}' | sort)
fi

# Get running VMs
RUNNING_VMS=$(qvm-ls --running --fields NAME --raw-list 2>/dev/null | grep -v "^dom0$" || true)

if command -v zenity >/dev/null 2>&1 && [ -n "$AVAILABLE_VMS" ]; then
    # Build zenity checklist
    ZENITY_ARGS=()
    for vm in $RUNNING_VMS; do
        ZENITY_ARGS+=(TRUE "$vm" "Running")
    done
    for vm in $AVAILABLE_VMS; do
        echo "$RUNNING_VMS" | grep -q "^${vm}$" && continue
        ZENITY_ARGS+=(FALSE "$vm" "Stopped")
    done

    SELECTED=$(zenity --list --checklist \
        --title="dom0 - VM Selector - qvm-remote" \
        --text="Select VMs to start and activate qvm-remote for.\nAlready-running VMs are pre-checked." \
        --column="" --column="VM" --column="Status" \
        --width=500 --height=500 \
        --separator="|" \
        "${ZENITY_ARGS[@]}" 2>/dev/null) || SELECTED=""

    if [ -n "$SELECTED" ]; then
        IFS='|' read -ra CHOSEN <<< "$SELECTED"
        for vm in "${CHOSEN[@]}"; do
            vm=$(echo "$vm" | tr -d ' ')
            [ -z "$vm" ] && continue
            if ! qvm-check "$vm" --running 2>/dev/null; then
                log "Starting VM: $vm"
                note "dom0 - Starting VM" "system-run-symbolic" "$vm"
                qvm-start "$vm" 2>/dev/null && \
                    log "$vm started" || log "WARN: $vm failed to start"
            fi
        done
        note "dom0 - VMs Ready" "emblem-ok-symbolic" "Selected VMs are running"
    fi
    log "VM selector done, selected: $SELECTED"
else
    log "No zenity or no available VMs for selector"
fi

# ── 6. OpenClaw (check in managed VM) ─────────────────────────────
MANAGED_VM="visyble"
if qvm-check "$MANAGED_VM" --running 2>/dev/null; then
    log "Checking OpenClaw in $MANAGED_VM..."
    # Check proxy health
    qvm-run --pass-io --no-gui "$MANAGED_VM" \
        'curl -sf --max-time 3 http://127.0.0.1:32125/health 2>/dev/null' >/dev/null 2>&1 && {
        log "OpenClaw proxy healthy in $MANAGED_VM"
        note "dom0 - OpenClaw" "network-transmit-receive-symbolic" "Proxy healthy in $MANAGED_VM"
    } || {
        log "OpenClaw proxy not responding in $MANAGED_VM"
    }
fi

# ── 7. Verify ConnectTCP policy ────────────────────────────────────
if [ -f /etc/qubes/policy.d/50-openclaw.policy ]; then
    log "OpenClaw ConnectTCP policy present"
else
    log "No OpenClaw ConnectTCP policy"
    note "dom0 - Missing Policy" "dialog-warning" \
        "Create /etc/qubes/policy.d/50-openclaw.policy for OpenClaw"
fi

# ── 8. Summary notification ───────────────────────────────────────
sleep 2
D="no"; W="no"; V="no"
systemctl is-active --quiet qvm-remote-dom0 2>/dev/null && D="yes"
curl -sf -o /dev/null http://127.0.0.1:9876/api/status 2>/dev/null && W="yes"
qvm-check "$MANAGED_VM" --running 2>/dev/null && V="yes"

SUMMARY="Daemon:$D  Web:$W  VM($MANAGED_VM):$V"
log "Final status: $SUMMARY"
note "dom0 - Setup Complete" "qubes-manager" "$SUMMARY"

log "=== dom0 - Qubes Global Admin autostart done ==="

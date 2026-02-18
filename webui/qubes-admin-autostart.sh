#!/bin/bash
# ┌──────────────────────────────────────────────────────────────────┐
# │ dom0 - Qubes Global Admin - Autostart                           │
# │                                                                  │
# │ Runs at XFCE login. Services are started by systemd (not here). │
# │ This script only handles XFCE-specific setup:                   │
# │   - Workspace names                                              │
# │   - Genmon panel plugin config                                   │
# │   - Opening Firefox with the admin UI                           │
# │   - Optional VM selector dialog                                 │
# │   - Summary notification                                        │
# │                                                                  │
# │ Set QVM_REMOTE_SKIP_SELECTOR=1 to skip the VM selector dialog.  │
# └──────────────────────────────────────────────────────────────────┘

LOG="/tmp/dom0-admin-autostart.log"
: > "$LOG"

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }
note() { notify-send -i "${2:-dialog-information}" -a "dom0 - Admin" "$1" "${3:-}" 2>/dev/null || true; }

log "=== dom0 autostart begin ==="

# Read managed VM from config (same logic as the web server)
MANAGED_VM="$(grep -m1 '^QVM_REMOTE_VMS=' /etc/qubes/remote.conf 2>/dev/null | cut -d= -f2 | tr -d '"'"'" | awk '{print $1}')"
MANAGED_VM="${MANAGED_VM:-unknown}"

# ── 1. Workspaces ──
log "Configuring workspaces"
xfconf-query -c xfwm4 -p /general/workspace_count -s 5 2>/dev/null || true
for attempt in \
    "xfconf-query -c xfwm4 -p /general/workspace_names -n -t string -t string -t string -t string -t string -s Admin -s Code -s Comms -s Media -s Ops" \
    "xfconf-query -c xfwm4 -p /general/workspace_names -s Admin -s Code -s Comms -s Media -s Ops"; do
    eval "$attempt" 2>/dev/null && break
done
log "Workspaces: Admin / Code / Comms / Media / Ops"

# ── 2. Wait for web server (started by systemd, not us) ──
WEB_READY=false
for i in $(seq 1 20); do
    curl -sf -o /dev/null http://127.0.0.1:9876/api/health 2>/dev/null && { WEB_READY=true; break; }
    sleep 1
done
if $WEB_READY; then
    log "Web server responding"
else
    log "WARN: Web server not ready after 20s"
    note "dom0 - Web Admin" "dialog-warning" "Web server slow to start"
fi

# ── 3. Genmon panel plugin ──
GENMON_CMD="/usr/local/bin/qubes-admin-genmon.sh"
if [ -f "$GENMON_CMD" ]; then
    xfconf-query -c xfce4-panel -p /plugins/plugin-19/command -s "$GENMON_CMD" 2>/dev/null || true
    xfconf-query -c xfce4-panel -p /plugins/plugin-19/update-period -s 15 2>/dev/null || true
    xfconf-query -c xfce4-panel -p /plugins/plugin-19/use-label -s false 2>/dev/null || true
    log "Genmon configured (15s)"
fi

# ── 4. Open Firefox ──
if $WEB_READY && command -v firefox >/dev/null 2>&1; then
    sleep 1
    firefox --new-window http://127.0.0.1:9876 &disown
    log "Firefox launched"
fi

# ── 5. VM selector (skip with QVM_REMOTE_SKIP_SELECTOR=1) ──
if [ "${QVM_REMOTE_SKIP_SELECTOR:-0}" != "1" ] && command -v zenity >/dev/null 2>&1 && command -v qvm-ls >/dev/null 2>&1; then
    sleep 3
    AVAILABLE_VMS=$(qvm-ls --halted --fields NAME,CLASS --raw-data 2>/dev/null | \
        grep -v "^dom0\|^sys-\|^default-mgmt\|TemplateVM" | \
        awk -F'|' '{print $1}' | sort)
    RUNNING_VMS=$(qvm-ls --running --fields NAME --raw-list 2>/dev/null | grep -v "^dom0$" || true)

    if [ -n "$AVAILABLE_VMS" ]; then
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
            --text="Select VMs to start." \
            --column="" --column="VM" --column="Status" \
            --width=500 --height=500 --separator="|" \
            "${ZENITY_ARGS[@]}" 2>/dev/null) || SELECTED=""

        if [ -n "$SELECTED" ]; then
            IFS='|' read -ra CHOSEN <<< "$SELECTED"
            for vm in "${CHOSEN[@]}"; do
                vm=$(echo "$vm" | tr -d ' ')
                [ -z "$vm" ] && continue
                if ! qvm-check "$vm" --running 2>/dev/null; then
                    log "Starting VM: $vm"
                    qvm-start "$vm" 2>/dev/null && log "$vm started" || log "WARN: $vm failed"
                fi
            done
        fi
        log "VM selector done: ${SELECTED:-none}"
    fi
fi

# ── 6. Summary ──
sleep 2
D="✗"; W="✗"; V="✗"; T="✗"
systemctl is-active --quiet qvm-remote-dom0 2>/dev/null && D="✓"
curl -sf -o /dev/null http://127.0.0.1:9876/api/health 2>/dev/null && W="✓"
qvm-check "$MANAGED_VM" --running 2>/dev/null && V="✓"
systemctl is-active --quiet qubes-admin-watchdog.timer 2>/dev/null && T="✓"

SUMMARY="Daemon:$D  Web:$W  VM($MANAGED_VM):$V  Timer:$T"
log "Final: $SUMMARY"
note "dom0 - Ready" "qubes-manager" "$SUMMARY"

log "=== dom0 autostart done ==="

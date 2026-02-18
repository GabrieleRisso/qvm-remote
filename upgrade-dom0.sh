#!/bin/bash
# upgrade-dom0.sh -- Upgrade qvm-remote in dom0 from a VM
#
# Usage: bash upgrade-dom0.sh [--gui] [--repo PATH] [--vm VMNAME]
#
# This script:
# 1. Pulls the latest daemon (and optionally GUI) from this VM
# 2. Upgrades them in dom0 (installing files directly)
# 3. Restarts the daemon
# 4. Verifies everything works
#
# Run from the VM: bash upgrade-dom0.sh

REPO="${QVM_REMOTE_REPO:-$(cd "$(dirname "$0")" && pwd)}"
VM="${QVM_REMOTE_VM:-$(hostname -s 2>/dev/null || echo unknown)}"
INSTALL_GUI=0

usage() {
    cat <<'USAGE'
usage: upgrade-dom0.sh [options]

Upgrade qvm-remote in dom0 from a VM using the qvm-remote bridge.

options:
  --gui            also upgrade the dom0 GUI and shared module
  --repo PATH      source repository path (default: script directory)
  --vm VMNAME      VM name as seen by dom0 (default: hostname)
  -h, --help       show this help

environment:
  QVM_REMOTE_REPO  override --repo
  QVM_REMOTE_VM    override --vm
USAGE
}

while [ $# -gt 0 ]; do
    case "$1" in
        --gui)        INSTALL_GUI=1; shift ;;
        --repo)       REPO="$2"; shift 2 ;;
        --vm)         VM="$2"; shift 2 ;;
        -h|--help)    usage; exit 0 ;;
        *)            echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

if [ ! -f "$REPO/dom0/qvm-remote-dom0" ]; then
    echo "ERROR: Cannot find dom0/qvm-remote-dom0 in $REPO"
    echo "  Use --repo to specify the qvm-remote source directory."
    exit 1
fi

echo "=== qvm-remote dom0 upgrade ==="
echo "  repo: $REPO"
echo "  vm:   $VM"
echo "  gui:  $([ $INSTALL_GUI -eq 1 ] && echo yes || echo no)"
echo ""

# 1. Verify daemon is reachable
echo "Checking dom0 connectivity..."
if ! qvm-remote -t 10 ping 2>/dev/null; then
    echo "ERROR: dom0 daemon is not responding."
    echo "  Start it in dom0: systemctl start qvm-remote-dom0"
    exit 1
fi
echo "  OK: dom0 daemon responding"

# 2. Stop current daemon gracefully
echo ""
echo "Stopping current daemon..."
qvm-remote -t 15 'systemctl stop qvm-remote-dom0 2>/dev/null; sleep 1; echo "stopped"' 2>&1 || true
sleep 2

# 3. Push new files to dom0 via tar bundle
echo ""
echo "Pushing updated files to dom0 via tar..."

TAR_FILES="dom0/qvm-remote-dom0 dom0/qvm-remote-dom0.service version"
if [ $INSTALL_GUI -eq 1 ]; then
    TAR_FILES="$TAR_FILES gui/qvm-remote-dom0-gui gui/qubes_remote_ui.py gui/qvm-remote-dom0-gui.desktop"
fi

# Also include webui and supporting files if present
if [ -f "$REPO/webui/qubes-global-admin-web" ]; then
    TAR_FILES="$TAR_FILES webui/qubes-global-admin-web webui/qubes-global-admin-web.service webui/qubes-global-admin-web.desktop"
    for f in webui/qubes-admin-watchdog.service webui/qubes-admin-watchdog.timer \
             webui/qubes-admin-genmon.sh webui/qubes-admin-autostart.sh \
             webui/qubes-admin-autostart.desktop; do
        [ -f "$REPO/$f" ] && TAR_FILES="$TAR_FILES $f"
    done
fi

qvm-remote -t 60 "qvm-run --pass-io --no-gui $VM 'tar czf - -C $REPO $TAR_FILES' | tar xzf - -C /tmp/qvm-remote-upgrade/ && echo 'tar bundle received'"

SRC_SIZE=$(qvm-remote -t 10 "qvm-run --pass-io --no-gui $VM 'tar czf - -C $REPO $TAR_FILES | wc -c'")
DST_SIZE=$(qvm-remote -t 10 "tar czf - -C /tmp/qvm-remote-upgrade $TAR_FILES 2>/dev/null | wc -c")
echo "  Transfer integrity: src=${SRC_SIZE:-?} dst=${DST_SIZE:-?} bytes"

# 4. Install files in dom0
echo ""
echo "Installing in dom0..."

INSTALL_GUI_FLAG=$INSTALL_GUI
cat << INSTALL_SCRIPT | qvm-remote -t 30
set -e
UP=/tmp/qvm-remote-upgrade

if [ -f /usr/bin/qvm-remote-dom0 ]; then
    cp /usr/bin/qvm-remote-dom0 /usr/bin/qvm-remote-dom0.bak
    echo "  backed up current daemon"
fi

cp \$UP/dom0/qvm-remote-dom0 /usr/bin/qvm-remote-dom0
chmod 755 /usr/bin/qvm-remote-dom0
echo "  installed daemon"

cp \$UP/dom0/qvm-remote-dom0.service /etc/systemd/system/qvm-remote-dom0.service
chmod 644 /etc/systemd/system/qvm-remote-dom0.service
systemctl daemon-reload
echo "  installed service file"

mkdir -p /usr/lib/qvm-remote
cp \$UP/version /usr/lib/qvm-remote/version
echo "  installed version"

if [ $INSTALL_GUI_FLAG -eq 1 ]; then
    cp \$UP/gui/qvm-remote-dom0-gui /usr/bin/qvm-remote-dom0-gui
    chmod 755 /usr/bin/qvm-remote-dom0-gui
    echo "  installed GUI"

    cp \$UP/gui/qubes_remote_ui.py /usr/lib/qvm-remote/qubes_remote_ui.py
    chmod 644 /usr/lib/qvm-remote/qubes_remote_ui.py
    echo "  installed shared module"

    mkdir -p /usr/share/applications
    cp \$UP/gui/qvm-remote-dom0-gui.desktop /usr/share/applications/qvm-remote-dom0-gui.desktop
    chmod 644 /usr/share/applications/qvm-remote-dom0-gui.desktop
    echo "  installed desktop file"
fi

# Install web UI if present
if [ -f \$UP/webui/qubes-global-admin-web ]; then
    cp \$UP/webui/qubes-global-admin-web /usr/bin/qubes-global-admin-web
    chmod 755 /usr/bin/qubes-global-admin-web
    echo "  installed web UI"
    if [ -f \$UP/webui/qubes-global-admin-web.service ]; then
        cp \$UP/webui/qubes-global-admin-web.service /etc/systemd/system/qubes-global-admin-web.service
        chmod 644 /etc/systemd/system/qubes-global-admin-web.service
        echo "  installed web UI service"
    fi
    if [ -f \$UP/webui/qubes-global-admin-web.desktop ]; then
        mkdir -p /usr/share/applications
        cp \$UP/webui/qubes-global-admin-web.desktop /usr/share/applications/qubes-global-admin-web.desktop
        chmod 644 /usr/share/applications/qubes-global-admin-web.desktop
        echo "  installed web UI desktop file"
    fi
    # Watchdog timer + service
    for f in qubes-admin-watchdog.service qubes-admin-watchdog.timer; do
        if [ -f \$UP/webui/\$f ]; then
            cp \$UP/webui/\$f /etc/systemd/system/\$f
            chmod 644 /etc/systemd/system/\$f
            echo "  installed \$f"
        fi
    done
    # Genmon and autostart scripts
    mkdir -p /usr/local/bin
    for f in qubes-admin-genmon.sh qubes-admin-autostart.sh; do
        if [ -f \$UP/webui/\$f ]; then
            cp \$UP/webui/\$f /usr/local/bin/\$f
            chmod 755 /usr/local/bin/\$f
            echo "  installed \$f"
        fi
    done
    # Autostart desktop entry
    if [ -f \$UP/webui/qubes-admin-autostart.desktop ]; then
        mkdir -p /etc/xdg/autostart
        cp \$UP/webui/qubes-admin-autostart.desktop /etc/xdg/autostart/qubes-admin-autostart.desktop
        chmod 644 /etc/xdg/autostart/qubes-admin-autostart.desktop
        echo "  installed autostart desktop entry"
    fi
    systemctl daemon-reload
fi

echo ""
echo "Verifying..."
/usr/bin/qvm-remote-dom0 --version

rm -rf /tmp/qvm-remote-upgrade

echo ""
echo "=== Files installed ==="
INSTALL_SCRIPT

# 5. Restart services
echo ""
echo "Restarting services..."
qvm-remote -t 30 'systemctl restart qvm-remote-dom0 qubes-global-admin-web 2>&1; systemctl enable --now qubes-admin-watchdog.timer 2>&1; sleep 2; echo "services restarted"' 2>&1 || true
sleep 3

# 6. Verify
echo ""
echo "Verifying..."
if qvm-remote -t 10 ping 2>/dev/null; then
    echo "  PASS: daemon responding"
else
    echo "  WARN: daemon not responding yet, may need a moment"
fi

qvm-remote -t 10 'qvm-remote-dom0 --version' 2>&1
qvm-remote -t 10 'systemctl is-active qvm-remote-dom0 qubes-global-admin-web qubes-admin-watchdog.timer 2>&1' || true

echo ""
echo "======================================"
echo "  DOM0 UPGRADE COMPLETE"
echo "======================================"

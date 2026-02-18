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
VM="${QVM_REMOTE_VM:-$(hostname 2>/dev/null || echo visyble)}"
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

# 3. Push new files to dom0
echo ""
echo "Pushing updated files to dom0..."

qvm-remote -t 30 "qvm-run --pass-io --no-gui $VM 'cat $REPO/dom0/qvm-remote-dom0' > /tmp/qvm-remote-dom0.new && chmod 755 /tmp/qvm-remote-dom0.new && echo 'daemon pulled'"
qvm-remote -t 15 "qvm-run --pass-io --no-gui $VM 'cat $REPO/dom0/qvm-remote-dom0.service' > /tmp/qvm-remote-dom0.service.new && echo 'service pulled'"
qvm-remote -t 10 "qvm-run --pass-io --no-gui $VM 'cat $REPO/version' > /tmp/qvm-remote-version.new && echo 'version pulled'"

if [ $INSTALL_GUI -eq 1 ]; then
    qvm-remote -t 30 "qvm-run --pass-io --no-gui $VM 'cat $REPO/gui/qvm-remote-dom0-gui' > /tmp/qvm-remote-dom0-gui.new && chmod 755 /tmp/qvm-remote-dom0-gui.new && echo 'gui pulled'"
    qvm-remote -t 30 "qvm-run --pass-io --no-gui $VM 'cat $REPO/gui/qubes_remote_ui.py' > /tmp/qubes_remote_ui.py.new && echo 'shared module pulled'"
    qvm-remote -t 10 "qvm-run --pass-io --no-gui $VM 'cat $REPO/gui/qvm-remote-dom0-gui.desktop' > /tmp/qvm-remote-dom0-gui.desktop.new && echo 'desktop file pulled'"
fi

# 4. Install files in dom0
echo ""
echo "Installing in dom0..."

INSTALL_GUI_FLAG=$INSTALL_GUI
cat << INSTALL_SCRIPT | qvm-remote -t 30
set -e

if [ -f /usr/bin/qvm-remote-dom0 ]; then
    cp /usr/bin/qvm-remote-dom0 /usr/bin/qvm-remote-dom0.bak
    echo "  backed up current daemon"
fi

cp /tmp/qvm-remote-dom0.new /usr/bin/qvm-remote-dom0
chmod 755 /usr/bin/qvm-remote-dom0
echo "  installed daemon"

cp /tmp/qvm-remote-dom0.service.new /etc/systemd/system/qvm-remote-dom0.service
chmod 644 /etc/systemd/system/qvm-remote-dom0.service
systemctl daemon-reload
echo "  installed service file"

if [ $INSTALL_GUI_FLAG -eq 1 ]; then
    cp /tmp/qvm-remote-dom0-gui.new /usr/bin/qvm-remote-dom0-gui
    chmod 755 /usr/bin/qvm-remote-dom0-gui
    echo "  installed GUI"

    mkdir -p /usr/lib/qvm-remote
    cp /tmp/qubes_remote_ui.py.new /usr/lib/qvm-remote/qubes_remote_ui.py
    chmod 644 /usr/lib/qvm-remote/qubes_remote_ui.py
    echo "  installed shared module"

    cp /tmp/qvm-remote-version.new /usr/lib/qvm-remote/version
    echo "  installed version"

    mkdir -p /usr/share/applications
    cp /tmp/qvm-remote-dom0-gui.desktop.new /usr/share/applications/qvm-remote-dom0-gui.desktop
    chmod 644 /usr/share/applications/qvm-remote-dom0-gui.desktop
    echo "  installed desktop file"
fi

echo ""
echo "Verifying..."
/usr/bin/qvm-remote-dom0 --version

rm -f /tmp/qvm-remote-dom0.new /tmp/qvm-remote-dom0.service.new \
      /tmp/qvm-remote-version.new /tmp/qvm-remote-dom0-gui.new \
      /tmp/qubes_remote_ui.py.new /tmp/qvm-remote-dom0-gui.desktop.new

echo ""
echo "=== Files installed ==="
INSTALL_SCRIPT

# 5. Restart daemon
echo ""
echo "Restarting daemon..."
qvm-remote -t 15 'systemctl start qvm-remote-dom0; sleep 2; echo "started"' 2>&1 || true
sleep 3

# 6. Verify
echo ""
echo "Verifying new daemon..."
if qvm-remote -t 10 ping 2>/dev/null; then
    echo "  PASS: daemon responding"
else
    echo "  WARN: daemon not responding yet, may need a moment"
fi

qvm-remote -t 10 'qvm-remote-dom0 --version' 2>&1

echo ""
echo "======================================"
echo "  DOM0 UPGRADE COMPLETE"
echo "======================================"

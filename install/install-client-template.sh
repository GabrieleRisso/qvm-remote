#!/bin/bash
# install-client-template.sh -- Install qvm-remote client into a template VM
#
# Usage (from dom0):
#   bash install-client-template.sh TEMPLATE_NAME [--source VM]
#
# This pushes the qvm-remote client binary from a source VM (or dom0)
# into a running template, then shuts it down so all AppVMs inherit the client.

set -euo pipefail

TEMPLATE=""
SOURCE_VM=""
CLIENT_PATH="/usr/bin/qvm-remote"

usage() {
    cat <<'EOF'
usage: install-client-template.sh TEMPLATE [options]

Install the qvm-remote client into a template VM from dom0.

arguments:
  TEMPLATE         Template VM name (e.g. fedora-42-xfce, archlinux)

options:
  --source VM      Source VM containing the client binary (default: use dom0 copy)
  -h, --help       Show this help

After installation and template shutdown, all AppVMs based on this
template will have /usr/bin/qvm-remote available on next boot.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --source)  SOURCE_VM="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        -*)        echo "Unknown option: $1"; usage; exit 1 ;;
        *)         TEMPLATE="$1"; shift ;;
    esac
done

if [ -z "$TEMPLATE" ]; then
    echo "ERROR: Template name required"
    usage
    exit 1
fi

echo "=== Install qvm-remote client in template: $TEMPLATE ==="

# Start template if needed
if ! qvm-check "$TEMPLATE" --running 2>/dev/null; then
    echo "Starting template..."
    qvm-start "$TEMPLATE"
    sleep 3
else
    echo "Template already running"
fi

# Determine source of the client binary
if [ -n "$SOURCE_VM" ]; then
    echo "Pushing client from VM: $SOURCE_VM"
    qvm-run --pass-io --no-gui "$SOURCE_VM" "cat $CLIENT_PATH" | \
        qvm-run --pass-io --no-gui "$TEMPLATE" "sudo tee /usr/bin/qvm-remote > /dev/null"
elif [ -f "$CLIENT_PATH" ]; then
    echo "Pushing client from dom0: $CLIENT_PATH"
    cat "$CLIENT_PATH" | \
        qvm-run --pass-io --no-gui "$TEMPLATE" "sudo tee /usr/bin/qvm-remote > /dev/null"
else
    echo "ERROR: No qvm-remote client found in dom0 or source VM"
    exit 1
fi

# Set permissions
qvm-run --pass-io --no-gui "$TEMPLATE" "sudo chmod 755 /usr/bin/qvm-remote"
echo "Installed /usr/bin/qvm-remote"

# Verify
VER=$(qvm-run --pass-io --no-gui "$TEMPLATE" "qvm-remote --version 2>&1" || echo "unknown")
echo "Version: $VER"

# Shut down template
echo "Shutting down template..."
qvm-shutdown --wait --timeout 60 "$TEMPLATE" || echo "Warning: template may still be running"

echo ""
echo "=== Done ==="
echo "All AppVMs based on $TEMPLATE will have qvm-remote on next boot."
echo "To connect a VM: run 'qvm-remote key gen' in the VM, then authorize in dom0."

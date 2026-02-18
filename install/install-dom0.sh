#!/bin/bash
# install-dom0.sh — Install qvm-remote-dom0 from a VM into dom0.
#
# Run in dom0:
#   qvm-run --pass-io --no-gui VMNAME \
#       'cat /path/to/qvm-remote/install/install-dom0.sh' \
#       > /tmp/install-dom0.sh
#   bash /tmp/install-dom0.sh VMNAME
#
# Non-interactive:
#   bash /tmp/install-dom0.sh --yes VMNAME

PROGNAME="install-dom0.sh"
FORCE=0
REMOTE_VM=""

# ── Helpers ────────────────────────────────────────────────────────

die()  { echo "$PROGNAME: error: $*" >&2; exit 1; }
warn() { echo "$PROGNAME: warning: $*" >&2; }
info() { echo "  $*"; }

# ── Argument parsing ──────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        -y|--yes|--force) FORCE=1; shift ;;
        -h|--help)
            echo "usage: $PROGNAME [--yes] <vm-name>"
            echo ""
            echo "Install qvm-remote-dom0 by pulling files from a VM."
            echo ""
            echo "  --yes, -y    Skip interactive confirmation"
            echo "  --help, -h   Show this help"
            exit 0 ;;
        -*) die "unknown option: $1" ;;
        *)  REMOTE_VM="$1"; shift ;;
    esac
done

# ── Validate ──────────────────────────────────────────────────────

[[ -n "$REMOTE_VM" ]] || die "usage: $PROGNAME [--yes] <vm-name>"

if [[ "$(hostname 2>/dev/null)" != "dom0" ]]; then
    die "this script must run in dom0 (current host: $(hostname 2>/dev/null || echo unknown))"
fi

if ! qvm-check "$REMOTE_VM" >/dev/null 2>&1; then
    die "VM '$REMOTE_VM' does not exist"
fi

# ── Security warning + confirmation ──────────────────────────────

cat <<'EOF'

  ┌──────────────────────────────────────────────────────────────┐
  │  WARNING: qvm-remote grants a VM full root-level command     │
  │  execution in dom0. This breaks the Qubes security model.    │
  │                                                              │
  │  Only proceed if you understand and accept this risk.        │
  └──────────────────────────────────────────────────────────────┘

EOF

if (( FORCE )); then
    echo "Non-interactive mode (--yes): proceeding."
elif [[ -t 0 ]]; then
    read -rp "Type 'yes' to install qvm-remote-dom0 for VM '$REMOTE_VM': " answer
    [[ "$answer" == "yes" ]] || { echo "Aborted."; exit 1; }
else
    die "stdin is not a terminal. Use --yes for non-interactive install."
fi

echo ""

# ── Pull files from VM ────────────────────────────────────────────

vm_cat() {
    qvm-run --pass-io --no-gui --no-autostart "$REMOTE_VM" "cat '$1'" 2>/dev/null
}

echo "Pulling qvm-remote-dom0 from $REMOTE_VM ..."
if ! vm_cat /usr/bin/qvm-remote-dom0 > /tmp/qvm-remote-dom0.tmp; then
    rm -f /tmp/qvm-remote-dom0.tmp
    die "failed to fetch /usr/bin/qvm-remote-dom0 from $REMOTE_VM"
fi
if [[ ! -s /tmp/qvm-remote-dom0.tmp ]]; then
    rm -f /tmp/qvm-remote-dom0.tmp
    die "fetched empty file — is qvm-remote installed in $REMOTE_VM? (sudo make install-vm)"
fi

echo "Pulling qvm-remote-dom0.service from $REMOTE_VM ..."
GOT_SERVICE=0
for svc_path in \
    /usr/lib/systemd/system/qvm-remote-dom0.service \
    /etc/systemd/system/qvm-remote-dom0.service \
    /lib/systemd/system/qvm-remote-dom0.service; do
    if vm_cat "$svc_path" > /tmp/qvm-remote-dom0.service.tmp 2>/dev/null; then
        if [[ -s /tmp/qvm-remote-dom0.service.tmp ]]; then
            GOT_SERVICE=1
            break
        fi
    fi
done
if (( ! GOT_SERVICE )); then
    rm -f /tmp/qvm-remote-dom0.service.tmp
    die "failed to fetch qvm-remote-dom0.service from $REMOTE_VM"
fi

# ── Install ──────────────────────────────────────────────────────

echo "Installing to dom0 ..."

install -m 0755 /tmp/qvm-remote-dom0.tmp /usr/bin/qvm-remote-dom0 ||
    die "failed to install /usr/bin/qvm-remote-dom0"

install -m 0644 /tmp/qvm-remote-dom0.service.tmp /etc/systemd/system/qvm-remote-dom0.service ||
    die "failed to install qvm-remote-dom0.service"

rm -f /tmp/qvm-remote-dom0.tmp /tmp/qvm-remote-dom0.service.tmp

mkdir -p /etc/qubes
if [[ ! -f /etc/qubes/remote.conf ]]; then
    printf 'QVM_REMOTE_VMS=%s\n' "$REMOTE_VM" > /etc/qubes/remote.conf
    chmod 0600 /etc/qubes/remote.conf
    info "Created /etc/qubes/remote.conf (QVM_REMOTE_VMS=$REMOTE_VM)"
else
    info "/etc/qubes/remote.conf exists — not overwriting"
    info "Verify it contains: QVM_REMOTE_VMS=$REMOTE_VM"
fi

# ── Key exchange ─────────────────────────────────────────────────

echo ""
echo "Fetching auth key from $REMOTE_VM ..."

VM_USER="${QVM_REMOTE_VM_USER:-user}"

vm_key=""
for key_path in \
    "/home/${VM_USER}/.qvm-remote/auth.key" \
    "/home/${VM_USER}/.qubes-remote/auth.key"; do
    vm_key=$(vm_cat "$key_path" 2>/dev/null) || true
    vm_key=$(printf '%s' "$vm_key" | tr -d '[:space:]')
    if [[ "$vm_key" =~ ^[0-9a-f]{64}$ ]]; then
        break
    fi
    vm_key=""
done

if [[ -n "$vm_key" ]]; then
    mkdir -p /etc/qubes/remote.d
    chmod 0700 /etc/qubes/remote.d
    printf '%s' "$vm_key" > "/etc/qubes/remote.d/${REMOTE_VM}.key"
    chmod 0600 "/etc/qubes/remote.d/${REMOTE_VM}.key"
    info "Auth key imported for '$REMOTE_VM'."
else
    warn "No key found in VM. Generate one:"
    info "(in $REMOTE_VM) qvm-remote key gen"
    info "(in dom0)       qvm-remote-dom0 authorize $REMOTE_VM <key>"
fi

# ── Start ────────────────────────────────────────────────────────

systemctl daemon-reload

if systemctl start qvm-remote-dom0 2>/dev/null; then
    echo ""
    echo "qvm-remote-dom0 is installed and running."
else
    echo ""
    warn "Service failed to start (VM may not be configured yet)."
    echo "Start manually after configuring:"
    echo "  systemctl start qvm-remote-dom0"
fi

echo "The service is TRANSIENT — it will stop on next reboot."
echo ""
echo "Verify from $REMOTE_VM:"
echo "  qvm-remote ping"
echo "  qvm-remote hostname"
echo ""
echo "To stop:   systemctl stop qvm-remote-dom0"
echo "To enable: qvm-remote-dom0 enable"

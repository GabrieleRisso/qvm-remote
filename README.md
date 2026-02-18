# qvm-remote

Execute commands in Qubes OS dom0 from one or more VMs.

**SSH for dom0** — `qvm-remote qvm-ls` is to dom0 what `ssh host ls` is
to a remote server.  Written in Python following official `qvm-*` tool
conventions.

> **Warning:** This tool grants VMs the ability to execute arbitrary commands
> in dom0 with root privileges.  This **breaks the Qubes security model** by
> design.  Only use it on machines you fully control.

## How it works

```
  VM (visyble)                            dom0
 ┌────────────────────┐              ┌──────────────────────┐
 │                    │              │                      │
 │ qvm-remote         │  qvm-run     │ qvm-remote-dom0      │
 │   "qvm-ls"        │◄────────────►│   polls queue        │
 │       │            │  --pass-io   │   verifies HMAC key  │
 │       ▼            │              │   executes command   │
 │ ~/.qvm-remote/     │              │   returns results    │
 │   queue/           │              │                      │
 │   auth.key         │              │ /etc/qubes/remote.d/ │
 │   history/         │              │   visyble.key        │
 │   audit.log        │              │   dev-vm.key         │
 └────────────────────┘              └──────────────────────┘
```

1. VM client writes a command + HMAC-SHA256 auth token to `~/.qvm-remote/queue/pending/`
2. Dom0 daemon polls authorized VMs via `qvm-run --pass-io --no-autostart`
3. Verifies the HMAC token against the VM's registered key
4. Fetches, validates, and executes the command with `bash`
5. Writes stdout, stderr, and exit code back to the VM
6. VM client outputs results and archives everything to `history/`

Every command is logged with timestamp, duration, and exit code on both sides.

## Quick start

### VM side

```bash
sudo make install-vm
qvm-remote key gen         # generates 256-bit auth key
```

### Dom0 side

From a **dom0 terminal**, use the installer:

```bash
VM=visyble
qvm-run --pass-io --no-gui $VM \
    'cat /path/to/qvm-remote/install/install-dom0.sh' \
    > /tmp/install-dom0.sh
bash /tmp/install-dom0.sh $VM
```

Or install manually:

```bash
VM=visyble

# Pull daemon
qvm-run --pass-io --no-gui $VM \
    'cat /usr/bin/qvm-remote-dom0' > /usr/bin/qvm-remote-dom0
chmod +x /usr/bin/qvm-remote-dom0

# Pull service file
qvm-run --pass-io --no-gui $VM \
    'cat /path/to/dom0/qvm-remote-dom0.service' \
    > /etc/systemd/system/qvm-remote-dom0.service

# Configure
echo "QVM_REMOTE_VMS=$VM" > /etc/qubes/remote.conf
chmod 0600 /etc/qubes/remote.conf

# Authorize the VM's key
KEY=$(qvm-run --pass-io --no-gui $VM 'cat ~/.qvm-remote/auth.key')
qvm-remote-dom0 authorize $VM $KEY

# Start
systemctl daemon-reload
systemctl start qvm-remote-dom0
```

### Verify

```bash
qvm-remote ping       # "qvm-remote-dom0 is responding."
qvm-remote hostname   # "dom0"
```

## Usage

```bash
# Run any command in dom0 (like ssh)
qvm-remote qvm-ls
qvm-remote 'qvm-prefs work memory 4096'
qvm-remote -t 60 'qvm-shutdown --wait work'
echo 'xl info' | qvm-remote
qvm-remote < deploy.sh

# Key management
qvm-remote key gen              # generate + store key
qvm-remote key show             # print key for dom0
qvm-remote key import KEY       # import a hex key

# Diagnostics
qvm-remote ping                 # health check
qvm-remote log                  # last 20 audit entries
qvm-remote log 50               # last 50 entries
qvm-remote history              # last 10 commands
```

### Dom0 daemon

```bash
# Key management
qvm-remote-dom0 authorize VM KEY  # register a VM
qvm-remote-dom0 revoke VM         # remove a VM
qvm-remote-dom0 keys              # list authorized VMs

# Service control
systemctl start qvm-remote-dom0          # this session only
journalctl -u qvm-remote-dom0            # view logs
qvm-remote-dom0 enable                   # autostart (risk prompt)
qvm-remote-dom0 disable                  # stop and disable
qvm-remote-dom0 --once                   # process queue once
qvm-remote-dom0 --dry-run --once         # preview without executing
```

## Authentication

qvm-remote uses **256-bit HMAC-SHA256 key authentication** — analogous to
SSH keys.  Each VM has its own unique key.  No passwords, PINs, or retries.

### How it works

- Each VM holds a 256-bit (64-hex-char) secret key in `~/.qvm-remote/auth.key`
- Dom0 holds a copy in `/etc/qubes/remote.d/<vm-name>.key`
- Every command carries `HMAC-SHA256(key, command_id)` as a token
- Dom0 recomputes the HMAC and verifies before executing
- Invalid tokens are silently rejected and logged

### Why this is secure

- **256-bit key**: 2^256 possible keys makes brute force mathematically impossible
- **Per-command HMAC**: each token is unique — replay is useless
- **Key never transmitted**: only the HMAC token travels; key lives on disk (mode 0600)
- **No retries/lockout needed**: with 256 bits, even unlimited attempts are futile
- **Per-VM isolation**: compromising one VM's key does not affect others

## Multi-VM support

Dom0 can poll multiple VMs simultaneously:

```bash
# /etc/qubes/remote.conf
QVM_REMOTE_VMS="visyble dev-vm staging"
```

Each VM must have its own key:

```bash
qvm-remote-dom0 authorize visyble <key1>
qvm-remote-dom0 authorize dev-vm <key2>
qvm-remote-dom0 authorize staging <key3>
```

## Configuration

`/etc/qubes/remote.conf` in dom0:

```bash
QVM_REMOTE_VMS="visyble dev-vm"
```

Per-VM keys in `/etc/qubes/remote.d/`:

```
/etc/qubes/remote.d/
├── visyble.key     # 64-hex-char key (mode 0600)
└── dev-vm.key      # 64-hex-char key (mode 0600)
```

The VM client requires no configuration beyond the key file.

## Web Admin Panel (new in v1.1)

Air-gapped web admin for Qubes OS dom0. Zero external dependencies -- pure
Python stdlib HTTP server on `127.0.0.1:9876`. No internet required.

### Install

```bash
# From dom0 (using upgrade script from a VM):
bash upgrade-dom0.sh

# Or manually:
sudo make install-web
```

### Enable and start

```bash
systemctl enable --now qvm-remote-dom0 qubes-global-admin-web qubes-admin-watchdog.timer
```

All three services survive reboots. The watchdog timer checks health every 60s
and auto-restarts failed services.

### Access

```bash
firefox http://127.0.0.1:9876
```

### XFCE genmon panel plugin

Add a Generic Monitor plugin to the XFCE panel, then configure:

- Command: `/usr/local/bin/qubes-admin-genmon.sh`
- Period: `15` seconds

The plugin shows a green/yellow/red dot for service health. Clicking opens the
web UI or restarts services.

### XFCE autostart

The autostart desktop entry (`/etc/xdg/autostart/qubes-admin-autostart.desktop`)
runs at XFCE login and configures workspaces, genmon, and opens Firefox.
Services are started by systemd, not the autostart script.

To skip the VM selector dialog at login:

```bash
QVM_REMOTE_SKIP_SELECTOR=1
```

### Features

- **Dashboard**: daemon status, service control, self-heal diagnostics
- **Execute**: run dom0 commands with streaming output
- **VM Tools**: authorize/revoke keys, start/stop/pause VMs, run commands in VMs
- **Files**: push/pull between dom0 and VMs
- **Backup**: system + config backups
- **Log**: daemon log viewer, VM logs, autostart logs
- **This Device**: system hardware and Xen info
- **OpenClaw**: manage multi-agent AI containers across VMs
- **Global Config**: Qubes OS global preferences
- **qvm-remote**: connection map, queue management, command history
- **Policy enforcement**: restrict dom0 modifications, per-VM access levels,
  blocked commands list (save-and-apply workflow, like Qubes Global Config)

### Architecture

```
dom0
├── qvm-remote-dom0.service       daemon (polls VMs for commands)
├── qubes-global-admin-web.service  web UI on 127.0.0.1:9876
├── qubes-admin-watchdog.timer     health check every 60s
├── qubes-admin-genmon.sh          XFCE panel status indicator
└── qubes-admin-autostart.sh       XFCE login setup
```

### E2E testing

```bash
# From dom0:
bash /tmp/test-dom0-e2e.sh

# Or from a VM (push + run):
bash upgrade-dom0.sh   # ensures test is deployed
qvm-remote 'bash /tmp/test-dom0-e2e.sh'
```

### RPM packaging

```bash
make docker-rpm   # builds qvm-remote-webui-dom0 RPM in container
```

## GTK Admin Panel (new in v1.1)

Native GTK admin panel for dom0 with sidebar navigation.

```bash
# Install GTK admin
sudo make install-gui2

# Launch from dom0
qubes-global-admin
```

Includes desktop entries and systemd service for autostart.

## GUI (optional)

GTK3-based graphical interfaces for both sides.  Requires `python3-gobject`
and `gtk3`.

```bash
# VM: install CLI + GUI
sudo make install-vm
sudo make install-gui-vm

# Dom0: install daemon + GUI
sudo make install-dom0
sudo make install-gui-dom0
```

**VM GUI** (`qvm-remote-gui`): Execute commands, file transfers, backup/restore,
command history, key management, audit log viewer.

**Dom0 GUI** (`qvm-remote-dom0-gui`): Dashboard, VM authorization, file push,
backup management, log viewer.

Both follow Qubes OS desktop conventions with `.desktop` entries.

## Building

### Docker/Podman build (recommended for non-Fedora hosts)

```bash
make docker-rpm   # builds in Fedora 41 container
```

### Local build

```bash
make dist    # create source tarballs
make rpm     # build RPMs (requires rpmbuild)
```

### Arch Linux

```bash
cd pkg && makepkg -si          # CLI only
cd pkg && makepkg -si -p PKGBUILD-gui   # GUI
```

### Debian/Ubuntu

```bash
make deb
```

### Qubes Builder v2

Add to your `builder.yml`:

```yaml
components:
  - qvm-remote:
      url: https://github.com/USER/qvm-remote.git
      branch: main
      verification-mode: insecure-skip-checking
```

Build: `./qb -c qvm-remote package fetch prep build`

### Testing

```bash
make check              # syntax-check all scripts
make test               # unit tests (CLI + GUI, any machine)
make docker-test        # RPM install test (Fedora 41 container)
make dom0-test          # dom0 simulation E2E (73 assertions)
make arch-test          # Arch Linux client test (36 assertions)
make gui-test           # GUI build + import test
make gui-integration-test  # GUI Xvfb integration test
make backup-e2e-test    # backup/restore E2E test
make all-test           # run ALL of the above
```

### Upgrading dom0

```bash
bash upgrade-dom0.sh              # upgrade daemon only
bash upgrade-dom0.sh --gui        # upgrade daemon + GUI
bash upgrade-dom0.sh --help       # see all options
```

## Security

### What this tool does

It grants authorized VMs **full root-level command execution in dom0**.

### Protections

**HMAC-SHA256 key auth.** 256-bit per-VM keys.  Mathematically impossible
to brute-force.  Python `hmac` module — compatible with openssl for
cross-version interop.

**Transient by default.** Service stops on reboot.  `enable` requires
typing "yes" to an explicit risk warning.

**Multi-VM isolation.** Each VM has its own key.  Revoking one doesn't
affect others.

**No VM auto-start.** Uses `qvm-run --no-autostart` — never starts VMs
as a side effect.

**Full audit trail.** Both sides log every command:
- VM: `~/.qvm-remote/audit.log`
- Dom0: `/var/log/qubes/qvm-remote.log`
- Full output: `~/.qvm-remote/history/YYYY-MM-DD/`

**Input validation.** Rejects empty, oversized (>1 MiB), and binary commands.

**Output limits.** Stdout/stderr truncated at 10 MiB.

### Recommendations

- Use dedicated, minimal VMs with no network access.
- Stop the service when not in use.
- Review `journalctl -u qvm-remote-dom0` periodically.
- Rotate keys periodically (`key gen` + `authorize`).

## Migrating from qubes-remote (v0.x)

v1.0.0 renames the project and rewrites everything in Python:

| v0.x (bash)             | v1.0.0 (Python)          |
|-------------------------|--------------------------|
| `qubes-remote`          | `qvm-remote`             |
| `qubes-remote-dom0`     | `qvm-remote-dom0`        |
| `~/.qubes-remote/`      | `~/.qvm-remote/`         |
| `--gen-key`             | `key gen`                |
| `--show-key`            | `key show`               |
| `--import-key KEY`      | `key import KEY`         |
| `--authorize VM KEY`    | `authorize VM KEY`       |
| `--revoke VM`           | `revoke VM`              |
| `--list-keys`           | `keys`                   |
| `QUBES_REMOTE_VMS=`     | `QVM_REMOTE_VMS=`        |

Data directories migrate automatically on first run.  RPM packages use
`Obsoletes:` for clean upgrades.  Config variables are backward compatible.

## Requirements

- Qubes OS 4.2+ (tested on 4.3)
- Python 3.8+ in both dom0 and VMs

## Project structure

```
qvm-remote/
├── vm/
│   └── qvm-remote                   VM client (Python)
├── dom0/
│   ├── qvm-remote-dom0              Dom0 daemon (Python)
│   └── qvm-remote-dom0.service      Systemd unit
├── webui/
│   ├── qubes-global-admin-web          Web admin panel (stdlib only)
│   ├── qubes-global-admin-web.service  Systemd unit
│   ├── qubes-global-admin-web.desktop  Desktop entry
│   ├── qubes-admin-watchdog.service    Health check oneshot
│   ├── qubes-admin-watchdog.timer      60s health check timer
│   ├── qubes-admin-genmon.sh           XFCE panel status plugin
│   ├── qubes-admin-autostart.sh        XFCE login setup
│   ├── qubes-admin-autostart.desktop   Autostart desktop entry
│   └── devilspie2.lua                  Window management rules
├── gui2/
│   ├── qubes-global-admin           GTK admin panel (978 lines)
│   ├── qubes-global-admin-dom0      Dom0 admin daemon (542 lines)
│   ├── qubes_admin_ui.py            Shared UI components
│   └── *.desktop                    Desktop entries
├── gui/
│   ├── qubes_remote_ui.py           Shared GTK3 UI library
│   ├── qvm-remote-gui               VM GUI (GTK3)
│   ├── qvm-remote-dom0-gui          Dom0 GUI (GTK3)
│   └── *.desktop                    Desktop entries
├── install/
│   ├── install-dom0.sh              Dom0 shell installer
│   └── install-client-template.sh   Install client in template VMs
├── etc/
│   └── qubes-remote.conf            Config template
├── rpm_spec/
│   ├── qvm-remote-dom0.spec         Dom0 CLI RPM
│   ├── qvm-remote-vm.spec           VM CLI RPM
│   ├── qvm-remote-gui-dom0.spec     Dom0 GUI RPM
│   ├── qvm-remote-gui-vm.spec       VM GUI RPM
│   └── qvm-remote-webui-dom0.spec   Dom0 Web Admin RPM
├── pkg/
│   ├── PKGBUILD                     Arch Linux CLI package
│   └── PKGBUILD-gui                 Arch Linux GUI package
├── debian/                           Debian packaging
├── salt/                             SaltStack formula
├── test/
│   ├── test_qvm_remote.py           CLI unit tests (92 tests)
│   ├── test_gui.py                  GUI unit tests
│   ├── test_gui_wiring.py           GUI wiring tests
│   ├── test_gui_integration.py      GUI integration tests
│   ├── test_backup_e2e.py           Backup E2E tests
│   ├── test-dom0-e2e.sh             Dom0 web admin E2E (24 tests)
│   ├── dom0-sim/                    Mock dom0 environment
│   └── Dockerfile.*                 Container test harnesses
├── .github/workflows/ci.yml         GitHub Actions CI
├── .qubesbuilder                     Qubes Builder v2 config
├── Makefile.builder                  Qubes Builder v2 Makefile
├── Dockerfile.build                  Fedora 41 build container
├── upgrade-dom0.sh                   Dom0 upgrade script
├── Makefile
├── version
└── CONTRIBUTING.md
```

## Contributing

- Run `make test` before submitting.
- Test on both VM and dom0.
- Follow Qubes OS coding conventions (Python, `qvm-*` CLI style).

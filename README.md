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
make test    # run full test suite
make check   # syntax-check scripts only
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
├── dom0/
│   ├── qvm-remote-dom0           Dom0 daemon (Python)
│   └── qvm-remote-dom0.service   Systemd unit
├── vm/
│   └── qvm-remote                VM client (Python)
├── etc/
│   └── qubes-remote.conf         Config template
├── rpm_spec/
│   ├── qvm-remote-dom0.spec      Dom0 RPM spec
│   └── qvm-remote-vm.spec        VM RPM spec
├── install/
│   └── install-dom0.sh           Dom0 shell installer
├── salt/
│   ├── qvm-remote/init.sls       Salt state
│   ├── qvm-remote.top            Salt top file
│   └── pillar/qvm-remote.sls     Salt pillar
├── test/
│   └── test_qvm_remote.py        Python test suite
├── .qubesbuilder                  Qubes Builder v2 config
├── Dockerfile.build               Fedora 41 build container
├── Makefile
├── version
└── README.md
```

## Contributing

- Run `make test` before submitting.
- Test on both VM and dom0.
- Follow Qubes OS coding conventions (Python, `qvm-*` CLI style).

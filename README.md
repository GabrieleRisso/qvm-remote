# qvm-remote

**SSH for Qubes OS dom0** — authenticated remote command execution from VMs.

`qvm-remote qvm-ls` is to dom0 what `ssh host ls` is to a remote server. Written in pure Python (stdlib only) following official `qvm-*` tool conventions.

> **Paper:** A full academic paper with formal protocol analysis, HMAC-SHA256 security proofs, and TikZ diagrams is available in [`paper/`](paper/).

[![CI](https://github.com/GabrieleRisso/qvm-remote/actions/workflows/ci.yml/badge.svg)](https://github.com/GabrieleRisso/qvm-remote/actions)
[![License](https://img.shields.io/badge/license-GPL--2.0-blue.svg)](LICENSE)

> **Warning:** This tool grants VMs the ability to execute arbitrary commands
> in dom0 with root privileges. This **intentionally weakens the Qubes security model**.
> Only use it on machines you fully control.

---

## How It Works — The Pull Model

The fundamental design principle: **dom0 initiates every I/O operation**. The VM never pushes data to dom0 — it only writes to its own local filesystem. dom0 *chooses* to read it.

```
  VM (visyble)                              dom0 (privileged)
 ┌──────────────────────┐                 ┌──────────────────────────┐
 │                      │   qvm-run       │                          │
 │  qvm-remote          │  --pass-io      │  qvm-remote-dom0         │
 │    "qvm-ls"          │◄───────────────►│    polls queue           │
 │        │             │  (dom0 → VM)    │    verifies HMAC-SHA256  │
 │        ▼             │                 │    executes in sandbox   │
 │  ~/.qvm-remote/      │                 │    returns results       │
 │    queue/            │                 │                          │
 │      pending/        │                 │  /etc/qubes/remote.d/    │
 │      running/        │                 │    visyble.key           │
 │      results/        │                 │    dev-vm.key            │
 │    auth.key          │                 │                          │
 │    audit.log         │                 │  /var/log/qubes/         │
 │    history/          │                 │    qvm-remote.log        │
 └──────────────────────┘                 └──────────────────────────┘
```

### Protocol Lifecycle

1. **Enqueue** (VM): Client generates unique command ID (`timestamp-pid-random8`), writes command to `pending/<cid>` and HMAC-SHA256 token to `pending/<cid>.auth`
2. **Poll** (dom0): Daemon lists `pending/` via `qvm-run --pass-io --no-autostart`
3. **Authenticate** (dom0): Recomputes HMAC, verifies with `hmac.compare_digest` (constant-time)
4. **Execute** (dom0): Writes command to 0700 work file, runs with `bash` under 300s timeout
5. **Return** (dom0): Writes `.out`, `.err`, `.exit`, `.meta` to `results/`, appends audit log

```
 Command ID structure:
 ┌──────────────────┬──────┬──────────┐
 │  20260218-143022  │ 1234 │ a1b2c3d4 │
 │    timestamp      │ PID  │ random   │
 └──────────────────┴──────┴──────────┘
                                ↑
                    secrets.token_hex(4)
```

## Defense in Depth — Five Security Layers

Each layer provides independent protection. Breaching one does not compromise the others.

```
┌──────────────────────────────────────────────┐
│  Layer 5: Transient by Default               │  Dies on reboot unless explicitly enabled
├──────────────────────────────────────────────┤
│  Layer 4: Dual-Sided Audit Trail             │  dom0 + VM logs, full history archive
├──────────────────────────────────────────────┤
│  Layer 3: Execution Sandboxing               │  0700 tmpdir, 300s timeout, bash only
├──────────────────────────────────────────────┤
│  Layer 2: Input Validation                   │  No empty/binary/oversized commands
├──────────────────────────────────────────────┤
│  Layer 1: HMAC-SHA256 Authentication         │  256-bit per-VM keys, per-command tokens
└──────────────────────────────────────────────┘
```

### Threat Model

| Attack | Layer | Mitigation |
|--------|-------|------------|
| Forge a command | L1 | HMAC-SHA256 — 2^256 key space (3.7 × 10^57 years to brute-force) |
| Replay a command | L1 | Unique command ID + dom0 deletes after processing |
| Binary injection | L2 | `has_binary_content()` rejects null/control chars |
| Command bomb (>1 MiB) | L2 | Size limit enforced before write |
| Fork bomb / resource exhaustion | L3 | 300s execution timeout |
| Cross-VM attack | L1 | Per-VM keys — compromising VM A has no effect on VM B |
| Undetected abuse | L4 | Dual-sided audit + web log viewer |
| Forgotten service running | L5 | Transient by default; `enable` requires typing "yes" |

## Authentication

qvm-remote uses **256-bit HMAC-SHA256 key authentication** — analogous to SSH keys. Each VM has its own unique key. No passwords, PINs, or retries.

### How It Works

- Each VM holds a 256-bit (64-hex-char) secret key in `~/.qvm-remote/auth.key` (mode 0600)
- Dom0 holds a copy in `/etc/qubes/remote.d/<vm>.key` (mode 0600, directory 0700)
- Every command carries `HMAC-SHA256(key, command_id)` as a token
- Dom0 recomputes and verifies with `hmac.compare_digest` (constant-time — immune to timing attacks)
- Invalid tokens are silently rejected and logged (`AUTH-FAIL`)

### Why This Is Secure

| Property | Guarantee |
|----------|-----------|
| **Forgery resistance** | Probability ≤ 2^-256 per attempt. Key never transmitted. |
| **Replay resistance** | Each command ID includes cryptographic randomness + timestamp. Processed exactly once. |
| **Cross-VM isolation** | Per-VM keys. Compromising one has zero effect on others. |
| **Timing resistance** | `hmac.compare_digest` runs in constant time. |
| **Brute-force immunity** | At 10^12 attempts/sec: 3.7 × 10^57 years. No lockout needed. |

## Performance

The framework adds ~48ms overhead per command (polling + HMAC + file I/O). The rest is the command's own execution time.

| Command | Latency | Overhead |
|---------|---------|----------|
| `echo ok` (baseline) | 48ms | — |
| `hostname` | 52ms | +4ms |
| `qvm-ls` | 310ms | +262ms |
| `qvm-ls --format json` | 380ms | +332ms |

Polling interval: 1s. Average command discovery: ~500ms.

## Quick Start

### VM side

```bash
sudo make install-vm
qvm-remote key gen         # generates 256-bit auth key
```

### Dom0 side

From a **dom0 terminal**:

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

## Multi-VM Support

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

## Web Admin Panel (v1.4)

Air-gapped web admin for dom0. Pure Python stdlib HTTP server on `127.0.0.1:9876`. No internet required. Styled after Qubes Global Config with a "stage, review, apply" workflow.

```bash
# Install and start
bash upgrade-dom0.sh
systemctl enable --now qvm-remote-dom0 qubes-global-admin-web qubes-admin-watchdog.timer

# Access (each page is deep-linkable)
firefox http://127.0.0.1:9876/#dashboard
firefox http://127.0.0.1:9876/#log
firefox http://127.0.0.1:9876/#policy
```

**12 tabs** — each opens in its own browser tab via hash routing:

| Tab | Description |
|-----|-------------|
| Dashboard | Daemon status, service control, panel info |
| Logs | Daemon, journal, container, autostart, config inspection (filterable, auto-refresh) |
| Virtual Machines | Authorize/revoke keys, start/stop/pause, template management, key generator |
| Execute | Run commands in dom0 or inside VMs (with datalist suggestions) |
| Files | Push/pull files between dom0 and VMs (browsable path selectors) |
| OpenClaw | Multi-agent container management, compose config, VM status |
| This Device | Dom0 hardware info, Xen hypervisor, running VMs |
| Global Config | Qubes global prefs, per-VM prefs, dom0 updates, templates |
| VM Tools | Firewall, devices, features, tags, services, qrexec policies |
| qvm-remote | Connection map, queue health, command history |
| Backup | System and config backups with browsable destination paths |
| Policy Enforcer | Restrict command execution per VM — dom0 protection, dev mode |

**Key features:**
- **Per-pane Apply/Discard** — stage changes in any tab, apply per-section or globally
- **Policy enforcer** — deny/read-only/monitor/manage/full per VM, blocked command list
- **Development mode** — temporary elevated permissions with auto-expiry countdown
- **Key generator** — cryptographic key generation and VM key fetch in the UI
- **Browsable paths** — select files/directories via dropdown instead of typing paths
- **Smart suggestions** — datalists for commands, properties, firewall rules, services
- **38 API endpoints** — all locally served, no external dependencies

### Threaded Daemon (v1.4)

The dom0 daemon processes commands from multiple VMs concurrently (up to 8 threads). A 15-second VM running-state cache skips halted VMs in the poll loop, and `list_pending` uses a dedicated 10-second timeout.

### XFCE Integration

- **Panel plugin:** Generic Monitor with `/usr/local/bin/qubes-admin-genmon.sh` — green/yellow/red health dot
- **Autostart:** Desktop entry configures workspaces and opens Firefox at login
- **Watchdog timer:** Auto-restarts services if they crash

## GTK Admin Panel (v1.1)

```bash
sudo make install-gui2
qubes-global-admin
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

## Comparison with Alternatives

| Property | Manual Terminal | Custom Qrexec | **qvm-remote** |
|----------|----------------|---------------|----------------|
| Ad-hoc commands | Yes | No (needs handler per command) | **Yes** |
| Authentication | Physical access | Qrexec policy | **HMAC-SHA256 (256-bit)** |
| Audit trail | No | Partial | **Yes (dual-sided)** |
| Multi-VM | Yes | Per-policy | **Yes** |
| Input validation | Human | No | **Yes** |
| Timeout control | Manual | No | **Yes (300s default)** |
| Scriptable | No | Yes | **Yes** |
| Pull model | N/A | No (push) | **Yes** |

## Building

```bash
make docker-rpm            # Fedora 41 container RPM build
make dist                  # source tarballs
make rpm                   # local RPM build
cd pkg && makepkg -si      # Arch Linux
make deb                   # Debian/Ubuntu
```

### Qubes Builder v2

Add to your `builder.yml`:

```yaml
components:
  - qvm-remote:
      url: https://github.com/GabrieleRisso/qvm-remote.git
      branch: main
      verification-mode: insecure-skip-checking
```

Build: `./qb -c qvm-remote package fetch prep build`

### Testing

```bash
make check                 # syntax-check all scripts
make test                  # unit tests
make docker-test           # RPM install test (Fedora 41 container)
make dom0-test             # dom0 simulation E2E (73 assertions)
make arch-test             # Arch Linux client test (36 assertions)
make gui-test              # GUI build + import test
make all-test              # run ALL of the above
```

## Recommendations

- Use dedicated, minimal VMs with no network access
- Stop the service when not in use
- Review `journalctl -u qvm-remote-dom0` periodically
- Rotate keys periodically (`key gen` + `authorize`)

## Migrating from qubes-remote (v0.x)

v1.0 renames the project and rewrites everything from bash to Python:

| v0.x (bash) | v1.0 (Python) |
|-------------|---------------|
| `qubes-remote` | `qvm-remote` |
| `qubes-remote-dom0` | `qvm-remote-dom0` |
| `~/.qubes-remote/` | `~/.qvm-remote/` |
| `--gen-key` | `key gen` |
| `--show-key` | `key show` |
| `--authorize VM KEY` | `authorize VM KEY` |
| `QUBES_REMOTE_VMS=` | `QVM_REMOTE_VMS=` |

Data directories migrate automatically on first run. RPM packages use `Obsoletes:` for clean upgrades.

## Requirements

- Qubes OS 4.2+ (tested on 4.3)
- Python 3.8+ in both dom0 and VMs

## Project Structure

```
qvm-remote/
├── vm/
│   └── qvm-remote                     VM client (Python, ~420 lines)
├── dom0/
│   ├── qvm-remote-dom0                Dom0 daemon (Python, ~685 lines)
│   └── qvm-remote-dom0.service        Systemd unit
├── webui/
│   ├── qubes-global-admin-web         Web admin panel (stdlib only)
│   ├── qubes-admin-watchdog.*         Health check timer
│   └── qubes-admin-genmon.sh          XFCE panel plugin
├── gui2/
│   ├── qubes-global-admin             GTK admin panel
│   └── qubes-global-admin-dom0        Dom0 admin daemon
├── gui/
│   ├── qvm-remote-gui                 VM GUI (GTK3)
│   └── qvm-remote-dom0-gui            Dom0 GUI (GTK3)
├── install/
│   └── install-dom0.sh                Dom0 shell installer
├── paper/
│   ├── qvm-remote.tex                 LaTeX source (6 TikZ diagrams, 40+ refs)
│   ├── qvm-remote.pdf                 Compiled paper (~8 pages)
│   ├── posts.md                       X/LinkedIn/Dev.to/HN/Reddit content
│   ├── blog-qvm-remote.md            Website-ready blog post
│   ├── MANIFEST.md                    Publication asset inventory
│   └── Makefile                       Build: make all (PDF + PNGs + sync)
├── rpm_spec/                          RPM specs (dom0, vm, gui, webui)
├── pkg/                               Arch Linux PKGBUILD
├── debian/                            Debian packaging
├── salt/                              SaltStack formula
├── test/                              Test suite (unit, E2E, GUI, dom0-sim)
├── .github/workflows/ci.yml           GitHub Actions (4 parallel jobs)
├── .qubesbuilder                      Qubes Builder v2 config
├── Makefile
├── upgrade-dom0.sh                    Dom0 upgrade script
├── version                            1.4.0
├── CONTRIBUTING.md
└── README.md                          This file
```

## Publications

The `paper/` directory contains a full academic paper and all associated marketing content. Run `make all` inside `paper/` to rebuild everything and sync to `~/Documents/qvm-remote/`.

| Asset | File | Description |
|-------|------|-------------|
| Paper (PDF) | [`paper/qvm-remote.pdf`](paper/qvm-remote.pdf) | ~8 pages, 40+ references (2025 included) |
| Blog post | [`paper/blog-qvm-remote.md`](paper/blog-qvm-remote.md) | Website-ready with frontmatter |
| Social content | [`paper/posts.md`](paper/posts.md) | X, LinkedIn, Dev.to, HN, Reddit |
| Architecture diagram | [`demo/architecture.png`](demo/architecture.png) | 1200x675, light academic palette |
| Security diagram | [`demo/security.png`](demo/security.png) | Five-layer defense visualization |
| Auth flow diagram | [`demo/auth-flow.png`](demo/auth-flow.png) | HMAC-SHA256 flow visualization |
| Queue states | [`demo/queue-states.png`](demo/queue-states.png) | Command lifecycle state machine |
| Build guide | [`paper/MANIFEST.md`](paper/MANIFEST.md) | Complete asset inventory + deps |

## Links

- **qubes-claw** (AI agent infrastructure built on qvm-remote): [github.com/GabrieleRisso/qubes-claw](https://github.com/GabrieleRisso/qubes-claw)
- **Qubes OS:** [qubes-os.org](https://www.qubes-os.org/)

## Citation

If you reference this work:

```bibtex
@misc{risso2026qvmremote,
  author = {Risso, Gabriele},
  title  = {qvm-remote: Authenticated Remote Execution in Qubes OS dom0 via File-Based Queues},
  year   = {2026},
  url    = {https://github.com/GabrieleRisso/qvm-remote}
}
```

## Contributing

- Run `make test` before submitting
- Test on both VM and dom0
- Follow Qubes OS coding conventions (Python, `qvm-*` CLI style)
- See [`CONTRIBUTING.md`](CONTRIBUTING.md) for details

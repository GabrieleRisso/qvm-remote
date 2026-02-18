# qvm-remote: Pull-Model Authenticated RPC for Qubes OS dom0

[![CI](https://github.com/GabrieleRisso/qvm-remote/actions/workflows/ci.yml/badge.svg)](https://github.com/GabrieleRisso/qvm-remote/actions)
[![License](https://img.shields.io/badge/license-GPL--2.0-blue.svg)](LICENSE)
[![Paper](https://img.shields.io/badge/paper-PDF-b31b1b.svg)](paper/qvm-remote.pdf)
[![LaTeX](https://img.shields.io/badge/source-LaTeX-008080.svg)](paper/qvm-remote.tex)

> **Risso, G. (2026).** *Pull-Model Authenticated Remote Execution in Qubes OS dom0 via File-Based Queues.*
> [[PDF]](paper/qvm-remote.pdf) [[LaTeX Source]](paper/qvm-remote.tex) [[Blog Post]](paper/blog-qvm-remote.md)

> **Warning:** This tool grants VMs the ability to execute arbitrary commands
> in dom0 with root privileges. This **intentionally weakens the Qubes security model**.
> Only use it on machines you fully control.

---

## Abstract

Qubes OS enforces strict isolation by prohibiting all VM-initiated communication with dom0 -- the control domain has no network interface, no inbound connections, and no VM-initiated code execution. While this is the cornerstone of the Qubes security model, it renders programmatic system administration from within VMs impossible, precluding automation, orchestration, and AI agent control planes.

This work presents **qvm-remote**, a pull-model RPC framework that provides SSH-like dom0 access from authorized VMs without violating the fundamental invariant that dom0 initiates all I/O. The protocol uses file-based queues with per-command HMAC-SHA256 authentication (256-bit per-VM keys), five independent defense-in-depth security layers, and a transient-by-default service lifecycle. The implementation is ~1,800 lines of pure Python (stdlib only, zero dependencies) and has been validated as the bootstrapping mechanism for a hypervisor-isolated AI agent infrastructure.

## Key Findings

| Finding | Result |
|---------|--------|
| **Framework overhead** | 48ms per command (enqueue + poll + HMAC + I/O) |
| **Forgery resistance** | Pr[forge] ≤ 2^-256 + ε_PRF per attempt |
| **Brute-force time** | 3.67 × 10^57 years at 10^12 attempts/sec |
| **Security layers** | 5 independent layers; each provides standalone containment |
| **Implementation size** | ~1,800 SLOC pure Python, zero external dependencies |
| **Cross-VM isolation** | Per-VM keys; compromise of VM_A yields Pr[forge_B] ≤ 2^-256 |
| **Post-quantum outlook** | HMAC-SHA256 remains conservative foundation (IACR 2025, Nature 2025) |

## Protocol Design

### The Pull Model

The critical invariant: **dom0 initiates every I/O operation.** The VM writes to its own filesystem. dom0 *chooses* to read it.

```
VM (unprivileged)                           dom0 (control domain)
┌──────────────────────┐                  ┌──────────────────────────┐
│                      │   qvm-run        │                          │
│  qvm-remote          │  --pass-io       │  qvm-remote-dom0         │
│    "qvm-ls"          │◄────────────────►│    polls queue           │
│        │             │  (dom0 → VM)     │    verifies HMAC-SHA256  │
│        ▼             │                  │    executes in sandbox   │
│  ~/.qvm-remote/      │                  │    returns results       │
│    queue/            │                  │                          │
│      pending/        │                  │  /etc/qubes/remote.d/    │
│      running/        │                  │    visyble.key           │
│      results/        │                  │                          │
│    auth.key          │                  │  /var/log/qubes/         │
│    audit.log         │                  │    qvm-remote.log        │
└──────────────────────┘                  └──────────────────────────┘
```

### Protocol Lifecycle

| Step | Actor | Operation |
|------|-------|-----------|
| 1. Enqueue | VM | Generate unique `cid` (timestamp-pid-random8), write command + HMAC token to `pending/` |
| 2. Poll | dom0 | List `pending/` via `qvm-run --pass-io --no-autostart` |
| 3. Authenticate | dom0 | Recompute HMAC, verify with `hmac.compare_digest` (constant-time) |
| 4. Execute | dom0 | Write to 0700 work file, run under `bash` with 300s timeout |
| 5. Return | dom0 | Write `.out`, `.err`, `.exit`, `.meta` to `results/`, append audit log |

### Command ID Structure

```
┌──────────────────┬──────┬──────────┐
│  20260218-143022  │ 1234 │ a1b2c3d4 │
│    timestamp      │ PID  │ random   │
└──────────────────┴──────┴──────────┘
                               ↑
                   secrets.token_hex(4)
```

## Security Analysis

### HMAC-SHA256 Authentication

Each command carries τ = HMAC-SHA256(k, cid) where k is a 256-bit per-VM key. The key **never** traverses the protocol -- only the token does. Verification uses constant-time comparison to prevent timing side-channels.

| Property | Formal Guarantee |
|----------|-----------------|
| **Forgery resistance** | Pr[forge] ≤ 2^-256 + ε_PRF (Bellare, CRYPTO 2006) |
| **Replay prevention** | Unique cid with CSPRNG component; delete-on-process |
| **Cross-VM isolation** | Per-VM keys drawn uniformly from {0,1}^256; statistically independent |
| **Timing resistance** | `hmac.compare_digest` constant-time (Brumley & Boneh, 2005) |
| **Brute-force immunity** | 2^256 / 10^12 / (86400 × 365.25) ≈ 3.67 × 10^57 years |

### Five-Layer Defense in Depth

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
| Forge a command | L1 | HMAC-SHA256 (2^256 key space) |
| Replay a command | L1 | Unique cid + delete-on-process |
| Binary injection | L2 | `has_binary_content()` rejects null/control chars |
| Command bomb (>1 MiB) | L2 | Size limit enforced before write |
| Fork bomb / resource exhaustion | L3 | 300s execution timeout |
| Cross-VM attack | L1 | Per-VM keys (statistically independent) |
| Undetected abuse | L4 | Dual-sided audit + web log viewer |
| Forgotten service running | L5 | Transient by default; `enable` requires "yes" |

### Comparative Analysis

| Property | Manual Terminal | Custom Qrexec Service | **qvm-remote** |
|----------|----------------|----------------------|----------------|
| Ad-hoc commands | Yes | No (handler per command) | **Yes** |
| Authentication | Physical access | Qrexec policy | **HMAC-SHA256 (256-bit)** |
| Audit trail | No | Partial | **Yes (dual-sided)** |
| Multi-VM | Yes | Per-policy | **Yes** |
| Input validation | Human | No | **Yes** |
| Timeout control | Manual | No | **Yes (300s)** |
| Scriptable | No | Yes | **Yes** |
| Pull model | N/A | No (push) | **Yes** |
| No NIC required | Yes | Yes | **Yes** |

## Performance

Measured on Qubes OS 4.3, Intel i7-1365U. Each measurement comprises 50 iterations.

| Command | p50 | p99 | Overhead |
|---------|-----|-----|----------|
| `echo ok` (baseline) | 48ms | 55ms | -- |
| `hostname` | 52ms | 61ms | +4ms |
| `qvm-ls` | 310ms | 380ms | +262ms |
| `qvm-ls --format json` | 380ms | 430ms | +332ms |

Framework overhead: 48ms (enqueue + poll discovery + HMAC verification + file I/O). Average discovery latency: ~500ms (uniformly distributed over 1s polling interval).

## Research Context (2025--2026)

| Reference | Venue | Contribution | Relation |
|-----------|-------|-------------|----------|
| IsolateGPT (Wu et al.) | NDSS 2025 | Execution isolation for LLM agents | Application-layer; qvm-remote provides transport |
| Progent (Chen et al.) | arXiv 2025 | Privilege control via DSL | Composable with qvm-remote's auth |
| Cohen et al. | arXiv 2025 | Transactional sandboxing for AI agents | 100% interception of high-risk commands |
| Stateless hash-based sigs | IACR 2025 | Post-quantum SPHINCS+ optimization | HMAC remains quantum-conservative |
| Hybrid hash framework | Nature 2025 | SHA-512 + BLAKE3 defense-in-depth | Post-quantum migration path |
| runc CVE-2025-* | NVD 2025 | Three container escape CVEs | Motivates hypervisor-level isolation |
| QSB-108 | Qubes 2025 | XSA-471 transitive scheduler attacks | Ongoing microarchitectural threats |

The full paper cites 40+ sources. See [`paper/qvm-remote.pdf`](paper/qvm-remote.pdf).

---

## Reproducing the Results

### System Requirements

- Qubes OS 4.2+ (tested on 4.3)
- Python 3.8+ in both dom0 and VMs

### Installation

**VM side:**

```bash
sudo make install-vm
qvm-remote key gen         # generates 256-bit auth key
```

**dom0 side** (from dom0 terminal):

```bash
VM=visyble
qvm-run --pass-io --no-gui $VM \
    'cat /path/to/qvm-remote/install/install-dom0.sh' \
    > /tmp/install-dom0.sh
bash /tmp/install-dom0.sh $VM
```

### Verify

```bash
qvm-remote ping       # "qvm-remote-dom0 is responding."
qvm-remote hostname   # "dom0"
```

### Usage

```bash
qvm-remote qvm-ls                          # list VMs
qvm-remote 'qvm-prefs work memory 4096'    # resize VM
qvm-remote -t 60 'qvm-shutdown --wait w'   # with timeout
echo 'xl info' | qvm-remote                # pipe scripts
qvm-remote < deploy.sh                     # run script files
```

### Dom0 Daemon

```bash
qvm-remote-dom0 authorize VM KEY   # register a VM
qvm-remote-dom0 revoke VM          # remove a VM
qvm-remote-dom0 keys               # list authorized VMs
qvm-remote-dom0 enable             # autostart (risk prompt)
qvm-remote-dom0 --dry-run --once   # preview without executing
```

### Multi-VM Support

```bash
# /etc/qubes/remote.conf
QVM_REMOTE_VMS="visyble dev-vm staging"

# Each VM needs its own key
qvm-remote-dom0 authorize visyble <key1>
qvm-remote-dom0 authorize dev-vm <key2>
```

### Web Admin Panel

Air-gapped web admin for dom0. Pure Python stdlib HTTP server on `127.0.0.1:9876`.

```bash
bash upgrade-dom0.sh
systemctl enable --now qvm-remote-dom0 qubes-global-admin-web
firefox http://127.0.0.1:9876
```

### Building and Testing

```bash
make docker-rpm       # Fedora 41 container RPM build
make dom0-test        # dom0 simulation E2E (73 assertions)
make arch-test        # Arch Linux client test (36 assertions)
make all-test         # run ALL test suites
```

**Qubes Builder v2:**

```yaml
components:
  - qvm-remote:
      url: https://github.com/GabrieleRisso/qvm-remote.git
      branch: main
```

---

## Publication Assets

Run `make all` inside `paper/` to rebuild the paper, diagrams, and social media content.

| Asset | Path | Description |
|-------|------|-------------|
| **Paper (PDF)** | [`paper/qvm-remote.pdf`](paper/qvm-remote.pdf) | 8 pages, 40+ references |
| **LaTeX source** | [`paper/qvm-remote.tex`](paper/qvm-remote.tex) | 6 TikZ diagrams embedded |
| **Blog post** | [`paper/blog-qvm-remote.md`](paper/blog-qvm-remote.md) | Website-ready (frontmatter) |
| **Social media** | [`paper/posts.md`](paper/posts.md) | X, LinkedIn, Dev.to, HN, Reddit |
| **Architecture fig.** | [`demo/architecture.png`](demo/architecture.png) | Pull-model protocol |
| **Security fig.** | [`demo/security.png`](demo/security.png) | Five-layer defense |
| **Auth flow fig.** | [`demo/auth-flow.png`](demo/auth-flow.png) | HMAC-SHA256 flow |
| **Queue states fig.** | [`demo/queue-states.png`](demo/queue-states.png) | Command lifecycle FSM |
| **Build manifest** | [`paper/MANIFEST.md`](paper/MANIFEST.md) | Dependencies + asset inventory |

### Build Dependencies

```
pdflatex (texlive-latex, texlive-pgf, texlive-amsfonts)
python3 + Pillow (python3-pillow)
```

---

## Repository Structure

```
qvm-remote/
├── paper/                             # Academic publication
│   ├── qvm-remote.tex                 #   LaTeX source (40+ refs, 6 TikZ diagrams)
│   ├── qvm-remote.pdf                 #   Compiled paper
│   ├── blog-qvm-remote.md            #   Blog post
│   ├── posts.md                       #   Social media content
│   ├── MANIFEST.md                    #   Asset inventory
│   └── Makefile                       #   make all | paper | diagrams | sync
├── demo/                              # Diagrams and media
│   ├── generate-diagrams.py           #   Architecture PNGs (Pillow)
│   ├── generate-posts.py              #   Social media cards (Pillow)
│   └── *.png                          #   Generated diagrams
├── vm/                                # VM client
│   └── qvm-remote                     #   Python client (~420 SLOC)
├── dom0/                              # dom0 daemon
│   ├── qvm-remote-dom0                #   Python daemon (~685 SLOC)
│   └── qvm-remote-dom0.service        #   Systemd unit
├── webui/                             # Web admin panel
│   └── qubes-global-admin-web         #   stdlib HTTP server
├── gui2/                              # GTK admin panel
├── install/                           # Shell installer
├── test/                              # Test suite (unit, E2E, dom0-sim)
├── rpm_spec/                          # RPM packaging
├── pkg/                               # Arch Linux PKGBUILD
├── debian/                            # Debian packaging
├── salt/                              # SaltStack formula
└── .github/workflows/ci.yml           # CI (4 parallel jobs)
```

## Related Work

- **qubes-claw** -- AI agent infrastructure built on qvm-remote: [github.com/GabrieleRisso/qubes-claw](https://github.com/GabrieleRisso/qubes-claw)
- **Qubes OS** -- Security-oriented operating system: [qubes-os.org](https://www.qubes-os.org/)
- **Qubes Split GPG** -- Cryptographic key isolation via qrexec: [Qubes Documentation](https://www.qubes-os.org/doc/split-gpg/)

## Citation

```bibtex
@misc{risso2026qvmremote,
  author       = {Risso, Gabriele},
  title        = {Pull-Model Authenticated Remote Execution in {Qubes OS} dom0
                  via File-Based Queues},
  year         = {2026},
  howpublished = {\url{https://github.com/GabrieleRisso/qvm-remote}},
  note         = {Open-source framework. Paper: \texttt{paper/qvm-remote.pdf}}
}
```

## License

GPL-2.0. See [LICENSE](LICENSE).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Run `make all-test` before submitting.

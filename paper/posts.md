# qvm-remote — Blog, Social & Sharing Resources

> Pull-Model Authenticated RPC for Qubes OS dom0
>
> **Repository:** [github.com/GabrieleRisso/qvm-remote](https://github.com/GabrieleRisso/qvm-remote)
> **Paper:** [github.com/GabrieleRisso/qvm-remote/tree/main/paper](https://github.com/GabrieleRisso/qvm-remote/tree/main/paper)

---

## X/Twitter Thread (3 posts)

### Post 1/3 — The Hook

qvm-remote: SSH-like access to Qubes OS dom0 — without a network stack.

```
qvm-remote qvm-ls         # runs in dom0, returns result
qvm-remote hostname        # "dom0"
```

Pull model: dom0 initiates ALL I/O. The VM just writes a file.
HMAC-SHA256 auth. 256-bit per-VM keys. Full audit trail.

1,800 lines of Python. Zero dependencies.

Thread ↓

github.com/GabrieleRisso/qvm-remote

### Post 2/3 — How It Works

The protocol:

1. VM writes command + HMAC token to its own filesystem
2. dom0 daemon polls via `qvm-run --pass-io` (dom0 → VM, never reverse)
3. Verifies HMAC-SHA256 with 256-bit per-VM key
4. Executes in sandboxed work dir (0700, timeout, no binary)
5. Writes stdout/stderr/exit back to VM

The VM never pushes to dom0. It writes a file. dom0 CHOOSES to read it.

This is the same invariant Qubes enforces at the hypervisor level — extended to RPC.

[attach: architecture or auth-flow diagram]

### Post 3/3 — Security

"Doesn't this break Qubes security?"

Deliberately. That is why there are 5 independent layers:

L1: HMAC-SHA256 (2^256 key space — 3.7 x 10^57 years to brute-force)
L2: Input validation (no binary, 1 MiB limit)
L3: Execution sandbox (timeout, 0700, tmpdir)
L4: Dual-sided audit (dom0 + VM logs)
L5: Transient by default (dies on reboot)

2025 context: QSB-108 (XSA-471) shows even hypervisors need ongoing mitigation. Post-quantum hash-based signatures (IACR 2025) confirm HMAC remains a conservative foundation.

Full paper with formal analysis: github.com/GabrieleRisso/qvm-remote/tree/main/paper

---

## LinkedIn Article

### Title: "Pull-Model RPC for Airgapped Domains: Solving the dom0 Administration Problem in Qubes OS"

**The Problem**

Qubes OS enforces strict isolation: dom0 (the control domain) has no network interface, no inbound connections, and no VM-initiated code execution. This makes it secure by design — and impractical for automation.

Every administrative command (listing VMs, resizing memory, managing services) requires physical terminal switching. For infrastructure automation, scripted orchestration, or AI agent control planes, the dom0 wall is impassable through standard mechanisms.

**The Solution: Pull-Model Authenticated RPC**

qvm-remote provides SSH-like access to dom0 from any authorized VM — without a network stack.

```bash
qvm-remote qvm-ls                          # list VMs
qvm-remote 'qvm-prefs work memory 4096'    # resize VM
echo 'xl info' | qvm-remote                # pipe scripts
```

**The Pull Model**

The critical design choice: dom0 initiates ALL I/O. The VM never pushes anything to dom0.

1. VM writes a command file to `~/.qvm-remote/queue/pending/`
2. VM writes an HMAC-SHA256 token alongside it
3. dom0 daemon polls via `qvm-run --pass-io --no-autostart`
4. dom0 verifies the HMAC, validates input, and executes
5. dom0 writes results back to the VM

The VM writes to its own disk. dom0 *chooses* to read it. This preserves the fundamental Qubes invariant at the protocol level.

**Authentication: 256-bit HMAC-SHA256**

Each VM receives a unique 256-bit key. Every command carries HMAC-SHA256(key, command_id). The key never traverses the protocol.

Brute-force analysis: at 10^12 attempts/second, exhaustive search takes 3.7 × 10^57 years. Constant-time comparison prevents timing side-channels.

Recent work on post-quantum hash-based signatures (IACR ePrint 2025/298) and hybrid hash frameworks (Nature Scientific Reports 2025) confirms that HMAC-based authentication remains a conservative, quantum-resistant foundation.

**Five Security Layers:**

| Layer | Protection | Mechanism |
|-------|-----------|-----------|
| L1 | Authentication | HMAC-SHA256, per-VM keys, constant-time verify |
| L2 | Input validation | Empty, oversized (>1 MiB), binary rejected |
| L3 | Execution sandbox | 0700 tmpdir, 300s timeout, cleaned env |
| L4 | Audit trail | Dual-sided logs (dom0 + VM), history archive |
| L5 | Transient default | Service dies on reboot; `enable` requires confirmation |

**Implementation:**

- Pure Python 3 (stdlib only — works in dom0's minimal environment)
- ~1,800 lines total
- Packaged for: Fedora RPM, Arch PKGBUILD, Qubes Builder v2, Salt formula
- Full test suite (unit + integration)

**The Paper:**

The repository includes a full academic paper with formal definitions (Pull-Model RPC), security lemmas (Forgery Resistance, Replay Prevention), a Cross-VM Isolation theorem, latency benchmarks (<50ms overhead), and 40+ references including 2025 publications on agent sandboxing and post-quantum authentication.

**Links:**
- Repository: [github.com/GabrieleRisso/qvm-remote](https://github.com/GabrieleRisso/qvm-remote)
- Paper: [github.com/GabrieleRisso/qvm-remote/tree/main/paper](https://github.com/GabrieleRisso/qvm-remote/tree/main/paper)

---

## Blog Post (Website / Personal Blog)

### Title: "qvm-remote: Bridging the dom0 Gap in Qubes OS with Authenticated File Queues"

*A pull-model RPC framework that provides SSH-like access to dom0 without violating the Qubes security model's core invariant.*

#### The dom0 Problem

Qubes OS keeps dom0 completely isolated from VMs — no network, no inbound connections, no VM-initiated code execution. For security, this is ideal. For administration and automation, this is a wall.

Checking running VMs, resizing memory, managing systemd services — each requires physically switching to the dom0 terminal. For scripted infrastructure management or AI agent orchestration, the barrier is absolute.

#### The Design: Pull-Model File Queues

qvm-remote resolves this with a file-based queue protocol where dom0 initiates all I/O:

```
VM (visyble)                              dom0
┌──────────────────────┐            ┌─────────────────────┐
│ qvm-remote "qvm-ls"  │            │ qvm-remote-dom0     │
│   │                  │  qvm-run   │   polls queue       │
│   ▼                  │◄──────────►│   verifies HMAC     │
│ ~/.qvm-remote/queue/ │  --pass-io │   executes command  │
│   pending/           │            │   returns results   │
│   results/           │            │                     │
└──────────────────────┘            └─────────────────────┘
```

The critical invariant: **dom0 initiates every I/O operation**. The VM writes to its own filesystem — that is all it can do. dom0's daemon discovers, authenticates, and processes requests at its own pace.

#### Authentication

Each command carries HMAC-SHA256(key, command_id) where:
- `key` is a 256-bit shared secret (unique per VM)
- `command_id` is `timestamp-pid-random8` (unique per command)

The key never travels over the protocol. Only the HMAC token does. Brute-force is mathematically irrelevant (2^256 key space = 3.7 × 10^57 years at 10^12 attempts/sec). Constant-time comparison prevents timing attacks.

#### The Five Security Layers

| Layer | Protection | Mechanism |
|-------|-----------|-----------|
| L1 | Authentication | HMAC-SHA256, per-VM keys |
| L2 | Input validation | Size limits, binary detection |
| L3 | Execution sandbox | Tmpdir (0700), 300s timeout |
| L4 | Audit trail | Dual-sided logs + history archive |
| L5 | Transient default | Service dies on reboot unless explicitly enabled |

#### Performance

The framework adds ~48ms overhead per command (polling + HMAC + file I/O). For `hostname`, total round-trip is 52ms. For `qvm-ls`, the 310ms total is dominated by `qvm-ls` itself (262ms).

#### Setup

```bash
# VM
sudo make install-vm
qvm-remote key gen

# dom0
bash install-dom0.sh visyble

# Verify
qvm-remote ping        # "qvm-remote-dom0 is responding."
qvm-remote hostname    # "dom0"
```

#### What This Enables

qvm-remote is the bootstrapping mechanism that makes [qubes-claw](https://github.com/GabrieleRisso/qubes-claw) possible — a hypervisor-isolated AI agent infrastructure on Qubes OS. Without the ability to programmatically manage dom0, none of that orchestration would exist.

**Repository:** [github.com/GabrieleRisso/qvm-remote](https://github.com/GabrieleRisso/qvm-remote)
**Paper:** [github.com/GabrieleRisso/qvm-remote/tree/main/paper](https://github.com/GabrieleRisso/qvm-remote/tree/main/paper)

---

## Dev.to / Medium Article

### Title: "SSH for dom0: Pull-Model RPC with HMAC-SHA256 Authentication on Qubes OS"

**Tags:** `#security` `#qubes` `#cryptography` `#opensource`

**TL;DR:** qvm-remote provides SSH-like dom0 access from VMs using a file-based queue protocol. Pull model (dom0 initiates all I/O). HMAC-SHA256 per-command auth. Five independent security layers. 1,800 LOC Python, zero dependencies. Full academic paper with formal proofs.

---

Qubes OS isolates everything. dom0 has no network interface. No SSH. No remote execution.

This is great for security. Terrible for automation.

qvm-remote bridges this gap with a file-queue protocol:

```bash
# From any authorized VM:
qvm-remote qvm-ls
qvm-remote 'systemctl status my-service'
qvm-remote < deploy-script.sh
```

**How it works:**
1. VM writes command + HMAC token to its own disk
2. dom0 daemon polls (dom0 → VM, never reverse)
3. dom0 verifies HMAC, validates input, executes
4. Results written back to VM

**Why this design:**
- The VM never pushes to dom0 (preserves the Qubes invariant)
- HMAC-SHA256 with 256-bit per-VM keys (3.7 × 10^57 years to brute-force)
- Five independent security layers (auth, validation, sandbox, audit, transience)
- Pure Python stdlib — works in dom0's minimal environment

**2025 research context:**
- Post-quantum hash research (IACR 2025, Nature 2025) confirms HMAC as quantum-resistant
- QSB-108 (XSA-471, July 2025) demonstrates ongoing hypervisor side-channel threats
- IsolateGPT (NDSS 2025), Progent (2025) show growing demand for agent isolation primitives

qvm-remote provides the plumbing layer these higher-level frameworks need.

**Links:**
- GitHub: [github.com/GabrieleRisso/qvm-remote](https://github.com/GabrieleRisso/qvm-remote)
- Paper: [github.com/GabrieleRisso/qvm-remote/tree/main/paper](https://github.com/GabrieleRisso/qvm-remote/tree/main/paper)

---

## Hacker News Submission

**Title:** qvm-remote: Pull-model authenticated RPC for Qubes OS dom0 (HMAC-SHA256, file queues)

**URL:** https://github.com/GabrieleRisso/qvm-remote

**Comment:**

qvm-remote provides SSH-like access to Qubes OS dom0 from VMs — without a network stack.

The design uses a pull model: dom0 polls the VM's filesystem for queued commands via `qvm-run --pass-io`. Every command is authenticated with HMAC-SHA256 (256-bit per-VM keys). The VM never initiates I/O to dom0.

Five security layers: authentication, input validation, execution sandboxing, dual-sided audit, and transient-by-default service lifecycle.

Implementation is ~1,800 lines of pure Python (stdlib only — works in dom0's constrained environment). Packaged for Fedora RPM, Arch, Qubes Builder v2, and Salt.

The repo includes a full academic paper with formal security definitions, forgery resistance and replay prevention lemmas, a Cross-VM isolation theorem, brute-force analysis, and 40+ references including 2025 publications.

This is the bootstrapping layer for qubes-claw (https://github.com/GabrieleRisso/qubes-claw), which runs AI agents in Xen-isolated VMs.

---

## Reddit Posts

### r/QubesOS

**Title:** qvm-remote: Authenticated remote execution from VMs to dom0 (pull-model, HMAC-SHA256, file queues)

qvm-remote provides SSH-like dom0 access from VMs using a pull-model file-queue protocol. dom0 initiates all I/O — the VM only writes to its own disk.

Key features:
- HMAC-SHA256 per-command auth (256-bit per-VM keys)
- Five independent security layers
- Pure Python stdlib (works in dom0)
- ~1,800 SLOC, zero dependencies
- Fedora RPM + Arch PKGBUILD + Qubes Builder v2 + Salt
- Transient by default (service dies on reboot unless explicitly enabled)
- Full academic paper with formal security analysis

The paper references QSB-108 (XSA-471, July 2025) and discusses trust assumptions relative to ongoing microarchitectural threats.

This is the bootstrapping layer for qubes-claw (AI agent isolation infrastructure).

GitHub: https://github.com/GabrieleRisso/qvm-remote

### r/netsec

**Title:** Academic paper: Pull-model authenticated RPC for airgapped domains (HMAC-SHA256, formal proofs, 40+ refs)

A formal treatment of file-queue-based RPC for Qubes OS dom0. The paper includes:

- Formal definition of Pull-Model RPC
- Forgery Resistance lemma (HMAC security bound: Pr[forge] ≤ 2^-256 + ε_PRF)
- Replay Prevention lemma (CSPRNG + delete-on-process)
- Cross-VM Isolation theorem (per-VM key independence)
- Brute-force analysis (3.7 × 10^57 years at 10^12 ops/sec)
- Five-layer defense-in-depth model
- Latency benchmarks (48ms overhead)
- 40+ citations including post-quantum hash research (IACR 2025), container escape CVEs (Nov 2025), QSB-108 (XSA-471)

Pure Python stdlib implementation (~1,800 SLOC, zero dependencies).

Paper: https://github.com/GabrieleRisso/qvm-remote/tree/main/paper
Repo: https://github.com/GabrieleRisso/qvm-remote

### r/crypto

**Title:** HMAC-SHA256 for cross-VM authentication: formal analysis and post-quantum considerations

A paper analyzing the use of HMAC-SHA256 for per-command authentication in a file-queue RPC protocol across Xen VM boundaries. Includes:

- Security bound: Pr[forge] ≤ 2^-256 + ε_PRF (Bellare 2006)
- Constant-time comparison against timing side-channels (Brumley & Boneh 2005)
- Replay prevention via CSPRNG command IDs + delete-on-process
- Cross-VM key independence proof
- Discussion of post-quantum migration paths referencing stateless hash-based signatures (IACR 2025/298) and hybrid hash frameworks (Nature Scientific Reports 2025)

Paper: https://github.com/GabrieleRisso/qvm-remote/tree/main/paper

---

## Image Assets

The following diagram PNGs are available in `demo/` for use in posts:

| File | Description | Recommended Use |
|------|-------------|-----------------|
| `architecture.png` | System architecture (VM ↔ dom0 flow) | LinkedIn header, blog hero |
| `security.png` | Five security layers diagram | X post 3, r/netsec |
| `auth-flow.png` | HMAC-SHA256 authentication flow | Dev.to article, blog detail |
| `queue-states.png` | Command queue state machine | Technical blog, r/crypto |

Social media cards are generated from the diagram generator script and available in `~/Documents/qvm-remote/posts/`.

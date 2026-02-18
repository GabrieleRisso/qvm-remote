---
title: "qvm-remote: Pull-Model Authenticated RPC for Qubes OS dom0"
date: 2026-02-18
author: Gabriele Risso
tags: [security, qubes-os, cryptography, rpc, open-source, hmac]
description: "A file-queue RPC framework providing SSH-like dom0 access from VMs with HMAC-SHA256 authentication and five independent security layers."
image: /images/qvm-remote-architecture.png
---

# qvm-remote: Pull-Model Authenticated RPC for Qubes OS dom0

Qubes OS keeps dom0 (the control domain) completely isolated from VMs — no network, no inbound connections, no VM-initiated code execution. This is the cornerstone of the Qubes security model. It is also the reason that every administrative action — listing VMs, resizing memory, managing services — requires physically switching to the dom0 terminal.

For automation, orchestration, or AI agent infrastructure, this wall is absolute.

**qvm-remote** resolves this with a pull-model file-queue protocol: HMAC-SHA256 authenticated, five-layer defense-in-depth, 1,800 lines of pure Python with zero dependencies.

**Repository:** [github.com/GabrieleRisso/qvm-remote](https://github.com/GabrieleRisso/qvm-remote)

---

## The Pull Model

The critical design choice: **dom0 initiates ALL I/O**. The VM never pushes anything to dom0.

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

The VM writes a command file to its own filesystem. That is all it can do. dom0's daemon discovers the file (via `qvm-run --pass-io`), authenticates it, and processes it at its own pace.

This preserves the fundamental Qubes invariant: dom0 always initiates. The VM is passive.

---

## Authentication: HMAC-SHA256

Each command carries `HMAC-SHA256(key, command_id)` where:

- **key**: 256-bit shared secret, unique per VM
- **command_id**: `timestamp-pid-random8` (unique per command, CSPRNG-generated)

The key **never** traverses the protocol. Only the HMAC token does. dom0 recomputes the expected token from its own copy of the key and verifies with constant-time comparison (preventing timing side-channels per Brumley & Boneh 2005).

**Brute-force analysis:** At 10^12 HMAC-SHA256 computations per second (exceeding any current hardware), exhaustive key search takes:

> T = 2^256 / (10^12 × 86400 × 365.25) ≈ **3.67 × 10^57 years**

This exceeds the remaining lifetime of the solar system by 48 orders of magnitude.

**Post-quantum considerations:** Recent work on stateless hash-based signatures (IACR ePrint 2025/298) and hybrid hash frameworks (Nature Scientific Reports 2025) confirms that HMAC-based authentication remains a conservative, quantum-resistant foundation. The system can be upgraded to post-quantum constructions as they mature and standardize.

---

## Five Security Layers

| Layer | Protection | Mechanism |
|-------|-----------|-----------|
| **L1** | Authentication | HMAC-SHA256 per-command, per-VM keys, constant-time verify |
| **L2** | Input validation | Empty, oversized (>1 MiB), and binary commands rejected |
| **L3** | Execution sandbox | 0700 tmpdir, 300s timeout, cleaned environment |
| **L4** | Audit trail | Dual-sided logs (dom0 + VM), command history archive |
| **L5** | Transient default | Service stops on reboot; `enable` requires interactive confirmation |

Each layer operates independently. Bypassing authentication (L1) still leaves the attacker facing input validation (L2), sandboxing (L3), comprehensive logging (L4), and service transience (L5).

---

## Usage

```bash
# Simple commands
qvm-remote qvm-ls
qvm-remote hostname
qvm-remote 'qvm-prefs work memory 4096'

# Piped scripts
echo 'xl info' | qvm-remote
qvm-remote < deploy-script.sh

# Status
qvm-remote ping        # "qvm-remote-dom0 is responding."
```

---

## Performance

| Command | Latency (p50) | Latency (p99) | Overhead |
|---------|--------------|--------------|----------|
| `echo ok` (baseline) | 48ms | 55ms | — |
| `hostname` | 52ms | 61ms | +4ms |
| `qvm-ls` | 310ms | 380ms | +262ms (dominated by qvm-ls) |

The framework overhead is **48ms** (enqueue + poll discovery + HMAC verification + file I/O). Average poll discovery latency is ~500ms (uniformly distributed over the 1-second polling interval).

---

## Setup

```bash
# On the VM
sudo make install-vm
qvm-remote key gen

# On dom0
bash install-dom0.sh visyble

# Verify
qvm-remote ping        # "qvm-remote-dom0 is responding."
qvm-remote hostname    # "dom0"
```

Packaged for Fedora RPM, Arch PKGBUILD, Qubes Builder v2, and Salt formula.

---

## What This Enables

qvm-remote is the bootstrapping mechanism that makes [qubes-claw](https://github.com/GabrieleRisso/qubes-claw) possible — a hypervisor-isolated AI agent infrastructure on Qubes OS. Without the ability to programmatically manage dom0, none of that orchestration (systemd service management, qrexec policy deployment, vchan tunnel provisioning) would be automatable from within a VM.

---

## Web Admin Panel

v1.4 includes a full web admin panel served air-gapped from dom0 (`127.0.0.1:9876`). Pure Python stdlib — no npm, no bundlers, no external assets.

- **12 deep-linkable tabs** — Dashboard, Logs, VMs, Execute, Files, OpenClaw, Device, Global Config, VM Tools, qvm-remote, Backup, Policy Enforcer
- **Policy enforcer** — restrict which VMs can execute which commands, with a Qubes-style device-attachment UI
- **Threaded daemon** — concurrent command processing from multiple VMs (up to 8 threads)
- **Development mode** — temporary elevated permissions with auto-expiry countdown
- **38 API endpoints** — health, vm-list, execute, browse, journal, suggestions, and more
- **55 automated E2E tests** — covering all services, APIs, HTML features, and policy enforcement

---

## The Paper

The repository includes a full academic paper (LaTeX source + compiled PDF) with:

- Formal definition of Pull-Model RPC
- Forgery Resistance lemma (Pr[forge] ≤ 2^-256 + ε_PRF)
- Replay Prevention lemma (CSPRNG + delete-on-process)
- Cross-VM Isolation theorem
- Brute-force analysis
- Five-layer defense-in-depth model
- Latency benchmarks
- Comparison with manual switching, qrexec services, SSH (hypothetical)
- 40+ cited references including 2025 publications on agent sandboxing, post-quantum authentication, and container escape CVEs

**Paper:** [github.com/GabrieleRisso/qvm-remote/tree/main/paper](https://github.com/GabrieleRisso/qvm-remote/tree/main/paper)

**Repository:** [github.com/GabrieleRisso/qvm-remote](https://github.com/GabrieleRisso/qvm-remote)

---

*See also: [qubes-claw](https://github.com/GabrieleRisso/qubes-claw) — the AI agent infrastructure built on top of qvm-remote.*

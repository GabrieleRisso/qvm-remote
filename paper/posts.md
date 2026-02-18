# qvm-remote — Social & Blog Posts

## X/Twitter Posts (3 posts, thread format)

### Post 1/3 — The Hook

I built SSH for Qubes OS dom0.

`qvm-remote qvm-ls` from a VM — runs in dom0 and returns the result.

HMAC-SHA256 auth. File-based queue. Pull model (dom0 initiates ALL I/O). Full audit trail.

1,800 lines of Python. Zero dependencies.

🧵 ↓

github.com/GabrieleRisso/qvm-remote

---

### Post 2/3 — How It Works

The protocol is elegant:

1. VM writes command + HMAC token to its own filesystem
2. dom0 daemon polls via `qvm-run --pass-io` (dom0 → VM, never reverse)
3. Verifies HMAC-SHA256 with 256-bit per-VM key
4. Executes in sandboxed work dir (0700, timeout, no binary)
5. Writes stdout/stderr/exit back to VM

Key insight: VM never pushes to dom0. It writes a file. dom0 CHOOSES to read it.

[protocol diagram]

---

### Post 3/3 — Security

"But doesn't this break Qubes security?"

Yes. Deliberately. That's why there are 5 layers:

L1: HMAC-SHA256 (2^256 key space — 3.7 × 10^57 years to brute-force)
L2: Input validation (no binary, 1 MiB limit)
L3: Execution sandbox (timeout, 0700, tmpdir)
L4: Dual-sided audit (dom0 + VM logs, history archive)
L5: Transient by default (dies on reboot unless you type "yes")

Full academic paper with formal analysis in the repo.

⭐ github.com/GabrieleRisso/qvm-remote

---

## LinkedIn Article

### Title: "SSH for dom0: How I Built Authenticated Remote Execution for Qubes OS"

**The Problem**

Qubes OS keeps dom0 (the control domain) completely isolated from VMs — no network, no inbound connections, no VM-initiated code execution. This is great for security, but terrible for developers.

Every time I need to run `qvm-ls`, resize a VM, or start a service, I have to physically switch to the dom0 terminal. When I'm automating infrastructure from a VM, this wall becomes impassable.

**The Solution: qvm-remote**

I built qvm-remote — an authenticated remote execution framework that provides SSH-like access to dom0 from any authorized VM.

```bash
qvm-remote qvm-ls                          # list VMs
qvm-remote 'qvm-prefs work memory 4096'    # resize VM
echo 'xl info' | qvm-remote                # pipe scripts
qvm-remote < deploy.sh                     # run whole scripts
```

**The Pull Model**

The key design choice is the *pull model*: dom0 initiates ALL I/O. The VM never pushes anything to dom0.

Here's the flow:
1. VM writes a command file to `~/.qvm-remote/queue/pending/`
2. VM writes an HMAC-SHA256 token alongside it
3. dom0 daemon polls via `qvm-run --pass-io --no-autostart`
4. dom0 verifies the HMAC, validates input, and executes
5. dom0 writes results back to the VM

The VM never touches dom0. It writes to its own disk. dom0 *chooses* to read it.

**Authentication: 256-bit HMAC-SHA256**

Each VM gets a unique 256-bit key. Every command carries HMAC-SHA256(key, command_id). The key never traverses the protocol — only the HMAC token does.

Brute-force analysis: at 10^12 attempts/second, exhaustive search takes 3.7 × 10^57 years. No lockout needed.

**Five Security Layers:**

1. **HMAC-SHA256 Authentication** — per-command, per-VM, constant-time verification
2. **Input Validation** — empty, oversized (>1 MiB), and binary commands rejected
3. **Execution Sandboxing** — 0700 tmpdir, 300s timeout, bash with cleaned env
4. **Dual-Sided Audit** — both dom0 and VM log every command with timestamps and duration
5. **Transient by Default** — service stops on reboot. `enable` requires typing "yes" to a risk warning

**Implementation:**

- Pure Python 3 (stdlib only — works in dom0's minimal environment)
- ~1,800 lines total across daemon + client + web UI + tests
- Packaged for: Fedora RPM, Arch PKGBUILD, Qubes Builder v2, Salt formula
- CI: 4 parallel GitHub Actions jobs (unit tests, Docker install, dom0 simulation, Arch test)

**The Paper:**

I've written a full academic paper covering the protocol design, formal authentication analysis, threat model, latency benchmarks (<50ms overhead), and comparison with alternatives (manual switching, custom qrexec services).

**Links:**
- GitHub: github.com/GabrieleRisso/qvm-remote
- Paper: github.com/GabrieleRisso/qvm-remote/tree/main/paper

---

## Blog Post

### Title: "qvm-remote: Bridging the dom0 Gap in Qubes OS with Authenticated File Queues"

*How I built a pull-model RPC framework that gives VMs SSH-like access to dom0 without violating the Qubes security architecture's core invariant.*

#### The dom0 Problem

If you've used Qubes OS, you know the pain. You're deep in a coding session in your `code` VM, and you need to check something in dom0:

```bash
# You want to run this from your VM:
qvm-ls --running
qvm-prefs another-vm memory 4096
systemctl restart my-service
```

But you can't. dom0 is a walled garden. You physically switch terminals, type the command, read the output, switch back. Repeat.

For scripting and automation, it's even worse. You literally cannot programmatically manage VMs from inside a VM.

#### The Design

qvm-remote solves this with a file-based queue protocol and a pull model:

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

The critical invariant: **dom0 initiates every I/O operation**. The VM writes to its own filesystem — that's all it can do. dom0's daemon discovers, authenticates, and processes the requests at its own pace.

#### Authentication

Each command carries HMAC-SHA256(key, command_id) where:
- `key` is a 256-bit shared secret (per-VM)
- `command_id` is `timestamp-pid-random8` (unique per command)

The key never travels over the wire. Only the HMAC token does. Brute-force is mathematically irrelevant (2^256 key space). Constant-time comparison prevents timing attacks.

#### The Five Layers

| Layer | Protection | Mechanism |
|-------|-----------|-----------|
| L1 | Authentication | HMAC-SHA256, per-VM keys |
| L2 | Input validation | Size limits, binary detection |
| L3 | Execution sandbox | Tmpdir (0700), timeouts |
| L4 | Audit trail | Dual-sided logs + history |
| L5 | Transient default | Service dies on reboot |

#### Performance

The framework adds ~48ms overhead per command (polling + HMAC + file I/O). For a `hostname` command, total round-trip is 52ms. For `qvm-ls`, the 310ms total is dominated by `qvm-ls` itself (262ms).

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

qvm-remote is the foundation that makes my other project, [qubes-claw](https://github.com/GabrieleRisso/qubes-claw), possible — an airgapped AI agent infrastructure on Qubes OS. Without the ability to programmatically manage dom0, none of that automation would exist.

**GitHub:** [github.com/GabrieleRisso/qvm-remote](https://github.com/GabrieleRisso/qvm-remote)  
**Paper:** [github.com/GabrieleRisso/qvm-remote/tree/main/paper](https://github.com/GabrieleRisso/qvm-remote/tree/main/paper)

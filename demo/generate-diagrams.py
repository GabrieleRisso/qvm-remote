#!/usr/bin/env python3
"""Generate architecture diagrams for qvm-remote using Pillow.

Usage: python3 generate-diagrams.py <output-dir>

Produces four diagrams (1200x675, light academic theme):
  1. architecture.png  — Pull-model protocol overview
  2. security.png      — Five-layer defense model
  3. auth-flow.png     — HMAC-SHA256 authentication flow
  4. queue-states.png  — Command queue state machine
"""

import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 675
BG = (248, 248, 245)
FG = (45, 45, 45)
SOFT = (107, 114, 128)
BLUE = (37, 99, 235)
GREEN = (22, 163, 74)
ORANGE = (217, 119, 6)
RED = (220, 38, 38)
PURPLE = (124, 58, 237)
TEAL = (13, 148, 136)
BORDER = (209, 213, 219)
CARD = (255, 255, 255)
YELLOW = (202, 138, 4)
CYAN = (2, 132, 199)

FONT_PATHS = [
    "/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf",
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/fira-code/FiraCode-Regular.ttf",
    "/usr/share/fonts/redhat/RedHatDisplay-Regular.otf",
    "/usr/share/fonts/redhat/RedHatDisplay-Bold.otf",
    "/usr/share/fonts/gnu-free/FreeSans.otf",
    "/usr/share/fonts/gnu-free/FreeSansBold.otf",
]


def load_font(style, size):
    style_map = {"mono": [0, 3], "text": [1, 4, 6], "bold": [2, 5, 7]}
    for idx in style_map.get(style, [0]):
        try:
            return ImageFont.truetype(FONT_PATHS[idx], size)
        except (OSError, IndexError):
            continue
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def rounded_rect(d, xy, fill, outline=None, r=12, width=2):
    d.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def arrow(d, x1, y1, x2, y2, color, width=2, head=8):
    d.line([(x1, y1), (x2, y2)], fill=color, width=width)
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    d.polygon([
        (x2, y2),
        (x2 - head * math.cos(angle - 0.4), y2 - head * math.sin(angle - 0.4)),
        (x2 - head * math.cos(angle + 0.4), y2 - head * math.sin(angle + 0.4)),
    ], fill=color)


def dashed_line(d, x1, y1, x2, y2, color, width=2, dash=8, gap=6):
    import math
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    pos = 0
    while pos < length:
        end = min(pos + dash, length)
        d.line([
            (x1 + ux * pos, y1 + uy * pos),
            (x1 + ux * end, y1 + uy * end),
        ], fill=color, width=width)
        pos = end + gap


def text_center(d, x, y, text, font, fill):
    bb = d.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text((x - tw // 2, y - th // 2), text, font=font, fill=fill)


# ─── Diagram 1: Architecture ─────────────────────────────────────
def gen_architecture(outdir):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    fb = load_font("bold", 22)
    ft = load_font("text", 14)
    fm = load_font("mono", 13)
    fs = load_font("text", 11)

    d.text((30, 20), "qvm-remote — Pull-Model Protocol Architecture", font=fb, fill=FG)
    d.line([(30, 52), (W - 30, 52)], fill=BORDER, width=1)

    # VM box
    rounded_rect(d, (40, 80, 470, 440), fill=CARD, outline=ORANGE, r=14, width=2)
    d.text((60, 90), "Unprivileged VM", font=load_font("bold", 16), fill=ORANGE)

    rounded_rect(d, (60, 125, 300, 160), fill=(255, 247, 237), outline=ORANGE, r=8)
    text_center(d, 180, 142, "qvm-remote (client)", font=fm, fill=ORANGE)

    # Queue
    rounded_rect(d, (60, 180, 450, 420), fill=(240, 253, 250), outline=TEAL, r=10, width=1)
    d.text((75, 188), "~/.qvm-remote/queue/", font=fm, fill=TEAL)

    for i, (name, col) in enumerate([
        ("pending/", TEAL), ("running/", YELLOW), ("results/", GREEN)
    ]):
        y = 218 + i * 42
        rounded_rect(d, (80, y, 280, y + 32), fill=(*col, 20), outline=col, r=6, width=1)
        d.text((95, y + 7), name, font=fm, fill=col)

    rounded_rect(d, (80, 348, 280, 380), fill=(248, 245, 255), outline=PURPLE, r=6, width=1)
    d.text((95, 355), "auth.key (0600)", font=fm, fill=PURPLE)
    rounded_rect(d, (80, 388, 280, 410), fill=(254, 243, 199), outline=YELLOW, r=6, width=1)
    d.text((95, 393), "audit.log", font=fs, fill=YELLOW)

    # dom0 box
    rounded_rect(d, (570, 80, 1000, 440), fill=CARD, outline=BLUE, r=14, width=2)
    d.text((590, 90), "Control Domain (dom0)", font=load_font("bold", 16), fill=BLUE)

    rounded_rect(d, (590, 125, 870, 160), fill=(239, 246, 255), outline=BLUE, r=8)
    text_center(d, 730, 142, "qvm-remote-dom0 (daemon)", font=fm, fill=BLUE)

    rounded_rect(d, (590, 180, 980, 310), fill=(248, 248, 255), outline=(*BLUE, 80), r=10, width=1)
    d.text((605, 188), "dom0 storage", font=load_font("text", 12), fill=SOFT)

    for i, (name, col) in enumerate([
        ("/etc/qubes/remote.d/", PURPLE),
        ("/var/log/qubes/", YELLOW),
        ("/var/run/qvm-remote/", RED),
    ]):
        y = 213 + i * 32
        rounded_rect(d, (610, y, 960, y + 26), fill=CARD, outline=col, r=5, width=1)
        d.text((625, y + 5), name, font=fs, fill=col)

    # Arrows between VM and dom0
    arrow(d, 476, 140, 585, 140, BLUE, width=3)
    d.text((490, 118), "qvm-run --pass-io", font=fs, fill=BLUE)
    arrow(d, 585, 160, 476, 160, GREEN, width=2)
    d.text((490, 165), "stdout / results", font=fs, fill=GREEN)

    # Step numbers
    for i, (x, y, col, txt) in enumerate([
        (55, 140, ORANGE, "1"), (530, 130, BLUE, "2"),
        (590, 210, PURPLE, "3"), (590, 275, RED, "4"),
        (530, 155, GREEN, "5"),
    ]):
        d.ellipse((x - 10, y - 10, x + 10, y + 10), fill=col)
        text_center(d, x, y, txt, font=load_font("bold", 12), fill=(255, 255, 255))

    # Xen bar
    rounded_rect(d, (40, 470, 1000, 510), fill=(254, 226, 226), outline=RED, r=8, width=2)
    text_center(d, 520, 490, "Xen Hypervisor — All I/O Initiated by dom0",
                font=load_font("bold", 15), fill=RED)

    dashed_line(d, 255, 440, 255, 470, RED, width=1)
    dashed_line(d, 785, 440, 785, 470, RED, width=1)

    # Legend
    d.text((40, 530), "Protocol: ", font=load_font("bold", 13), fill=FG)
    for i, (txt, col) in enumerate([
        ("1 enqueue", ORANGE), ("2 poll", BLUE), ("3 verify HMAC", PURPLE),
        ("4 execute", RED), ("5 return", GREEN),
    ]):
        x = 130 + i * 180
        d.ellipse((x, 530, x + 14, 544), fill=col)
        d.text((x + 20, 530), txt, font=ft, fill=col)

    d.text((40, 560), "github.com/GabrieleRisso/qvm-remote", font=fm, fill=SOFT)

    img.save(outdir / "architecture.png")
    print(f"  architecture.png ({W}x{H})")


# ─── Diagram 2: Security Layers ──────────────────────────────────
def gen_security(outdir):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    fb = load_font("bold", 22)
    ft = load_font("text", 14)
    fm = load_font("mono", 12)

    d.text((30, 20), "qvm-remote — Five-Layer Defense in Depth", font=fb, fill=FG)
    d.line([(30, 52), (W - 30, 52)], fill=BORDER, width=1)

    layers = [
        ("L1: HMAC-SHA256 Authentication", RED, "256-bit keys, per-command tokens, constant-time verify"),
        ("L2: Input Validation", ORANGE, "No empty/binary/oversized (>1 MiB) commands"),
        ("L3: Execution Sandboxing", BLUE, "0700 tmpdir, 300s timeout, bash only"),
        ("L4: Dual-Sided Audit Trail", PURPLE, "dom0 + VM logs, full history archive"),
        ("L5: Transient by Default", GREEN, "Dies on reboot unless explicitly enabled"),
    ]

    for i, (name, col, desc) in enumerate(layers):
        w = 900 - i * 100
        x = (W - w) // 2
        y = 90 + i * 95
        # Layer rectangle
        rounded_rect(d, (x, y, x + w, y + 55), fill=(*col, 30), outline=col, r=10, width=2)
        text_center(d, W // 2, y + 18, name, font=load_font("bold", 17), fill=col)
        text_center(d, W // 2, y + 40, desc, font=ft, fill=SOFT)

    # Brace text
    d.text((980, 260), "Independent", font=load_font("bold", 13), fill=SOFT)
    d.text((980, 278), "containment", font=ft, fill=SOFT)
    d.text((980, 296), "layers", font=ft, fill=SOFT)

    d.text((40, 590), "Each layer provides containment independent of the others.",
           font=ft, fill=SOFT)
    d.text((40, 615), "github.com/GabrieleRisso/qvm-remote", font=fm, fill=SOFT)

    img.save(outdir / "security.png")
    print(f"  security.png ({W}x{H})")


# ─── Diagram 3: HMAC Auth Flow ───────────────────────────────────
def gen_auth_flow(outdir):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    fb = load_font("bold", 22)
    ft = load_font("text", 14)
    fm = load_font("mono", 13)
    fs = load_font("text", 11)

    d.text((30, 20), "qvm-remote — HMAC-SHA256 Authentication Flow", font=fb, fill=FG)
    d.line([(30, 52), (W - 30, 52)], fill=BORDER, width=1)

    # VM column
    cx_vm = 250
    d.text((cx_vm - 30, 75), "VM Side", font=load_font("bold", 16), fill=ORANGE)

    boxes_vm = [
        ("k (auth.key)", 120, PURPLE),
        ("command_id", 185, ORANGE),
        ("HMAC-SHA256(k, cid)", 260, TEAL),
        ("τ (token)", 335, GREEN),
    ]
    for text, y, col in boxes_vm:
        rounded_rect(d, (cx_vm - 100, y, cx_vm + 100, y + 38), fill=CARD, outline=col, r=8, width=2)
        text_center(d, cx_vm, y + 19, text, font=fm, fill=col)

    arrow(d, cx_vm, 158, cx_vm, 260, PURPLE, width=2)
    arrow(d, cx_vm + 40, 223, cx_vm + 40, 260, ORANGE, width=2)
    arrow(d, cx_vm, 298, cx_vm, 335, TEAL, width=2)

    # dom0 column
    cx_d0 = 750
    d.text((cx_d0 - 40, 75), "dom0 Side", font=load_font("bold", 16), fill=BLUE)

    boxes_d0 = [
        ("k (vm.key)", 120, PURPLE),
        ("command_id", 185, ORANGE),
        ("HMAC-SHA256(k, cid)", 260, TEAL),
        ("τ' (recomputed)", 335, BLUE),
    ]
    for text, y, col in boxes_d0:
        rounded_rect(d, (cx_d0 - 100, y, cx_d0 + 100, y + 38), fill=CARD, outline=col, r=8, width=2)
        text_center(d, cx_d0, y + 19, text, font=fm, fill=col)

    arrow(d, cx_d0, 158, cx_d0, 260, PURPLE, width=2)
    arrow(d, cx_d0 - 40, 223, cx_d0 - 40, 260, ORANGE, width=2)
    arrow(d, cx_d0, 298, cx_d0, 335, TEAL, width=2)

    # Token transfer
    dashed_line(d, cx_vm + 105, 354, cx_d0 - 105, 354, SOFT, width=2, dash=10, gap=6)
    text_center(d, 500, 340, "τ via queue file", font=fs, fill=SOFT)
    text_center(d, 500, 358, "(key never transmitted)", font=load_font("bold", 11), fill=RED)

    # Comparison
    rounded_rect(d, (380, 420, 620, 465), fill=(240, 253, 244), outline=GREEN, r=10, width=2)
    text_center(d, 500, 442, "compare_digest(τ, τ')", font=fm, fill=GREEN)
    d.text((420, 472), "constant-time comparison", font=fs, fill=SOFT)

    arrow(d, cx_vm, 373, 395, 430, GREEN, width=2)
    arrow(d, cx_d0, 373, 605, 430, BLUE, width=2)

    # Result
    rounded_rect(d, (330, 510, 500, 548), fill=(240, 253, 244), outline=GREEN, r=8)
    text_center(d, 415, 529, "Accept → Execute", font=ft, fill=GREEN)

    rounded_rect(d, (520, 510, 680, 548), fill=(254, 226, 226), outline=RED, r=8)
    text_center(d, 600, 529, "Reject → Log", font=ft, fill=RED)

    arrow(d, 460, 465, 415, 510, GREEN, width=2)
    arrow(d, 540, 465, 600, 510, RED, width=2)

    d.text((40, 590), "Pr[forge] ≤ 2⁻²⁵⁶ — brute force requires 3.7 × 10⁵⁷ years",
           font=ft, fill=SOFT)
    d.text((40, 615), "github.com/GabrieleRisso/qvm-remote", font=fm, fill=SOFT)

    img.save(outdir / "auth-flow.png")
    print(f"  auth-flow.png ({W}x{H})")


# ─── Diagram 4: Queue State Machine ──────────────────────────────
def gen_queue_states(outdir):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    fb = load_font("bold", 22)
    ft = load_font("text", 14)
    fm = load_font("mono", 13)

    d.text((30, 20), "qvm-remote — Command Queue State Machine", font=fb, fill=FG)
    d.line([(30, 52), (W - 30, 52)], fill=BORDER, width=1)

    states = [
        ("IDLE", 130, 180, BLUE),
        ("PENDING", 380, 180, TEAL),
        ("AUTH", 630, 180, PURPLE),
        ("RUNNING", 630, 370, YELLOW),
        ("RESULTS", 880, 370, GREEN),
        ("REJECTED", 380, 370, RED),
    ]

    for name, x, y, col in states:
        rounded_rect(d, (x - 65, y - 25, x + 65, y + 25), fill=CARD, outline=col, r=12, width=2)
        text_center(d, x, y, name, font=load_font("bold", 15), fill=col)

    transitions = [
        (130, 180, 380, 180, "enqueue", TEAL),
        (380, 180, 630, 180, "poll + read", PURPLE),
        (630, 205, 630, 345, "HMAC ok", GREEN),
        (630, 205, 380, 345, "HMAC fail", RED),
        (630, 370, 880, 370, "complete", GREEN),
    ]

    for x1, y1, x2, y2, label, col in transitions:
        arrow(d, x1 + 65, y1, x2 - 65, y2, col, width=2, head=10)
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2 - 15
        if y2 > y1 + 50:
            mx = x1 + (x2 - x1) // 2 - 30
            my = (y1 + y2) // 2
        d.text((mx - 20, my), label, font=ft, fill=col)

    # Archive arrow
    arrow(d, 945, 370, 1020, 370, SOFT, width=2)
    d.text((1025, 363), "archive", font=ft, fill=SOFT)

    # Log arrow
    arrow(d, 315, 370, 240, 370, SOFT, width=2)
    d.text((195, 363), "log", font=ft, fill=SOFT)

    # Legend
    y = 470
    d.line([(40, y), (W - 40, y)], fill=BORDER)
    d.text((40, y + 15), "Queue directories:", font=load_font("bold", 14), fill=FG)
    for i, (name, desc, col) in enumerate([
        ("pending/", "New commands awaiting processing", TEAL),
        ("running/", "Currently executing in dom0", YELLOW),
        ("results/", "Completed (stdout, stderr, exit code)", GREEN),
        ("history/", "Archived results by date", SOFT),
    ]):
        x = 40 + (i % 2) * 500
        yl = y + 45 + (i // 2) * 30
        d.ellipse((x, yl + 2, x + 12, yl + 14), fill=col)
        d.text((x + 18, yl), f"{name} — {desc}", font=ft, fill=SOFT)

    d.text((40, 590), "All state transitions are initiated by dom0 (pull model).",
           font=ft, fill=SOFT)
    d.text((40, 615), "github.com/GabrieleRisso/qvm-remote", font=fm, fill=SOFT)

    img.save(outdir / "queue-states.png")
    print(f"  queue-states.png ({W}x{H})")


# ─── Main ─────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage: generate-diagrams.py <output-dir>")
        sys.exit(1)

    outdir = Path(sys.argv[1])
    outdir.mkdir(parents=True, exist_ok=True)
    print("Generating diagrams...")
    gen_architecture(outdir)
    gen_security(outdir)
    gen_auth_flow(outdir)
    gen_queue_states(outdir)
    print("Done.")


if __name__ == "__main__":
    main()

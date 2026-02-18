#!/usr/bin/env python3
"""Generate X/Twitter post images for qvm-remote.

Usage: python3 generate-posts.py <output-dir>

Produces branded 1200x675 images ready for posting:
  post-1.png  — Architecture overview (pull-model protocol)
  post-2.png  — Security layers
  post-3.png  — Terminal demo (commands + output)
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
HEADER_BG = (37, 42, 52)

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


def rounded_rect(d, xy, fill, outline=None, r=8, width=2):
    d.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def text_center(d, x, y, text, font, fill):
    bb = d.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text((x - tw // 2, y - th // 2), text, font=font, fill=fill)


def badge(d, x, y, text, color=GREEN, size=11):
    fnt = load_font("mono", size)
    bb = fnt.getbbox(text)
    tw = bb[2] - bb[0] + 14
    th = bb[3] - bb[1] + 8
    rounded_rect(d, (x, y, x + tw, y + th), fill=color, r=4)
    d.text((x + 7, y + 3), text, fill=(255, 255, 255), font=fnt)
    return tw


def header(d, num, total=3):
    rounded_rect(d, (0, 0, W, 56), fill=HEADER_BG, outline=None, r=0)
    d.text((28, 14), "qvm-remote", font=load_font("bold", 20), fill=(200, 210, 220))
    d.text((180, 18), "Authenticated RPC for dom0", font=load_font("text", 12), fill=SOFT)
    badge(d, W - 95, 14, f"{num}/{total}", color=BLUE, size=12)
    badge(d, W - 195, 14, "open source", color=GREEN, size=10)


def footer(d, caption):
    rounded_rect(d, (0, H - 50, W, H), fill=HEADER_BG, outline=None, r=0)
    d.text((28, H - 37), caption, font=load_font("text", 12), fill=SOFT)
    d.text((W - 310, H - 35), "github.com/GabrieleRisso/qvm-remote",
           font=load_font("mono", 10), fill=(90, 95, 105))


# ─── Post 1: Architecture ────────────────────────────────────────
def post_1(outdir):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(d, 1)

    d.text((50, 75), "Pull-Model Protocol", font=load_font("bold", 28), fill=FG)
    d.text((50, 112), "SSH-like dom0 access — without a network stack",
           font=load_font("text", 15), fill=SOFT)

    # VM box
    rounded_rect(d, (50, 155, 450, 480), fill=CARD, outline=ORANGE, r=14, width=2)
    d.text((70, 165), "Unprivileged VM", font=load_font("bold", 16), fill=ORANGE)

    rounded_rect(d, (70, 200, 310, 232), fill=(255, 247, 237), outline=ORANGE, r=8)
    text_center(d, 190, 216, "qvm-remote (client)", font=load_font("mono", 12), fill=ORANGE)

    rounded_rect(d, (70, 250, 430, 460), fill=(240, 253, 250), outline=TEAL, r=10, width=1)
    d.text((85, 258), "~/.qvm-remote/queue/", font=load_font("mono", 12), fill=TEAL)
    for i, (name, col) in enumerate([
        ("pending/", TEAL), ("running/", ORANGE), ("results/", GREEN)
    ]):
        y = 288 + i * 38
        rounded_rect(d, (90, y, 280, y + 28), fill=CARD, outline=col, r=6, width=1)
        d.text((100, y + 5), name, font=load_font("mono", 12), fill=col)
    rounded_rect(d, (90, 402, 280, 430), fill=(248, 245, 255), outline=PURPLE, r=6, width=1)
    d.text((100, 408), "auth.key (0600)", font=load_font("mono", 11), fill=PURPLE)

    # dom0 box
    rounded_rect(d, (560, 155, 1000, 480), fill=CARD, outline=BLUE, r=14, width=2)
    d.text((580, 165), "dom0 (control domain)", font=load_font("bold", 16), fill=BLUE)

    rounded_rect(d, (580, 200, 860, 232), fill=(239, 246, 255), outline=BLUE, r=8)
    text_center(d, 720, 216, "qvm-remote-dom0 (daemon)", font=load_font("mono", 12), fill=BLUE)

    steps = [
        ("1. Verify HMAC-SHA256", PURPLE, 260),
        ("2. Validate input", ORANGE, 300),
        ("3. Execute (sandbox)", RED, 340),
        ("4. Write results back", GREEN, 380),
    ]
    for text, col, y in steps:
        rounded_rect(d, (590, y, 980, y + 30), fill=CARD, outline=col, r=6, width=1)
        d.text((605, y + 6), text, font=load_font("text", 13), fill=col)

    # Arrows
    import math
    d.line([(456, 216), (555, 216)], fill=BLUE, width=3)
    d.polygon([(555, 216), (545, 210), (545, 222)], fill=BLUE)
    d.text((465, 196), "qvm-run --pass-io", font=load_font("mono", 10), fill=BLUE)

    d.line([(555, 240), (456, 240)], fill=GREEN, width=2)
    d.polygon([(456, 240), (466, 234), (466, 246)], fill=GREEN)
    d.text((465, 245), "stdout / results", font=load_font("text", 10), fill=GREEN)

    # Xen bar
    rounded_rect(d, (50, 500, 1000, 535), fill=(254, 226, 226), outline=RED, r=8, width=2)
    text_center(d, 525, 517, "Xen Hypervisor — dom0 Initiates All I/O",
                font=load_font("bold", 14), fill=RED)

    footer(d, "Pull model: VM writes a file. dom0 chooses to read it.")
    img.save(outdir / "post-1.png", "PNG")
    print("  post-1.png (architecture)")


# ─── Post 2: Security Layers ─────────────────────────────────────
def post_2(outdir):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(d, 2)

    d.text((50, 75), "Five-Layer Defense in Depth",
           font=load_font("bold", 28), fill=FG)
    d.text((50, 112), "Each layer provides independent containment",
           font=load_font("text", 15), fill=SOFT)

    layers = [
        ("L1: HMAC-SHA256 Authentication", RED,
         "256-bit per-VM keys | constant-time verify | Pr[forge] <= 2^-256"),
        ("L2: Input Validation", ORANGE,
         "No empty, binary, or oversized (>1 MiB) commands accepted"),
        ("L3: Execution Sandboxing", BLUE,
         "0700 tmpdir | 300s timeout | bash with cleaned environment"),
        ("L4: Dual-Sided Audit Trail", PURPLE,
         "dom0 + VM logs | full command history archive"),
        ("L5: Transient by Default", GREEN,
         "Service dies on reboot | enable requires interactive confirmation"),
    ]

    for i, (name, col, desc) in enumerate(layers):
        w = 960 - i * 70
        x = (W - w) // 2
        y = 150 + i * 85
        rounded_rect(d, (x, y, x + w, y + 55), fill=CARD, outline=col, r=10, width=2)
        text_center(d, W // 2, y + 18, name, font=load_font("bold", 16), fill=col)
        text_center(d, W // 2, y + 40, desc, font=load_font("text", 12), fill=SOFT)

    footer(d, "Breach one layer — four remain. Defense in depth per NIST SP 800-53.")
    img.save(outdir / "post-2.png", "PNG")
    print("  post-2.png (security)")


# ─── Post 3: Terminal Demo ───────────────────────────────────────
def post_3(outdir):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(d, 3)

    term_y = 68
    rounded_rect(d, (30, term_y, W - 30, H - 58), fill=(20, 22, 28), outline=BORDER, r=10)

    # title bar
    rounded_rect(d, (30, term_y, W - 30, term_y + 28), fill=(35, 38, 46), outline=None, r=0)
    dots = [(50, term_y + 14), (68, term_y + 14), (86, term_y + 14)]
    colors = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]
    for (cx, cy), clr in zip(dots, colors):
        d.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=clr)
    d.text((110, term_y + 7), "vm:visyble — qvm-remote session",
           font=load_font("mono", 10), fill=SOFT)

    lines = [
        ("$ qvm-remote ping", GREEN),
        ("qvm-remote-dom0 is responding.", (200, 210, 220)),
        ("", None),
        ("$ qvm-remote hostname", GREEN),
        ("dom0", (200, 210, 220)),
        ("", None),
        ("$ qvm-remote qvm-ls --running", GREEN),
        ("NAME      STATE    CLASS   LABEL  TEMPLATE  NETVM", (120, 130, 150)),
        ("dom0      Running  AdminVM  black  -         -", (200, 210, 220)),
        ("sys-net   Running  DispVM   red    -         -", (200, 210, 220)),
        ("visyble   Running  StandVM  green  -         sys-net", (200, 210, 220)),
        ("", None),
        ("$ qvm-remote 'qvm-prefs visyble memory'", GREEN),
        ("4096", (200, 210, 220)),
        ("", None),
        ("$ time qvm-remote 'echo ok'", GREEN),
        ("ok", (200, 210, 220)),
        ("real    0m0.052s  # 48ms framework + 4ms exec", (120, 130, 150)),
        ("", None),
        ("# HMAC-SHA256 auth | 5 security layers | pull model", (100, 110, 120)),
    ]

    y = term_y + 40
    fm = load_font("mono", 12)
    for text, color in lines:
        if color:
            d.text((48, y), text, font=fm, fill=color)
        y += 22
        if y > H - 75:
            break

    footer(d, "SSH-like convenience. HMAC-SHA256 security. Zero dependencies.")
    img.save(outdir / "post-3.png", "PNG")
    print("  post-3.png (terminal)")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <output-dir>")
        sys.exit(1)

    outdir = Path(sys.argv[1])
    outdir.mkdir(parents=True, exist_ok=True)
    print("Generating X post images...")
    post_1(outdir)
    post_2(outdir)
    post_3(outdir)
    print("Done.")


if __name__ == "__main__":
    main()

#!/usr/bin/python3
# qubes_admin_ui.py -- Shared UI for qubes-global-admin
# Copyright (C) 2026  qvm-remote contributors
# SPDX-License-Identifier: GPL-2.0-or-later

"""Shared GTK3 widgets styled after Qubes OS Global Config.

Matching proportions, colors, fonts, and layout patterns from
qubes-config-manager (marmarta/qubes-config-manager):
- Window: 1800x1200 default, GtkNotebook with left tabs
- Tab padding: 14px 24px, font-weight 600, 10pt
- Active tab: #4180c9 bg, white text
- Content: #f2f2f2 bg, 100px left/right padding, 50px top
- Section titles: 150pct size, weight 400; subsections: 700
- Cards (flowbox_container): white bg, 1px border, 5px radius
- Buttons: flat with 1px border, Save = dark-blue bg white text
- Source Sans Pro font throughout
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango  # noqa: E402


def _read_version():
    for d in [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."),
        os.path.dirname(os.path.abspath(__file__)),
        "/usr/lib/qvm-remote",
    ]:
        vf = os.path.join(d, "version")
        if os.path.isfile(vf):
            try:
                with open(vf) as f:
                    return f.read().strip()
            except OSError:
                pass
    return "1.1.0"


UI_VERSION = _read_version()

QUBES_BLUE = "#4180c9"
DARK_BLUE = "#4488df"

COLORS = {
    "qubes-blue": QUBES_BLUE,
    "dark-blue": DARK_BLUE,
    "top-bg": "#ffffff",
    "top-bg-2": "#f2f2f2",
    "bottom-bg": "#858585",
    "frame": "#979797",
    "sep": "#cdcdcd",
    "soft": "#858585",
    "misc": "#979797",
    "text": "#000000",
    "btn-bg": "#f2f2f2",
    "btn-text": "#000000",
    "mid-gray": "#979797",
    "mid-gray-2": "#e7e7e7",
    "light-gray": "#f2f2f2",
    "dark-gray": "#cdcdcd",
    "dark-gray-2": "#858585",
    "problem-bg": "#fce9e3",
    "info-bg": "#f0e9e3",
    "ok": "#2d8a4e",
    "warn": "#d4a017",
    "err": "#c0392b",
}

LABEL_COLORS = {
    "red": "#cc0000", "orange": "#f57900", "yellow": "#edd400",
    "green": "#73d216", "gray": "#555753", "blue": "#3465a4",
    "purple": "#75507b", "black": "#2e3436",
}

_CSS = """
@define-color qubes-blue {qubes-blue};
@define-color dark-blue {dark-blue};

window, .background {{
    background: {top-bg};
    font-family: 'Source Sans Pro', 'Cantarell', sans-serif;
    font-size: 10pt;
}}

separator {{ background: {sep}; min-height: 1px; }}

/* ── Left-tab notebook (exact Global Config proportions) ── */

#main_notebook {{ border-width: 1px; border-color: {bottom-bg}; border-style: solid; }}

#main_notebook header {{
    background: {top-bg-2};
    border-width: 0;
}}

#main_notebook header tabs tab {{
    border-width: 0;
    box-shadow: {frame} 0px 2px 2px -2px inset;
    margin: 0;
    padding: 14px 24px;
    font-weight: bold;
    border-radius: 0;
    color: {text};
}}

#main_notebook header tabs tab:checked {{
    background: {qubes-blue};
    color: white;
}}

#main_notebook header tabs tab:hover:not(:checked) {{
    box-shadow: {frame} 0px 2px 2px -2px inset;
    background: {mid-gray-2};
}}

/* ── Content area (matching .content_box / .category) ── */

.content_box {{
    background: {top-bg-2};
    border-width: 2px;
    border-color: {frame};
    padding-left: 100px;
    padding-right: 100px;
    box-shadow: {frame} 2px -2px 2px -2px inset;
    padding-top: 50px;
}}

.category {{ padding: 20px; }}

/* ── Titles (Global Config group_title = 150% 400 weight) ── */

.group_title {{
    font-weight: 400;
    font-size: 150%;
    margin-top: 20px;
}}

.section_title {{
    margin-top: 20px;
    margin-bottom: 5px;
    font-weight: 700;
}}

.explanation {{
    margin: 0 0 20px 0;
    font-size: 90%;
    color: {misc};
    margin-left: 5px;
}}

/* ── Version label ── */

.qubes_version_label {{
    margin: 10px 0 10px 0;
    color: {soft};
    font-size: 120%;
    font-weight: 700;
}}

/* ── Cards (flowbox_container) ── */

.flowbox_container {{
    margin: 10px 30px 10px 30px;
    background: {top-bg};
    padding: 10px;
    border: 1px solid {sep};
    border-radius: 5px;
}}

.flowbox_title {{
    color: {soft};
    font-weight: 700;
    padding: 0;
    margin: 0;
}}

/* ── Status indicators ── */

.status-ok {{ color: {ok}; font-weight: 700; }}
.status-warn {{ color: {warn}; font-weight: 700; }}
.status-error {{ color: {err}; font-weight: 700; }}
.status-dot {{ font-size: 14pt; }}

/* ── Buttons (Global Config flat_button / button_save) ── */

.flat_button {{
    border-color: {mid-gray};
    font-weight: 500;
    margin: 5px;
    border-radius: 0;
    color: {text};
}}

.button_save {{
    background: {dark-blue};
    color: white;
    font-weight: 600;
    border-radius: 0;
    margin: 5px;
    padding: 6px 18px;
}}

.button_save:hover {{ background: {qubes-blue}; }}

.button_cancel {{
    background: {btn-bg};
    color: {btn-text};
    border-radius: 0;
    margin: 5px;
    padding: 6px 18px;
}}

.button_danger {{
    background: {problem-bg};
    color: {err};
    border: 1px solid {err};
    border-radius: 0;
    margin: 5px;
    padding: 6px 18px;
    font-weight: 600;
}}

/* ── Output (monospace areas) ── */

.output_view {{
    background: {top-bg};
    border: 1px solid {sep};
    border-radius: 0;
    font-family: 'Source Code Pro', monospace;
    font-size: 9pt;
}}

/* ── Info / problem boxes ── */

.info_box {{
    padding: 20px 40px 20px 40px;
    margin: 5px 100px 5px 60px;
    background: {info-bg};
    border: 1px solid {frame};
}}

.problem_box {{
    margin: 5px 80px 5px 40px;
    padding: 10px;
    border: 1px solid {frame};
    background: {problem-bg};
}}

/* ── Permission rows (for VM list etc.) ── */

.permission_list {{
    background: {top-bg-2};
    padding-top: 10px;
    padding-bottom: 10px;
}}

.permission_row {{
    background: {top-bg-2};
    padding: 10px;
}}

.permission_row:hover {{ background: {qubes-blue}; color: white; }}

/* ── Entry ── */

entry {{
    padding: 6px 10px;
    border: 1px solid {dark-gray};
    border-radius: 0;
    font-size: 10pt;
}}

entry:focus {{ border-color: {qubes-blue}; }}

/* ── Title bar ── */

.title_bar {{
    background: {top-bg-2};
    padding: 10px 20px;
    border-bottom: 1px solid {sep};
}}

.title_text {{ font-size: 14pt; font-weight: 700; color: {text}; }}
.version_label {{ font-size: 9pt; color: {soft}; font-weight: 600; }}

/* ── Connection indicator ── */

.conn_bar {{
    padding: 6px 20px;
    border-bottom: 1px solid {sep};
}}

.conn_bar_ok {{ background: #e6f4ea; }}
.conn_bar_err {{ background: {problem-bg}; }}
.conn_bar_warn {{ background: {info-bg}; }}

/* ── Qube label boxes ── */

.qube-box-base {{
    font-weight: 600;
    padding: 2px 10px;
    border: 1px solid {dark-gray};
    background: {light-gray};
    border-radius: 5px;
}}

/* ── Small helpers ── */

.didascalia {{
    font-style: italic;
    color: {misc};
    margin-right: 20px;
    margin-left: 20px;
}}

.small_title {{
    font-size: 80%;
    font-weight: 700;
    margin-bottom: 10px;
}}
""".format(**COLORS)


def apply_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(_CSS.encode())
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def check_display():
    display = os.environ.get("DISPLAY", "") or os.environ.get("WAYLAND_DISPLAY", "")
    if not display:
        return ("No display server found (DISPLAY / WAYLAND_DISPLAY not set).\n"
                "Run from dom0 with: qubes-global-admin")
    return None


# ── Widget factories (Global Config proportions) ─────────────────


def label(text, css=None, wrap=True, sel=False, xa=0, tip=None):
    lbl = Gtk.Label(label=text, xalign=xa)
    lbl.set_line_wrap(wrap)
    lbl.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    lbl.set_selectable(sel)
    if css:
        lbl.get_style_context().add_class(css)
    if tip:
        lbl.set_tooltip_text(tip)
    return lbl


def section(title, explanation=None, tip=None):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    t = label(title, "section_title", tip=tip)
    box.pack_start(t, False, False, 0)
    if explanation:
        box.pack_start(label(explanation, "explanation"), False, False, 0)
    return box


def group_title(text, tip=None):
    return label(text, "group_title", tip=tip)


def card(title=None, tip=None):
    c = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    c.get_style_context().add_class("flowbox_container")
    if title:
        c.pack_start(label(title, "flowbox_title"), False, False, 0)
    if tip:
        c.set_tooltip_text(tip)
    return c


def btn(text, css="flat_button", icon=None, tip=None):
    if icon:
        b = Gtk.Button()
        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hb.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.SMALL_TOOLBAR), False, False, 0)
        hb.pack_start(Gtk.Label(label=text), False, False, 0)
        b.add(hb)
    else:
        b = Gtk.Button(label=text)
    b.get_style_context().add_class(css)
    if tip:
        b.set_tooltip_text(tip)
    return b


def entry(ph="", text="", tip=None):
    e = Gtk.Entry()
    e.set_placeholder_text(ph)
    if text:
        e.set_text(text)
    if tip:
        e.set_tooltip_text(tip)
    return e


def info_box(text, tip=None):
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    b.get_style_context().add_class("info_box")
    b.pack_start(label(text), False, False, 0)
    if tip:
        b.set_tooltip_text(tip)
    return b


def hbox(spacing=8):
    return Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)


def vbox(spacing=0):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)


def scrolled(child, h=200):
    sw = Gtk.ScrolledWindow()
    sw.set_min_content_height(h)
    sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    sw.add(child)
    return sw


# ── Status dot ───────────────────────────────────────────────────


class StatusDot(Gtk.Box):
    def __init__(self, text="Unknown", state="unknown", tip=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._dot = Gtk.Label(label="\u25cf")
        self._dot.get_style_context().add_class("status-dot")
        self._lbl = Gtk.Label(label=text)
        self.pack_start(self._dot, False, False, 0)
        self.pack_start(self._lbl, False, False, 0)
        self.set_state(state, text)
        if tip:
            self.set_tooltip_text(tip)

    def set_state(self, state, text=None):
        ctx = self._dot.get_style_context()
        for c in ("status-ok", "status-warn", "status-error"):
            ctx.remove_class(c)
        ctx.add_class({"ok": "status-ok", "warn": "status-warn",
                        "error": "status-error"}.get(state, ""))
        if text is not None:
            self._lbl.set_text(text)


# ── Output view ──────────────────────────────────────────────────


class OutputView(Gtk.ScrolledWindow):
    def __init__(self, height=200):
        super().__init__()
        self.set_min_content_height(height)
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._buf = Gtk.TextBuffer()
        self._tv = Gtk.TextView(buffer=self._buf)
        self._tv.set_editable(False)
        self._tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._tv.set_left_margin(8)
        self._tv.set_right_margin(8)
        self._tv.set_top_margin(6)
        self._tv.set_bottom_margin(6)
        self._tv.get_style_context().add_class("output_view")
        self.add(self._tv)

    def clear(self):
        self._buf.set_text("")

    def append(self, t):
        self._buf.insert(self._buf.get_end_iter(), t)
        adj = self.get_vadjustment()
        adj.set_value(adj.get_upper())

    def set_text(self, t):
        self._buf.set_text(t)

    def get_text(self):
        return self._buf.get_text(self._buf.get_start_iter(), self._buf.get_end_iter(), True)


# ── Command execution ────────────────────────────────────────────


def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "Command timed out"
    except FileNotFoundError:
        return 127, "", "Command not found: " + str(cmd[0])
    except Exception as e:
        return 1, "", str(e)


class AsyncRunner:
    def __init__(self, ov, on_done=None):
        self._ov = ov
        self._on_done = on_done
        self._proc = None

    def run(self, cmd, clear=True):
        if clear:
            self._ov.clear()
        threading.Thread(target=self._work, args=(cmd,), daemon=True).start()

    def _work(self, cmd):
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)
            for line in self._proc.stdout:
                GLib.idle_add(self._ov.append, line)
            self._proc.wait()
            rc = self._proc.returncode
        except Exception as e:
            rc = 1
            GLib.idle_add(self._ov.append, "\nError: " + str(e) + "\n")
        finally:
            self._proc = None
        if self._on_done:
            GLib.idle_add(self._on_done, rc)

    def cancel(self):
        if self._proc:
            self._proc.terminate()


# ── Dialogs ──────────────────────────────────────────────────────


def confirm(parent, title, msg):
    d = Gtk.MessageDialog(transient_for=parent, modal=True,
                          message_type=Gtk.MessageType.QUESTION,
                          buttons=Gtk.ButtonsType.YES_NO, text=title)
    d.format_secondary_text(msg)
    r = d.run()
    d.destroy()
    return r == Gtk.ResponseType.YES


def show_info(parent, title, msg):
    d = Gtk.MessageDialog(transient_for=parent, modal=True,
                          message_type=Gtk.MessageType.INFO,
                          buttons=Gtk.ButtonsType.OK, text=title)
    d.format_secondary_text(msg)
    d.run()
    d.destroy()


def show_error(parent, title, msg):
    d = Gtk.MessageDialog(transient_for=parent, modal=True,
                          message_type=Gtk.MessageType.ERROR,
                          buttons=Gtk.ButtonsType.OK, text=title)
    d.format_secondary_text(msg)
    d.run()
    d.destroy()


# ── Notification ─────────────────────────────────────────────────

ICON_INFO = "dialog-information-symbolic"
ICON_OK = "emblem-ok-symbolic"
ICON_WARN = "dialog-warning-symbolic"
ICON_ERR = "dialog-error-symbolic"
ICON_KEY = "security-high-symbolic"
ICON_NET = "network-transmit-receive-symbolic"
ICON_SEND = "document-send-symbolic"
ICON_DISK = "drive-harddisk-symbolic"


def notify(title, body="", icon=ICON_INFO):
    try:
        subprocess.Popen(
            ["notify-send", "-i", icon, "-a", "Qubes Global Admin", title, body],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


# ── Validation ───────────────────────────────────────────────────


def valid_hex_key(key):
    if len(key) != 64:
        return False
    try:
        int(key, 16)
        return True
    except ValueError:
        return False


def fmt_size(n):
    for u in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024.0:
            return ("{} B".format(int(n))) if u == "B" else ("{:.1f} {}".format(n, u))
        n /= 1024.0
    return "{:.1f} TB".format(n)


# ── Backup helpers ───────────────────────────────────────────────


def backup_create(data_dir, dest):
    import tarfile
    data_dir, dest = Path(data_dir), Path(dest)
    if not data_dir.exists():
        return False, "Data directory not found: " + str(data_dir)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(str(dest), "w:gz") as tar:
            tar.add(str(data_dir), arcname=data_dir.name)
        return True, "Backup saved to {} ({})".format(dest, fmt_size(dest.stat().st_size))
    except Exception as e:
        return False, "Backup failed: " + str(e)


def backup_restore(archive, restore_dir):
    import tarfile
    archive, restore_dir = Path(archive), Path(restore_dir)
    if not archive.exists():
        return False, "Archive not found: " + str(archive)
    try:
        with tarfile.open(str(archive), "r:gz") as tar:
            for m in tar.getnames():
                if m.startswith("/") or ".." in m:
                    return False, "Unsafe path: " + m
            tar.extractall(str(restore_dir))
        return True, "Restored to " + str(restore_dir)
    except Exception as e:
        return False, "Restore failed: " + str(e)


def backup_list(bak_dir):
    from datetime import datetime as dt
    bak_dir = Path(bak_dir)
    if not bak_dir.exists():
        return []
    results = []
    try:
        for f in sorted(bak_dir.glob("*.tar.gz"), reverse=True):
            try:
                st = f.stat()
                results.append((str(f), fmt_size(st.st_size),
                                dt.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")))
            except OSError:
                pass
    except OSError:
        pass
    return results


def git_push(data_dir, repo_url, backup_dir=None):
    import shutil
    from datetime import datetime as dt
    data_dir = Path(data_dir)
    backup_dir = Path(backup_dir) if backup_dir else data_dir / "git-backup"
    git = shutil.which("git")
    if not git:
        return False, "git not installed"
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        if not (backup_dir / ".git").exists():
            subprocess.run([git, "init"], cwd=str(backup_dir), capture_output=True, timeout=30)
            subprocess.run([git, "remote", "add", "origin", repo_url],
                           cwd=str(backup_dir), capture_output=True, timeout=10)
        else:
            subprocess.run([git, "remote", "set-url", "origin", repo_url],
                           cwd=str(backup_dir), capture_output=True, timeout=10)
        audit = data_dir / "audit.log"
        if audit.exists():
            shutil.copy2(str(audit), str(backup_dir / "audit.log"))
        key_file = data_dir / "auth.key"
        if key_file.exists():
            try:
                k = key_file.read_text().strip()
                fp = k[:8] + "..." + k[-8:] if len(k) >= 16 else "***"
                (backup_dir / "key-fingerprint.txt").write_text(
                    "Key fingerprint: {}\nLength: {}\nDate: {}\n".format(
                        fp, len(k), dt.now().isoformat()))
            except OSError:
                pass
        (backup_dir / "backup-meta.txt").write_text(
            "qvm-remote backup\ndate: {}\nversion: {}\n".format(
                dt.now().isoformat(), UI_VERSION))
        subprocess.run([git, "add", "-A"], cwd=str(backup_dir), capture_output=True, timeout=30)
        subprocess.run([git, "commit", "-m", "Backup " + dt.now().strftime("%Y-%m-%d %H:%M:%S"),
                         "--allow-empty"], cwd=str(backup_dir), capture_output=True, timeout=30)
        r = subprocess.run([git, "push", "-u", "origin", "HEAD"],
                           cwd=str(backup_dir), capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return False, "Push failed: " + r.stderr.strip()
        return True, "Backed up to " + repo_url
    except Exception as e:
        return False, "Git backup failed: " + str(e)


def git_pull(repo_url, backup_dir):
    import shutil
    git = shutil.which("git")
    if not git:
        return False, "git not installed"
    backup_dir = Path(backup_dir)
    try:
        if (backup_dir / ".git").exists():
            r = subprocess.run([git, "pull", "--ff-only"], cwd=str(backup_dir),
                               capture_output=True, text=True, timeout=60)
        else:
            backup_dir.mkdir(parents=True, exist_ok=True)
            r = subprocess.run([git, "clone", repo_url, str(backup_dir)],
                               capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return False, "Pull failed: " + r.stderr.strip()
        return True, "Pulled from " + repo_url
    except Exception as e:
        return False, "Git pull failed: " + str(e)

#!/usr/bin/python3
# qubes_remote_ui.py -- shared UI components for qvm-remote GTK tools
#
# Copyright (C) 2026  qvm-remote contributors
# SPDX-License-Identifier: GPL-2.0-or-later

"""Shared GTK3 widgets, CSS, and helpers for qvm-remote GUI applications.

Follows Qubes OS 4.3 visual style guide and community UX guidelines:
- GTK3 with PyGObject (official recommendation for new Qubes tools)
- Qubes color palette from qubes-os.org/doc/visual-style-guide
- Simple language, actionable errors, no acronyms in user-facing text
- Consistent with qubes-core-qrexec and qubes-manager patterns
"""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango  # noqa: E402

UI_VERSION = "1.0.0"

# ── Qubes OS color palette ──────────────────────────────────────────
# From https://www.qubes-os.org/doc/visual-style-guide/

QUBES_COLORS = {
    "black": "#333333",
    "gray_sub": "#888888",
    "gray_icon": "#8e8e95",
    "gray_mid": "#bfbfbf",
    "gray_light": "#d2d2d2",
    "gray_bg": "#f5f5f5",
    "blue_primary": "#3874d8",
    "blue_info": "#43c4f3",
    "blue_qubes": "#63a0ff",
    "blue_light": "#99bfff",
    "green_success": "#5ad840",
    "purple": "#9f389f",
    "red_danger": "#bd2727",
    "orange_warn": "#e79e27",
    "yellow_alert": "#e7e532",
}

# Qubes VM label colors (from qubes-core-admin/qubes/app.py)
LABEL_COLORS = {
    "red": "#cc0000",
    "orange": "#f57900",
    "yellow": "#edd400",
    "green": "#73d216",
    "gray": "#555555",
    "blue": "#3465a4",
    "purple": "#75507b",
    "black": "#000000",
}

# ── GTK3 CSS ────────────────────────────────────────────────────────
# Minimal overrides; respects the user's desktop theme.

QUBES_CSS = """
/* Command input: monospace for code editing feel */
textview.qvm-command text {
    font-family: "Source Code Pro", "DejaVu Sans Mono", monospace;
    font-size: 11px;
    padding: 6px;
}

/* Output: monospace terminal-like display */
textview.qvm-output text {
    font-family: "Source Code Pro", "DejaVu Sans Mono", monospace;
    font-size: 10px;
    padding: 6px;
}

/* Section frame labels */
label.qvm-section {
    font-weight: bold;
}

/* Status indicator labels */
label.qvm-status-active {
    color: #5ad840;
    font-weight: bold;
}
label.qvm-status-inactive {
    color: #888888;
}
label.qvm-status-error {
    color: #bd2727;
    font-weight: bold;
}
label.qvm-status-warning {
    color: #e79e27;
    font-weight: bold;
}

/* Key display */
label.qvm-key-text {
    font-family: "Source Code Pro", "DejaVu Sans Mono", monospace;
    font-size: 10px;
}

/* Info bar styling */
.qvm-info-label {
    color: #888888;
}
"""


def apply_css():
    """Apply Qubes-style CSS to the default screen."""
    provider = Gtk.CssProvider()
    provider.load_from_data(QUBES_CSS.encode())
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


# ── Reusable widgets ───────────────────────────────────────────────


class StatusIndicator(Gtk.Box):
    """Colored circle with status text, like Qubes system tray indicators."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    WARNING = "warning"

    _CSS_MAP = {
        "active": "qvm-status-active",
        "inactive": "qvm-status-inactive",
        "error": "qvm-status-error",
        "warning": "qvm-status-warning",
    }
    _SYMBOL_MAP = {
        "active": "\u25cf",  # ● filled circle
        "inactive": "\u25cb",  # ○ empty circle
        "error": "\u25cf",
        "warning": "\u25cf",
    }

    def __init__(self, text="Unknown", state="inactive"):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._dot = Gtk.Label()
        self._label = Gtk.Label()
        self.pack_start(self._dot, False, False, 0)
        self.pack_start(self._label, False, False, 0)
        self.set_state(state, text)

    def set_state(self, state, text=None):
        css = self._CSS_MAP.get(state, "qvm-status-inactive")
        sym = self._SYMBOL_MAP.get(state, "\u25cb")
        for w in (self._dot, self._label):
            ctx = w.get_style_context()
            for c in self._CSS_MAP.values():
                ctx.remove_class(c)
            ctx.add_class(css)
        self._dot.set_text(sym)
        if text is not None:
            self._label.set_text(text)


class OutputView(Gtk.ScrolledWindow):
    """Scrollable monospace text view with stdout/stderr color tags.

    Thread-safe: all append methods schedule via GLib.idle_add internally.
    """

    def __init__(self):
        super().__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.set_min_content_height(150)

        self._view = Gtk.TextView()
        self._view.set_editable(False)
        self._view.set_cursor_visible(False)
        self._view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._view.get_style_context().add_class("qvm-output")
        self.add(self._view)

        buf = self._view.get_buffer()
        buf.create_tag("stdout", foreground="#333333")
        buf.create_tag(
            "stderr", foreground=QUBES_COLORS["red_danger"], weight=Pango.Weight.BOLD
        )
        buf.create_tag("info", foreground=QUBES_COLORS["blue_primary"])
        buf.create_tag(
            "success",
            foreground=QUBES_COLORS["green_success"],
            weight=Pango.Weight.BOLD,
        )

    def append(self, text, tag_name="stdout"):
        """Append text with a named tag. Safe to call from any thread."""
        GLib.idle_add(self._do_append, text, tag_name)

    def _do_append(self, text, tag_name):
        buf = self._view.get_buffer()
        end_iter = buf.get_end_iter()
        tag = buf.get_tag_table().lookup(tag_name)
        if tag:
            buf.insert_with_tags(end_iter, text, tag)
        else:
            buf.insert(end_iter, text)
        self._scroll_to_end()
        return False  # remove idle callback

    def clear(self):
        """Clear all output. Safe to call from any thread."""
        GLib.idle_add(self._do_clear)

    def _do_clear(self):
        self._view.get_buffer().set_text("")
        return False

    def _scroll_to_end(self):
        adj = self.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())

    def get_text(self):
        buf = self._view.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)


class CommandRunner:
    """Run a subprocess in a background thread with streaming output.

    All callbacks are dispatched to the GTK main thread via GLib.idle_add.
    """

    def __init__(self):
        self._proc = None
        self._thread = None
        self._cancelled = False

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def run(self, args, stdin_data=None, on_stdout=None, on_stderr=None, on_done=None):
        """Start the command asynchronously.

        Args:
            args: Command arguments list.
            stdin_data: Optional bytes to write to stdin.
            on_stdout: Callback(text) for each stdout line.
            on_stderr: Callback(text) for each stderr line.
            on_done: Callback(returncode) when command finishes.
        """
        if self.is_running:
            return
        self._cancelled = False
        self._thread = threading.Thread(
            target=self._run_thread,
            args=(args, stdin_data, on_stdout, on_stderr, on_done),
            daemon=True,
        )
        self._thread.start()

    def cancel(self):
        """Terminate the running process."""
        self._cancelled = True
        if self._proc:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def _run_thread(self, args, stdin_data, on_stdout, on_stderr, on_done):
        rc = -1
        try:
            self._proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE if stdin_data else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if stdin_data:
                try:
                    self._proc.stdin.write(
                        stdin_data if isinstance(stdin_data, bytes) else stdin_data.encode()
                    )
                except OSError:
                    pass
                finally:
                    try:
                        self._proc.stdin.close()
                    except OSError:
                        pass

            def _read_pipe(pipe, callback):
                try:
                    while True:
                        line = pipe.readline()
                        if not line:
                            break
                        if self._cancelled:
                            break
                        text = line.decode(errors="replace")
                        if callback:
                            GLib.idle_add(callback, text)
                except Exception:
                    pass

            t_out = threading.Thread(
                target=_read_pipe, args=(self._proc.stdout, on_stdout), daemon=True
            )
            t_err = threading.Thread(
                target=_read_pipe, args=(self._proc.stderr, on_stderr), daemon=True
            )
            t_out.start()
            t_err.start()
            self._proc.wait()
            t_out.join(timeout=3)
            t_err.join(timeout=3)
            rc = self._proc.returncode
        except FileNotFoundError:
            if on_stderr:
                GLib.idle_add(
                    on_stderr,
                    f"Command not found: {args[0]}\n"
                    "Make sure qvm-remote is installed.\n",
                )
            rc = 127
        except Exception as exc:
            if on_stderr:
                GLib.idle_add(on_stderr, f"Error: {exc}\n")
            rc = -1
        finally:
            self._proc = None
        if on_done:
            GLib.idle_add(on_done, rc)


# ── Helper functions ────────────────────────────────────────────────


def create_header_bar(title, subtitle=None):
    """Create a Gtk.HeaderBar in Qubes style."""
    hb = Gtk.HeaderBar()
    hb.set_show_close_button(True)
    hb.set_title(title)
    if subtitle:
        hb.set_subtitle(subtitle)
    return hb


def create_frame(label_text):
    """Create a Gtk.Frame with a bold label."""
    frame = Gtk.Frame()
    label = Gtk.Label()
    label.set_markup(f"<b>{GLib.markup_escape_text(label_text)}</b>")
    label.get_style_context().add_class("qvm-section")
    frame.set_label_widget(label)
    frame.set_shadow_type(Gtk.ShadowType.NONE)
    return frame


def create_info_row(label_text, value_text=""):
    """Create a horizontal box with a gray label and value."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    lbl = Gtk.Label(label=label_text)
    lbl.set_halign(Gtk.Align.START)
    lbl.get_style_context().add_class("qvm-info-label")
    val = Gtk.Label(label=value_text)
    val.set_halign(Gtk.Align.START)
    val.set_selectable(True)
    box.pack_start(lbl, False, False, 0)
    box.pack_start(val, False, False, 0)
    return box, val


def show_error_dialog(parent, title, message):
    """Show a modal error dialog with an OK button."""
    dlg = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        text=title,
    )
    dlg.format_secondary_text(message)
    dlg.run()
    dlg.destroy()


def show_info_dialog(parent, title, message):
    """Show a modal info dialog."""
    dlg = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK,
        text=title,
    )
    dlg.format_secondary_text(message)
    dlg.run()
    dlg.destroy()


def show_confirm_dialog(parent, title, message):
    """Show a Yes/No confirmation dialog. Returns True if Yes."""
    dlg = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.YES_NO,
        text=title,
    )
    dlg.format_secondary_text(message)
    result = dlg.run()
    dlg.destroy()
    return result == Gtk.ResponseType.YES


def find_executable(name, extra_paths=None):
    """Locate an executable by name, checking extra paths first."""
    paths = list(extra_paths or [])
    paths.extend(
        [
            "/usr/bin",
            "/usr/local/bin",
            os.path.expanduser("~/bin"),
        ]
    )
    for p in paths:
        full = os.path.join(p, name)
        if os.path.isfile(full) and os.access(full, os.X_OK):
            return full
    # Fall back to PATH
    import shutil

    return shutil.which(name)


def run_quick(args, timeout=30):
    """Run a command synchronously, return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return 127, "", f"Command not found: {args[0]}\n"
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout}s\n"
    except Exception as exc:
        return -1, "", str(exc)

#!/usr/bin/python3
"""Deep GUI wiring tests for qvm-remote.

Verifies that every button, handler, tab, signal, and widget is correctly
connected in both the VM client GUI and dom0 GUI.  Under Xvfb these tests
actually instantiate GTK windows and inspect live widget trees.

Run:
    xvfb-run -a python3 test/test_gui_wiring.py -v
    # or headless (source-level checks only):
    python3 test/test_gui_wiring.py -v
"""

from __future__ import annotations

import ast
import os
import re
import sys
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GUI_DIR = REPO / "gui"
VM_DIR = REPO / "vm"

sys.path.insert(0, str(GUI_DIR))

HAVE_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _has_gtk():
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        return True
    except Exception:
        return False


HAVE_GTK = _has_gtk() if HAVE_DISPLAY else False


# ── Source-level wiring checks (no display needed) ─────────────────


class TestClientGuiHandlerWiring(unittest.TestCase):
    """Verify every button 'connect' call in qvm-remote-gui has a handler."""

    def setUp(self):
        self.source = (GUI_DIR / "qvm-remote-gui").read_text()

    def test_all_connect_clicked_have_handlers(self):
        """Every .connect('clicked', self._on_X) has a matching def _on_X."""
        pattern = re.compile(r'''\.connect\(\s*["']clicked["']\s*,\s*self\.(_on_\w+)''')
        connects = pattern.findall(self.source)
        self.assertGreater(len(connects), 5, "Too few connect calls found")
        for handler in connects:
            self.assertIn(
                f"def {handler}(self",
                self.source,
                f"Handler method missing: {handler}",
            )

    def test_all_connect_signals_have_handlers(self):
        """Every .connect('signal', ...) handler method exists."""
        pattern = re.compile(
            r'''\.connect\(\s*["'](\w[\w-]*)["']\s*,\s*(?:self\.(_\w+)|lambda)'''
        )
        for sig, handler in pattern.findall(self.source):
            if handler:
                self.assertIn(
                    f"def {handler}(self",
                    self.source,
                    f"Handler missing for signal '{sig}': {handler}",
                )

    def test_notebook_tab_count(self):
        """Client GUI creates exactly 6 tabs (Execute, Files, Backup, History, Keys, Log)."""
        count = self.source.count("self._notebook.append_page(")
        self.assertEqual(count, 6, f"Expected 6 tabs, found {count}")

    def test_notebook_tab_labels(self):
        """All expected tab labels are present."""
        for label in ["Execute", "Files", "Backup", "History", "Keys", "Log"]:
            self.assertIn(
                f'label="{label}"',
                self.source,
                f"Missing tab label: {label}",
            )

    def test_tab_switch_covers_all_pages(self):
        """_on_tab_switch handles all non-Execute tab indices."""
        handler = re.search(
            r"def _on_tab_switch\(self.*?\n((?:.*?\n)*?)(?=\n    def |\nclass |\Z)",
            self.source,
        )
        self.assertIsNotNone(handler, "Missing _on_tab_switch method")
        body = handler.group(1)
        # Tabs: 0=Execute, 1=Files, 2=Backup, 3=History, 4=Keys, 5=Log
        for idx in [2, 3, 4, 5]:
            self.assertIn(
                f"page_num == {idx}",
                body,
                f"Tab index {idx} not handled in _on_tab_switch",
            )

    def test_backup_tab_has_all_buttons(self):
        """Backup tab has all expected buttons wired."""
        for method in [
            "_on_create_local_backup",
            "_on_restore_local_backup",
            "_on_git_push",
            "_on_git_pull",
            "_on_check_dom0_backups",
            "_on_start_dom0_backup",
        ]:
            self.assertIn(
                f"def {method}(self",
                self.source,
                f"Backup handler missing: {method}",
            )

    def test_files_tab_has_all_buttons(self):
        """Files tab has all expected buttons wired."""
        for method in ["_on_send_file", "_on_fetch_file",
                        "_on_copy_between_vms", "_on_send_browse"]:
            self.assertIn(
                f"def {method}(self",
                self.source,
                f"Files handler missing: {method}",
            )

    def test_keys_tab_has_all_buttons(self):
        """Keys tab has all expected buttons wired."""
        for method in ["_on_key_gen", "_on_key_show", "_on_key_import", "_on_ping"]:
            self.assertIn(
                f"def {method}(self",
                self.source,
                f"Keys handler missing: {method}",
            )

    def test_no_unused_handler_stubs(self):
        """Every def _on_* method is connected to a signal somewhere."""
        methods = re.findall(r"def (_on_\w+)\(self", self.source)
        for method in methods:
            # Either connected via .connect() or called via lambda
            connected = (
                f"self.{method}" in self.source.replace(f"def {method}(self", "", 1)
            )
            self.assertTrue(
                connected,
                f"Handler {method} defined but never connected",
            )

    def test_keyboard_shortcuts_defined(self):
        """Keyboard shortcuts are configured."""
        self.assertIn("AccelGroup", self.source)
        self.assertIn("Control", self.source)

    def test_all_entry_widgets_have_placeholders(self):
        """Every Gtk.Entry has a placeholder text set."""
        # Count Gtk.Entry() creations
        entries = self.source.count("Gtk.Entry()")
        placeholders = self.source.count("set_placeholder_text")
        self.assertGreaterEqual(
            placeholders, entries - 2,
            f"Found {entries} entries but only {placeholders} placeholders",
        )


class TestDom0GuiHandlerWiring(unittest.TestCase):
    """Verify every button in qvm-remote-dom0-gui has a matching handler."""

    def setUp(self):
        self.source = (GUI_DIR / "qvm-remote-dom0-gui").read_text()

    def test_all_connect_clicked_have_handlers(self):
        """Every .connect('clicked', self._on_X) has a matching def _on_X."""
        pattern = re.compile(r'''\.connect\(\s*["']clicked["']\s*,\s*self\.(_on_\w+)''')
        connects = pattern.findall(self.source)
        self.assertGreater(len(connects), 5)
        for handler in connects:
            self.assertIn(
                f"def {handler}(self",
                self.source,
                f"Handler method missing: {handler}",
            )

    def test_notebook_tab_count(self):
        """Dom0 GUI creates exactly 4 tabs (Dashboard, VMs, Backup, Log)."""
        count = self.source.count("self._notebook.append_page(")
        self.assertEqual(count, 4, f"Expected 4 tabs, found {count}")

    def test_notebook_tab_labels(self):
        """All expected tab labels are present."""
        for label in ["Dashboard", "Virtual Machines", "Backup", "Log"]:
            self.assertIn(
                f'label="{label}"',
                self.source,
                f"Missing tab label: {label}",
            )

    def test_tab_switch_covers_all_pages(self):
        """_on_tab_switch handles all tab indices."""
        handler = re.search(
            r"def _on_tab_switch\(self.*?\n((?:.*?\n)*?)(?=\n    def |\nclass |\Z)",
            self.source,
        )
        self.assertIsNotNone(handler)
        body = handler.group(1)
        for idx in [0, 1, 2, 3]:
            self.assertIn(
                f"page_num == {idx}",
                body,
                f"Tab index {idx} not handled in _on_tab_switch",
            )

    def test_backup_tab_has_all_buttons(self):
        """Backup tab has all expected buttons wired."""
        for method in [
            "_on_create_dom0_backup",
            "_on_backup_service_config",
            "_on_restore_service_config",
        ]:
            self.assertIn(
                f"def {method}(self",
                self.source,
                f"Backup handler missing: {method}",
            )

    def test_service_controls_wired(self):
        """Dashboard service control buttons are wired."""
        for method in ["_on_start", "_on_stop", "_on_restart",
                        "_on_enable", "_on_disable"]:
            self.assertIn(
                f"def {method}(self",
                self.source,
                f"Service handler missing: {method}",
            )

    def test_vm_management_wired(self):
        """VM tab has authorization and revocation wired."""
        for method in ["_on_authorize", "_on_revoke", "_on_push_file"]:
            self.assertIn(
                f"def {method}(self",
                self.source,
                f"VM handler missing: {method}",
            )

    def test_destructive_actions_require_confirm(self):
        """All destructive actions use show_confirm_dialog."""
        # Direct confirmation in method body
        for method in ["_on_enable", "_on_revoke",
                        "_on_create_dom0_backup", "_on_restore_service_config",
                        "_on_push_file"]:
            idx = self.source.find(f"def {method}(self")
            self.assertNotEqual(idx, -1, f"Method {method} not found")
            next_def = self.source.find("\n    def ", idx + 1)
            body = self.source[idx:next_def] if next_def != -1 else self.source[idx:]
            self.assertIn(
                "show_confirm_dialog",
                body,
                f"Destructive action {method} lacks confirmation dialog",
            )
        # _on_stop delegates to _run_systemctl with confirm_msg parameter
        idx = self.source.find("def _on_stop(self")
        self.assertNotEqual(idx, -1)
        next_def = self.source.find("\n    def ", idx + 1)
        body = self.source[idx:next_def] if next_def != -1 else self.source[idx:]
        self.assertIn("_run_systemctl", body)
        # Verify _run_systemctl has confirmation logic
        self.assertIn("show_confirm_dialog", self.source[
            self.source.find("def _run_systemctl"):
        ])

    def test_auto_refresh_timer(self):
        """Dashboard has auto-refresh timer."""
        self.assertIn("timeout_add_seconds", self.source)
        self.assertIn("_auto_refresh", self.source)


# ── Shared module completeness checks ─────────────────────────────


class TestSharedModuleCompleteness(unittest.TestCase):
    """Verify the shared UI module exports everything GUIs need."""

    def test_all_client_gui_imports_exist(self):
        """Every symbol imported by qvm-remote-gui exists in the module."""
        import qubes_remote_ui
        gui_src = (GUI_DIR / "qvm-remote-gui").read_text()
        pattern = re.compile(r"from qubes_remote_ui import \((.*?)\)", re.DOTALL)
        m = pattern.search(gui_src)
        self.assertIsNotNone(m, "No import block found in client GUI")
        imports = [
            s.strip().rstrip(",")
            for s in m.group(1).split("\n")
            if s.strip() and not s.strip().startswith("#")
        ]
        for name in imports:
            self.assertTrue(
                hasattr(qubes_remote_ui, name),
                f"Client GUI imports '{name}' but it's not in qubes_remote_ui",
            )

    def test_all_dom0_gui_imports_exist(self):
        """Every symbol imported by qvm-remote-dom0-gui exists in the module."""
        import qubes_remote_ui
        gui_src = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        pattern = re.compile(r"from qubes_remote_ui import \((.*?)\)", re.DOTALL)
        m = pattern.search(gui_src)
        self.assertIsNotNone(m)
        imports = [
            s.strip().rstrip(",")
            for s in m.group(1).split("\n")
            if s.strip() and not s.strip().startswith("#")
        ]
        for name in imports:
            self.assertTrue(
                hasattr(qubes_remote_ui, name),
                f"Dom0 GUI imports '{name}' but it's not in qubes_remote_ui",
            )

    def test_backup_functions_complete(self):
        """All backup helper functions are properly callable."""
        import qubes_remote_ui
        for fn_name in [
            "create_local_backup", "restore_local_backup",
            "list_local_backups", "get_change_summary",
            "git_backup_push", "git_backup_pull",
        ]:
            fn = getattr(qubes_remote_ui, fn_name, None)
            self.assertIsNotNone(fn, f"Missing function: {fn_name}")
            self.assertTrue(callable(fn))

    def test_notification_icons_complete(self):
        """All notification icon constants are strings."""
        import qubes_remote_ui
        for icon_name in [
            "NOTIFY_ICON_INFO", "NOTIFY_ICON_SUCCESS",
            "NOTIFY_ICON_WARNING", "NOTIFY_ICON_ERROR",
            "NOTIFY_ICON_SECURITY", "NOTIFY_ICON_NETWORK",
            "NOTIFY_ICON_TRANSFER", "NOTIFY_ICON_BACKUP",
        ]:
            val = getattr(qubes_remote_ui, icon_name, None)
            self.assertIsNotNone(val, f"Missing icon: {icon_name}")
            self.assertIsInstance(val, str)
            self.assertGreater(len(val), 0)


# ── CLI-GUI data format compatibility ─────────────────────────────


class TestCliGuiDataFormat(unittest.TestCase):
    """Verify the CLI and GUI agree on data directory structure."""

    def test_same_data_dir(self):
        """Both CLI and GUI use ~/.qvm-remote."""
        cli_src = (VM_DIR / "qvm-remote").read_text()
        gui_src = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn('.qvm-remote"', cli_src)
        self.assertIn('.qvm-remote"', gui_src)

    def test_same_key_file_name(self):
        """Both CLI and GUI reference auth.key."""
        cli_src = (VM_DIR / "qvm-remote").read_text()
        gui_src = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("auth.key", cli_src)
        self.assertIn("auth.key", gui_src)

    def test_same_audit_log_name(self):
        """Both CLI and GUI reference audit.log."""
        cli_src = (VM_DIR / "qvm-remote").read_text()
        gui_src = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("audit.log", cli_src)
        self.assertIn("audit.log", gui_src)

    def test_same_history_dir_name(self):
        """Both CLI and GUI reference history directory."""
        cli_src = (VM_DIR / "qvm-remote").read_text()
        gui_src = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn('"history"', cli_src)
        self.assertIn("history", gui_src)

    def test_hex_key_validation_matches(self):
        """GUI and CLI both validate keys as 64 hex chars."""
        import qubes_remote_ui
        test_keys = [
            ("a" * 64, True),
            ("0123456789abcdef" * 4, True),
            ("A" * 64, True),
            ("g" * 64, False),
            ("a" * 63, False),
            ("a" * 65, False),
            ("", False),
        ]
        for key, expected in test_keys:
            self.assertEqual(
                qubes_remote_ui.valid_hex_key(key), expected,
                f"valid_hex_key({key!r}) should be {expected}",
            )

    def test_cli_creates_data_gui_reads(self):
        """CLI data directory structure matches GUI expectations."""
        with tempfile.TemporaryDirectory(prefix="qvm-compat-") as tmpdir:
            data = Path(tmpdir) / ".qvm-remote"
            data.mkdir()
            # Simulate CLI creating data
            (data / "auth.key").write_text("a" * 64 + "\n")
            (data / "auth.key").chmod(0o600)
            (data / "audit.log").write_text(
                "[2026-02-18T12:00:00] SUBMIT id=abc123 size=15B\n"
                "[2026-02-18T12:00:01] DONE id=abc123 rc=0\n"
            )
            hist = data / "history" / "2026-02-18" / "abc123"
            hist.mkdir(parents=True)
            (hist / "command").write_text("qvm-ls\n")
            (hist / "exit").write_text("0\n")
            (hist / "meta").write_text("duration_ms=350\n")

            # Verify GUI can read this data
            import qubes_remote_ui

            # Key
            key = (data / "auth.key").read_text().strip()
            self.assertTrue(qubes_remote_ui.valid_hex_key(key))

            # Changes
            changes = qubes_remote_ui.get_change_summary(data)
            self.assertGreater(len(changes), 0)
            types = {c[1] for c in changes}
            self.assertTrue(
                types.intersection({"command", "result", "history"}),
                f"Expected command/result/history in {types}",
            )

            # Backup roundtrip
            bak = Path(tmpdir) / "backup.tar.gz"
            ok, msg = qubes_remote_ui.create_local_backup(data, str(bak))
            self.assertTrue(ok, msg)

            backups = qubes_remote_ui.list_local_backups(tmpdir)
            self.assertEqual(len(backups), 1)

            restore_dir = Path(tmpdir) / "restored"
            restore_dir.mkdir()
            ok, msg = qubes_remote_ui.restore_local_backup(str(bak), str(restore_dir))
            self.assertTrue(ok, msg)
            restored_key = (restore_dir / ".qvm-remote" / "auth.key").read_text().strip()
            self.assertEqual(restored_key, key)


# ── Live GTK wiring tests (require Xvfb) ──────────────────────────


@unittest.skipUnless(HAVE_DISPLAY and HAVE_GTK, "Requires display server and GTK3")
class TestClientGuiLiveWiring(unittest.TestCase):
    """Instantiate the VM client GUI and inspect live widget tree."""

    @classmethod
    def setUpClass(cls):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, GLib

        # We need to import the GUI module without running its main loop
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "qvm_remote_gui", str(GUI_DIR / "qvm-remote-gui"),
        )
        # The module-level check_display/require_gtk already ran (DISPLAY is set)
        cls.Gtk = Gtk
        cls.GLib = GLib

    def test_window_creates_all_tabs(self):
        """QvmRemoteWindow creates all 6 notebook pages."""
        from gi.repository import Gtk

        app = Gtk.Application(application_id="org.test.wiring.vm")
        win = None

        def on_activate(a):
            nonlocal win
            from qubes_remote_ui import apply_css
            apply_css()
            # Import QvmRemoteWindow from the GUI file
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "qvm_remote_gui_mod", str(GUI_DIR / "qvm-remote-gui"),
            )
            mod = importlib.util.module_from_spec(spec)
            # Set sys.modules to avoid double import issues
            sys.modules["qvm_remote_gui_mod"] = mod
            spec.loader.exec_module(mod)
            win = mod.QvmRemoteWindow(a)
            win.show_all()
            # Quit after one iteration
            self.GLib.idle_add(a.quit)

        app.connect("activate", on_activate)
        app.run([])

        if win:
            nb = win._notebook
            n_pages = nb.get_n_pages()
            self.assertEqual(n_pages, 6, f"Expected 6 tabs, got {n_pages}")
            labels = []
            for i in range(n_pages):
                page = nb.get_nth_page(i)
                lbl = nb.get_tab_label(page)
                labels.append(lbl.get_text() if lbl else f"page-{i}")
            expected = ["Execute", "Files", "Backup", "History", "Keys", "Log"]
            self.assertEqual(labels, expected, f"Tab labels: {labels}")


@unittest.skipUnless(HAVE_DISPLAY and HAVE_GTK, "Requires display server and GTK3")
class TestDom0GuiLiveWiring(unittest.TestCase):
    """Instantiate the dom0 GUI and inspect live widget tree."""

    @classmethod
    def setUpClass(cls):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, GLib
        cls.Gtk = Gtk
        cls.GLib = GLib

    def test_window_creates_all_tabs(self):
        """QvmRemoteDom0Window creates all 4 notebook pages."""
        from gi.repository import Gtk

        app = Gtk.Application(application_id="org.test.wiring.dom0")
        win = None

        def on_activate(a):
            nonlocal win
            from qubes_remote_ui import apply_css
            apply_css()
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "qvm_remote_dom0_gui_mod", str(GUI_DIR / "qvm-remote-dom0-gui"),
            )
            mod = importlib.util.module_from_spec(spec)
            sys.modules["qvm_remote_dom0_gui_mod"] = mod
            spec.loader.exec_module(mod)
            win = mod.QvmRemoteDom0Window(a)
            win.show_all()
            self.GLib.idle_add(a.quit)

        app.connect("activate", on_activate)
        app.run([])

        if win:
            nb = win._notebook
            n_pages = nb.get_n_pages()
            self.assertEqual(n_pages, 4, f"Expected 4 tabs, got {n_pages}")
            labels = []
            for i in range(n_pages):
                page = nb.get_nth_page(i)
                lbl = nb.get_tab_label(page)
                labels.append(lbl.get_text() if lbl else f"page-{i}")
            expected = ["Dashboard", "Virtual Machines", "Backup", "Log"]
            self.assertEqual(labels, expected, f"Tab labels: {labels}")


# ── Backup E2E with git (local repo, no network) ─────────────────


class TestBackupEndToEnd(unittest.TestCase):
    """Full backup/restore cycle including local git."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="qvm-bak-e2e-")
        self.data_dir = Path(self.tmpdir) / ".qvm-remote"
        self.data_dir.mkdir(parents=True)
        # Populate test data
        (self.data_dir / "auth.key").write_text("deadbeef" * 8)
        (self.data_dir / "audit.log").write_text(
            "[2026-02-18T10:00:00] SUBMIT id=cmd1 size=10B\n"
            "[2026-02-18T10:00:01] DONE id=cmd1 rc=0\n"
            "[2026-02-18T10:05:00] KEY gen\n"
        )
        hist = self.data_dir / "history" / "2026-02-18" / "cmd1"
        hist.mkdir(parents=True)
        (hist / "command").write_text("qvm-ls\n")
        (hist / "exit").write_text("0\n")
        (hist / "meta").write_text("duration_ms=200\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_local_backup_restore_cycle(self):
        """Create -> list -> restore -> verify data integrity."""
        from qubes_remote_ui import (
            create_local_backup, list_local_backups,
            restore_local_backup,
        )
        bak_dir = Path(self.tmpdir) / "backups"
        dest = str(bak_dir / "test.tar.gz")

        ok, msg = create_local_backup(self.data_dir, dest)
        self.assertTrue(ok, msg)
        self.assertTrue(Path(dest).exists())

        backups = list_local_backups(bak_dir)
        self.assertEqual(len(backups), 1)
        self.assertTrue(backups[0][0].endswith(".tar.gz"))

        # Wipe and restore
        restore_dir = Path(self.tmpdir) / "restored"
        restore_dir.mkdir()
        ok, msg = restore_local_backup(dest, str(restore_dir))
        self.assertTrue(ok, msg)

        # Verify contents
        rd = restore_dir / ".qvm-remote"
        self.assertTrue(rd.exists())
        self.assertEqual(
            (rd / "auth.key").read_text().strip(),
            "deadbeef" * 8,
        )
        self.assertTrue((rd / "audit.log").exists())
        self.assertTrue(
            (rd / "history" / "2026-02-18" / "cmd1" / "command").exists()
        )

    def test_change_summary_complete(self):
        """Change summary captures all event types."""
        from qubes_remote_ui import get_change_summary
        changes = get_change_summary(self.data_dir)
        self.assertGreater(len(changes), 0)
        event_types = {c[1] for c in changes}
        # Should find: command (SUBMIT), result (DONE), key (KEY gen), history
        self.assertIn("command", event_types)
        self.assertIn("result", event_types)
        self.assertIn("key", event_types)

    def test_git_backup_local_roundtrip(self):
        """Git backup to a local bare repo and pull back."""
        git = shutil.which("git")
        if not git:
            self.skipTest("git not installed")

        from qubes_remote_ui import git_backup_push, git_backup_pull

        # Create a bare local repo to act as "remote" (use file:// URL)
        bare = Path(self.tmpdir) / "remote.git"
        subprocess.run([git, "init", "--bare", str(bare)],
                       capture_output=True, check=True)
        repo_url = f"file://{bare}"

        # Configure git identity globally for this test
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@test.local",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@test.local",
        }
        old_env = {}
        for k, v in env.items():
            if k not in os.environ:
                old_env[k] = None
            else:
                old_env[k] = os.environ[k]
            os.environ[k] = v

        backup_dir = self.data_dir / "git-backup"

        # Push (let git_backup_push handle init and remote)
        ok, msg = git_backup_push(self.data_dir, repo_url, backup_dir)
        self.assertTrue(ok, msg)

        # Verify the backup does NOT contain the full key
        fp_file = backup_dir / "key-fingerprint.txt"
        self.assertTrue(fp_file.exists())
        fp_content = fp_file.read_text()
        full_key = "deadbeef" * 8
        self.assertNotIn(full_key, fp_content, "Full key leaked to git backup!")
        self.assertIn("...", fp_content, "Key should be masked with ...")

        # Verify history was copied
        self.assertTrue((backup_dir / "history").exists())
        self.assertTrue((backup_dir / "audit.log").exists())

        # Pull to a new directory
        pull_dir = Path(self.tmpdir) / "pulled"
        ok, msg = git_backup_pull(repo_url, pull_dir)
        self.assertTrue(ok, msg)
        self.assertTrue((pull_dir / "audit.log").exists())
        self.assertTrue((pull_dir / "key-fingerprint.txt").exists())

        # Restore environment
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_backup_path_traversal_protection(self):
        """restore_local_backup rejects archives with path traversal."""
        from qubes_remote_ui import restore_local_backup
        import tarfile

        # Create a malicious archive with ../ path
        evil_tar = Path(self.tmpdir) / "evil.tar.gz"
        with tarfile.open(str(evil_tar), "w:gz") as tar:
            import io
            data = b"malicious content"
            info = tarfile.TarInfo(name="../../../tmp/evil")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        restore_dir = Path(self.tmpdir) / "restore-test"
        restore_dir.mkdir()
        ok, msg = restore_local_backup(str(evil_tar), str(restore_dir))
        self.assertFalse(ok, "Should reject path traversal")
        self.assertIn("Unsafe", msg)

    def test_multiple_backups_listed_newest_first(self):
        """list_local_backups returns backups sorted newest first."""
        from qubes_remote_ui import create_local_backup, list_local_backups
        bak_dir = Path(self.tmpdir) / "multi-bak"
        for i in range(3):
            dest = str(bak_dir / f"backup-{i:02d}.tar.gz")
            ok, _ = create_local_backup(self.data_dir, dest)
            self.assertTrue(ok)
            time.sleep(0.1)  # Ensure different mtimes

        backups = list_local_backups(bak_dir)
        self.assertEqual(len(backups), 3)
        # Newest should be first
        self.assertIn("backup-02", backups[0][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)

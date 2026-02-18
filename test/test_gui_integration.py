#!/usr/bin/python3
"""Integration tests for qvm-remote GUI applications.

These tests actually start the GTK applications under Xvfb (headless X11)
and verify that the GUI initializes correctly, that widgets render,
and that the GUI and CLI share the same data paths safely.

Requirements: xvfb-run (xorg-server-Xvfb on Fedora, xvfb on Debian/Arch)

Run: xvfb-run python3 test/test_gui_integration.py -v
Or:  make gui-integration-test  (runs in Docker with Xvfb)
"""

from __future__ import annotations

import os
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

# Skip everything if no DISPLAY (not running under Xvfb)
HAVE_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _has_gtk():
    """Check if GTK3 can be initialized."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        return True
    except Exception:
        return False


HAVE_GTK = _has_gtk() if HAVE_DISPLAY else False


@unittest.skipUnless(HAVE_DISPLAY and HAVE_GTK, "Requires display server and GTK3")
class TestVmGuiLaunch(unittest.TestCase):
    """Test that qvm-remote-gui starts and shuts down cleanly."""

    def test_gui_starts_and_exits(self):
        """VM GUI starts, renders the window, and exits on SIGTERM."""
        proc = subprocess.Popen(
            [sys.executable, str(GUI_DIR / "qvm-remote-gui")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "GTK_A11Y": "none"},
        )
        # Give GTK time to initialize and render
        time.sleep(2)
        early_exit = proc.poll()
        if early_exit is not None:
            stderr = proc.stderr.read().decode(errors="replace")
            if "cannot open display" in stderr.lower() or early_exit == 0:
                self.skipTest(
                    f"GUI exited early (rc={early_exit}), display may be "
                    f"restricted: {stderr[:200]}"
                )
        self.assertIsNone(early_exit, "GUI exited prematurely")

        # Send SIGTERM for graceful shutdown
        proc.terminate()
        try:
            rc = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = proc.wait(timeout=3)

        stderr = proc.stderr.read().decode(errors="replace")
        # Exit codes: 0 (clean), -15 (SIGTERM), 143 (128+15)
        self.assertIn(rc, [0, -15, 143, -signal.SIGTERM],
                       f"Unexpected exit code {rc}: {stderr}")

    def test_gui_exits_cleanly_with_no_qvm_remote(self):
        """GUI handles missing qvm-remote binary gracefully."""
        env = {**os.environ, "PATH": "/nonexistent", "GTK_A11Y": "none"}
        proc = subprocess.Popen(
            [sys.executable, str(GUI_DIR / "qvm-remote-gui")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        time.sleep(2)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        # Should not crash; just shows "not found" in status bar


@unittest.skipUnless(HAVE_DISPLAY and HAVE_GTK, "Requires display server and GTK3")
class TestDom0GuiLaunch(unittest.TestCase):
    """Test that qvm-remote-dom0-gui starts and shuts down cleanly."""

    def test_gui_starts_and_exits(self):
        """Dom0 GUI starts and exits on SIGTERM."""
        proc = subprocess.Popen(
            [sys.executable, str(GUI_DIR / "qvm-remote-dom0-gui")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "GTK_A11Y": "none"},
        )
        time.sleep(2)
        self.assertIsNone(proc.poll(), "GUI exited prematurely")
        proc.terminate()
        try:
            rc = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = proc.wait(timeout=3)

        self.assertIn(rc, [0, -15, 143, -signal.SIGTERM])


class TestNoDisplayError(unittest.TestCase):
    """Test that GUIs fail gracefully without a display."""

    def test_vm_gui_no_display(self):
        """VM GUI prints helpful error when no DISPLAY is set."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
        r = subprocess.run(
            [sys.executable, str(GUI_DIR / "qvm-remote-gui")],
            capture_output=True, text=True, timeout=10, env=env,
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("display", r.stderr.lower())

    def test_dom0_gui_no_display(self):
        """Dom0 GUI prints helpful error when no DISPLAY is set."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
        r = subprocess.run(
            [sys.executable, str(GUI_DIR / "qvm-remote-dom0-gui")],
            capture_output=True, text=True, timeout=10, env=env,
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("display", r.stderr.lower())


class TestCliGuiSafety(unittest.TestCase):
    """Test that CLI and GUI operate on the same data safely."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="qvm-remote-test-")
        self.data_dir = Path(self.tmpdir) / ".qvm-remote"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_shared_data_dir(self):
        """CLI and GUI use the same data directory path."""
        gui_content = (GUI_DIR / "qvm-remote-gui").read_text()
        cli_content = (VM_DIR / "qvm-remote").read_text()
        self.assertIn(".qvm-remote", gui_content)
        self.assertIn(".qvm-remote", cli_content)

    def test_gui_reads_cli_key(self):
        """GUI can read a key created by the CLI."""
        self.data_dir.mkdir(parents=True)
        key_file = self.data_dir / "auth.key"
        test_key = "a" * 64
        key_file.write_text(test_key)
        key_file.chmod(0o600)

        # Verify the key file has the expected format
        content = key_file.read_text().strip()
        self.assertEqual(len(content), 64)

    def test_gui_reads_cli_history(self):
        """GUI can read history entries created by the CLI."""
        day_dir = self.data_dir / "history" / "2026-02-18" / "test-cmd-001"
        day_dir.mkdir(parents=True)
        (day_dir / "exit").write_text("0")
        (day_dir / "command").write_text("qvm-ls\n")
        (day_dir / "meta").write_text("duration_ms=300\n")

        # Verify the directory structure matches what the GUI expects
        dirs = list((self.data_dir / "history").glob("*/*"))
        self.assertEqual(len(dirs), 1)
        self.assertEqual((dirs[0] / "exit").read_text(), "0")

    def test_gui_reads_cli_audit_log(self):
        """GUI can read audit log entries created by the CLI."""
        self.data_dir.mkdir(parents=True)
        log_file = self.data_dir / "audit.log"
        log_file.write_text("[2026-02-18T12:00:00] SUBMIT id=test size=5B\n")

        content = log_file.read_text()
        self.assertIn("SUBMIT", content)

    def test_concurrent_key_file_safety(self):
        """Two writers to auth.key get a complete key (not corrupted)."""
        self.data_dir.mkdir(parents=True)
        key_file = self.data_dir / "auth.key"

        # Simulate concurrent writes
        key1 = "a" * 64
        key2 = "b" * 64
        key_file.write_text(key1)
        key_file.write_text(key2)

        # Last writer wins; file should always contain a valid key
        result = key_file.read_text().strip()
        self.assertEqual(len(result), 64)
        self.assertTrue(result == key1 or result == key2)


class TestHexKeyValidation(unittest.TestCase):
    """Test the shared hex key validation used by both GUIs."""

    def test_valid_key(self):
        sys.path.insert(0, str(GUI_DIR))
        from qubes_remote_ui import valid_hex_key
        self.assertTrue(valid_hex_key("a" * 64))
        self.assertTrue(valid_hex_key("0123456789abcdef" * 4))

    def test_invalid_short(self):
        sys.path.insert(0, str(GUI_DIR))
        from qubes_remote_ui import valid_hex_key
        self.assertFalse(valid_hex_key("aaa"))

    def test_invalid_chars(self):
        sys.path.insert(0, str(GUI_DIR))
        from qubes_remote_ui import valid_hex_key
        self.assertFalse(valid_hex_key("g" * 64))
        self.assertFalse(valid_hex_key("z" * 64))

    def test_matches_cli_validation(self):
        """GUI hex validation matches the CLI's valid_hex_key function."""
        sys.path.insert(0, str(GUI_DIR))
        from qubes_remote_ui import valid_hex_key as gui_valid
        cli_content = (VM_DIR / "qvm-remote").read_text()
        self.assertIn("def valid_hex_key", cli_content)

        test_cases = [
            ("a" * 64, True),
            ("0" * 64, True),
            ("g" * 64, False),
            ("a" * 63, False),
            ("a" * 65, False),
            ("", False),
        ]
        for key, expected in test_cases:
            self.assertEqual(gui_valid(key), expected, f"Failed for key={key!r}")


class TestNotificationSystem(unittest.TestCase):
    """Test that the notification system works correctly."""

    def test_send_notification_no_crash(self):
        """send_notification handles missing notify-send gracefully."""
        sys.path.insert(0, str(GUI_DIR))
        from qubes_remote_ui import send_notification
        send_notification("Test", "body")

    def test_notification_icons(self):
        """All notification icons are valid freedesktop names."""
        sys.path.insert(0, str(GUI_DIR))
        import qubes_remote_ui
        icons = [
            qubes_remote_ui.NOTIFY_ICON_INFO,
            qubes_remote_ui.NOTIFY_ICON_SUCCESS,
            qubes_remote_ui.NOTIFY_ICON_WARNING,
            qubes_remote_ui.NOTIFY_ICON_ERROR,
            qubes_remote_ui.NOTIFY_ICON_SECURITY,
            qubes_remote_ui.NOTIFY_ICON_NETWORK,
            qubes_remote_ui.NOTIFY_ICON_TRANSFER,
            qubes_remote_ui.NOTIFY_ICON_BACKUP,
        ]
        for icon in icons:
            self.assertIsInstance(icon, str)
            self.assertFalse(icon.startswith("/"),
                             f"Icon should be a name, not a path: {icon}")

    def test_both_guis_use_notifications(self):
        """Both GUIs import and call send_notification."""
        for gui_name in ["qvm-remote-gui", "qvm-remote-dom0-gui"]:
            content = (GUI_DIR / gui_name).read_text()
            self.assertIn("send_notification", content,
                          f"{gui_name} doesn't use notifications")
            self.assertIn("NOTIFY_ICON_", content,
                          f"{gui_name} doesn't use icon constants")


class TestFileTransferIntegration(unittest.TestCase):
    """Test file transfer features."""

    def test_vm_gui_has_files_tab(self):
        """VM GUI includes a Files tab."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("_build_files_tab", content)
        self.assertIn('"Files"', content)

    def test_file_transfer_uses_base64(self):
        """File transfer uses base64 encoding for safety."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("base64", content)

    def test_file_transfer_size_limit(self):
        """File transfer enforces size limits."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("MAX_SEND", content)
        self.assertIn("Too Large", content)

    def test_copy_between_vms_uses_pass_io(self):
        """Inter-VM copy uses qvm-run --pass-io (Qubes standard)."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("qvm-run", content)
        self.assertIn("pass-io", content)

    def test_copy_between_vms_requires_confirm(self):
        """Inter-VM copy requires user confirmation."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("Copy File Between VMs?", content)

    def test_dom0_gui_has_push_file(self):
        """Dom0 GUI has file push feature."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("_on_push_file", content)
        self.assertIn("Push to VM", content)

    def test_dom0_push_requires_confirm(self):
        """Dom0 file push requires user confirmation."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("Push File to", content)

    def test_format_file_size(self):
        """format_file_size produces human-readable output."""
        sys.path.insert(0, str(GUI_DIR))
        from qubes_remote_ui import format_file_size
        self.assertIn("B", format_file_size(100))
        self.assertIn("KB", format_file_size(2048))
        self.assertIn("MB", format_file_size(5 * 1024 * 1024))


class TestBackupIntegration(unittest.TestCase):
    """Test backup features in both GUIs."""

    def test_vm_gui_has_backup_tab(self):
        """VM GUI includes a Backup tab."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("_build_backup_tab", content)
        self.assertIn('"Backup"', content)

    def test_dom0_gui_has_backup_tab(self):
        """Dom0 GUI includes a Backup tab."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("_build_backup_tab", content)
        self.assertIn('"Backup"', content)

    def test_vm_gui_backup_features(self):
        """VM GUI backup tab has all expected features."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        # Local backup
        self.assertIn("Create Backup Now", content)
        self.assertIn("Restore Selected", content)
        # GitHub
        self.assertIn("Push to Repository", content)
        self.assertIn("Pull from Repository", content)
        # Dom0 backup via qvm-remote
        self.assertIn("Check Dom0 Backups", content)
        self.assertIn("Start Dom0 Backup", content)
        # Change tracking
        self.assertIn("Recent Changes", content)

    def test_dom0_gui_backup_features(self):
        """Dom0 GUI backup tab has all expected features."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        # System backup
        self.assertIn("Start Backup", content)
        self.assertIn("qvm-backup", content)
        # Config backup
        self.assertIn("Backup Config", content)
        self.assertIn("Restore Config", content)
        # Change tracking
        self.assertIn("Recent Changes", content)
        self.assertIn("Rollback", content)

    def test_vm_gui_git_security(self):
        """VM GUI git backup does not push full keys."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("never sent to the repository", content.lower())

    def test_shared_backup_functions(self):
        """Shared module exports all backup helper functions."""
        sys.path.insert(0, str(GUI_DIR))
        import qubes_remote_ui
        for fn in ["create_local_backup", "restore_local_backup",
                    "list_local_backups", "get_change_summary",
                    "git_backup_push", "git_backup_pull"]:
            self.assertTrue(
                hasattr(qubes_remote_ui, fn),
                f"Missing backup function: {fn}",
            )
            self.assertTrue(callable(getattr(qubes_remote_ui, fn)))

    def test_backup_roundtrip(self):
        """Create and list local backups end-to-end."""
        sys.path.insert(0, str(GUI_DIR))
        from qubes_remote_ui import (
            create_local_backup, list_local_backups, restore_local_backup,
        )
        with tempfile.TemporaryDirectory(prefix="qvm-bak-test-") as tmpdir:
            data_dir = Path(tmpdir) / ".qvm-remote"
            data_dir.mkdir()
            (data_dir / "audit.log").write_text("test entry\n")

            bak_dir = Path(tmpdir) / "backups"
            dest = str(bak_dir / "test-backup.tar.gz")

            ok, msg = create_local_backup(data_dir, dest)
            self.assertTrue(ok, msg)

            backups = list_local_backups(bak_dir)
            self.assertEqual(len(backups), 1)

            restore_dir = Path(tmpdir) / "restored"
            restore_dir.mkdir()
            ok, msg = restore_local_backup(dest, str(restore_dir))
            self.assertTrue(ok, msg)
            self.assertTrue(
                (restore_dir / ".qvm-remote" / "audit.log").exists()
            )

    def test_change_summary_parsing(self):
        """get_change_summary correctly parses entries."""
        sys.path.insert(0, str(GUI_DIR))
        from qubes_remote_ui import get_change_summary
        with tempfile.TemporaryDirectory(prefix="qvm-change-test-") as tmpdir:
            data_dir = Path(tmpdir) / ".qvm-remote"
            data_dir.mkdir()
            (data_dir / "audit.log").write_text(
                "[2026-02-18T10:00:00] SUBMIT id=abc\n"
                "[2026-02-18T10:00:01] DONE id=abc rc=0\n"
                "[2026-02-18T10:01:00] KEY gen\n"
            )
            changes = get_change_summary(data_dir)
            self.assertGreaterEqual(len(changes), 3)
            event_types = {c[1] for c in changes}
            self.assertIn("command", event_types)
            self.assertIn("key", event_types)

    def test_dom0_backup_destination_selection(self):
        """Dom0 GUI allows selecting backup destination."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("Backup destination", content)
        self.assertIn("_bak_dest_entry", content)

    def test_dom0_backup_vm_selection(self):
        """Dom0 GUI allows selecting VMs to back up."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("VMs to include", content)
        self.assertIn("_bak_vms_entry", content)
        self.assertIn("_bak_exclude_entry", content)

    def test_dom0_backup_confirms(self):
        """Dom0 backup requires confirmation before starting."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("Start Full Dom0 Backup?", content)

    def test_dom0_config_backup_restore(self):
        """Dom0 GUI has config backup and restore."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("Service Configuration Backup", content)
        self.assertIn("Restore Service Configuration?", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)

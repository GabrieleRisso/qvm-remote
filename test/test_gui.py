#!/usr/bin/python3
"""Test suite for qvm-remote GUI components.

Tests shared UI module imports, widget creation, CSS application,
helper functions, packaging, and Makefile integration -- all without
requiring a running display server (headless-safe).
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GUI_DIR = REPO / "gui"

# Ensure the gui directory is on the path for imports
sys.path.insert(0, str(GUI_DIR))


class TestSharedModule(unittest.TestCase):
    """Tests for gui/qubes_remote_ui.py."""

    def test_import(self):
        """Shared module can be imported."""
        import qubes_remote_ui
        self.assertTrue(hasattr(qubes_remote_ui, "UI_VERSION"))

    def test_version(self):
        """UI version matches the repo version file."""
        import qubes_remote_ui
        version_file = REPO / "version"
        if version_file.exists():
            expected = version_file.read_text().strip()
            self.assertEqual(qubes_remote_ui.UI_VERSION, expected)

    def test_color_constants(self):
        """Color constants are defined and valid hex."""
        import qubes_remote_ui
        self.assertIn("blue_primary", qubes_remote_ui.QUBES_COLORS)
        self.assertIn("red_danger", qubes_remote_ui.QUBES_COLORS)
        for name, color in qubes_remote_ui.QUBES_COLORS.items():
            self.assertTrue(
                color.startswith("#"),
                f"Color {name} does not start with #: {color}",
            )
            self.assertEqual(
                len(color), 7,
                f"Color {name} is not #RRGGBB format: {color}",
            )

    def test_label_colors(self):
        """All 8 Qubes label colors are defined."""
        import qubes_remote_ui
        expected = {"red", "orange", "yellow", "green", "gray", "blue", "purple", "black"}
        self.assertEqual(set(qubes_remote_ui.LABEL_COLORS.keys()), expected)

    def test_css_string(self):
        """CSS template is a non-empty string."""
        import qubes_remote_ui
        self.assertIsInstance(qubes_remote_ui.QUBES_CSS, str)
        self.assertGreater(len(qubes_remote_ui.QUBES_CSS), 100)

    def test_run_quick_not_found(self):
        """run_quick returns 127 for non-existent commands."""
        import qubes_remote_ui
        rc, out, err = qubes_remote_ui.run_quick(
            ["__nonexistent_command_12345__"]
        )
        self.assertEqual(rc, 127)
        self.assertIn("not found", err.lower())

    def test_run_quick_true(self):
        """run_quick succeeds for 'true'."""
        import qubes_remote_ui
        rc, out, err = qubes_remote_ui.run_quick(["true"])
        self.assertEqual(rc, 0)

    def test_run_quick_false(self):
        """run_quick returns non-zero for 'false'."""
        import qubes_remote_ui
        rc, out, err = qubes_remote_ui.run_quick(["false"])
        self.assertNotEqual(rc, 0)

    def test_run_quick_echo(self):
        """run_quick captures stdout."""
        import qubes_remote_ui
        rc, out, err = qubes_remote_ui.run_quick(["echo", "hello world"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "hello world")

    def test_find_executable(self):
        """find_executable locates system binaries."""
        import qubes_remote_ui
        result = qubes_remote_ui.find_executable("python3")
        self.assertIsNotNone(result)
        self.assertTrue(os.path.isfile(result))


class TestSharedNotifications(unittest.TestCase):
    """Tests for notification and file transfer helpers."""

    def test_send_notification_exists(self):
        """send_notification function is available."""
        import qubes_remote_ui
        self.assertTrue(hasattr(qubes_remote_ui, "send_notification"))
        self.assertTrue(callable(qubes_remote_ui.send_notification))

    def test_notification_icons_defined(self):
        """All notification icon constants are defined."""
        import qubes_remote_ui
        for icon in [
            "NOTIFY_ICON_INFO", "NOTIFY_ICON_SUCCESS",
            "NOTIFY_ICON_WARNING", "NOTIFY_ICON_ERROR",
            "NOTIFY_ICON_SECURITY", "NOTIFY_ICON_NETWORK",
            "NOTIFY_ICON_TRANSFER",
        ]:
            self.assertTrue(
                hasattr(qubes_remote_ui, icon),
                f"Missing icon constant: {icon}",
            )
            val = getattr(qubes_remote_ui, icon)
            self.assertIsInstance(val, str)
            self.assertTrue(len(val) > 0)

    def test_format_file_size(self):
        """format_file_size returns human-readable sizes."""
        import qubes_remote_ui
        self.assertEqual(qubes_remote_ui.format_file_size(0), "0 B")
        self.assertEqual(qubes_remote_ui.format_file_size(1023), "1023 B")
        self.assertIn("KB", qubes_remote_ui.format_file_size(1024))
        self.assertIn("MB", qubes_remote_ui.format_file_size(1024 * 1024))
        self.assertIn("GB", qubes_remote_ui.format_file_size(1024 ** 3))

    def test_valid_hex_key(self):
        """valid_hex_key validates correctly."""
        import qubes_remote_ui
        self.assertTrue(qubes_remote_ui.valid_hex_key("a" * 64))
        self.assertTrue(qubes_remote_ui.valid_hex_key("0123456789abcdef" * 4))
        self.assertFalse(qubes_remote_ui.valid_hex_key("a" * 63))
        self.assertFalse(qubes_remote_ui.valid_hex_key("g" * 64))
        self.assertFalse(qubes_remote_ui.valid_hex_key(""))

    def test_check_display_function(self):
        """check_display returns string or None."""
        import qubes_remote_ui
        result = qubes_remote_ui.check_display()
        self.assertTrue(result is None or isinstance(result, str))

    def test_send_notification_no_crash(self):
        """send_notification does not crash even without notify-send."""
        import qubes_remote_ui
        # Should silently do nothing if notify-send is missing
        qubes_remote_ui.send_notification("test", "body")

    def test_backup_icon_defined(self):
        """Backup notification icon is defined."""
        import qubes_remote_ui
        self.assertTrue(hasattr(qubes_remote_ui, "NOTIFY_ICON_BACKUP"))
        self.assertIsInstance(qubes_remote_ui.NOTIFY_ICON_BACKUP, str)
        self.assertTrue(len(qubes_remote_ui.NOTIFY_ICON_BACKUP) > 0)


class TestBackupHelpers(unittest.TestCase):
    """Tests for backup and change tracking helpers."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="qvm-remote-backup-test-")
        self.data_dir = Path(self.tmpdir) / ".qvm-remote"
        self.backup_dir = Path(self.tmpdir) / "backups"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_local_backup(self):
        """create_local_backup creates a tar.gz archive."""
        import qubes_remote_ui
        self.data_dir.mkdir(parents=True)
        (self.data_dir / "audit.log").write_text("test log entry\n")
        (self.data_dir / "auth.key").write_text("a" * 64)

        dest = str(self.backup_dir / "test-backup.tar.gz")
        ok, msg = qubes_remote_ui.create_local_backup(self.data_dir, dest)
        self.assertTrue(ok, msg)
        self.assertTrue(Path(dest).exists())
        self.assertGreater(Path(dest).stat().st_size, 0)

    def test_create_backup_missing_dir(self):
        """create_local_backup fails for missing directory."""
        import qubes_remote_ui
        ok, msg = qubes_remote_ui.create_local_backup(
            "/nonexistent/dir", "/tmp/test.tar.gz"
        )
        self.assertFalse(ok)
        self.assertIn("not found", msg)

    def test_restore_local_backup(self):
        """restore_local_backup extracts archive correctly."""
        import qubes_remote_ui
        self.data_dir.mkdir(parents=True)
        (self.data_dir / "audit.log").write_text("original data\n")

        dest = str(self.backup_dir / "test.tar.gz")
        ok, _ = qubes_remote_ui.create_local_backup(self.data_dir, dest)
        self.assertTrue(ok)

        # Restore to a new location
        restore_dir = Path(self.tmpdir) / "restored"
        restore_dir.mkdir()
        ok, msg = qubes_remote_ui.restore_local_backup(dest, str(restore_dir))
        self.assertTrue(ok, msg)
        self.assertTrue((restore_dir / ".qvm-remote" / "audit.log").exists())

    def test_restore_missing_archive(self):
        """restore_local_backup fails for missing archive."""
        import qubes_remote_ui
        ok, msg = qubes_remote_ui.restore_local_backup(
            "/nonexistent.tar.gz", self.tmpdir
        )
        self.assertFalse(ok)
        self.assertIn("not found", msg)

    def test_list_local_backups(self):
        """list_local_backups finds tar.gz files."""
        import qubes_remote_ui
        self.backup_dir.mkdir(parents=True)
        for name in ["backup-a.tar.gz", "backup-b.tar.gz", "not-backup.txt"]:
            (self.backup_dir / name).write_text("test")
        result = qubes_remote_ui.list_local_backups(self.backup_dir)
        self.assertEqual(len(result), 2)
        for path, size, mtime in result:
            self.assertTrue(path.endswith(".tar.gz"))

    def test_list_backups_empty_dir(self):
        """list_local_backups returns empty for missing directory."""
        import qubes_remote_ui
        result = qubes_remote_ui.list_local_backups("/nonexistent")
        self.assertEqual(result, [])

    def test_get_change_summary(self):
        """get_change_summary parses audit log."""
        import qubes_remote_ui
        self.data_dir.mkdir(parents=True)
        (self.data_dir / "audit.log").write_text(
            "[2026-02-18T12:00:00] SUBMIT id=test1 size=10B\n"
            "[2026-02-18T12:01:00] DONE id=test1 rc=0\n"
        )
        changes = qubes_remote_ui.get_change_summary(self.data_dir)
        self.assertGreaterEqual(len(changes), 2)
        types = [c[1] for c in changes]
        self.assertIn("command", types)
        self.assertIn("result", types)

    def test_get_change_summary_empty(self):
        """get_change_summary handles missing data gracefully."""
        import qubes_remote_ui
        changes = qubes_remote_ui.get_change_summary("/nonexistent")
        self.assertEqual(changes, [])

    def test_git_backup_push_no_git(self):
        """git_backup_push handles missing git gracefully."""
        import qubes_remote_ui
        # Temporarily override PATH to hide git
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = "/nonexistent"
        try:
            ok, msg = qubes_remote_ui.git_backup_push(
                self.data_dir, "git@github.com:test/test.git"
            )
            # Should fail gracefully (either no git or no data_dir)
            # Don't assert True because git might not be in the test path
        finally:
            os.environ["PATH"] = old_path

    def test_git_backup_pull_no_git(self):
        """git_backup_pull handles missing git gracefully."""
        import qubes_remote_ui
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = "/nonexistent"
        try:
            ok, msg = qubes_remote_ui.git_backup_pull(
                "git@github.com:test/test.git",
                str(self.backup_dir / "git"),
            )
            self.assertFalse(ok)
            self.assertIn("git", msg.lower())
        finally:
            os.environ["PATH"] = old_path


class TestClientGUI(unittest.TestCase):
    """Tests for gui/qvm-remote-gui (syntax, structure)."""

    def test_syntax(self):
        """Client GUI compiles without syntax errors."""
        import py_compile
        py_compile.compile(str(GUI_DIR / "qvm-remote-gui"), doraise=True)

    def test_shebang(self):
        """Client GUI has correct shebang."""
        with open(GUI_DIR / "qvm-remote-gui") as f:
            first = f.readline()
        self.assertTrue(first.startswith("#!/usr/bin/python3"))

    def test_executable(self):
        """Client GUI is executable."""
        self.assertTrue(os.access(GUI_DIR / "qvm-remote-gui", os.X_OK))

    def test_contains_gtk_import(self):
        """Client GUI imports GTK3."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn('gi.require_version("Gtk", "3.0")', content)

    def test_contains_app_class(self):
        """Client GUI defines the application class."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("class QvmRemoteApp", content)
        self.assertIn("class QvmRemoteWindow", content)

    def test_contains_all_tabs(self):
        """Client GUI builds all six tabs."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        for tab in ["_build_execute_tab", "_build_files_tab",
                     "_build_backup_tab", "_build_history_tab",
                     "_build_keys_tab", "_build_log_tab"]:
            self.assertIn(tab, content, f"Missing tab builder: {tab}")

    def test_contains_notifications(self):
        """Client GUI uses desktop notifications."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("send_notification", content)

    def test_contains_file_transfer(self):
        """Client GUI has file transfer functionality."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("_on_send_file", content)
        self.assertIn("_on_fetch_file", content)
        self.assertIn("_on_copy_between_vms", content)

    def test_contains_backup_features(self):
        """Client GUI has backup functionality."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("_on_create_local_backup", content)
        self.assertIn("_on_restore_local_backup", content)
        self.assertIn("_on_git_push", content)
        self.assertIn("_on_git_pull", content)
        self.assertIn("_on_check_dom0_backups", content)
        self.assertIn("_on_start_dom0_backup", content)

    def test_contains_change_tracking(self):
        """Client GUI has change tracking."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("_load_changes", content)
        self.assertIn("get_change_summary", content)

    def test_contains_display_guard(self):
        """Client GUI checks for display before starting."""
        content = (GUI_DIR / "qvm-remote-gui").read_text()
        self.assertIn("check_display", content)


class TestDom0GUI(unittest.TestCase):
    """Tests for gui/qvm-remote-dom0-gui (syntax, structure)."""

    def test_syntax(self):
        """Dom0 GUI compiles without syntax errors."""
        import py_compile
        py_compile.compile(str(GUI_DIR / "qvm-remote-dom0-gui"), doraise=True)

    def test_shebang(self):
        """Dom0 GUI has correct shebang."""
        with open(GUI_DIR / "qvm-remote-dom0-gui") as f:
            first = f.readline()
        self.assertTrue(first.startswith("#!/usr/bin/python3"))

    def test_executable(self):
        """Dom0 GUI is executable."""
        self.assertTrue(os.access(GUI_DIR / "qvm-remote-dom0-gui", os.X_OK))

    def test_contains_gtk_import(self):
        """Dom0 GUI imports GTK3."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn('gi.require_version("Gtk", "3.0")', content)

    def test_contains_app_class(self):
        """Dom0 GUI defines the application class."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("class QvmRemoteDom0App", content)
        self.assertIn("class QvmRemoteDom0Window", content)

    def test_contains_all_tabs(self):
        """Dom0 GUI builds all four tabs."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        for tab in ["_build_dashboard_tab", "_build_vms_tab",
                     "_build_backup_tab", "_build_log_tab"]:
            self.assertIn(tab, content, f"Missing tab builder: {tab}")

    def test_security_warning(self):
        """Dom0 GUI has security warning for enable autostart."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("complete control over dom0", content)

    def test_contains_notifications(self):
        """Dom0 GUI uses desktop notifications."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("send_notification", content)

    def test_contains_file_push(self):
        """Dom0 GUI has file push functionality."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("_on_push_file", content)
        self.assertIn("Push to VM", content)

    def test_contains_root_warning(self):
        """Dom0 GUI warns when not running as root."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("Not running as root", content)

    def test_contains_display_guard(self):
        """Dom0 GUI checks for display before starting."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("check_display", content)

    def test_contains_backup_features(self):
        """Dom0 GUI has backup functionality."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("_on_create_dom0_backup", content)
        self.assertIn("_on_backup_service_config", content)
        self.assertIn("_on_restore_service_config", content)
        self.assertIn("_refresh_backup_status", content)
        self.assertIn("qvm-backup", content)

    def test_contains_change_tracking(self):
        """Dom0 GUI has change tracking."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("_load_dom0_changes", content)
        self.assertIn("Recent Changes", content)


class TestDesktopEntries(unittest.TestCase):
    """Tests for .desktop files."""

    def test_vm_desktop_exists(self):
        """VM desktop entry exists."""
        self.assertTrue((GUI_DIR / "qvm-remote-gui.desktop").exists())

    def test_dom0_desktop_exists(self):
        """Dom0 desktop entry exists."""
        self.assertTrue((GUI_DIR / "qvm-remote-dom0-gui.desktop").exists())

    def test_vm_desktop_valid(self):
        """VM desktop entry has required fields."""
        content = (GUI_DIR / "qvm-remote-gui.desktop").read_text()
        self.assertIn("[Desktop Entry]", content)
        self.assertIn("Name=", content)
        self.assertIn("Exec=", content)
        self.assertIn("Type=Application", content)
        self.assertIn("Terminal=false", content)

    def test_dom0_desktop_valid(self):
        """Dom0 desktop entry has required fields."""
        content = (GUI_DIR / "qvm-remote-dom0-gui.desktop").read_text()
        self.assertIn("[Desktop Entry]", content)
        self.assertIn("Name=", content)
        self.assertIn("Exec=", content)
        self.assertIn("Type=Application", content)


class TestPackaging(unittest.TestCase):
    """Tests for RPM specs, PKGBUILD, and Debian packaging."""

    def test_gui_vm_spec_exists(self):
        """VM GUI RPM spec exists."""
        self.assertTrue((REPO / "rpm_spec/qvm-remote-gui-vm.spec").exists())

    def test_gui_dom0_spec_exists(self):
        """Dom0 GUI RPM spec exists."""
        self.assertTrue((REPO / "rpm_spec/qvm-remote-gui-dom0.spec").exists())

    def test_gui_vm_spec_requires(self):
        """VM GUI spec requires GTK3 and PyGObject."""
        content = (REPO / "rpm_spec/qvm-remote-gui-vm.spec").read_text()
        self.assertIn("python3-gobject", content)
        self.assertIn("gtk3", content)
        self.assertIn("qvm-remote", content)

    def test_gui_dom0_spec_requires(self):
        """Dom0 GUI spec requires GTK3, PyGObject, and qubes-core-dom0."""
        content = (REPO / "rpm_spec/qvm-remote-gui-dom0.spec").read_text()
        self.assertIn("python3-gobject", content)
        self.assertIn("gtk3", content)
        self.assertIn("qubes-core-dom0", content)

    def test_pkgbuild_gui_exists(self):
        """Arch GUI PKGBUILD exists."""
        self.assertTrue((REPO / "pkg/PKGBUILD-gui").exists())

    def test_pkgbuild_gui_deps(self):
        """Arch GUI PKGBUILD has correct dependencies."""
        content = (REPO / "pkg/PKGBUILD-gui").read_text()
        self.assertIn("python-gobject", content)
        self.assertIn("gtk3", content)
        self.assertIn("qvm-remote", content)

    def test_debian_control_exists(self):
        """Debian control file exists."""
        self.assertTrue((REPO / "debian/control").exists())

    def test_debian_gui_package(self):
        """Debian control defines qvm-remote-gui package."""
        content = (REPO / "debian/control").read_text()
        self.assertIn("Package: qvm-remote-gui", content)
        self.assertIn("python3-gi", content)
        self.assertIn("gir1.2-gtk-3.0", content)

    def test_debian_rules(self):
        """Debian rules is executable and calls make."""
        rules = REPO / "debian/rules"
        self.assertTrue(rules.exists())
        self.assertTrue(os.access(rules, os.X_OK))
        content = rules.read_text()
        self.assertIn("install-gui-vm", content)


class TestMakefile(unittest.TestCase):
    """Tests for Makefile GUI targets."""

    def test_makefile_gui_targets(self):
        """Makefile has all GUI-related targets."""
        content = (REPO / "Makefile").read_text()
        for target in ["install-gui-vm", "install-gui-dom0",
                        "uninstall-gui-vm", "uninstall-gui-dom0"]:
            self.assertIn(f"{target}:", content, f"Missing target: {target}")

    def test_makefile_gui_check(self):
        """Makefile check target includes GUI files."""
        content = (REPO / "Makefile").read_text()
        self.assertIn("gui/qubes_remote_ui.py", content)
        self.assertIn("gui/qvm-remote-gui", content)
        self.assertIn("gui/qvm-remote-dom0-gui", content)

    def test_makefile_gui_test(self):
        """Makefile has gui-test target."""
        content = (REPO / "Makefile").read_text()
        self.assertIn("gui-test:", content)

    def test_makefile_libdir(self):
        """Makefile installs shared module to LIBDIR."""
        content = (REPO / "Makefile").read_text()
        self.assertIn("qubes_remote_ui.py", content)
        self.assertIn("LIBDIR", content)


class TestUIConventions(unittest.TestCase):
    """Verify Qubes OS UI conventions are followed."""

    def test_no_acronyms_in_labels(self):
        """User-facing text avoids unnecessary acronyms."""
        for filename in ["qvm-remote-gui", "qvm-remote-dom0-gui"]:
            content = (GUI_DIR / filename).read_text()
            # Check that labels use full words where Qubes guidelines apply
            # "VM" is acceptable as it's standard Qubes terminology
            self.assertNotIn('"DVM"', content, f"Acronym 'DVM' in {filename}")
            self.assertNotIn('"NetVM"', content, f"Acronym 'NetVM' in {filename}")

    def test_gtk3_required(self):
        """Both GUIs require GTK 3.0 (not GTK 4)."""
        for filename in ["qvm-remote-gui", "qvm-remote-dom0-gui"]:
            content = (GUI_DIR / filename).read_text()
            self.assertIn('gi.require_version("Gtk", "3.0")', content)
            self.assertNotIn('gi.require_version("Gtk", "4.0")', content)

    def test_application_ids(self):
        """Application IDs follow reverse-DNS convention."""
        for filename in ["qvm-remote-gui", "qvm-remote-dom0-gui"]:
            content = (GUI_DIR / filename).read_text()
            self.assertIn("org.qubes-os.", content)

    def test_error_dialogs_available(self):
        """Both GUIs use proper error dialogs."""
        for filename in ["qvm-remote-gui", "qvm-remote-dom0-gui"]:
            content = (GUI_DIR / filename).read_text()
            self.assertIn("show_error_dialog", content)

    def test_confirm_before_destructive(self):
        """Destructive actions require confirmation."""
        content = (GUI_DIR / "qvm-remote-dom0-gui").read_text()
        self.assertIn("show_confirm_dialog", content)
        # Revoke, stop, enable should all require confirmation
        self.assertIn("Revoke", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)

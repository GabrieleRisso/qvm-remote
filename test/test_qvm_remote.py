#!/usr/bin/python3
# test_qvm_remote.py -- test suite for qvm-remote
#
# Usage: python3 test/test_qvm_remote.py -v
#        python3 -m pytest test/test_qvm_remote.py -v
#
# Tests that can run on any machine (VM or dom0).
# Qubes-specific tests (qvm-run, service) are skipped automatically.
#
# Follows Qubes OS contribution guidelines: simple, readable, one
# assertion per test, clear pass/fail output.

from __future__ import annotations

import hashlib
import hmac
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VM_CLIENT = REPO_ROOT / "vm" / "qvm-remote"
DOM0_DAEMON = REPO_ROOT / "dom0" / "qvm-remote-dom0"
VERSION_FILE = REPO_ROOT / "version"


def run(cmd, **kw):
    """Run a command, return CompletedProcess."""
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), **kw
    )


# ── version ──────────────────────────────────────────────────────────

class TestVersion(unittest.TestCase):

    def test_version_file_exists_in_repo_root(self):
        self.assertTrue(VERSION_FILE.exists())

    def test_version_format_is_semver(self):
        ver = VERSION_FILE.read_text().strip()
        parts = ver.split(".")
        self.assertEqual(len(parts), 3, f"Bad version format: {ver}")
        for p in parts:
            self.assertTrue(p.isdigit(), f"Non-numeric: {p}")

    def test_version_matches_vm_client_source(self):
        ver = VERSION_FILE.read_text().strip()
        self.assertIn(f'VERSION = "{ver}"', VM_CLIENT.read_text())

    def test_version_matches_dom0_daemon_source(self):
        ver = VERSION_FILE.read_text().strip()
        self.assertIn(f'VERSION = "{ver}"', DOM0_DAEMON.read_text())


# ── syntax ───────────────────────────────────────────────────────────

class TestSyntax(unittest.TestCase):

    def test_vm_client_compiles_without_errors(self):
        r = run([
            "python3", "-c",
            f"import py_compile; "
            f"py_compile.compile('{VM_CLIENT}', doraise=True)",
        ])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_dom0_daemon_compiles_without_errors(self):
        r = run([
            "python3", "-c",
            f"import py_compile; "
            f"py_compile.compile('{DOM0_DAEMON}', doraise=True)",
        ])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_install_script_passes_bash_syntax_check(self):
        r = run(["bash", "-n", str(REPO_ROOT / "install" / "install-dom0.sh")])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_install_script_help_shows_usage(self):
        script = REPO_ROOT / "install" / "install-dom0.sh"
        r = subprocess.run(
            ["bash", str(script), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("--yes", r.stdout)
        self.assertIn("vm-name", r.stdout)

    def test_install_script_does_not_use_set_e(self):
        """Install script must NOT use set -euo pipefail."""
        text = (REPO_ROOT / "install" / "install-dom0.sh").read_text()
        self.assertNotIn("set -euo pipefail", text)
        self.assertNotIn("set -e", text)

    def test_install_script_checks_tty_before_read(self):
        """Install script must check for tty before read -rp."""
        text = (REPO_ROOT / "install" / "install-dom0.sh").read_text()
        self.assertIn("-t 0", text, "Missing tty check before read")

    def test_install_script_accepts_yes_flag_for_noninteractive(self):
        """Install script must accept --yes for non-interactive mode."""
        text = (REPO_ROOT / "install" / "install-dom0.sh").read_text()
        self.assertIn("--yes", text)
        self.assertIn("FORCE", text)

    def test_vm_client_file_is_executable(self):
        self.assertTrue(
            os.access(VM_CLIENT, os.X_OK),
            f"{VM_CLIENT} is not executable",
        )

    def test_dom0_daemon_file_is_executable(self):
        self.assertTrue(
            os.access(DOM0_DAEMON, os.X_OK),
            f"{DOM0_DAEMON} is not executable",
        )

    def test_vm_client_shebang_is_python3(self):
        first_line = VM_CLIENT.read_text().splitlines()[0]
        self.assertIn("python3", first_line)

    def test_dom0_daemon_shebang_is_python3(self):
        first_line = DOM0_DAEMON.read_text().splitlines()[0]
        self.assertIn("python3", first_line)


# ── CLI ──────────────────────────────────────────────────────────────

class TestCLI(unittest.TestCase):

    def test_vm_client_help_shows_usage_and_subcommands(self):
        r = run(["python3", str(VM_CLIENT), "--help"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("Execute commands", r.stdout)
        self.assertIn("key gen", r.stdout)

    def test_vm_client_version_matches_version_file(self):
        ver = VERSION_FILE.read_text().strip()
        r = run(["python3", str(VM_CLIENT), "--version"])
        self.assertEqual(r.returncode, 0)
        self.assertIn(ver, r.stdout)

    def test_dom0_daemon_help_shows_usage_and_subcommands(self):
        r = run(["python3", str(DOM0_DAEMON), "--help"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("Dom0 executor", r.stdout)
        self.assertIn("authorize", r.stdout)

    def test_dom0_daemon_version_matches_version_file(self):
        ver = VERSION_FILE.read_text().strip()
        r = run(["python3", str(DOM0_DAEMON), "--version"])
        self.assertEqual(r.returncode, 0)
        self.assertIn(ver, r.stdout)

    def test_vm_client_rejects_unknown_option(self):
        r = run(["python3", str(VM_CLIENT), "--bogus"])
        self.assertNotEqual(r.returncode, 0)

    def test_dom0_daemon_rejects_unknown_option(self):
        r = run(["python3", str(DOM0_DAEMON), "--bogus"])
        self.assertNotEqual(r.returncode, 0)

    def test_vm_client_short_help_flag_works(self):
        r = run(["python3", str(VM_CLIENT), "-h"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("qvm-remote", r.stdout)

    def test_vm_client_key_without_subcommand_shows_error(self):
        r = run(["python3", str(VM_CLIENT), "key"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gen | show | import", r.stderr)


# ── HMAC ─────────────────────────────────────────────────────────────

class TestHMAC(unittest.TestCase):
    """Verify HMAC-SHA256 token generation."""

    KEY = "abcdef0123456789abcdef0123456789" \
          "abcdef0123456789abcdef0123456789"
    KEY2 = "1234567890abcdef1234567890abcdef" \
           "1234567890abcdef1234567890abcdef"

    def _hmac(self, key: str, data: str) -> str:
        return hmac.new(
            key.encode(), data.encode(), hashlib.sha256
        ).hexdigest()

    def test_hmac_token_is_deterministic(self):
        t1 = self._hmac(self.KEY, "cmd-001")
        t2 = self._hmac(self.KEY, "cmd-001")
        self.assertEqual(t1, t2)

    def test_hmac_different_keys_produce_different_tokens(self):
        t1 = self._hmac(self.KEY, "cmd-001")
        t2 = self._hmac(self.KEY2, "cmd-001")
        self.assertNotEqual(t1, t2)

    def test_hmac_different_ids_produce_different_tokens(self):
        t1 = self._hmac(self.KEY, "cmd-A")
        t2 = self._hmac(self.KEY, "cmd-B")
        self.assertNotEqual(t1, t2)

    def test_hmac_output_is_64_hex_characters(self):
        t = self._hmac(self.KEY, "test")
        self.assertEqual(len(t), 64)
        int(t, 16)  # should not raise

    def test_hmac_compatible_with_openssl(self):
        """Python HMAC must match openssl for cross-version compat."""
        try:
            r = subprocess.run(
                ["openssl", "dgst", "-sha256", "-hmac", self.KEY, "-hex"],
                input=b"cmd-001",
                capture_output=True,
                timeout=5,
            )
            if r.returncode != 0:
                self.skipTest("openssl returned non-zero")
            openssl_tok = r.stdout.decode().strip().split()[-1]
            python_tok = self._hmac(self.KEY, "cmd-001")
            self.assertEqual(openssl_tok, python_tok)
        except FileNotFoundError:
            self.skipTest("openssl not installed")


# ── key management ───────────────────────────────────────────────────

class TestKeyManagement(unittest.TestCase):

    def test_generated_key_is_64_hex_characters(self):
        key = os.urandom(32).hex()
        self.assertEqual(len(key), 64)
        int(key, 16)

    def test_key_import_then_show_returns_same_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            key = os.urandom(32).hex()
            env = {**os.environ, "HOME": tmpdir}
            r = run(
                ["python3", str(VM_CLIENT), "key", "import", key],
                env=env,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            r = run(
                ["python3", str(VM_CLIENT), "key", "show"], env=env
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), key)

    def test_key_file_permissions_are_0600(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            key = os.urandom(32).hex()
            env = {**os.environ, "HOME": tmpdir}
            run(
                ["python3", str(VM_CLIENT), "key", "import", key],
                env=env,
            )
            kf = Path(tmpdir) / ".qvm-remote" / "auth.key"
            self.assertTrue(kf.exists())
            mode = oct(kf.stat().st_mode & 0o777)
            self.assertEqual(mode, "0o600", f"Expected 0600, got {mode}")

    def test_key_import_rejects_invalid_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {**os.environ, "HOME": tmpdir}
            r = run(
                ["python3", str(VM_CLIENT), "key", "import", "bad"],
                env=env,
            )
            self.assertNotEqual(r.returncode, 0)

    def test_key_show_fails_without_existing_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {**os.environ, "HOME": tmpdir}
            r = run(
                ["python3", str(VM_CLIENT), "key", "show"], env=env
            )
            self.assertNotEqual(r.returncode, 0)

    def test_key_gen_creates_key_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {**os.environ, "HOME": tmpdir}
            r = run(
                ["python3", str(VM_CLIENT), "key", "gen"], env=env
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            key = r.stdout.strip()
            self.assertEqual(len(key), 64)
            kf = Path(tmpdir) / ".qvm-remote" / "auth.key"
            self.assertTrue(kf.exists())
            self.assertEqual(kf.read_text().strip(), key)

    def test_key_gen_sets_file_permissions_to_0600(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {**os.environ, "HOME": tmpdir}
            run(["python3", str(VM_CLIENT), "key", "gen"], env=env)
            kf = Path(tmpdir) / ".qvm-remote" / "auth.key"
            mode = oct(kf.stat().st_mode & 0o777)
            self.assertEqual(mode, "0o600")


# ── command validation ───────────────────────────────────────────────

class TestCommandValidation(unittest.TestCase):

    def test_empty_stdin_command_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {**os.environ, "HOME": tmpdir}
            r = subprocess.run(
                ["python3", str(VM_CLIENT)],
                input="",
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("empty command", r.stderr)


# ── data migration ───────────────────────────────────────────────────

class TestMigration(unittest.TestCase):

    def test_old_qubes_remote_dir_migrates_to_qvm_remote(self):
        """Old .qubes-remote dir migrates to .qvm-remote."""
        with tempfile.TemporaryDirectory() as tmpdir:
            old = Path(tmpdir) / ".qubes-remote"
            old.mkdir()
            (old / "auth.key").write_text("a" * 64)
            new = Path(tmpdir) / ".qvm-remote"
            self.assertFalse(new.exists())
            env = {**os.environ, "HOME": tmpdir}
            run(["python3", str(VM_CLIENT), "key", "show"], env=env)
            self.assertTrue(new.exists())
            self.assertFalse(old.exists())


# ── security hardening ───────────────────────────────────────────────

class TestSecurity(unittest.TestCase):
    """Verify security hardening measures are present in source code."""

    def test_daemon_uses_constant_time_hmac_comparison(self):
        src = DOM0_DAEMON.read_text()
        self.assertIn("compare_digest", src,
                       "Daemon must use hmac.compare_digest for token comparison")

    def test_daemon_command_execution_has_timeout(self):
        src = DOM0_DAEMON.read_text()
        self.assertIn("timeout=EXEC_TIMEOUT", src,
                       "Daemon must set timeout on command execution subprocess")

    def test_daemon_handles_timeout_expired(self):
        src = DOM0_DAEMON.read_text()
        self.assertIn("subprocess.TimeoutExpired", src,
                       "Daemon must handle subprocess.TimeoutExpired")

    def test_daemon_sets_work_file_permissions_after_write(self):
        src = DOM0_DAEMON.read_text()
        self.assertIn("work_file.chmod(0o700)", src,
                       "Daemon must chmod work file to 0700 after write")

    def test_daemon_validates_before_writing_to_disk(self):
        """Validation (size, binary) must come before work_file.write_bytes."""
        src = DOM0_DAEMON.read_text()
        validate_pos = src.find("has_binary_content")
        write_pos = src.find("work_file.write_bytes")
        self.assertGreater(write_pos, validate_pos,
                           "Validation must happen before writing to disk")

    def test_daemon_systemctl_calls_have_timeout(self):
        src = DOM0_DAEMON.read_text()
        lines = src.splitlines()
        for i, line in enumerate(lines):
            if "systemctl" in line and "subprocess.run" in line:
                context = "\n".join(lines[max(0, i):i + 3])
                self.assertIn("timeout=", context,
                              f"systemctl call on line {i+1} lacks timeout")

    def test_client_uses_secrets_module_for_command_ids(self):
        src = VM_CLIENT.read_text()
        self.assertIn("import secrets", src,
                       "Client must use secrets module for ID generation")
        self.assertIn("secrets.token_hex", src,
                       "Client must use secrets.token_hex for unpredictable IDs")

    def test_client_does_not_use_random_module(self):
        src = VM_CLIENT.read_text()
        self.assertNotIn("import random", src,
                          "Client must not use non-cryptographic random module")

    def test_client_sets_audit_log_permissions(self):
        src = VM_CLIENT.read_text()
        self.assertIn("LOG_FILE.chmod(0o600)", src,
                       "Client must set audit log permissions to 0600")

    def test_audit_log_created_with_restricted_permissions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {**os.environ, "HOME": tmpdir}
            r = run(["python3", str(VM_CLIENT), "key", "gen"], env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            log_file = Path(tmpdir) / ".qvm-remote" / "audit.log"
            if log_file.exists():
                mode = oct(log_file.stat().st_mode & 0o777)
                self.assertEqual(mode, "0o600",
                                 f"audit.log should be 0600, got {mode}")

    def test_daemon_configurable_vm_user(self):
        src = DOM0_DAEMON.read_text()
        self.assertIn("QVM_REMOTE_VM_USER", src,
                       "Daemon must support QVM_REMOTE_VM_USER config")
        self.assertIn("DEFAULT_VM_USER", src,
                       "Daemon must have a default VM user")

    def test_daemon_has_error_handling_for_key_operations(self):
        src = DOM0_DAEMON.read_text()
        self.assertIn("except OSError", src,
                       "Daemon must handle OSError for file operations")

    def test_client_has_error_handling_for_key_operations(self):
        src = VM_CLIENT.read_text()
        count = src.count("except OSError")
        self.assertGreaterEqual(count, 3,
                                f"Client needs OSError handling (found {count})")

    def test_install_script_supports_configurable_vm_user(self):
        src = (REPO_ROOT / "install" / "install-dom0.sh").read_text()
        self.assertIn("VM_USER", src,
                       "Install script must support configurable VM user")


# ── packaging ────────────────────────────────────────────────────────

class TestPackaging(unittest.TestCase):

    def _read(self, path: str) -> str:
        return (REPO_ROOT / path).read_text()

    def test_spec_dom0_has_source_field(self):
        self.assertIn("Source0:", self._read("rpm_spec/qvm-remote-dom0.spec"))

    def test_spec_dom0_has_license_field(self):
        self.assertIn("License:", self._read("rpm_spec/qvm-remote-dom0.spec"))

    def test_spec_dom0_has_prep_section(self):
        self.assertIn("%prep", self._read("rpm_spec/qvm-remote-dom0.spec"))

    def test_spec_dom0_requires_python3(self):
        self.assertIn("python3", self._read("rpm_spec/qvm-remote-dom0.spec"))

    def test_spec_dom0_obsoletes_old_package(self):
        self.assertIn("Obsoletes:", self._read("rpm_spec/qvm-remote-dom0.spec"))

    def test_spec_vm_has_source_field(self):
        self.assertIn("Source0:", self._read("rpm_spec/qvm-remote-vm.spec"))

    def test_spec_vm_has_license_field(self):
        self.assertIn("License:", self._read("rpm_spec/qvm-remote-vm.spec"))

    def test_spec_vm_requires_python3(self):
        self.assertIn("python3", self._read("rpm_spec/qvm-remote-vm.spec"))

    def test_spec_vm_obsoletes_old_package(self):
        self.assertIn("Obsoletes:", self._read("rpm_spec/qvm-remote-vm.spec"))

    def test_qubesbuilder_config_exists(self):
        self.assertTrue((REPO_ROOT / ".qubesbuilder").exists())

    def test_qubesbuilder_has_host_section(self):
        self.assertIn("host:", self._read(".qubesbuilder"))

    def test_qubesbuilder_has_vm_section(self):
        self.assertIn("vm:", self._read(".qubesbuilder"))

    def test_makefile_has_required_targets(self):
        mk = self._read("Makefile")
        for target in (
            "install-vm", "install-dom0", "dist", "rpm", "check", "clean",
            "docker-test", "dom0-test", "arch-test",
        ):
            found = any(
                line.startswith(f"{target}:")
                for line in mk.splitlines()
            )
            self.assertTrue(found, f"Missing Makefile target: {target}")

    def test_dockerfile_build_exists(self):
        self.assertTrue((REPO_ROOT / "Dockerfile.build").exists())

    def test_dockerfile_build_uses_fedora_41(self):
        self.assertIn("fedora:41", self._read("Dockerfile.build"))

    def test_dockerfile_build_installs_python3(self):
        self.assertIn("python3", self._read("Dockerfile.build"))

    def test_config_file_documents_remote_d_directory(self):
        self.assertIn("remote.d", self._read("etc/qubes-remote.conf"))

    def test_config_file_documents_vm_user_option(self):
        self.assertIn("QVM_REMOTE_VM_USER", self._read("etc/qubes-remote.conf"))

    def test_pkgbuild_exists_for_arch_linux(self):
        self.assertTrue((REPO_ROOT / "pkg" / "PKGBUILD").exists())

    def test_pkgbuild_depends_on_python(self):
        self.assertIn("python", self._read("pkg/PKGBUILD"))

    def test_dockerfile_arch_exists(self):
        self.assertTrue((REPO_ROOT / "test" / "Dockerfile.arch").exists())


# ── build ────────────────────────────────────────────────────────────

class TestBuild(unittest.TestCase):

    def test_make_dist_creates_source_tarballs(self):
        run(["make", "clean"])
        r = run(["make", "dist"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ver = VERSION_FILE.read_text().strip()
        self.assertTrue(
            (REPO_ROOT / "build" / "SOURCES"
             / f"qvm-remote-dom0-{ver}.tar.gz").exists()
        )
        self.assertTrue(
            (REPO_ROOT / "build" / "SOURCES"
             / f"qvm-remote-{ver}.tar.gz").exists()
        )

    def test_dist_spec_contains_correct_version(self):
        ver = VERSION_FILE.read_text().strip()
        spec = REPO_ROOT / "build" / "SPECS" / "qvm-remote-dom0.spec"
        if not spec.exists():
            run(["make", "dist"])
        self.assertIn(f"Version:        {ver}", spec.read_text())

    @unittest.skipUnless(
        subprocess.run(
            ["which", "rpmbuild"], capture_output=True
        ).returncode == 0,
        "rpmbuild not available",
    )
    def test_make_rpm_builds_successfully(self):
        r = run(["make", "rpm"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    @unittest.skipUnless(
        subprocess.run(
            ["which", "rpmbuild"], capture_output=True
        ).returncode == 0,
        "rpmbuild not available",
    )
    def test_rpm_dom0_contains_expected_files(self):
        ver = VERSION_FILE.read_text().strip()
        rpm_path = (
            REPO_ROOT / "build" / "RPMS" / "noarch"
            / f"qvm-remote-dom0-{ver}-1.noarch.rpm"
        )
        if not rpm_path.exists():
            run(["make", "rpm"])
        if not rpm_path.exists():
            self.skipTest("RPM not built")
        r = run(["rpm", "--dbpath", "/tmp", "-qlp", str(rpm_path)])
        self.assertIn("/usr/bin/qvm-remote-dom0", r.stdout)
        self.assertIn("qvm-remote-dom0.service", r.stdout)
        self.assertIn("remote.conf", r.stdout)

    @unittest.skipUnless(
        subprocess.run(
            ["which", "rpmbuild"], capture_output=True
        ).returncode == 0,
        "rpmbuild not available",
    )
    def test_rpm_vm_contains_expected_files(self):
        ver = VERSION_FILE.read_text().strip()
        rpm_path = (
            REPO_ROOT / "build" / "RPMS" / "noarch"
            / f"qvm-remote-{ver}-1.noarch.rpm"
        )
        if not rpm_path.exists():
            run(["make", "rpm"])
        if not rpm_path.exists():
            self.skipTest("RPM not built")
        r = run(["rpm", "--dbpath", "/tmp", "-qlp", str(rpm_path)])
        self.assertIn("/usr/bin/qvm-remote", r.stdout)


# ── salt ─────────────────────────────────────────────────────────────

class TestSalt(unittest.TestCase):

    def test_salt_state_file_exists(self):
        self.assertTrue(
            (REPO_ROOT / "salt" / "qvm-remote" / "init.sls").exists()
        )

    def test_salt_top_file_exists(self):
        self.assertTrue(
            (REPO_ROOT / "salt" / "qvm-remote.top").exists()
        )

    def test_salt_pillar_file_exists(self):
        self.assertTrue(
            (REPO_ROOT / "salt" / "pillar" / "qvm-remote.sls").exists()
        )

    def test_salt_state_references_qvm_present(self):
        sls = (
            REPO_ROOT / "salt" / "qvm-remote" / "init.sls"
        ).read_text()
        self.assertIn("qvm.present", sls)
        self.assertIn("qvm-remote-dom0", sls)


if __name__ == "__main__":
    unittest.main(verbosity=2)

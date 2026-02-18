#!/usr/bin/python3
"""CLI-GUI cross-integration backup test.

Tests that CLI-created data can be backed up and restored by GUI functions,
including local archives, git backups, and change tracking.

Run: python3 test/test_backup_e2e.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gui"))

from qubes_remote_ui import (
    create_local_backup, restore_local_backup, list_local_backups,
    get_change_summary, git_backup_push, git_backup_pull,
    valid_hex_key, format_file_size,
)


def main():
    passed = 0
    failed = 0
    tmp = tempfile.mkdtemp(prefix="qvm-e2e-")

    try:
        # --- Create realistic CLI data ---
        data = Path(tmp) / ".qvm-remote"
        data.mkdir()
        key = os.urandom(32).hex()
        (data / "auth.key").write_text(key)
        os.chmod(str(data / "auth.key"), 0o600)
        (data / "audit.log").write_text(
            "[2026-02-18T10:00:00] SUBMIT id=test001 size=8B\n"
            "[2026-02-18T10:00:01] DONE id=test001 rc=0\n"
            "[2026-02-18T10:02:00] SUBMIT id=test002 size=20B\n"
            "[2026-02-18T10:02:03] DONE id=test002 rc=1\n"
            "[2026-02-18T10:05:00] KEY gen\n"
        )
        hist = data / "history" / "2026-02-18" / "test001"
        hist.mkdir(parents=True)
        (hist / "command").write_text("qvm-ls\n")
        (hist / "exit").write_text("0\n")
        (hist / "meta").write_text("duration_ms=350\n")
        hist2 = data / "history" / "2026-02-18" / "test002"
        hist2.mkdir(parents=True)
        (hist2 / "command").write_text("qvm-prefs work memory 8192\n")
        (hist2 / "exit").write_text("1\n")
        (hist2 / "meta").write_text("duration_ms=500\n")

        # --- Validate key format ---
        assert valid_hex_key(key), f"Key validation failed: {key}"
        print("PASS: key validation")
        passed += 1

        # --- Test local backup cycle ---
        bak_dir = Path(tmp) / "backups"
        dest = str(bak_dir / "backup-test.tar.gz")
        ok, msg = create_local_backup(data, dest)
        assert ok, f"Backup failed: {msg}"
        print(f"PASS: local backup created ({msg})")
        passed += 1

        backups = list_local_backups(bak_dir)
        assert len(backups) == 1, f"Expected 1 backup, got {len(backups)}"
        print(f"PASS: backup listed: {backups[0][0]}")
        passed += 1

        restore = Path(tmp) / "restored"
        restore.mkdir()
        ok, msg = restore_local_backup(dest, str(restore))
        assert ok, f"Restore failed: {msg}"
        restored_key = (restore / ".qvm-remote" / "auth.key").read_text().strip()
        assert restored_key == key, "Restored key does not match!"
        print("PASS: backup restored with correct key")
        passed += 1

        # Verify restored audit log
        restored_log = (restore / ".qvm-remote" / "audit.log").read_text()
        assert "SUBMIT" in restored_log, "Audit log not restored"
        assert "KEY gen" in restored_log, "Key event not in restored log"
        print("PASS: audit log restored correctly")
        passed += 1

        # Verify restored history
        restored_hist = restore / ".qvm-remote" / "history" / "2026-02-18" / "test001"
        assert restored_hist.exists(), "History not restored"
        assert (restored_hist / "command").read_text().strip() == "qvm-ls"
        print("PASS: command history restored correctly")
        passed += 1

        # --- Test change summary ---
        changes = get_change_summary(data)
        assert len(changes) >= 4, f"Expected 4+ changes, got {len(changes)}"
        event_types = {c[1] for c in changes}
        assert "command" in event_types, f"No command events in {event_types}"
        assert "key" in event_types, f"No key events in {event_types}"
        assert "result" in event_types, f"No result events in {event_types}"
        print(f"PASS: change summary has {len(changes)} entries, types={event_types}")
        passed += 1

        # --- Test git backup (local bare repo) ---
        git = shutil.which("git")
        if git:
            bare = Path(tmp) / "remote.git"
            subprocess.run(
                [git, "init", "--bare", str(bare)],
                capture_output=True, check=True,
            )
            repo_url = f"file://{bare}"

            git_dir = data / "git-backup"
            ok, msg = git_backup_push(data, repo_url, git_dir)
            assert ok, f"Git push failed: {msg}"
            print("PASS: git backup pushed")
            passed += 1

            # Verify full key is NOT in git
            fp = (git_dir / "key-fingerprint.txt").read_text()
            assert key not in fp, "SECURITY: full key leaked to git!"
            assert "..." in fp, "Key fingerprint should be masked"
            print("PASS: full key NOT in git backup (security check)")
            passed += 1

            # Verify audit log in git
            assert (git_dir / "audit.log").exists(), "audit.log not in git"
            assert (git_dir / "history").exists(), "history not in git"
            assert (git_dir / "backup-meta.txt").exists(), "metadata not in git"
            print("PASS: audit log, history, and metadata in git backup")
            passed += 1

            # Pull to new location
            pull = Path(tmp) / "pulled"
            ok, msg = git_backup_pull(repo_url, pull)
            assert ok, f"Git pull failed: {msg}"
            assert (pull / "audit.log").exists(), "audit.log not pulled"
            assert (pull / "key-fingerprint.txt").exists(), "fingerprint not pulled"
            assert (pull / "backup-meta.txt").exists(), "metadata not pulled"
            print("PASS: git backup pulled successfully")
            passed += 1

            # Verify pulled content matches
            pulled_log = (pull / "audit.log").read_text()
            assert "SUBMIT" in pulled_log, "Pulled log incomplete"
            print("PASS: pulled backup content verified")
            passed += 1
        else:
            print("SKIP: git not installed, skipping git backup tests")

        # --- Test format_file_size ---
        assert "B" in format_file_size(100)
        assert "KB" in format_file_size(2048)
        assert "MB" in format_file_size(5 * 1024 * 1024)
        assert "GB" in format_file_size(2 * 1024 ** 3)
        print("PASS: format_file_size works")
        passed += 1

        # --- Test path traversal protection ---
        import tarfile
        import io
        evil_tar = Path(tmp) / "evil.tar.gz"
        with tarfile.open(str(evil_tar), "w:gz") as tar:
            d = b"malicious"
            info = tarfile.TarInfo(name="../../../tmp/evil")
            info.size = len(d)
            tar.addfile(info, io.BytesIO(d))
        evil_restore = Path(tmp) / "evil-restore"
        evil_restore.mkdir()
        ok, msg = restore_local_backup(str(evil_tar), str(evil_restore))
        assert not ok, "Should reject path traversal"
        assert "Unsafe" in msg
        print("PASS: path traversal protection works")
        passed += 1

        # --- Test multiple backups ---
        import time
        multi_dir = Path(tmp) / "multi-bak"
        for i in range(3):
            d = str(multi_dir / f"backup-{i:02d}.tar.gz")
            ok, _ = create_local_backup(data, d)
            assert ok
            time.sleep(0.05)
        backups = list_local_backups(multi_dir)
        assert len(backups) == 3, f"Expected 3 backups, got {len(backups)}"
        assert "backup-02" in backups[0][0], "Newest should be first"
        print("PASS: multiple backups listed newest first")
        passed += 1

    except AssertionError as e:
        print(f"FAIL: {e}")
        failed += 1
    except Exception as e:
        print(f"ERROR: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    total = passed + failed
    print(f"{'=' * 50}")
    print(f"  RESULT: {passed} passed, {failed} failed (total: {total})")
    print(f"{'=' * 50}")
    if failed:
        print()
        print("  SOME TESTS FAILED")
        sys.exit(1)
    else:
        print()
        print("  ALL CLI-GUI CROSS-INTEGRATION TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()

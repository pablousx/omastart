import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

from backend.common import Error, Store, bounded_process, closed_environment, file_value, run, snapshot
from .support import Fixture


class SafetyTests(Fixture):
    def test_external_commands_use_absolute_identity_closed_environment_and_bounded_output(self):
        with patch.dict(os.environ, {"OMASTART_UNTRUSTED": "present", "PATH": "/tmp/hostile"}):
            result = bounded_process(
                ["/usr/bin/python3", "-c",
                 "import os; print(os.getenv('OMASTART_UNTRUSTED')); print(os.getenv('PATH'))"],
                env=closed_environment(),
            )
        self.assertEqual(result.stdout.splitlines(), ["None", "None"])
        with self.assertRaisesRegex(Error, "absolute"):
            bounded_process(["python3", "-c", "pass"])
        with self.assertRaisesRegex(Error, "safety limit"):
            bounded_process(["/usr/bin/python3", "-c", "print('x' * 1000)"], stdout_limit=32)
        with self.assertRaisesRegex(Error, "untrusted"):
            run(["python3", "-c", "pass"])

    def test_external_command_timeout_kills_process_group(self):
        pid_file = Path(self.temporary.name) / "child.pid"
        script = ("import pathlib,subprocess,time,sys; "
                  "p=subprocess.Popen(['/usr/bin/sleep','30']); "
                  "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(30)")
        started = time.monotonic()
        with self.assertRaisesRegex(Error, "exceeded"):
            bounded_process(["/usr/bin/python3", "-c", script, str(pid_file)], timeout=0.2)
        self.assertLess(time.monotonic() - started, 2)
        child = int(pid_file.read_text())
        for _ in range(20):
            if not Path(f"/proc/{child}").exists():
                break
            time.sleep(0.05)
        self.assertFalse(Path(f"/proc/{child}").exists())

    def test_external_command_deadline_includes_blocked_stdin(self):
        started = time.monotonic()
        with self.assertRaisesRegex(Error, "exceeded"):
            bounded_process(["/usr/bin/python3", "-c", "import time; time.sleep(30)"],
                            input="x" * 1_000_000, timeout=0.2)
        self.assertLess(time.monotonic() - started, 2)

    def test_external_command_cleans_descendants_after_direct_exit(self):
        pid_file = Path(self.temporary.name) / "detached-child.pid"
        script = ("import os,pathlib,subprocess,sys; "
                  "p=subprocess.Popen(['/usr/bin/sleep','30'], stdin=subprocess.DEVNULL, "
                  "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
                  "pathlib.Path(sys.argv[1]).write_text(str(p.pid))")
        result = bounded_process(["/usr/bin/python3", "-c", script, str(pid_file)])
        self.assertEqual(result.returncode, 0)
        child = int(pid_file.read_text())
        for _ in range(20):
            if not Path(f"/proc/{child}").exists():
                break
            time.sleep(0.05)
        self.assertFalse(Path(f"/proc/{child}").exists())

    def test_external_command_inherits_only_explicit_descriptors(self):
        directory = os.open(self.temporary.name, os.O_RDONLY | os.O_DIRECTORY)
        try:
            result = bounded_process(
                ["/usr/bin/python3", "-c",
                 "import os,sys; print(os.readlink('/proc/self/fd/' + sys.argv[1]))",
                 str(directory)],
                pass_fds=(directory,),
            )
        finally:
            os.close(directory)
        self.assertEqual(Path(result.stdout.strip()), Path(self.temporary.name))

    def test_scan_has_no_filesystem_side_effects(self):
        self.desktop("example")
        before = sorted(str(p) for p in Path(self.temporary.name).rglob("*"))
        self.engine.scan()
        after = sorted(str(p) for p in Path(self.temporary.name).rglob("*"))
        self.assertEqual(before, after)

    def test_stale_revision_refuses_write(self):
        path = self.desktop("example")
        item = self.item("xdg:example.desktop")
        path.write_text(path.read_text() + "# external update\n")
        before = path.read_bytes()
        with self.assertRaisesRegex(Error, "changed"):
            self.engine.request({"action": "toggle", "id": item["id"], "revision": item["revision"], "enabled": False})
        self.assertEqual(path.read_bytes(), before)

    def test_changed_global_layer_invalidates_xdg_revision(self):
        vendor = self.desktop("example", system=True)
        self.desktop("example")
        item = self.item("xdg:example.desktop")
        vendor.write_text(vendor.read_text() + "# changed\n")
        self.assertNotEqual(item["revision"], self.item(item["id"])["revision"])

    def test_symlink_file_and_parent_are_read_only(self):
        target = self.write(self.roots.home / "outside.desktop", "[Desktop Entry]\nType=Application\nExec=example\nName=Example\n")
        self.roots.autostart.mkdir(parents=True)
        path = self.roots.autostart / "example.desktop"
        path.symlink_to(target)
        self.assertIn("Symlink", self.item("xdg:example.desktop")["readOnly"])
        path.unlink()
        self.roots.autostart.rmdir()
        directory = self.roots.home / "redirect"
        directory.mkdir()
        self.roots.autostart.symlink_to(directory)
        self.write(directory / "example.desktop", target.read_text())
        self.assertIn("Symlink", self.item("xdg:example.desktop")["readOnly"])

    def test_arbitrary_destination_or_id_is_rejected(self):
        self.desktop("example")
        with self.assertRaisesRegex(Error, "changed"):
            self.engine.request({"action": "toggle", "id": "xdg:../../outside", "revision": "bad", "enabled": False})
        with self.assertRaisesRegex(Error, "outside"):
            self.engine.store.safe_path(self.roots.home / "not-config")
        with self.assertRaises(Error):
            self.engine.request({"action": "toggle", "id": "xdg:example.desktop", "revision": "bad", "enabled": "false"})

    def test_backup_contains_original_bytes_and_permissions(self):
        path = self.desktop("example")
        path.chmod(0o640)
        original = path.read_bytes()
        self.toggle("xdg:example.desktop", False)
        records = list((self.roots.state / "transactions").glob("*.json"))
        self.assertEqual(len(records), 1)
        record = json.loads(records[0].read_text())
        self.assertEqual(record["status"], "committed")
        before = record["entries"][0]["before"]
        self.assertEqual(base64.b64decode(before["data"]), original)
        self.assertEqual(before["mode"], 0o640)
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(records[0].stat().st_mode & 0o777, 0o600)

    def test_external_edit_after_disable_is_preserved_by_targeted_toggle(self):
        path = self.desktop("example")
        self.toggle("xdg:example.desktop", False)
        path.write_text(path.read_text() + "# preserve me\n")
        self.toggle("xdg:example.desktop", True)
        self.assertIn("# preserve me", path.read_text())
        self.assertIn("Hidden=false", path.read_text())

    def test_failure_before_replace_preserves_original(self):
        path = self.desktop("example")
        original = path.read_bytes()
        original_rename = os.rename

        def fail_rename(src, dst, **kwargs):
            if dst == path.name:
                raise OSError("simulated full disk")
            return original_rename(src, dst, **kwargs)

        with patch("backend.common.os.rename", side_effect=fail_rename):
            with self.assertRaisesRegex(Error, "rolled back"):
                self.toggle("xdg:example.desktop", False)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(path.parent.glob(".omastart-*")), [])

    def test_atomic_replace_exposes_complete_file(self):
        path = self.desktop("example")
        before = path.read_bytes()
        real_rename = os.rename
        seen = []

        def check_replace(src, dst, **kwargs):
            if dst == path.name:
                self.assertEqual(path.read_bytes(), before)
                seen.append(Path(f"/proc/self/fd/{kwargs['src_dir_fd']}/{src}").read_bytes())
                self.assertIn(b"Hidden=true", seen[-1])
            return real_rename(src, dst, **kwargs)

        with patch("backend.common.os.rename", side_effect=check_replace):
            self.toggle("xdg:example.desktop", False)
        self.assertEqual(len(seen), 1)

    def test_parent_substitution_cannot_redirect_final_replace(self):
        path = self.desktop("example")
        original_parent = path.parent
        pinned_parent = self.roots.config / "pinned-autostart"
        outside = self.roots.home / "outside"
        outside.mkdir()
        (outside / path.name).write_text("outside")
        replace = self.engine.store._replace_at
        substituted = False

        def swap_then_replace(parent_fd, name, value):
            nonlocal substituted
            if name == path.name and not substituted:
                original_parent.rename(pinned_parent)
                original_parent.symlink_to(outside, target_is_directory=True)
                substituted = True
            return replace(parent_fd, name, value)

        item = self.item("xdg:example.desktop")
        with patch.object(self.engine.store, "_replace_at", side_effect=swap_then_replace):
            self.engine.request({"action": "toggle", "id": item["id"],
                                 "revision": item["revision"], "enabled": False})
        self.assertEqual((outside / path.name).read_text(), "outside")
        self.assertIn("Hidden=true", (pinned_parent / path.name).read_text())

    def test_interruption_keeps_prepared_journal_and_original_backup(self):
        path = self.desktop("example")
        store = self.engine.store
        before = snapshot(path)
        replacement = file_value(b"changed")
        real_replace = store._replace_at

        def interrupt(parent_fd, name, value):
            real_replace(parent_fd, name, value)
            if name == path.name:
                raise KeyboardInterrupt("simulated process crash")

        with store.locked(), patch.object(store, "_replace_at", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                store.transact("xdg:example.desktop", [(path, before, replacement)])
        record = json.loads(next((self.roots.state / "transactions").glob("*.json")).read_text())
        self.assertEqual(record["status"], "prepared")
        self.assertEqual(record["entries"][0]["before"], before)
        self.assertTrue(any("interrupted" in warning for warning in self.engine.scan()["warnings"]))
        recovery = self.engine.scan()["recoveries"][0]
        self.assertTrue(recovery["recoverable"])
        with self.assertRaisesRegex(Error, "interrupted"):
            self.toggle("xdg:example.desktop", True)
        self.engine.request({"action": "recover", "id": recovery["id"], "revision": recovery["revision"]})
        self.assertEqual(snapshot(path), before)
        self.assertFalse(self.engine.scan()["recoveries"])

    def test_rollback_preserves_concurrent_external_edit(self):
        path = self.desktop("example")
        store = self.engine.store

        def external_edit():
            path.write_text("external")
            raise Error("simulated error")

        with store.locked(), self.assertRaisesRegex(Error, "External changes were preserved"):
            store.transact("test", [(path, snapshot(path), file_value(b"ours"))], after=external_edit)
        self.assertEqual(path.read_text(), "external")
        record = json.loads(next((self.roots.state / "transactions").glob("*.json")).read_text())
        self.assertEqual(record["status"], "recovery-required")

    def test_store_lock_serializes_processes(self):
        script = "import fcntl,sys; f=open(sys.argv[1],'r+'); fcntl.flock(f,fcntl.LOCK_EX); print('locked',flush=True)"
        with self.engine.store.locked():
            process = subprocess.Popen([sys.executable, "-c", script, str(self.roots.state / "lock")], stdout=subprocess.PIPE, text=True)
            try:
                time.sleep(0.08)
                self.assertIsNone(process.poll())
            except BaseException:
                process.kill()
                process.communicate()
                raise
        output, _ = process.communicate(timeout=5)
        self.assertEqual(output.strip(), "locked")

    def test_undo_added_application_restores_absence(self):
        self.desktop("sample", catalog=True)
        app = self.engine.scan()["catalog"][0]
        self.engine.request({"action":"add", "id":app["id"], "revision":app["revision"]})
        item = self.item("xdg:sample.desktop")
        self.assertTrue(item["canUndo"])
        self.engine.request({"action":"undo", "id":item["id"], "revision":item["revision"]})
        self.assertFalse((self.roots.autostart / "sample.desktop").exists())

    def test_recovery_refuses_newer_external_edits(self):
        path = self.desktop("sample")
        store = self.engine.store
        with store.locked():
            journal = self.roots.state / "transactions/interrupted.json"
            record = {"version":1, "item":"xdg:sample.desktop", "status":"prepared",
                      "entries":[{"path":str(path), "before":snapshot(path), "after":file_value(b"ours")}]}
            store.journal_write(journal, record)
        path.write_text("external")
        recovery = self.engine.scan()["recoveries"][0]
        self.assertFalse(recovery["recoverable"])
        with self.assertRaisesRegex(Error, "newer external edits"):
            self.engine.request({"action":"recover", "id":recovery["id"], "revision":recovery["revision"]})
        self.assertEqual(path.read_text(), "external")

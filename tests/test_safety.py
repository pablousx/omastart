import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

from backend.common import Error, Store, file_value, snapshot
from .support import Fixture


class SafetyTests(Fixture):
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
        with patch("backend.common.os.replace", side_effect=OSError("simulated full disk")):
            with self.assertRaises(OSError):
                self.toggle("xdg:example.desktop", False)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(path.parent.glob(".omastart-*")), [])

    def test_atomic_replace_exposes_complete_file(self):
        path = self.desktop("example")
        before = path.read_bytes()
        real_replace = os.replace
        seen = []

        def check_replace(src, dst):
            if Path(dst) == path:
                self.assertEqual(path.read_bytes(), before)
                seen.append(Path(src).read_bytes())
                self.assertIn(b"Hidden=true", seen[-1])
            return real_replace(src, dst)

        with patch("backend.common.os.replace", side_effect=check_replace):
            self.toggle("xdg:example.desktop", False)
        self.assertEqual(len(seen), 1)

    def test_interruption_keeps_prepared_journal_and_original_backup(self):
        path = self.desktop("example")
        store = self.engine.store
        before = snapshot(path)
        replacement = file_value(b"changed")
        real_replace = store._replace

        def interrupt(destination, value, **kwargs):
            real_replace(destination, value, **kwargs)
            if destination == path:
                raise KeyboardInterrupt("simulated process crash")

        with store.locked(), patch.object(store, "_replace", side_effect=interrupt):
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

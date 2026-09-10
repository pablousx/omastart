from unittest.mock import patch

from backend.common import Error
from backend.desktop import Desktop, identity
from .support import Fixture


class DesktopTests(Fixture):
    def test_disabling_added_app_keeps_a_reenableable_entry(self):
        self.desktop("sample", catalog=True)
        choice = self.engine.scan()["catalog"][0]
        self.engine.request({"action": "add", "id": choice["id"], "revision": choice["revision"]})
        path = self.roots.autostart / "sample.desktop"
        for _ in range(2):
            self.toggle("xdg:sample.desktop", False)
            self.assertTrue(path.exists())
            item = self.item("xdg:sample.desktop")
            self.assertFalse(item["enabled"])
            self.assertFalse(item["readOnly"])
            self.assertIn("Hidden=true", path.read_text())
            self.assertTrue(self.engine.scan()["catalog"][0]["exists"])
            self.toggle(item["id"], True)
            self.assertTrue(self.item(item["id"])["enabled"])

    def test_vicinae_actions_and_exact_restore(self):
        path = self.desktop("vicinae", "vicinae server --replace", "Hidden=false\n\n[Desktop Action open]\nName=Open\nExec=vicinae open\n")
        original = path.read_bytes()
        self.toggle("xdg:vicinae.desktop", False)
        self.assertIn("Hidden=true", path.read_text())
        self.assertIn("[Desktop Action open]\nName=Open\nExec=vicinae open", path.read_text())
        self.toggle("xdg:vicinae.desktop", True)
        self.assertEqual(original, path.read_bytes())

    def test_system_override_restore_removes_only_owned_file(self):
        vendor = self.desktop("sample", "sample", system=True)
        original = vendor.read_bytes()
        self.toggle("xdg:sample.desktop", False)
        self.assertEqual(vendor.read_bytes(), original)
        self.assertTrue((self.roots.autostart / "sample.desktop").exists())
        self.toggle("xdg:sample.desktop", True)
        self.assertFalse((self.roots.autostart / "sample.desktop").exists())

    def test_precedence_and_hidden_metadata(self):
        self.desktop("sample", system=True, name="Friendly Sample")
        self.write(self.roots.autostart / "sample.desktop", "[Desktop Entry]\nHidden=true\n")
        data = self.engine.scan()
        self.assertEqual(len(data["applications"]), 1)
        self.assertEqual(data["applications"][0]["name"], "Friendly Sample")
        self.assertFalse(data["applications"][0]["enabled"])

    def test_external_override_is_not_removed_on_enable(self):
        self.desktop("sample", system=True)
        path = self.desktop("sample", extra="Hidden=true\nX-Custom=keep\n")
        self.toggle("xdg:sample.desktop", True)
        self.assertTrue(path.exists())
        self.assertIn("X-Custom=keep", path.read_text())

    def test_localization_and_crlf(self):
        d = Desktop("[Desktop Entry]\r\nName=English\r\nName[es]=Español\r\nHidden=false\r\n", "es_GT.UTF-8")
        self.assertEqual(d.name, "Español")
        self.assertEqual(d.with_keys({"Hidden": "true"}), "[Desktop Entry]\r\nName=English\r\nName[es]=Español\r\nHidden=true\r\n")

    def test_eligibility_and_duplicate_keys(self):
        cases = [("OnlyShowIn=GNOME;\n", "restricted"), ("NotShowIn=Hyprland;\n", "excludes"),
                 ("TryExec=/definitely/not/an/executable\n", "unavailable"),
                 ("X-systemd-skip=true\n", "excludes"), ("AutostartCondition=if-exists foo\n", "Conditional"),
                 ("X-GNOME-Autostart-Phase=Initialization\n", "phases"),
                 ("Hidden=false\nHidden=true\n", "Duplicate")]
        for index, (extra, reason) in enumerate(cases):
            self.desktop("case" + str(index), extra=extra)
            item = self.item("xdg:case" + str(index) + ".desktop")
            self.assertIn(reason.lower(), item["readOnly"].lower())

    def test_nodisplay_does_not_disable_autostart(self):
        self.desktop("internal", extra="NoDisplay=true\n")
        item = self.item("xdg:internal.desktop")
        self.assertTrue(item["enabled"])
        self.assertTrue(item["system"])

    def test_injection_is_copied_not_executed(self):
        payload = "example --arg '$(touch /tmp/omastart-pwned)' ; echo `whoami`"
        self.desktop("example", payload, catalog=True)
        catalog = self.engine.scan()["catalog"][0]
        self.engine.request({"action": "add", "id": catalog["id"], "revision": catalog["revision"]})
        self.assertIn(payload, (self.roots.autostart / "example.desktop").read_text())
        self.assertFalse(any("example" in argv for argv, _ in self.runner.calls))

    def test_add_is_rejected_for_existing_independent_source(self):
        self.desktop("vicinae", "vicinae server", catalog=True)
        self.unit("vicinae", "vicinae server")
        choice = self.engine.scan()["catalog"][0]
        self.assertTrue(choice["exists"])
        with self.assertRaisesRegex(Error, "already"):
            self.engine.request({"action": "add", "id": choice["id"], "revision": choice["revision"]})

    def test_application_id_precedence(self):
        self.desktop("app", catalog=True, extra="Hidden=true\n")
        self.assertEqual(self.engine.scan()["catalog"], [])

    def test_identity_wrappers_and_interpreters(self):
        self.assertEqual(identity("env FOO=bar uwsm-app -- /opt/Synergy/synergy-service -d"), "synergy")
        self.assertEqual(identity("flatpak run --branch=stable org.example.App %U"), "flatpak:org.example.App")
        self.assertNotEqual(identity("flatpak run org.example.One"), identity("flatpak run org.example.Two"))
        self.assertEqual(identity("python3 /different/apps.py"), "")
        self.assertEqual(identity("unclosed 'quote"), "")

    def test_xdg_edits_refresh_generator_without_starting_or_stopping_apps(self):
        self.desktop("sample")
        self.toggle("xdg:sample.desktop", False)
        self.assertIn((["systemctl", "--user", "daemon-reload"], {}), self.runner.calls)
        self.assertTrue(all(argv[2] in ("show", "list-unit-files", "daemon-reload") for argv, _ in self.runner.calls))

    def test_system_symlink_target_content_invalidates_revision(self):
        target = self.desktop("sample", catalog=True)
        link = self.etc / "autostart/sample.desktop"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        before = self.item("xdg:sample.desktop")["revision"]
        target.write_text(target.read_text() + "# changed vendor content\n")
        self.assertNotEqual(before, self.item("xdg:sample.desktop")["revision"])

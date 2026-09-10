import os

from backend.common import Error
from .support import Fixture


class SystemdTests(Fixture):
    def test_global_synergy_mask_and_exact_restore(self):
        unit = self.unit("synergy", "/opt/Synergy/synergy-service -d", global_enabled=True)
        global_link = self.global_units / "graphical-session.target.wants/synergy.service"
        original = unit.read_bytes()
        item = self.item("systemd:synergy.service")
        self.assertTrue(item["enabled"])
        self.assertTrue(item["globalEnabled"])
        self.assertEqual(item["readOnly"], "")
        self.toggle(item["id"], False)
        mask = self.roots.user_units / "synergy.service"
        self.assertEqual(os.readlink(mask), "/dev/null")
        self.assertFalse(self.item(item["id"])["enabled"])
        self.toggle(item["id"], True)
        self.assertFalse(mask.is_symlink())
        self.assertTrue(global_link.is_symlink())
        self.assertEqual(unit.read_bytes(), original)
        self.assertTrue(self.item(item["id"])["enabled"])

    def test_user_service_link_roundtrip(self):
        path = self.unit("personal", "personal --hello", local_enabled=True, user=True)
        original = path.read_bytes()
        link = self.roots.user_units / "graphical-session.target.wants/personal.service"
        self.toggle("systemd:personal.service", False)
        self.assertFalse(link.exists())
        self.assertTrue(path.exists())
        self.toggle("systemd:personal.service", True)
        self.assertEqual(os.readlink(link), str(path))
        self.assertEqual(path.read_bytes(), original)

    def test_enable_disabled_vendor_application(self):
        unit = self.unit("hyprsunset")
        self.toggle("systemd:hyprsunset.service", True)
        link = self.roots.user_units / "graphical-session.target.wants/hyprsunset.service"
        self.assertEqual(os.readlink(link), str(unit))
        self.assertTrue(self.item("systemd:hyprsunset.service")["enabled"])

    def test_required_targets_aliases_and_triggers_are_protected(self):
        for property_name, value in (("RequiredBy", "important.service"), ("TriggeredBy", "example.timer"),
                                     ("UnitFileState", "static"), ("UnitFileState", "enabled-runtime")):
            self.unit("hyprsunset")
            self.runner.overrides["hyprsunset.service"] = {property_name: value}
            self.assertTrue(self.item("systemd:hyprsunset.service")["readOnly"])
        self.runner.overrides.clear()
        self.unit("hyprsunset", extra="Also=other.service\n")
        self.assertTrue(self.item("systemd:hyprsunset.service")["readOnly"])

    def test_external_mask_is_read_only(self):
        self.unit("synergy", global_enabled=True)
        mask = self.roots.user_units / "synergy.service"
        mask.parent.mkdir(parents=True, exist_ok=True)
        mask.symlink_to("/dev/null")
        item = self.item("systemd:synergy.service")
        self.assertFalse(item["enabled"])
        self.assertIn("outside omastart", item["readOnly"])

    def test_global_with_existing_local_unit_is_protected(self):
        self.unit("synergy", global_enabled=True, user=True)
        self.assertTrue(self.item("systemd:synergy.service")["readOnly"])

    def test_infrastructure_is_protected_even_with_desktop_metadata(self):
        self.unit("pipewire", local_enabled=True)
        self.desktop("pipewire", catalog=True)
        item = self.item("systemd:pipewire.service")
        self.assertTrue(item["system"])
        with self.assertRaisesRegex(Error, "Protected"):
            self.toggle(item["id"], False)

    def test_unavailable_bus_preserves_read_only_inventory(self):
        self.unit("synergy", global_enabled=True)
        self.runner.unavailable = True
        data = self.engine.scan()
        self.assertTrue(data["warnings"])
        item = self.engine.items[0]
        self.assertTrue(item["enabled"])
        self.assertIn("unavailable", item["readOnly"])

    def test_generated_xdg_unit_is_merged(self):
        path = self.desktop("vicinae", "vicinae server --replace")
        generated = self.roots.runtime / "systemd/generator.late/app-vicinae@autostart.service"
        self.write(generated, f"[Unit]\nSourcePath={path}\nPartOf=graphical-session.target\n[Service]\nExecStart=vicinae server --replace\n")
        self.unit("vicinae", "vicinae server --replace")
        data = self.engine.scan()
        self.assertEqual(len(data["applications"]), 1)
        app = data["applications"][0]
        self.assertEqual(app["status"], "Enabled")
        self.assertEqual(len(app["sources"]), 2)
        self.assertFalse(app["duplicate"])
        self.assertEqual(app["sources"][0]["generatedUnits"], ["app-vicinae@autostart.service"])

    def test_required_live_examples(self):
        self.desktop("vicinae", "vicinae server --replace")
        self.unit("vicinae", "vicinae server --replace")
        self.unit("synergy", "/opt/Synergy/synergy-service -d", global_enabled=True)
        self.unit("hyprsunset")
        self.write(self.roots.lua, 'o.launch_on_start("hyprsunset")\n')
        apps = {app["name"]: app for app in self.engine.scan()["applications"]}
        self.assertEqual(set(apps), {"Vicinae", "Synergy", "hyprsunset"})
        for app in apps.values():
            self.assertEqual(app["status"], "Enabled")
            self.assertFalse(app["system"])
            self.assertFalse(app["duplicate"])
        self.assertEqual(apps["hyprsunset"]["activeKinds"], ["hyprland"])
        self.assertEqual(apps["Synergy"]["activeKinds"], ["systemd"])
        self.assertEqual(apps["Vicinae"]["activeKinds"], ["xdg"])

    def test_multiple_independent_active_sources_are_not_silently_deduplicated(self):
        self.desktop("vicinae", "vicinae server")
        self.unit("vicinae", "vicinae server", global_enabled=True)
        app = self.engine.scan()["applications"][0]
        self.assertTrue(app["duplicate"])
        self.assertEqual(len(app["sources"]), 2)

    def test_reload_failure_restores_links(self):
        self.unit("synergy", global_enabled=True)
        self.runner.fail_reload = True
        with self.assertRaisesRegex(Error, "rolled back"):
            self.toggle("systemd:synergy.service", False)
        self.assertFalse((self.roots.user_units / "synergy.service").is_symlink())
        self.assertTrue(self.item("systemd:synergy.service")["enabled"])

    def test_no_process_control_commands(self):
        self.unit("synergy", global_enabled=True)
        self.toggle("systemd:synergy.service", False)
        self.toggle("systemd:synergy.service", True)
        allowed = {"show", "list-unit-files", "daemon-reload"}
        for argv, _ in self.runner.calls:
            self.assertEqual(argv[:2], ["systemctl", "--user"])
            self.assertIn(argv[2], allowed)

    def test_templates_are_not_sent_to_manager_show(self):
        self.unit("example@")
        self.engine.scan()
        calls = [argv for argv, _ in self.runner.calls if len(argv) > 2 and argv[2] == "show"]
        self.assertFalse(any("example@.service" in argv for argv in calls))

    def test_alias_resolves_to_one_canonical_source(self):
        unit = self.unit("hyprsunset")
        (self.vendor / "nightlight.service").symlink_to(unit)
        self.runner.overrides["hyprsunset.service"] = {"Names": "hyprsunset.service nightlight.service"}
        self.runner.overrides["nightlight.service"] = {"Id": "hyprsunset.service", "Names": "hyprsunset.service nightlight.service"}
        app = self.engine.scan()["applications"][0]
        self.assertEqual(len(app["sources"]), 1)

    def test_symlinked_vendor_content_is_part_of_revision(self):
        unit = self.unit("synergy")
        link = self.global_units / "synergy.service"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(unit)
        before = self.item("systemd:synergy.service")["revision"]
        unit.write_text(unit.read_text() + "# vendor changed\n")
        self.assertNotEqual(before, self.item("systemd:synergy.service")["revision"])

    def test_masked_generated_unit_still_belongs_to_xdg(self):
        path = self.desktop("vicinae", "vicinae server")
        name = "app-vicinae@autostart.service"
        self.write(self.roots.runtime / "systemd/generator.late" / name,
                   f"[Unit]\nSourcePath={path}\nPartOf=graphical-session.target\n[Service]\nExecStart=vicinae server\n")
        mask = self.roots.user_units / name
        mask.parent.mkdir(parents=True, exist_ok=True)
        mask.symlink_to("/dev/null")
        self.runner.overrides[name] = {"FragmentPath":str(mask), "UnitFileState":"masked"}
        app = self.engine.scan()["applications"][0]
        self.assertEqual(len(app["sources"]), 1)
        self.assertFalse(app["enabled"])
        self.assertIn("masked", app["sources"][0]["readOnly"])

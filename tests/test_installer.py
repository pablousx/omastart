import importlib.util
from pathlib import Path
import unittest


PROJECT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("omastart_installer", PROJECT / "scripts/install.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerPlacementTests(unittest.TestCase):
    plugin_id = "io.github.pablousx.omastart"

    def test_direct_layout_entry_preserves_exact_placement_and_settings(self):
        entry = {"id": self.plugin_id, "compact": True}
        config = {"bar": {"layout": {"left": [], "right": [{"id": "a"}, entry]}},
                  "plugins": [{"id": self.plugin_id}]}

        enabled, placed, placement, old_entry = installer.previous_placement(
            config, self.plugin_id)

        self.assertTrue(enabled)
        self.assertTrue(placed)
        self.assertEqual(placement, ["--section", "right", "--index", "1"])
        self.assertIs(old_entry, entry)

    def test_orphaned_pocket_member_is_repaired_before_the_pocket(self):
        config = {
            "bar": {"layout": {"right": [
                {"id": "a"},
                {"id": "jrmmhm.pocket", "members": "a, io.github.pablousx.omastart"},
            ]}},
            "plugins": [{"id": self.plugin_id}],
        }

        enabled, placed, placement, old_entry = installer.previous_placement(
            config, self.plugin_id)

        self.assertFalse(enabled)
        self.assertFalse(placed)
        self.assertEqual(placement, ["--section", "right", "--index", "1"])
        self.assertEqual(old_entry, {})

    def test_configured_unplaced_widget_is_enabled_in_default_section(self):
        config = {"bar": {"layout": {"center": []}},
                  "plugins": [{"id": self.plugin_id}]}

        enabled, placed, placement, _ = installer.previous_placement(config, self.plugin_id)

        self.assertFalse(enabled)
        self.assertFalse(placed)
        self.assertEqual(placement, ["--section", "left"])

    def test_array_pocket_members_are_supported(self):
        config = {"bar": {"layout": {"right": [
            {"id": "jrmmhm.pocket", "members": [self.plugin_id]},
        ]}}, "plugins": [{"id": self.plugin_id}]}

        _, placed, placement, _ = installer.previous_placement(config, self.plugin_id)

        self.assertFalse(placed)
        self.assertEqual(placement, ["--section", "right", "--index", "0"])

    def test_generic_plugin_entry_is_detected_for_bar_widget_repair(self):
        config = {"plugins": [{"id": "another.plugin"}, {"id": self.plugin_id}]}

        self.assertTrue(installer.configured_as_generic_plugin(config, self.plugin_id))
        self.assertFalse(installer.configured_as_generic_plugin(config, "missing.plugin"))


if __name__ == "__main__":
    unittest.main()

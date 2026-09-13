import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent


class BoundaryContractTests(unittest.TestCase):
    def test_panel_uses_closed_bounded_bridge(self):
        panel = (ROOT / "Panel.qml").read_text()
        self.assertIn('["/usr/bin/python3", "-I", "-B", root.bridgePath', panel)
        self.assertIn("clearEnvironment: true", panel)
        self.assertNotIn("StdioCollector", panel)
        self.assertIn("response exceeded its safety limit", panel)
        self.assertIn("request exceeded its time limit", panel)

    def test_installer_replacements_are_descriptor_relative(self):
        source = (ROOT / "scripts/install.py").read_text()
        tree = ast.parse(source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("os.replace", source)
        self.assertIn("secure._target", source)
        renames = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute) and node.func.attr == "rename"]
        self.assertTrue(renames)
        for call in renames:
            keywords = {item.arg for item in call.keywords}
            self.assertIn("src_dir_fd", keywords)
            self.assertIn("dst_dir_fd", keywords)

    def test_runtime_tool_identities_are_absolute(self):
        common = (ROOT / "backend/common.py").read_text()
        installer = (ROOT / "scripts/install.py").read_text()
        self.assertIn('"systemctl": "/usr/bin/systemctl"', common)
        self.assertIn('"luac": "/usr/bin/luac"', common)
        self.assertIn('OMARCHY = "/usr/bin/omarchy"', installer)
        self.assertIn('OMARCHY_SHELL = "/usr/bin/omarchy-shell"', installer)


if __name__ == "__main__":
    unittest.main()

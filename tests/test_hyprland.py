from backend.common import Error
from backend.hyprland import lex, literal, parse
from .support import Fixture


class HyprlandTests(Fixture):
    def lua_item(self):
        self.engine.scan()
        return next(s for s in self.engine.items if s["kind"] == "hyprland" and not s["readOnly"])

    def test_single_line_roundtrip_preserves_bytes(self):
        original = '-- Heading\n  o.launch_on_start("hyprsunset") -- night light\n\n'
        self.write(self.roots.lua, original)
        item = self.lua_item()
        self.toggle(item["id"], False)
        off = self.lua_item()
        self.assertFalse(off["enabled"])
        self.assertEqual(off["id"], item["id"])
        self.toggle(off["id"], True)
        self.assertEqual(self.roots.lua.read_text(), original)

    def test_multiline_long_literal_roundtrip(self):
        original = 'o.launch_on_start(\n  [[hyprsunset]]\n)\n'
        self.write(self.roots.lua, original)
        item = self.lua_item()
        self.toggle(item["id"], False)
        off = self.lua_item()
        self.assertFalse(off["enabled"])
        self.toggle(off["id"], True)
        self.assertEqual(self.roots.lua.read_text(), original)

    def test_nested_and_dynamic_calls_are_read_only(self):
        text = 'if true then\n o.launch_on_start("nested")\nend\no.launch_on_start(command)\n'
        rows = parse(text)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["readOnly"] for row in rows))

    def test_words_in_comments_and_strings_do_not_change_depth(self):
        text = '-- function if then end\nlocal value = "if function"\no.launch_on_start("hyprsunset")\n'
        self.assertFalse(parse(text)[0]["readOnly"])

    def test_long_comment_is_not_an_entry(self):
        self.assertEqual(parse('--[=[\no.launch_on_start("hidden")\n]=]\n'), [])

    def test_shared_statement_is_not_editable(self):
        self.assertTrue(parse('o.launch_on_start("one"); print("two")')[0]["readOnly"])
        self.assertTrue(parse('local value = o.launch_on_start("one")')[0]["readOnly"])

    def test_existing_commented_literal_can_be_enabled(self):
        self.write(self.roots.lua, '-- o.exec_on_start("example")\n')
        item = self.lua_item()
        self.assertFalse(item["enabled"])
        self.toggle(item["id"], True)
        self.assertEqual(self.roots.lua.read_text(), 'o.exec_on_start("example")\n')

    def test_escape_decoding(self):
        self.assertEqual(literal(r'"a\x20b\032c\n"'), 'a b c\n')
        self.assertEqual(literal('[=[\nhello]=]'), 'hello')
        with self.assertRaises(Error):
            literal(r'"bad\q"')

    def test_invalid_surrounding_lua_is_not_written(self):
        original = 'invalid !!!\no.launch_on_start("hyprsunset")\n'
        self.write(self.roots.lua, original)
        item = self.lua_item()
        with self.assertRaises(Error):
            self.toggle(item["id"], False)
        self.assertEqual(self.roots.lua.read_text(), original)

    def test_template_is_protected(self):
        self.write(self.roots.lua, '-- o.launch_on_start("my-service")\n')
        self.engine.scan()
        self.assertTrue(self.engine.items[0]["system"])
        self.assertIn("template", self.engine.items[0]["readOnly"])

    def test_managed_marker_inside_long_string_is_not_an_entry(self):
        self.assertEqual(parse('local documentation = [[\n-- omastart:off o.launch_on_start("example")\n]]'), [])

    def test_adjacent_disabled_statements_remain_independent(self):
        self.write(self.roots.lua, 'o.launch_on_start("one")\no.launch_on_start("two")\n')
        self.engine.scan()
        ids = [s["id"] for s in self.engine.items]
        for item_id in ids:
            self.toggle(item_id, False)
        self.engine.scan()
        self.assertEqual(len(self.engine.items), 2)
        self.assertTrue(all(not s["enabled"] and not s["readOnly"] for s in self.engine.items))

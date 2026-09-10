"""Application toggles use one reversible transaction across startup providers."""
import json
from unittest.mock import patch

from backend.common import Error, snapshot
from backend import desktop
from backend.engine import group
from .support import Fixture


class ApplicationTests(Fixture):
    def application(self):
        return self.engine.scan()['applications'][0]

    def change_app(self, enabled):
        app = self.application()
        return self.engine.request(dict(action='toggleApplication', id=app['id'], revision=app['revision'], enabled=enabled))

    def undo_app(self):
        app = self.application()
        return self.engine.request(dict(action='undoApplication', id=app['id'], revision=app['revision']))

    def methods(self, *, enabled=True):
        self.desktop('vicinae', 'vicinae server', extra='' if enabled else 'Hidden=true\n')
        self.unit('vicinae', 'vicinae server', global_enabled=enabled)
        self.write(self.roots.lua, ('' if enabled else '-- ') + 'o.launch_on_start("vicinae server")\n')

    def states(self):
        return {s['kind']: s['enabled'] for s in self.application()['sources']}

    def test_disable_all_methods_in_one_journal_and_exact_undo(self):
        self.methods()
        original_lua = snapshot(self.roots.lua)
        original_desktop = snapshot(self.roots.autostart / 'vicinae.desktop')
        self.change_app(False)
        self.assertEqual(self.states(), dict(hyprland=False, xdg=False, systemd=False))
        journals = list((self.roots.state / 'transactions').glob('*.json'))
        self.assertEqual(len(journals), 1)
        record = json.loads(journals[0].read_text())
        self.assertEqual(len(record['sources']), 3)
        self.assertEqual(len(record['entries']), 3)
        self.assertTrue(self.application()['canUndo'])
        self.assertTrue(all(not s['canUndo'] for s in self.application()['sources']))
        self.undo_app()
        self.assertEqual(self.states(), dict(hyprland=True, xdg=True, systemd=True))
        self.assertEqual(snapshot(self.roots.lua), original_lua)
        self.assertEqual(snapshot(self.roots.autostart / 'vicinae.desktop'), original_desktop)
        self.assertFalse((self.roots.user_units / 'vicinae.service').is_symlink())

    def test_reenable_only_prefers_existing_hyprland_entry(self):
        self.methods()
        self.change_app(False)
        self.change_app(True)
        self.assertEqual(self.states(), dict(hyprland=True, xdg=False, systemd=False))
        self.assertFalse(self.application()['duplicate'])
        self.change_app(False)
        self.change_app(True)
        self.assertEqual(self.states(), dict(hyprland=True, xdg=False, systemd=False))

    def test_xdg_is_preferred_to_systemd_when_no_hyprland_entry(self):
        self.desktop('vicinae', 'vicinae server', extra='Hidden=true\n')
        self.unit('vicinae', 'vicinae server')
        self.change_app(True)
        self.assertEqual(self.states(), dict(xdg=True, systemd=False))

    def test_ineligible_xdg_falls_back_to_systemd(self):
        self.desktop('vicinae', 'vicinae server', extra='Hidden=true\nOnlyShowIn=GNOME;\n')
        self.unit('vicinae', 'vicinae server')
        self.change_app(True)
        self.assertEqual(self.states(), dict(xdg=False, systemd=True))

    def test_enable_without_eligible_method_is_rejected(self):
        self.desktop('vicinae', 'vicinae server', extra='Hidden=true\nOnlyShowIn=GNOME;\n')
        with self.assertRaisesRegex(Error, 'No editable'):
            self.change_app(True)
        self.assertFalse(self.application()['startupEnabled'])

    def test_enabled_ineligible_protected_method_is_not_silently_skipped(self):
        self.desktop('vicinae', 'vicinae server', extra='OnlyShowIn=GNOME;\n')
        self.unit('vicinae', 'vicinae server', local_enabled=True)
        with self.assertRaisesRegex(Error, 'read-only'):
            self.change_app(False)
        self.assertEqual(self.states(), dict(xdg=True, systemd=True))

    def test_any_enabled_readonly_method_blocks_whole_change(self):
        self.desktop('vicinae', 'vicinae server')
        self.unit('vicinae', 'vicinae server', local_enabled=True)
        self.runner.overrides['vicinae.service'] = {'TriggeredBy': 'example.socket'}
        before = snapshot(self.roots.autostart / 'vicinae.desktop')
        with self.assertRaisesRegex(Error, 'read-only'):
            self.change_app(False)
        self.assertEqual(snapshot(self.roots.autostart / 'vicinae.desktop'), before)
        self.assertTrue(all(self.states().values()))

    def test_disabled_readonly_alternative_does_not_block_other_method(self):
        self.desktop('vicinae', 'vicinae server', extra='Hidden=true\n')
        self.unit('vicinae', 'vicinae server')
        self.runner.overrides['vicinae.service'] = {'TriggeredBy': 'example.socket'}
        self.change_app(True)
        self.assertEqual(self.states(), dict(xdg=True, systemd=False))

    def test_unknown_state_blocks_toggle(self):
        self.desktop('vicinae', 'vicinae server')
        self.engine.scan()
        item = dict(self.engine.items[0], enabled=None)
        app = group([item])[0]
        self.assertIn('unknown', app['toggleReadOnly'])
        with self.assertRaisesRegex(Error, 'unknown'):
            self.engine.toggle_application(app, False)

    def test_stale_source_or_new_method_refuses_application_request(self):
        self.desktop('vicinae', 'vicinae server')
        app = self.application()
        self.unit('vicinae', 'vicinae server')
        with self.assertRaisesRegex(Error, 'changed'):
            self.engine.request(dict(action='toggleApplication', id=app['id'], revision=app['revision'], enabled=False))
        app = self.application()
        path = self.roots.autostart / 'vicinae.desktop'
        path.write_text(path.read_text() + '# external edit\n')
        with self.assertRaisesRegex(Error, 'changed'):
            self.engine.request(dict(action='toggleApplication', id=app['id'], revision=app['revision'], enabled=False))
        self.assertTrue(self.application()['startupEnabled'])

    def test_reload_failure_rolls_back_all_providers(self):
        self.methods()
        before = snapshot(self.roots.lua)
        self.runner.fail_reload = True
        with self.assertRaisesRegex(Error, 'rolled back'):
            self.change_app(False)
        self.assertEqual(self.states(), dict(hyprland=True, xdg=True, systemd=True))
        self.assertEqual(snapshot(self.roots.lua), before)
        self.assertFalse(self.application()['canUndo'])

    def test_edit_during_planning_is_preserved_without_partial_writes(self):
        self.methods()
        path = self.roots.autostart / 'vicinae.desktop'
        planner = desktop.toggle_changes

        def edit_before_plan(*args):
            path.write_text(path.read_text() + '# concurrent edit\n')
            return planner(*args)

        with patch.object(desktop, 'toggle_changes', side_effect=edit_before_plan):
            with self.assertRaisesRegex(Error, 'changed'):
                self.change_app(False)
        self.assertIn('# concurrent edit', path.read_text())
        self.assertEqual(self.states(), dict(hyprland=True, xdg=True, systemd=True))

    def test_removed_method_invalidates_group_undo(self):
        self.desktop('vicinae', 'vicinae server')
        unit = self.unit('vicinae', 'vicinae server', local_enabled=True)
        self.change_app(False)
        unit.unlink()
        self.assertFalse(self.application()['canUndo'])
        with self.assertRaisesRegex(Error, 'changed'):
            self.undo_app()

    def test_two_lua_methods_are_disabled_together_and_restored(self):
        original = 'o.launch_on_start("vicinae server")\n\no.exec_on_start("vicinae server")\n'
        self.write(self.roots.lua, original)
        self.assertEqual(len(self.application()['sources']), 2)
        self.change_app(False)
        self.assertTrue(all(s['enabled'] is False for s in self.application()['sources']))
        self.undo_app()
        self.assertEqual(self.roots.lua.read_text(), original)
        self.change_app(False)
        self.change_app(True)
        self.assertEqual(sum(s['enabled'] for s in self.application()['sources']), 1)
        self.assertIn('o.launch_on_start("vicinae server")\n', self.roots.lua.read_text().split('-- omastart:off')[0])

    def test_provider_toggle_restores_only_its_portion_of_group(self):
        self.methods()
        self.change_app(False)
        masked = self.item('systemd:vicinae.service')
        self.assertFalse(masked['readOnly'])
        self.toggle(masked['id'], True)
        self.assertEqual(self.states(), dict(hyprland=False, xdg=False, systemd=True))
        self.assertFalse(self.application()['canUndo'])

    def test_source_undo_cannot_silently_restore_a_group(self):
        self.methods()
        self.change_app(False)
        item = self.item('xdg:vicinae.desktop')
        with self.assertRaisesRegex(Error, "application's Undo"):
            self.engine.request(dict(action='undo', id=item['id'], revision=item['revision']))
        self.assertEqual(self.states(), dict(hyprland=False, xdg=False, systemd=False))

    def test_external_edit_invalidates_group_undo(self):
        self.methods()
        self.change_app(False)
        self.roots.lua.write_text(self.roots.lua.read_text() + '-- external\n')
        self.assertFalse(self.application()['canUndo'])
        with self.assertRaisesRegex(Error, 'changed'):
            self.undo_app()
        self.assertIn('-- external', self.roots.lua.read_text())

    def test_interrupted_group_can_be_recovered_with_systemd_reload(self):
        self.methods()
        before = snapshot(self.roots.lua)
        store = self.engine.store
        replace = store._replace

        def interrupt(path, value, **kwargs):
            replace(path, value, **kwargs)
            if path == self.roots.autostart / 'vicinae.desktop':
                raise KeyboardInterrupt('simulated interruption')

        with patch.object(store, '_replace', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.change_app(False)
        recovery = self.engine.scan()['recoveries'][0]
        self.assertTrue(recovery['recoverable'])
        self.runner.calls.clear()
        self.engine.request(dict(action='recover', id=recovery['id'], revision=recovery['revision']))
        self.assertEqual(self.states(), dict(hyprland=True, xdg=True, systemd=True))
        self.assertEqual(snapshot(self.roots.lua), before)
        self.assertIn((['systemctl', '--user', 'daemon-reload'], {}), self.runner.calls)
        self.assertFalse(self.engine.scan()['recoveries'])

    def test_invalid_boolean_rejected_and_noop_writes_nothing(self):
        self.methods()
        with self.assertRaisesRegex(Error, 'boolean'):
            self.change_app('false')
        self.change_app(True)
        self.assertFalse((self.roots.state / 'transactions').exists())

    def test_group_never_starts_or_stops_running_programs(self):
        self.methods()
        self.change_app(False)
        self.change_app(True)
        self.undo_app()
        for argv, _ in self.runner.calls:
            self.assertTrue(argv == ['luac', '-p', '-'] or argv[:2] == ['systemctl', '--user']
                            and argv[2] in {'show', 'list-unit-files', 'daemon-reload'})

import os
from unittest.mock import patch

from backend.common import Error, snapshot
from backend.engine import Engine
from backend import removal
from .support import Fixture


class RemovalTests(Fixture):
    def app(self):
        return self.engine.scan()['applications'][0]

    def add(self):
        choice = self.engine.scan()['catalog'][0]
        return self.engine.request(dict(action='add', id=choice['id'], revision=choice['revision']))

    def add_disabled(self):
        self.desktop('sample', catalog=True)
        self.add()
        self.toggle('xdg:sample.desktop', False)
        return self.app()

    def remove(self):
        app = self.app()
        return self.engine.request(dict(action='remove', id=app['id'], revision=app['revision']))

    def test_remove_persists_without_deleting_disabled_configuration(self):
        app = self.add_disabled()
        path = self.roots.autostart / 'sample.desktop'
        before = snapshot(path)
        result = self.remove()
        self.assertEqual(result['applications'], [])
        self.assertFalse(result['catalog'][0]['exists'])
        self.assertEqual(snapshot(path), before)
        self.assertEqual(Engine(self.roots, self.runner).scan()['applications'], [])
        self.assertEqual(removal.path_for(self.roots, app['id']).stat().st_mode & 0o777, 0o600)

    def test_enabled_application_cannot_be_removed(self):
        self.desktop('sample')
        self.assertFalse(self.app()['canRemove'])
        with self.assertRaisesRegex(Error, 'fully disabled'):
            self.remove()
        self.assertTrue(self.app()['enabled'])

    def test_any_active_method_prevents_removal(self):
        self.desktop('sample', extra='Hidden=true\n')
        self.desktop('sample', catalog=True)
        self.unit('sample', global_enabled=True)
        with self.assertRaisesRegex(Error, 'fully disabled'):
            self.remove()
        self.assertEqual(len(self.app()['sources']), 2)

    def test_undo_removal_restores_disabled_row_without_reloading_services(self):
        self.add_disabled()
        before = snapshot(self.roots.autostart / 'sample.desktop')
        self.runner.calls.clear()
        entry = self.remove()['removed'][0]
        self.assertTrue(entry['canUndo'])
        result = self.engine.request(dict(action='undoRemoval', id=entry['id'], revision=entry['revision']))
        self.assertEqual(len(result['applications']), 1)
        self.assertFalse(result['applications'][0]['enabled'])
        self.assertEqual(snapshot(self.roots.autostart / 'sample.desktop'), before)
        self.assertFalse(any(argv == ['systemctl', '--user', 'daemon-reload'] for argv, _ in self.runner.calls))

    def test_adding_back_reuses_entry_and_disabling_still_keeps_it(self):
        self.add_disabled()
        self.remove()
        result = self.add()
        self.assertEqual(result['addedApplicationUndo'], 'application')
        self.assertEqual(result['addedApplicationId'], result['applications'][0]['id'])
        self.assertTrue(result['applications'][0]['enabled'])
        self.assertEqual(len(result['applications'][0]['sources']), 1)
        self.toggle('xdg:sample.desktop', False)
        self.assertEqual(len(self.engine.scan()['applications']), 1)
        self.assertFalse(self.app()['enabled'])

    def test_removal_keeps_global_mask_and_readd_is_undoable(self):
        self.desktop('sample', catalog=True)
        self.unit('sample', global_enabled=True)
        self.toggle('systemd:sample.service', False)
        self.remove()
        mask = self.roots.user_units / 'sample.service'
        self.assertEqual(os.readlink(mask), '/dev/null')
        result = self.add()
        app = result['applications'][0]
        self.assertTrue(app['enabled'])
        self.assertFalse(mask.is_symlink())
        self.assertFalse((self.roots.autostart / 'sample.desktop').exists())
        self.assertTrue(app['canUndo'])
        result = self.engine.request(dict(action='undoApplication', id=app['id'], revision=app['revision']))
        self.assertFalse(result['applications'])
        self.assertEqual(os.readlink(mask), '/dev/null')

    def test_readonly_disabled_service_can_be_removed_without_editing_it(self):
        self.desktop('sample', catalog=True)
        unit = self.unit('sample')
        self.runner.overrides['sample.service'] = {'UnitFileState': 'static'}
        before = snapshot(unit)
        self.assertTrue(self.app()['canRemove'])
        self.remove()
        self.assertEqual(snapshot(unit), before)
        self.assertEqual(self.engine.scan()['applications'], [])
        # The installed desktop entry offers a new eligible method; the
        # protected service itself remains untouched when adding the app back.
        result = self.add()
        app = result['applications'][0]
        self.assertEqual(len(app['sources']), 2)
        self.assertTrue(app['enabled'])
        self.assertEqual(snapshot(unit), before)
        self.engine.request(dict(action='undoApplication', id=app['id'], revision=app['revision']))
        self.assertEqual(self.engine.scan()['applications'], [])

    def test_external_reenable_then_disable_never_reactivates_old_removal(self):
        self.add_disabled()
        self.remove()
        path = self.roots.autostart / 'sample.desktop'
        path.write_text(path.read_text().replace('Hidden=true', 'Hidden=false'))
        self.assertTrue(self.app()['enabled'])
        result = self.toggle('xdg:sample.desktop', False)
        self.assertEqual(len(result['applications']), 1)
        self.assertFalse(result['applications'][0]['enabled'])
        self.assertTrue(result['applications'][0]['canUndo'])
        self.assertFalse(removal.path_for(self.roots, self.app()['id']).exists())

    def test_stale_remove_request_preserves_external_enablement(self):
        app = self.add_disabled()
        self.toggle('xdg:sample.desktop', True)
        with self.assertRaisesRegex(Error, 'changed'):
            self.engine.request(dict(action='remove', id=app['id'], revision=app['revision']))
        self.assertTrue(self.app()['enabled'])
        self.assertFalse(removal.path_for(self.roots, app['id']).exists())

    def test_removed_record_symlink_is_not_overwritten(self):
        app = self.add_disabled()
        target = self.write(self.roots.home / 'external', 'preserve this')
        marker = removal.path_for(self.roots, app['id'])
        marker.parent.mkdir(parents=True)
        marker.symlink_to(target)
        self.assertFalse(self.app()['canRemove'])
        with self.assertRaises(Error):
            self.remove()
        self.assertTrue(marker.is_symlink())
        self.assertEqual(target.read_text(), 'preserve this')

    def test_failed_remove_leaves_the_app_visible_and_disabled(self):
        app = self.add_disabled()
        marker = removal.path_for(self.roots, app['id'])
        replace = self.engine.store._replace_at

        def fail(parent_fd, name, value):
            if name == marker.name:
                raise Error('simulated failure')
            return replace(parent_fd, name, value)

        with patch.object(self.engine.store, '_replace_at', side_effect=fail):
            with self.assertRaisesRegex(Error, 'rolled back'):
                self.remove()
        self.assertEqual(self.app()['id'], app['id'])
        self.assertFalse(self.app()['enabled'])

    def test_interrupted_remove_has_recovery_without_startup_edits(self):
        app = self.add_disabled()
        marker = removal.path_for(self.roots, app['id'])
        before = snapshot(self.roots.autostart / 'sample.desktop')
        replace = self.engine.store._replace_at

        def interrupt(parent_fd, name, value):
            replace(parent_fd, name, value)
            if name == marker.name:
                raise KeyboardInterrupt('simulated interruption')

        with patch.object(self.engine.store, '_replace_at', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.remove()
        recovery = self.engine.scan()['recoveries'][0]
        self.engine.request(dict(action='recover', id=recovery['id'], revision=recovery['revision']))
        self.assertEqual(self.app()['id'], app['id'])
        self.assertEqual(snapshot(self.roots.autostart / 'sample.desktop'), before)

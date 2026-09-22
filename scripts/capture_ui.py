#!/usr/bin/env python3
"""Capture the actual panel with isolated sample data and the current theme."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

project = Path(__file__).resolve().parent.parent
output = project / '.verification/look-and-feel'
output.mkdir(parents=True, exist_ok=True)
fixture_source = (project / 'tests/qml/shell.qml').read_text()
fixture = fixture_source.split('property var fixture: ', 1)[1].split('\n    })', 1)[0] + '\n    })'
with tempfile.TemporaryDirectory(prefix='omastart-capture-') as directory:
    root = Path(directory)
    (root / 'Commons').symlink_to('/usr/share/omarchy/shell/Commons', target_is_directory=True)
    shutil.copytree('/usr/share/omarchy/shell/Ui', root / 'Ui')
    shutil.copy2(project / 'tests/qml/KeyboardPanel.qml', root / 'Ui/KeyboardPanel.qml')
    (root / 'plugin').mkdir()
    for pattern in ('*.qml', '*.js'):
        for path in project.glob(pattern):
            shutil.copy2(path, root / 'plugin' / path.name)
    for name in ('home', 'config', 'cache', 'runtime'):
        (root / name).mkdir(mode=0o700)
    theme = root / 'home/.local/state/omarchy/current/theme'
    theme.parent.mkdir(parents=True)
    shutil.copytree(Path.home() / '.local/state/omarchy/current/theme', theme)
    source = '''import QtQuick
import Quickshell
import qs.Commons
import "plugin" as Plugin
ShellRoot {
    id: capture
    property var fixture: FIXTURE
    property int step: 0
    property var names: ["overview", "details", "picker", "alert", "filters", "readonly", "disabled"]
    FloatingWindow {
        visible: true
        implicitWidth: Style.space(432)
        implicitHeight: Style.space(652)
        color: Color.popups.background
        Rectangle {
            id: card
            anchors.fill: parent
            color: Color.popups.background
            border.color: Qt.alpha(Color.accent, 0.25)
            Item { id: anchor }
            Plugin.Panel { id: panel; x: Style.space(16); y: Style.space(16); anchorItem: anchor; fixtureData: capture.fixture }
        }
    }
    Component.onCompleted: {
        var disabledSystem = JSON.parse(JSON.stringify(fixture.applications[2]))
        disabledSystem.id = "legacy"
        disabledSystem.name = "Legacy service"
        disabledSystem.search = "legacy service systemd"
        disabledSystem.enabled = false
        disabledSystem.status = "Disabled"
        disabledSystem.canRemove = true
        disabledSystem.sources[0].id = "systemd:legacy.service"
        disabledSystem.sources[0].enabled = false
        disabledSystem.sources[0].readOnly = "This service is controlled by another startup mechanism."
        fixture.applications.push(disabledSystem)
        fixture.counts.system = 2
        fixture.applications[0].icon = "application-x-executable"
        fixture.applications[1].icon = "preferences-desktop-remote-desktop"
        fixture.catalog = [
            {id:"browser.desktop", name:"Web Browser", command:"browser", icon:"web-browser", exists:false, revision:"fixture"},
            {id:"files.desktop", name:"Files", command:"files", icon:"system-file-manager", exists:false, revision:"fixture"},
            {id:"vicinae.desktop", identity:"vicinae", name:"Vicinae", command:"vicinae", icon:"application-x-executable", exists:true, revision:"fixture"}
        ]
        panel.refresh()
    }
    Timer {
        interval: 600; running: true; repeat: true
        onTriggered: {
            card.grabToImage(function(result) {
                if (!result.saveToFile("OUTPUT/" + capture.names[capture.step] + ".png")) throw new Error("Capture failed")
                capture.step++
                panel.expandedId = ""
                panel.adding = false
                panel.error = ""
                if (capture.step === 1) panel.expandedId = "vicinae"
                if (capture.step === 2) panel.enterPicker()
                if (capture.step === 3) panel.error = "The startup settings changed while you were editing. Refresh to load the latest settings, then try again."
                if (capture.step === 4) panel.filtersOpen = true
                if (capture.step === 5) { panel.filtersOpen = false; panel.statusFilter = "readonly" }
                if (capture.step === 6) {
                    var data = JSON.parse(JSON.stringify(capture.fixture))
                    data.applications[1].enabled = false
                    data.applications[1].status = "Disabled"
                    data.applications[1].canRemove = true
                    data.applications[1].sources[0].enabled = false
                    panel.fixtureData = data
                    panel.refresh()
                    panel.statusFilter = "all"
                    panel.expandedId = "synergy"
                }
                if (capture.step === capture.names.length) Qt.quit()
            })
        }
    }
}
'''.replace('FIXTURE', fixture).replace('OUTPUT', str(output))
    (root / 'shell.qml').write_text(source)
    env = {**os.environ, 'HOME': str(root / 'home'), 'XDG_CONFIG_HOME': str(root / 'config'),
           'XDG_CACHE_HOME': str(root / 'cache'), 'XDG_RUNTIME_DIR': str(root / 'runtime'),
           'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
           'QT_QPA_PLATFORMTHEME': '', 'QT_QUICK_CONTROLS_STYLE': 'Basic', 'DISPLAY': '', 'WAYLAND_DISPLAY': '',
           'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/nonexistent-omastart-capture-bus',
           'HYPRLAND_INSTANCE_SIGNATURE': 'omastart-capture-no-compositor'}
    result = subprocess.run(['quickshell', '--no-color', '-p', str(root)], env=env, capture_output=True, text=True, timeout=15)
    print(result.stdout + result.stderr)
    if result.returncode or any('plugin/' in line and ('WARN' in line or 'ERROR' in line) for line in (result.stdout + result.stderr).splitlines()):
        raise SystemExit(1)
print(output)

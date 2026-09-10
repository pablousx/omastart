#!/usr/bin/env python3
"""Load the actual panel in a separate offscreen Quickshell with fixture data."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

project = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix="omastart-ui-test-") as directory:
    root = Path(directory)
    (root / "Commons").symlink_to(Path("/usr/share/omarchy/shell/Commons"), target_is_directory=True)
    shutil.copytree(Path("/usr/share/omarchy/shell/Ui"), root / "Ui")
    shutil.copy2(project / "tests/qml/KeyboardPanel.qml", root / "Ui/KeyboardPanel.qml")
    plugin = root / "plugin"
    plugin.mkdir()
    for pattern in ("*.qml", "*.js"):
        for path in project.glob(pattern):
            shutil.copy2(path, plugin / path.name)
    # Deliberately do not copy the backend into this harness.
    shutil.copy2(project / "tests/qml/shell.qml", root / "shell.qml")
    for name in ("home", "config", "cache", "runtime"):
        (root / name).mkdir(mode=0o700)
    env = {**os.environ, "HOME": str(root / "home"), "XDG_CONFIG_HOME": str(root / "config"),
           "XDG_CACHE_HOME": str(root / "cache"), "XDG_RUNTIME_DIR": str(root / "runtime"),
           "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
           "QT_QPA_PLATFORMTHEME": "", "QT_QUICK_CONTROLS_STYLE": "Basic", "DISPLAY": "", "WAYLAND_DISPLAY": "",
           "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent-omastart-test-bus",
           "HYPRLAND_INSTANCE_SIGNATURE": "omastart-test-no-compositor"}
    result = subprocess.run(["quickshell", "--no-color", "-p", str(root)], env=env,
                            capture_output=True, text=True, timeout=20)
    output = result.stdout + result.stderr
    print(output, end="")
    failed = "OMASTART_QML_PASS" not in output or "OMASTART_QML_FAIL" in output
    # Omarchy's theme readers can warn about absent fixture theme files. Plugin
    # binding/type errors are never accepted.
    failed = failed or any("plugin/" in line and ("WARN" in line or "ERROR" in line) for line in output.splitlines())
    raise SystemExit(1 if failed else 0)

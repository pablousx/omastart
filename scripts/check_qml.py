#!/usr/bin/env python3
"""Create temporary import aliases for Omarchy's qs.* modules and run qmllint.

The real shell resolves qs.* from its root. These temporary symlinks are
analysis artifacts only; no symlinks are shipped inside the plugin.
"""
from pathlib import Path
import json
import re
import subprocess
import tempfile

project = Path(__file__).resolve().parent.parent
shell = Path("/usr/share/omarchy/shell")
with tempfile.TemporaryDirectory(prefix="omastart-qml-") as folder:
    root = Path(folder)
    (root / "qs").mkdir()
    for module in ("Commons", "Ui"):
        (root / "qs" / module).symlink_to(shell / module, target_is_directory=True)
    result = subprocess.run(["/usr/lib/qt6/bin/qmllint", "--ignore-settings", "--json", "-", "-I", str(root),
                             *map(str, sorted(project.glob("*.qml")))], capture_output=True, text=True)
    report = json.loads(result.stdout)
    failures = []
    deferred = 0
    for file in report["files"]:
        lines = Path(file["filename"]).read_text().splitlines()
        for warning in file["warnings"]:
            if warning["type"] == "info":
                continue
            line = lines[warning["line"] - 1] if warning["line"] else ""
            # Exact dynamic host boundaries whose published types are QObject
            # or QQuickItem. Their concrete members are exercised in live UI.
            member = re.search(r'Member "([^"]+)"', warning["message"])
            name = member[1] if member else ""
            dynamic = warning["id"] == "missing-property" and any(
                expression in line for expression in (
                    *(["Style.font." + name] if name in {"family", "body", "caption", "subtitle"} else []),
                    *(["Color.popups.text"] if name == "text" else []),
                    *(["panelLoader.item." + name] if name in {"opened", "popoutSwitchClosing", "open", "close", "closeForPopoutSwitch"} else []),
                    *(["root.bar.moduleWidgets"] if name == "moduleWidgets" else []),
                    *(["bar.barForeground"] if name == "barForeground" else []),
                    *(["QsWindow.window.screen"] if name == "screen" else []),
                    *(["listView.currentItem.entry"] if name == "entry" else []),
                    *(["currentItem.activate"] if name == "activate" else [])))
            enum_gap = warning["id"] == "signal-handler-parameters" and "QProcess::ExitStatus" in warning["message"]
            if dynamic or enum_gap:
                deferred += 1
            else:
                failures.append(f"{file['filename']}:{warning['line']}: {warning['message']}")
    if failures:
        print("\n".join(failures))
        raise SystemExit(1)
    print(f"QML checks passed ({len(report['files'])} files). {deferred} dynamic Omarchy/Quickshell type diagnostics require runtime checks.")

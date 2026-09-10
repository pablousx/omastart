#!/usr/bin/env python3
"""Install a validated local snapshot; never run plugin install hooks."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

project = Path(__file__).resolve().parent.parent
manifest = json.loads((project / "manifest.json").read_text())
plugin_id = manifest["id"]
config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "omarchy"
destination = config / "plugins" / plugin_id
ipc_env = {**os.environ, "OMARCHY_SHELL_IPC_TIMEOUT": "10s"}
subprocess.run(["omarchy", "plugin", "validate", str(project)], check=True)
config.mkdir(parents=True, exist_ok=True)
backup = config / "omastart-install-backups" / str(time.time_ns())
backup.mkdir(parents=True, mode=0o700)
if (config / "shell.json").exists():
    shutil.copy2(config / "shell.json", backup / "shell.json")
    previous_config = json.loads((config / "shell.json").read_text())
else:
    previous_config = {}
was_enabled = any(entry.get("id") == plugin_id
                  for entries in previous_config.get("bar", {}).get("layout", {}).values()
                  for entry in entries)
placement = ["--section", "left"]
old_entry = {}
for section, entries in previous_config.get("bar", {}).get("layout", {}).items():
    for index, entry in enumerate(entries):
        if entry.get("id") == plugin_id:
            placement = ["--section", section, "--index", str(index)]
            old_entry = entry
disabled_for_update = False
stage = Path(tempfile.mkdtemp(prefix=".omastart-stage-", dir=config))
try:
    shutil.copytree(project, stage, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", ".agents", ".codex", ".verification", "__pycache__", "*.pyc"))
    # Omarchy reloads plugin instances, but Qt can retain compiled components
    # at unchanged URLs. New code receives new URLs without restarting the shell.
    runtime_files = sorted([*project.glob("*.qml"), *project.glob("*.js"), *project.glob("backend/*.py")])
    content_hash = hashlib.sha256()
    for path in runtime_files:
        content_hash.update(str(path.relative_to(project)).encode())
        content_hash.update(path.read_bytes())
    runtime = stage / "runtime" / content_hash.hexdigest()[:16]
    for path in runtime_files:
        target = runtime / path.relative_to(project)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    installed_manifest = {**manifest, "entryPoints": {"barWidget": str((runtime / "BarWidget.qml").relative_to(stage))}}
    (stage / "manifest.json").write_text(json.dumps(installed_manifest, indent=2) + "\n")
    subprocess.run(["omarchy", "plugin", "validate", str(stage)], check=True)
    if was_enabled:
        old_manifest_path = destination / "manifest.json"
        old_manifest = json.loads(old_manifest_path.read_text()) if old_manifest_path.exists() else {}
        if old_manifest.get("entryPoints") != installed_manifest["entryPoints"]:
            # Unregister the old URL before replacement. A live asynchronous
            # component registration can otherwise remain stranded in the host.
            subprocess.run(["omarchy", "plugin", "disable", plugin_id], check=True, env=ipc_env)
            disabled_for_update = True
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise RuntimeError("Refusing to replace a symlinked plugin directory")
    if destination.exists():
        os.replace(destination, backup / plugin_id)
    os.replace(stage, destination)
    subprocess.run(["omarchy-shell", "shell", "rescanPlugins"], check=True, env=ipc_env)
    # Rescanning is asynchronous: its IPC reply precedes catalog discovery.
    for attempt in range(40):
        discovered = subprocess.run(["omarchy", "plugin", "list", "--json"], capture_output=True, text=True, env=ipc_env)
        if discovered.returncode == 0 and any(p.get("id") == plugin_id for p in json.loads(discovered.stdout)):
            break
        time.sleep(0.25)
    else:
        raise RuntimeError("Omarchy did not discover the installed plugin within 10 seconds")
    if not was_enabled or disabled_for_update:
        for attempt in range(3):
            enabled = subprocess.run(["omarchy", "plugin", "enable", plugin_id, *placement],
                                     capture_output=True, text=True, env=ipc_env)
            # A busy shell can persist the enablement but miss the IPC reply
            # deadline. Check the result before treating it as a failed install.
            current = json.loads((config / "shell.json").read_text())
            if any(entry.get("id") == plugin_id for entries in current.get("bar", {}).get("layout", {}).values() for entry in entries):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError(enabled.stderr.strip() or "Omarchy could not enable the widget")
        for key, value in old_entry.items():
            if key != "id":
                subprocess.run(["omarchy", "bar", "set", plugin_id, key, json.dumps(value), "--json"], check=True, env=ipc_env)
    for attempt in range(40):
        mounted = subprocess.run(["omarchy-shell", plugin_id, "inspect"], capture_output=True, text=True, env=ipc_env)
        if mounted.returncode == 0 and mounted.stdout.strip().startswith("{"):
            break
        time.sleep(0.25)
    else:
        raise RuntimeError("Plugin files are installed, but the shell has not mounted its widget; installation backup: " + str(backup))
    print(f"Installed {plugin_id} at {destination}\nInstallation backup: {backup}")
finally:
    if stage.exists():
        shutil.rmtree(stage)

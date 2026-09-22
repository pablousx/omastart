#!/usr/bin/python3
"""Install a validated local snapshot; never run plugin install hooks."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time
import uuid

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
from backend.common import Roots, Store, bounded_process, closed_environment


OMARCHY = "/usr/bin/omarchy"
OMARCHY_SHELL = "/usr/bin/omarchy-shell"
OMARCHY_PATH = "/usr/share/omarchy"


def command(argv, environment, *, check=True, timeout=15, pass_fds=()):
    result = bounded_process(argv, timeout=timeout, env=environment, pass_fds=pass_fds)
    if check and result.returncode:
        raise RuntimeError((result.stderr.strip() or result.stdout.strip() or
                            f"{Path(argv[0]).name} exited with {result.returncode}")[:1500])
    return result


def member_ids(value):
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def configured_as_generic_plugin(config, plugin_id):
    return any(entry.get("id") == plugin_id for entry in config.get("plugins", []))


def previous_placement(config, plugin_id):
    """Return enabled/placed state and the best placement to restore.

    Pocket keeps its members in the ordinary bar layout and mirrors their ids
    in its own ``members`` setting.  A failed or interrupted reinstall can
    leave only that mirror.  Treat it as placement evidence so the next local
    install repairs the missing layout entry immediately before the pocket.
    """
    layout = config.get("bar", {}).get("layout", {})
    placement = ["--section", "left"]
    old_entry = {}
    for section, entries in layout.items():
        for index, entry in enumerate(entries):
            if entry.get("id") == plugin_id:
                return True, True, ["--section", section, "--index", str(index)], entry

    for section, entries in layout.items():
        for index, entry in enumerate(entries):
            if plugin_id in member_ids(entry.get("members")):
                placement = ["--section", section, "--index", str(index)]
                return False, False, placement, old_entry
    return False, False, placement, old_entry


def main():
    manifest = json.loads((PROJECT / "manifest.json").read_text())
    plugin_id = manifest["id"]
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    config = config_home / "omarchy"
    destination = config / "plugins" / plugin_id
    environment = {**closed_environment(), "OMARCHY_PATH": OMARCHY_PATH,
                   "PATH": "/usr/bin", "OMARCHY_SHELL_IPC_TIMEOUT": "10s"}
    roots = Roots(Path.home(), config_home, config_home / ".omastart-installer-state",
                  (), (), (), Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"))
    secure = Store(roots)

    command([OMARCHY, "plugin", "validate", str(PROJECT)], environment)
    backup = config / "omastart-install-backups" / str(time.time_ns())
    with secure._target(backup / ".anchor", create=True) as (backup_fd, _), \
         secure._target(destination, create=True) as (plugins_fd, destination_name):
        backup_path = Path(f"/proc/self/fd/{backup_fd}")
        shell_path = config / "shell.json"
        if shell_path.exists():
            shutil.copy2(shell_path, backup_path / "shell.json")
            previous_config = json.loads(shell_path.read_text())
        else:
            previous_config = {}
        was_enabled, _, placement, old_entry = previous_placement(
            previous_config, plugin_id)
        stale_generic_entry = configured_as_generic_plugin(previous_config, plugin_id)

        stage_name = ".omastart-stage-" + uuid.uuid4().hex
        os.mkdir(stage_name, 0o700, dir_fd=plugins_fd)
        stage = Path(f"/proc/self/fd/{plugins_fd}") / stage_name
        disabled_for_update = False
        try:
            shutil.copytree(PROJECT, stage, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(".git", ".agents", ".codex", ".verification",
                                                         "__pycache__", "*.pyc"))
            runtime_files = sorted([*PROJECT.glob("*.qml"), *PROJECT.glob("*.js"),
                                    *PROJECT.glob("backend/*.py")])
            content_hash = hashlib.sha256()
            for path in runtime_files:
                content_hash.update(str(path.relative_to(PROJECT)).encode())
                content_hash.update(path.read_bytes())
            runtime = stage / "runtime" / content_hash.hexdigest()[:16]
            for path in runtime_files:
                target = runtime / path.relative_to(PROJECT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
            installed_manifest = {**manifest, "entryPoints": {
                "barWidget": str((runtime / "BarWidget.qml").relative_to(stage))}}
            (stage / "manifest.json").write_text(json.dumps(installed_manifest, indent=2) + "\n")
            command([OMARCHY, "plugin", "validate", str(stage)], environment,
                    pass_fds=(plugins_fd,))

            try:
                destination_stat = os.stat(destination_name, dir_fd=plugins_fd, follow_symlinks=False)
            except FileNotFoundError:
                destination_stat = None
            if destination_stat is not None and not stat.S_ISDIR(destination_stat.st_mode):
                raise RuntimeError("Refusing to replace a non-directory plugin destination")
            if was_enabled and destination_stat is not None:
                old_manifest_path = Path(f"/proc/self/fd/{plugins_fd}") / destination_name / "manifest.json"
                old_manifest = json.loads(old_manifest_path.read_text()) if old_manifest_path.exists() else {}
                if old_manifest.get("entryPoints") != installed_manifest["entryPoints"]:
                    command([OMARCHY, "plugin", "disable", plugin_id], environment)
                    disabled_for_update = True
            if destination_stat is not None:
                os.rename(destination_name, plugin_id, src_dir_fd=plugins_fd, dst_dir_fd=backup_fd)
            os.rename(stage_name, destination_name, src_dir_fd=plugins_fd, dst_dir_fd=plugins_fd)
            os.fsync(plugins_fd)

            command([OMARCHY_SHELL, "shell", "rescanPlugins"], environment)
            for _ in range(40):
                discovered = command([OMARCHY, "plugin", "list", "--json"], environment, check=False)
                if discovered.returncode == 0 and any(
                        p.get("id") == plugin_id for p in json.loads(discovered.stdout)):
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError("Omarchy did not discover the installed plugin within 10 seconds")
            if stale_generic_entry and not was_enabled:
                command([OMARCHY, "plugin", "disable", plugin_id], environment)
            needs_enable = not was_enabled or disabled_for_update
            if needs_enable:
                for _ in range(3):
                    enabled = command([OMARCHY, "plugin", "enable", plugin_id, *placement],
                                      environment, check=False)
                    current = json.loads(shell_path.read_text())
                    if any(entry.get("id") == plugin_id
                           for entries in current.get("bar", {}).get("layout", {}).values()
                           for entry in entries):
                        break
                    time.sleep(0.5)
                else:
                    raise RuntimeError(enabled.stderr.strip() or "Omarchy could not enable the widget")
                for key, value in old_entry.items():
                    if key != "id":
                        command([OMARCHY, "bar", "set", plugin_id, key, json.dumps(value), "--json"],
                                environment)
            for _ in range(40):
                mounted = command([OMARCHY_SHELL, plugin_id, "inspect"], environment, check=False)
                if mounted.returncode == 0 and mounted.stdout.strip().startswith("{"):
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError("Plugin files are installed, but the shell has not mounted its widget; "
                                   "installation backup: " + str(backup))
            print(f"Installed {plugin_id} at {destination}\nInstallation backup: {backup}")
        finally:
            try:
                os.stat(stage_name, dir_fd=plugins_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                shutil.rmtree(stage)


if __name__ == "__main__":
    main()

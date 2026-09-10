"""Lossless desktop entry edits, application identity and XDG precedence."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shlex
import shutil

from .common import Error, digest, file_value, read_text, snapshot, source


ALIASES = {"synergy-service": "synergy", "synergyc": "synergy", "synergys": "synergy"}
FRIENDLY = {
    "hyprsunset": ("hyprsunset", "weather-clear-night"),
    "synergy": ("Synergy", "synergy"),
    "vicinae": ("Vicinae", "vicinae"),
    "nextcloud": ("Nextcloud", "Nextcloud"),
    "voxtype": ("Voxtype", "audio-input-microphone"),
    "rclone": ("Rclone", "folder-remote"),
    "relai": ("Relai", "preferences-system"),
}
INFRASTRUCTURE = re.compile(
    r"^(?:systemd|dbus|xdg[-.]|wayland-wm|wayland-session|pipewire|wireplumber|"
    r"gnome-keyring|gcr-|gpg-agent|ssh-agent|at-spi|org\.a11y|gvfs|dconf|"
    r"p11-kit|polkit|keyboxd|dirmngr|localsearch|tinysparql|snap-userd|"
    r"snapd\.session|flatpak-(?:portal|session|oci)|user-dirs|limine-|"
    r"org\.gnome\.SettingsDaemon|omarchy-(?:crash|recover|migrate|sleep|brightness|fcitx)|"
    r"hyprmoncfgd|bt-agent|org\.fcitx|fcitx|udiskie|wine-window-cleaner)", re.I)


def identity(command):
    """Parse for matching only; never run the resulting tokens."""
    try:
        words = shlex.split(command)
    except ValueError:
        return ""
    if words and Path(words[0]).name == "env":
        words.pop(0)
        while words and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]) or words[0] == "--"):
            words.pop(0)
    if words and Path(words[0]).name == "uwsm-app":
        words.pop(0)
        if words and words[0] == "--":
            words.pop(0)
    if not words or words[0].startswith("-"):
        return ""
    executable = Path(words[0]).name
    if executable in ("sh", "bash", "zsh", "fish", "python", "python3", "node", "ruby", "perl"):
        # Sharing an interpreter is not evidence of sharing an application.
        return ""
    if executable in ("flatpak", "snap") and len(words) > 2 and words[1] == "run":
        candidates = [w for w in words[2:] if not w.startswith("-")]
        return f"{executable}:{candidates[0]}" if candidates else ""
    return ALIASES.get(executable.lower(), executable.lower())


def unescape(value):
    escapes = {"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}
    return re.sub(r"\\([sntr\\])", lambda m: escapes[m[1]], value)


class Desktop:
    def __init__(self, text, language="en_US"):
        self.text = text
        self.fields = {}
        self.problem = ""
        section = ""
        seen_main = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section = stripped[1:-1]
                if section == "Desktop Entry":
                    if seen_main:
                        self.problem = "Duplicate Desktop Entry sections are read-only."
                    seen_main = True
            elif section == "Desktop Entry" and stripped and not stripped.startswith("#"):
                if "=" not in line:
                    self.problem = "Malformed desktop entry lines are read-only."
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if key in self.fields:
                    self.problem = f"Duplicate desktop entry key: {key}."
                self.fields[key] = value.strip()
        if not seen_main:
            self.problem = "Missing Desktop Entry section."
        for key in ("Hidden", "NoDisplay", "Terminal", "DBusActivatable", "X-systemd-skip"):
            if key in self.fields and self.fields[key] not in ("true", "false"):
                self.problem = f"Invalid boolean value for {key}."
        locale = language.split(".")[0]
        lang = locale.split("_")[0].split("@")[0]
        base = locale.split("@")[0]
        modifier = locale.split("@", 1)[1] if "@" in locale else ""
        keys = [f"Name[{locale}]", f"Name[{base}]"]
        if modifier:
            keys.append(f"Name[{lang}@{modifier}]")
        keys += [f"Name[{lang}]", "Name"]
        self.name = next((unescape(self.fields[k]) for k in keys if self.fields.get(k)), "")

    def get(self, key, default=""):
        return self.fields.get(key, default)

    def yes(self, key):
        return self.get(key) == "true"

    def with_keys(self, changes):
        if self.problem:
            raise Error(self.problem)
        lines = self.text.splitlines(keepends=True)
        ending = "\r\n" if "\r\n" in self.text else "\n"
        section = ""
        remaining = dict(changes)
        output = []

        def insert():
            if remaining:
                if output and not output[-1].endswith(("\n", "\r")):
                    output[-1] += ending
                output.extend(f"{key}={value}{ending}" for key, value in remaining.items())
                remaining.clear()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                if section == "Desktop Entry":
                    insert()
                section = stripped[1:-1]
            if section == "Desktop Entry" and "=" in line and not stripped.startswith("#"):
                key = line.split("=", 1)[0].strip()
                if key in remaining:
                    suffix = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
                    output.append(f"{key}={remaining.pop(key)}{suffix}")
                    continue
            output.append(line)
        if section == "Desktop Entry":
            insert()
        return "".join(output)

    def eligibility(self, roots):
        if self.get("Type") != "Application":
            return False, "Only Type=Application entries can be started."
        desktops = set(roots.desktop.split(":"))
        only = set(self.get("OnlyShowIn").split(";")) - {""}
        exclude = set(self.get("NotShowIn").split(";")) - {""}
        if only and exclude:
            return None, "Both OnlyShowIn and NotShowIn are set; eligibility is ambiguous."
        if only and not only.intersection(desktops):
            return False, "This entry is restricted to another desktop: " + ", ".join(sorted(only))
        if exclude.intersection(desktops):
            return False, "This entry excludes the current desktop."
        attempt = unescape(self.get("TryExec"))
        if attempt and not shutil.which(attempt):
            return False, f"Required executable is unavailable: {attempt}"
        if self.yes("X-systemd-skip"):
            return False, "X-systemd-skip excludes this entry from systemd autostart."
        if self.get("X-GNOME-Autostart-Phase"):
            return False, "The systemd XDG generator does not support GNOME startup phases."
        for field in ("AutostartCondition", "X-KDE-autostart-condition"):
            if self.get(field):
                return None, f"Conditional startup ({field}); omastart does not evaluate it."
        if not self.get("Exec"):
            return False, "The systemd XDG generator requires an Exec command."
        return True, ""


def application_catalog(roots):
    entries = {}
    for directory in roots.data_dirs:
        base = directory / "applications"
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.desktop")):
            key = str(path.relative_to(base)).replace("/", "-")
            if key in entries:
                continue
            try:
                desktop = Desktop(read_text(path), roots.language)
            except Error:
                continue
            eligible, reason = desktop.eligibility(roots)
            entries[key] = {"id": key, "name": desktop.name or path.stem,
                            "icon": unescape(desktop.get("Icon")) or "application-x-executable",
                            "command": desktop.get("Exec"), "path": str(path),
                            "identity": identity(desktop.get("Exec")),
                            "available": bool(not desktop.problem and eligible is True
                                              and not desktop.yes("Hidden") and not desktop.yes("NoDisplay")),
                            "revision": digest(desktop.text.encode()), "_desktop": desktop}
    return entries


def enrich(item, catalog):
    app_id = identity(item["command"])
    item["appKey"] = app_id or item["id"]
    matching = [app for app in catalog.values() if app_id and app["identity"] == app_id and app["available"]]
    if matching:
        app = matching[0]
        if item["kind"] != "xdg":
            item["name"] = app["name"]
        item["icon"] = app["icon"]
    if app_id in FRIENDLY:
        item["name"], fallback = FRIENDLY[app_id]
        if item["icon"] == "application-x-executable":
            item["icon"] = fallback
    basename = Path(item["path"]).name
    protected = bool(INFRASTRUCTURE.match(app_id) or INFRASTRUCTURE.match(basename))
    if protected:
        item["system"] = True
        item["readOnly"] = "Protected session infrastructure. Manage it with its dedicated settings."
    return bool(matching or app_id in FRIENDLY)


def discover(roots, store, catalog, warnings):
    paths = {}
    for directory in (roots.config,) + roots.config_dirs:
        folder = directory / "autostart"
        try:
            for path in sorted(folder.glob("*.desktop")):
                paths.setdefault(path.name, []).append(path)
        except OSError as exc:
            warnings.append(f"Cannot scan {folder}: {exc}")
    items = []
    for key, alternatives in paths.items():
        path = alternatives[0]
        try:
            desktop = Desktop(read_text(path), roots.language)
            # Minimal Hidden overrides inherit display metadata, not eligibility.
            metadata = desktop
            if not desktop.name:
                for lower in alternatives[1:]:
                    try:
                        candidate = Desktop(read_text(lower), roots.language)
                        if candidate.name:
                            metadata = candidate
                            break
                    except Error:
                        pass
            item = source("xdg", key, metadata.name or path.stem, metadata.get("Exec"), path,
                          not desktop.yes("Hidden"), icon=unescape(metadata.get("Icon")) or "application-x-executable")
            eligible, reason = (metadata if desktop.yes("Hidden") else desktop).eligibility(roots)
            item.update(eligible=eligible, eligibility=reason, readOnly=desktop.problem,
                        _desktop=desktop, _alternatives=alternatives)
            destination = roots.autostart / key
            item["readOnly"] = item["readOnly"] or store.writable(destination)
            if eligible is not True:
                item["readOnly"] = item["readOnly"] or reason
            if desktop.yes("Hidden") and not desktop.get("Exec"):
                item["readOnly"] = item["readOnly"] or "Minimal external override; restore its original desktop entry to enable it."
            # Include all precedence layers and destination, not just the effective file.
            item["revision"] = digest([[(str(p), snapshot(p), digest(read_text(p).encode())) for p in alternatives], snapshot(destination)])
            enrich(item, catalog)
            if metadata.yes("NoDisplay") and not identity(item["command"]) in FRIENDLY:
                item["system"] = True
                item["readOnly"] = item["readOnly"] or "Background desktop component; protected from casual changes."
            items.append(item)
        except (Error, OSError) as exc:
            items.append(source("xdg", key, path.stem, "", path, None,
                                readOnly=str(exc), eligible=None))
    return items


def toggle(item, enabled, roots, store, runner):
    destination = roots.autostart / item["id"].split(":", 1)[1]
    before = snapshot(destination)
    previous = store.previous(item["id"])
    if previous and len(previous["entries"]) == 1:
        entry = previous["entries"][0]
        old = entry["before"]
        # Restore precisely when the requested state matches the prior configuration.
        if old["type"] == "absent":
            old_enabled = len(item["_alternatives"]) > 1
        elif old["type"] == "file":
            import base64
            old_enabled = not Desktop(base64.b64decode(old["data"]).decode()).yes("Hidden")
        else:
            old_enabled = None
        if enabled == old_enabled and str(destination) == entry["path"] and before == entry["after"]:
            return store.transact(item["id"], store.undo_changes(previous),
                                  after=lambda: runner(["systemctl", "--user", "daemon-reload"]))
    desktop = item["_desktop"]
    if enabled and not desktop.get("Exec"):
        raise Error("This minimal override cannot be enabled safely; restore its original application entry.")
    text = desktop.with_keys({"Hidden": "false" if enabled else "true"})
    mode = before.get("mode", 0o644)
    return store.transact(item["id"], [(destination, before, file_value(text.encode(), mode))],
                          after=lambda: runner(["systemctl", "--user", "daemon-reload"]))

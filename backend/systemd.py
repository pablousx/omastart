"""Persistent user-service startup state, independent of process activity."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex

from .common import Error, digest, read_text, snapshot, source
from .desktop import enrich


PROPERTIES = ("Id", "Names", "FragmentPath", "SourcePath", "DropInPaths", "UnitFileState",
              "ActiveState", "WantedBy", "RequiredBy", "PartOf", "BindsTo", "TriggeredBy")
STARTUP_TARGETS = {"graphical-session.target", "graphical-session-pre.target", "default.target"}
UNIT_NAME = re.compile(r"^[A-Za-z0-9_.:@\\-]+\.service$")
TARGET_NAME = re.compile(r"^[A-Za-z0-9_.@\\-]+\.target$")


def fields(text):
    result = {}
    section = ""
    # Unit line continuations insert a space. No shell expansion takes place.
    text = re.sub(r"\\\r?\n\s*", " ", text)
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif "=" in line:
            key, value = line.split("=", 1)
            full = section + "." + key.strip()
            if value.strip():
                result.setdefault(full, []).append(value.strip())
            else:
                result[full] = []
    return result


def words(values):
    return " ".join(values).split()


def links_for(roots, name):
    result = []
    for directory in roots.unit_dirs:
        if not directory.is_dir():
            continue
        for suffix in ("wants", "requires"):
            for path in sorted(directory.glob(f"*.{suffix}/{name}")):
                if path.is_symlink():
                    result.append(path)
    return result


def native_path(roots, name):
    for directory in roots.unit_dirs:
        path = directory / name
        if path.exists() and (not path.is_symlink() or os.readlink(path) != "/dev/null"):
            return path
    return None


def read_metadata(runner):
    listing = json.loads(runner(["systemctl", "--user", "list-unit-files", "--type=service",
                                 "--no-pager", "--output=json"]))
    names = [row["unit_file"] for row in listing
             if isinstance(row.get("unit_file"), str) and UNIT_NAME.fullmatch(row["unit_file"])
             and not row["unit_file"].endswith("@.service")]
    if not names:
        return {}
    output = runner(["systemctl", "--user", "show", "--no-pager",
                     "--property=" + ",".join(PROPERTIES), "--", *names])
    result = {}
    for block in output.strip().split("\n\n"):
        data = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        if data.get("Id"):
            result[data["Id"]] = data
            for alias in data.get("Names", "").split():
                result[alias] = data
    return result


def discover(roots, store, catalog, warnings, runner):
    available = True
    try:
        metadata = read_metadata(runner)
    except (Error, ValueError, KeyError) as exc:
        warnings.append("User systemd is unavailable. Service state is read-only until it reconnects. " + str(exc))
        metadata = {}
        available = False
    names = set(metadata)
    for directory in roots.unit_dirs:
        if directory.is_dir():
            names.update(p.name for p in directory.glob("*.service"))
    items = []
    generated = []
    for name in sorted(names):
        if not UNIT_NAME.fullmatch(name):
            continue
        meta = metadata.get(name, {})
        if meta.get("Id", name) != name:
            continue
        fragment = Path(meta["FragmentPath"]) if meta.get("FragmentPath") else native_path(roots, name)
        masked = any((d / name).is_symlink() and os.readlink(d / name) == "/dev/null" for d in roots.unit_dirs)
        if fragment and (str(fragment) == "/dev/null" or fragment.is_symlink() and os.readlink(fragment) == "/dev/null"):
            fragment = native_path(roots, name)
        if fragment and (meta.get("UnitFileState") == "generated" or "generator" in str(fragment.parent)):
            origin = meta.get("SourcePath", "")
            if not origin:
                try:
                    origin = " ".join(fields(read_text(fragment)).get("Unit.SourcePath", []))
                except Error:
                    pass
            if origin.endswith(".desktop"):
                generated.append({"unit": name, "path": origin, "running": meta.get("ActiveState", "unknown"),
                                  "masked": masked})
                continue
        if not fragment:
            continue
        mask = roots.user_units / name
        if str(fragment) == "/dev/null" or fragment.is_symlink() and os.readlink(fragment) == "/dev/null":
            fragment = native_path(roots, name)
        if not fragment:
            item = source("systemd", name, name.removesuffix(".service"), "", mask, False,
                          readOnly="Masked service with no discoverable original unit.", system=True)
            items.append(item)
            continue
        try:
            original_text = read_text(fragment)
            unit = fields(original_text)
            dropins = shlex.split(meta.get("DropInPaths", ""))
            for dropin in dropins:
                updates = fields(read_text(Path(dropin)))
                # For safety, install metadata with drop-ins is not editable.
                unit.update(updates)
            configured_links = links_for(roots, name)
            targets = words(unit.get("Install.WantedBy", []))
            required_targets = words(unit.get("Install.RequiredBy", []))
            attached = [p.parent.name.rsplit(".", 1)[0] for p in configured_links]
            graph = words(unit.get("Unit.PartOf", []) + unit.get("Unit.BindsTo", []) + unit.get("Unit.Requires", []))
            relevant = bool(STARTUP_TARGETS.intersection(targets + required_targets + attached) or
                            any("graphical-session" in value for value in graph))
            if not relevant and not masked:
                continue
            executable = (unit.get("Service.ExecStart") or [""])[0]
            command = executable.lstrip("-+!:@")
            description = " ".join(unit.get("Unit.Description", [])) or name.removesuffix(".service")
            persistent_links = [p for p in configured_links if not p.is_relative_to(roots.runtime)]
            enabled = bool(not masked and any(p.parent.name.rsplit(".", 1)[0] in STARTUP_TARGETS
                                              for p in persistent_links))
            local_links = [p for p in persistent_links if p.is_relative_to(roots.user_units)]
            global_links = [p for p in persistent_links if not p.is_relative_to(roots.user_units)]
            item = source("systemd", name, description, command, fragment, enabled,
                          running=meta.get("ActiveState", "unknown"), globalEnabled=bool(global_links),
                          unit=name, masked=masked, _targets=targets, _links=local_links,
                          _global=global_links, _fragment=fragment, _metadata=meta)
            known = enrich(item, catalog)
            user_file = fragment.is_relative_to(roots.user_units)
            if not known and not user_file:
                item["system"] = True
                item["readOnly"] = item["readOnly"] or "Unclassified session component; protected from casual changes."
            if not available:
                item["readOnly"] = "User systemd is unavailable; refresh when the session bus is accessible."
            elif meta.get("UnitFileState") in ("alias", "static", "indirect", "transient", "generated", "enabled-runtime", "masked-runtime"):
                item["readOnly"] = item["readOnly"] or "This unit uses indirect, runtime, or generated activation."
            elif "@" in name or "%" in command or dropins:
                item["readOnly"] = item["readOnly"] or "Templates, specifiers and service drop-ins require dedicated configuration."
            elif unit.get("Install.Also") or unit.get("Install.Alias") or required_targets or meta.get("RequiredBy"):
                item["readOnly"] = item["readOnly"] or "This service has aliases, linked units, or required dependents."
            elif meta.get("TriggeredBy"):
                item["readOnly"] = item["readOnly"] or "A socket, timer, or other trigger controls this service."
            elif not targets or any(t not in STARTUP_TARGETS or not TARGET_NAME.fullmatch(t) for t in targets):
                item["readOnly"] = item["readOnly"] or "This service does not have simple graphical/user login enablement."
            elif any(p.parent.name.rsplit(".", 1)[0] not in STARTUP_TARGETS or p.parent.name.endswith(".requires")
                     for p in persistent_links):
                item["readOnly"] = item["readOnly"] or "Additional dependency targets control this service."
            if masked:
                previous = store.previous(item["id"])
                owned = previous and any(e["path"] == str(mask) and e["after"] == {"type": "link", "target": "/dev/null"}
                                         for e in previous["entries"])
                if not owned:
                    item["readOnly"] = item["readOnly"] or "Masked outside omastart; remove that mask with its original configuration tool."
            if global_links and snapshot(mask)["type"] not in ("absent", "link"):
                item["readOnly"] = item["readOnly"] or "A local unit file prevents a safe per-user mask."
            for destination in [mask] + [roots.user_units / (t + ".wants") / name for t in targets if TARGET_NAME.fullmatch(t)]:
                item["readOnly"] = item["readOnly"] or store.writable(destination, links=True)
            item["revision"] = digest({"file": snapshot(fragment), "contents": original_text, "mask": snapshot(mask),
                                       "links": [(str(p), snapshot(p)) for p in configured_links],
                                       "targets": targets, "state": meta.get("UnitFileState"),
                                       "dropins": [(p, snapshot(Path(p))) for p in dropins]})
            items.append(item)
        except (Error, OSError, ValueError) as exc:
            items.append(source("systemd", name, name.removesuffix(".service"), "", fragment, None,
                                readOnly=str(exc), eligible=None, system=True))
    return items, generated


def toggle_changes(item, enabled, roots, store):
    name = item["unit"]
    mask = roots.user_units / name
    changes = []
    previous = store.previous(item["id"])
    if enabled and item["masked"]:
        changes = store.undo_changes(previous)
    elif not enabled and item["_global"]:
        before = snapshot(mask)
        if before["type"] != "absent":
            raise Error("A local unit or mask already exists. It will not be overwritten.")
        changes = [(mask, before, {"type": "link", "target": "/dev/null"})]
    elif not enabled:
        changes = [(p, snapshot(p), {"type": "absent"}) for p in item["_links"]]
    else:
        # A disable made here restores the exact prior enablement links.
        if previous and all(e["after"]["type"] == "absent" and e["before"]["type"] == "link"
                            for e in previous["entries"]):
            changes = store.undo_changes(previous)
        else:
            for target in item["_targets"]:
                path = roots.user_units / (target + ".wants") / name
                before = snapshot(path)
                if before["type"] != "absent":
                    raise Error("An unexpected enablement entry already exists; refresh before changing it.")
                changes.append((path, before, {"type": "link", "target": str(item["_fragment"])}))
    return changes


def toggle(item, enabled, roots, store, runner):
    return store.transact(item["id"], toggle_changes(item, enabled, roots, store),
                          after=lambda: runner(["systemctl", "--user", "daemon-reload"]))

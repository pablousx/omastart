"""Application model and the only mutation entry point."""
from __future__ import annotations

import json
from pathlib import Path

from . import desktop, hyprland, removal, systemd
from .common import Error, Roots, Store, digest, file_value, read_text, run, snapshot


def public(value):
    if isinstance(value, dict):
        return {k: public(v) for k, v in value.items() if not k.startswith("_")}
    if isinstance(value, list):
        return [public(v) for v in value]
    return value


def group(items):
    grouped = {}
    for item in items:
        key = item.get("appKey", item["id"])
        grouped.setdefault(key, []).append(item)
    result = []
    for key, sources in grouped.items():
        sources.sort(key=lambda item: (not bool(item["enabled"]), ["hyprland", "xdg", "systemd"].index(item["kind"]), item["id"]))
        first = sources[0]
        enabled = any(s["enabled"] is True and s["eligible"] is not False for s in sources)
        uncertain = any(s["enabled"] is None or s["enabled"] and s["eligible"] is None for s in sources)
        status = "Conditional" if enabled and uncertain else "Enabled" if enabled else "Unknown" if uncertain else "Disabled"
        if not enabled and any(s["enabled"] and s["eligible"] is False for s in sources):
            status = "Not applicable"
        kinds = list(dict.fromkeys(s["kind"] for s in sources))
        active_kinds = list(dict.fromkeys(s["kind"] for s in sources if s["enabled"] and s["eligible"] is not False))
        # Existing session configuration is preferred; never create a new
        # method just to satisfy the application toggle.
        available = [s for s in sources if not s["readOnly"] and s["eligible"] is True
                     and type(s["enabled"]) is bool]
        preferred = min(available, key=lambda s: (["hyprland", "xdg", "systemd"].index(s["kind"]),
                                                 s.get("_method") != "launch_on_start", s["id"]), default=None)
        startup_enabled = any(s["enabled"] is True for s in sources)
        blocked = ""
        if any(s["enabled"] is None for s in sources):
            blocked = "A startup method has an unknown state. Review its details before changing this app."
        elif startup_enabled and any(s["enabled"] is True and s["readOnly"] for s in sources):
            blocked = "An enabled startup method is read-only. Review its details to turn this app off."
        elif not startup_enabled and not preferred:
            blocked = "No editable startup method applies to this session. Review the methods below."
        result.append(dict(id=key, name=first["name"], icon=first["icon"], enabled=enabled, status=status,
                           system=all(s["system"] for s in sources), sources=sources, kinds=kinds,
                           activeKinds=active_kinds,
                           startupEnabled=startup_enabled, toggleReadOnly=blocked,
                           preferredSource=preferred["id"] if preferred else "",
                           revision=digest(sorted((s["id"], s["revision"], s["enabled"], s["eligible"], s["readOnly"]) for s in sources)),
                           duplicate=sum(bool(s["enabled"] and s["eligible"] is not False) for s in sources) > 1,
                           search=" ".join([first["name"], key] + [str(s[field]) for s in sources for field in ("command", "path", "name", "kind")]).lower()))
    return sorted(result, key=lambda app: (app["system"], app["name"].casefold()))


class Engine:
    def __init__(self, roots=None, runner=run):
        self.roots = roots or Roots.live()
        self.runner = runner
        self.store = Store(self.roots)
        self.items = []
        self.catalog = {}
        self.all_applications = []

    def scan(self):
        warnings = []
        self.catalog = desktop.application_catalog(self.roots)
        items = desktop.discover(self.roots, self.store, self.catalog, warnings)
        items += hyprland.discover(self.roots, self.store, self.catalog, warnings)
        units, generated = systemd.discover(self.roots, self.store, self.catalog, warnings, self.runner)
        items += units
        for unit in generated:
            matching = next((item for item in items if item["kind"] == "xdg"
                             and Path(item["path"]) == Path(unit["path"])), None)
            if matching:
                matching.setdefault("generatedUnits", []).append(unit["unit"])
                matching["running"] = unit["running"]
                if unit.get("masked"):
                    matching["eligible"] = False
                    matching["eligibility"] = "The generated systemd unit is masked outside omastart."
                    matching["readOnly"] = matching["readOnly"] or "The generated systemd unit is masked externally; restore that mask with its original tool."
                matching["revision"] = digest([matching["revision"], unit.get("masked", False)])
            else:
                from .common import source
                items.append(source("systemd", unit["unit"], Path(unit["path"]).stem, "", unit["path"], None,
                                    running=unit["running"], eligible=None,
                                    readOnly="Generated XDG unit whose source is no longer present. It will be regenerated at login."))
        self.items = items
        for item in items:
            previous = self.store.previous(item["id"])
            item["canUndo"] = bool(previous and not previous.get("grouped") and not item["readOnly"] and
                                   all(snapshot(Path(e["path"])) == e["after"] for e in previous["entries"]))
        applications = group(items)
        for app in applications:
            previous = self.store.previous("application:" + app["id"])
            app["canUndo"] = bool(previous and all(snapshot(Path(e["path"])) == e["after"] for e in previous["entries"])
                                  and set(previous.get("sources", {})) <= {s["id"] for s in app["sources"]}
                                  and all(not s["readOnly"] for s in app["sources"] if s["id"] in previous.get("sources", {})))
        self.all_applications = applications
        applications, removed = removal.partition(applications, self.roots, self.store, warnings)
        visible_items = [s for app in applications for s in app["sources"]]
        existing = {s.get("appKey") for s in visible_items}
        xdg_ids = {s["id"].split(":", 1)[1] for s in visible_items if s["kind"] == "xdg"}
        choices = []
        for app in self.catalog.values():
            if app["available"]:
                choice = public(app)
                choice["exists"] = app["id"] in xdg_ids or bool(app["identity"] and app["identity"] in existing)
                choices.append(choice)
        recoveries = []
        for path, record in self.store.pending():
            recoverable = True
            for entry in record["entries"]:
                try:
                    destination = self.store.safe_path(Path(entry["path"]))
                    recoverable = recoverable and snapshot(destination) in (entry["before"], entry["after"])
                except (Error, OSError):
                    recoverable = False
            warnings.append("An interrupted startup change has a backup. " +
                            ("Restore it before making another change." if recoverable else "Newer external edits need manual review; they will not be overwritten."))
            recoveries.append({"id": path.name, "revision": digest(record), "recoverable": recoverable,
                               "path": str(path), "item": record["item"]})
        return {"ok": True, "version": 1, "applications": public(applications),
                "catalog": sorted(choices, key=lambda app: app["name"].casefold()), "warnings": warnings,
                "recoveries": recoveries, "removed": removed,
                "counts": {"applications": sum(not a["system"] for a in applications),
                           "enabled": sum(a["enabled"] and not a["system"] for a in applications),
                           "system": sum(a["system"] for a in applications)}}

    def request(self, request):
        if not isinstance(request, dict):
            raise Error("Expected a JSON request object.")
        action = request.get("action", "scan")
        if action == "scan":
            return self.scan()
        if action not in ("toggle", "toggleApplication", "add", "remove", "undoRemoval", "undo", "undoApplication", "recover"):
            raise Error("Unknown action.")
        if not isinstance(request.get("id"), str) or not isinstance(request.get("revision"), str):
            raise Error("A discovered identifier and revision are required.")
        with self.store.locked():
            inventory = self.scan()
            added_id = None
            application_undo_id = None
            pending = self.store.pending()
            if action == "recover":
                found = next(((p, r) for p, r in pending if p.name == request["id"]), None)
                if not found or digest(found[1]) != request["revision"]:
                    raise Error("The recovery record changed. Refresh and try again.")
                path, record = found
                callback = None
                if record["item"].startswith(("systemd:", "xdg:")):
                    callback = lambda: self.runner(["systemctl", "--user", "daemon-reload"])
                if record["item"].startswith("hyprland:"):
                    import base64
                    for entry in record["entries"]:
                        if entry["before"]["type"] == "file":
                            self.runner(["luac", "-p", "-"], input=base64.b64decode(entry["before"]["data"]).decode())
                if record["item"].startswith("application:"):
                    callback = self.restore_effects([(Path(e["path"]), e["after"], e["before"]) for e in record["entries"]])
                self.store.recover(path, record, after=callback)
            elif pending:
                raise Error("An interrupted change must be recovered or reviewed before another startup change.")
            elif action == "add":
                added_id = self.add(request, inventory)
            elif action == "undoRemoval":
                entry = next((entry for entry in inventory["removed"] if entry["id"] == request["id"]), None)
                if not entry or entry["revision"] != request["revision"] or not entry["canUndo"]:
                    raise Error("The removed startup item changed. Refresh and try again.")
                record = self.store.previous("remove:" + entry["id"])
                self.store.transact(record["item"], self.store.undo_changes(record))
            elif action in ("toggleApplication", "undoApplication", "remove"):
                app = next((a for a in inventory["applications"] if a["id"] == request["id"]), None)
                if not app or app["revision"] != request["revision"]:
                    raise Error("The startup configuration changed. Refresh and try again.")
                if action == "remove":
                    changes = removal.changes(app, self.roots, self.store)
                    current = next((a for a in self.scan()["applications"] if a["id"] == app["id"]), None)
                    if not current or current["revision"] != app["revision"]:
                        raise Error("The startup configuration changed. Refresh and try again.")
                    self.store.transact("remove:" + app["id"], changes)
                elif action == "undoApplication":
                    if not app["canUndo"]:
                        raise Error("This application's startup methods changed. Refresh; the backup was preserved.")
                    record = self.store.previous("application:" + app["id"])
                    changes = self.store.undo_changes(record)
                    self.store.transact(record["item"], changes, after=self.restore_effects(changes), sources=record.get("sources"))
                else:
                    self.toggle_application(app, request.get("enabled"))
            else:
                item = next((item for item in self.items if item["id"] == request["id"]), None)
                if not item or item["revision"] != request["revision"]:
                    raise Error("The startup configuration changed. Refresh and try again.")
                if item["readOnly"]:
                    raise Error(item["readOnly"])
                if action == "undo":
                    record = self.store.previous(item["id"])
                    if record and record.get("grouped"):
                        raise Error("Use the application's Undo to restore all startup methods together.")
                    changes = self.store.undo_changes(record)
                    callback = None
                    if item["kind"] in ("systemd", "xdg"):
                        callback = lambda: self.runner(["systemctl", "--user", "daemon-reload"])
                    if item["kind"] == "hyprland":
                        import base64
                        for _, _, value in changes:
                            if value["type"] == "file":
                                self.runner(["luac", "-p", "-"], input=base64.b64decode(value["data"]).decode())
                    self.store.transact(item["id"], changes, after=callback)
                else:
                    enabled = request.get("enabled")
                    if type(enabled) is not bool:
                        raise Error("The requested startup state must be a boolean.")
                    if enabled != item["enabled"]:
                        app = next(a for a in self.all_applications if any(s["id"] == item["id"] for s in a["sources"]))
                        marker = removal.path_for(self.roots, app["id"])
                        if snapshot(marker)["type"] != "absent":
                            # A previously removed item may have been enabled
                            # externally. A new user toggle retires that old
                            # removal so disabling cannot hide it again.
                            if item["kind"] == "hyprland":
                                planned = hyprland.toggle_changes([item], enabled, self.roots, self.runner)
                            else:
                                provider = desktop if item["kind"] == "xdg" else systemd
                                planned = provider.toggle_changes(item, enabled, self.roots, self.store)
                            changes = planned + removal.restore_changes(app, self.roots, self.store)
                            self.scan()
                            current = next((s for s in self.items if s["id"] == item["id"]), None)
                            if not current or current["revision"] != item["revision"]:
                                raise Error("The startup configuration changed. Refresh and try again.")
                            self.store.transact("application:" + app["id"], changes,
                                after=self.restore_effects(changes), sources={item["id"]: [str(path) for path, _, _ in planned]})
                            application_undo_id = app["id"]
                        elif item["kind"] == "xdg":
                            desktop.toggle(item, enabled, self.roots, self.store, self.runner)
                        elif item["kind"] == "hyprland":
                            hyprland.toggle(item, enabled, self.roots, self.store, self.runner)
                        else:
                            systemd.toggle(item, enabled, self.roots, self.store, self.runner)
            result = self.scan()
            if application_undo_id:
                result["applicationUndoId"] = application_undo_id
            if action == "add":
                result["addedApplicationId"] = added_id or next((a["id"] for a in result["applications"]
                    if any(s["id"] == "xdg:" + request["id"] for s in a["sources"])), "")
                result["addedApplicationUndo"] = "application" if added_id else "source"
            result["message"] = "Application added for future logins." if action == "add" else "Saved for future logins. Running programs were left alone."
            return result

    def restore_effects(self, changes):
        """Validate restored Lua and refresh systemd for a mixed transaction."""
        import base64
        for path, _, value in changes:
            if path == self.roots.lua and value["type"] == "file":
                self.runner(["luac", "-p", "-"], input=base64.b64decode(value["data"]).decode())
        if any(path.is_relative_to(self.roots.autostart) or path.is_relative_to(self.roots.user_units) for path, _, _ in changes):
            return lambda: self.runner(["systemctl", "--user", "daemon-reload"])
        return None

    def toggle_application(self, app, enabled, extra_changes=()):
        if type(enabled) is not bool:
            raise Error("The requested startup state must be a boolean.")
        if app["toggleReadOnly"]:
            raise Error(app["toggleReadOnly"])
        if enabled == app["startupEnabled"] and not extra_changes:
            return
        ids = {s["id"] for s in app["sources"]}
        targets = [s for s in self.items if s["id"] in ids
                   and (s["id"] == app["preferredSource"] if enabled else s["enabled"] is True)]
        changes = list(extra_changes)
        if not extra_changes and snapshot(removal.path_for(self.roots, app["id"]))["type"] != "absent":
            changes += removal.restore_changes(app, self.roots, self.store)
        source_paths = {}
        lua = [s for s in targets if s["kind"] == "hyprland"]
        if lua:
            changes.extend(hyprland.toggle_changes(lua, enabled, self.roots, self.runner))
            for item in lua:
                source_paths[item["id"]] = [str(self.roots.lua)]
        for item in targets:
            if item["kind"] == "hyprland":
                continue
            provider = desktop if item["kind"] == "xdg" else systemd
            planned = provider.toggle_changes(item, enabled, self.roots, self.store)
            changes.extend(planned)
            source_paths[item["id"]] = [str(path) for path, _, _ in planned]
        if len({path for path, _, _ in changes}) != len(changes):
            raise Error("Startup methods share a destination. Manage them separately in the details.")
        # Planning may invoke a syntax checker and inspect several providers.
        # Reject edits made since discovery, including to precedence layers
        # that are not themselves transaction destinations.
        self.scan()
        current = next((a for a in self.all_applications if a["id"] == app["id"]), None)
        if not current or current["revision"] != app["revision"]:
            raise Error("The startup configuration changed. Refresh and try again.")
        callback = (lambda: self.runner(["systemctl", "--user", "daemon-reload"])) if any(s["kind"] != "hyprland" for s in targets) else None
        self.store.transact("application:" + app["id"], changes, after=callback, sources=source_paths)

    def add(self, request, inventory):
        app = self.catalog.get(request["id"])
        if not app or not app["available"] or app["revision"] != request["revision"]:
            raise Error("The application entry changed or is not eligible. Refresh and try again.")
        existing = next((a for a in self.all_applications if any(s["id"] == "xdg:" + app["id"] for s in a["sources"])
                         or app["identity"] and a["id"] == app["identity"]), None)
        hidden = existing and any(a["id"] == existing["id"] for a in inventory["removed"])
        if existing and not hidden:
            raise Error("This application already has a startup source. Manage its existing entry instead.")
        if hidden and existing["preferredSource"]:
            self.toggle_application(existing, True, removal.restore_changes(existing, self.roots, self.store))
            return existing["id"]
        destination = self.roots.autostart / app["id"]
        problem = self.store.writable(destination)
        if problem:
            raise Error(problem)
        before = snapshot(destination)
        if before["type"] != "absent":
            raise Error("An autostart entry already exists; it will not be overwritten.")
        text = app["_desktop"].with_keys({"Hidden": "false"})
        changes = [(destination, before, file_value(text.encode()))]
        if hidden:
            changes += removal.restore_changes(existing, self.roots, self.store)
        self.store.transact("application:" + existing["id"] if hidden else "xdg:" + app["id"], changes,
                            after=lambda: self.runner(["systemctl", "--user", "daemon-reload"]),
                            sources={"xdg:" + app["id"]: [str(destination)]} if hidden else None)
        return existing["id"] if hidden else None

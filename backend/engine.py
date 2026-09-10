"""Application model and the only mutation entry point."""
from __future__ import annotations

import json
from pathlib import Path

from . import desktop, hyprland, systemd
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
        result.append(dict(id=key, name=first["name"], icon=first["icon"], enabled=enabled, status=status,
                           system=all(s["system"] for s in sources), sources=sources, kinds=kinds,
                           activeKinds=active_kinds,
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
            item["canUndo"] = bool(previous and not item["readOnly"] and
                                   all(snapshot(Path(e["path"])) == e["after"] for e in previous["entries"]))
        applications = group(items)
        existing = {s.get("appKey") for s in items}
        xdg_ids = {s["id"].split(":", 1)[1] for s in items if s["kind"] == "xdg"}
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
                "recoveries": recoveries,
                "counts": {"applications": sum(not a["system"] for a in applications),
                           "enabled": sum(a["enabled"] and not a["system"] for a in applications),
                           "system": sum(a["system"] for a in applications)}}

    def request(self, request):
        if not isinstance(request, dict):
            raise Error("Expected a JSON request object.")
        action = request.get("action", "scan")
        if action == "scan":
            return self.scan()
        if action not in ("toggle", "add", "undo", "recover"):
            raise Error("Unknown action.")
        if not isinstance(request.get("id"), str) or not isinstance(request.get("revision"), str):
            raise Error("A discovered identifier and revision are required.")
        with self.store.locked():
            self.scan()
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
                self.store.recover(path, record, after=callback)
            elif pending:
                raise Error("An interrupted change must be recovered or reviewed before another startup change.")
            elif action == "add":
                self.add(request)
            else:
                item = next((item for item in self.items if item["id"] == request["id"]), None)
                if not item or item["revision"] != request["revision"]:
                    raise Error("The startup configuration changed. Refresh and try again.")
                if item["readOnly"]:
                    raise Error(item["readOnly"])
                if action == "undo":
                    record = self.store.previous(item["id"])
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
                        if item["kind"] == "xdg":
                            desktop.toggle(item, enabled, self.roots, self.store, self.runner)
                        elif item["kind"] == "hyprland":
                            hyprland.toggle(item, enabled, self.roots, self.store, self.runner)
                        else:
                            systemd.toggle(item, enabled, self.roots, self.store, self.runner)
            result = self.scan()
            result["message"] = "Application added for future logins." if action == "add" else "Saved for future logins. Running programs were left alone."
            return result

    def add(self, request):
        app = self.catalog.get(request["id"])
        if not app or not app["available"] or app["revision"] != request["revision"]:
            raise Error("The application entry changed or is not eligible. Refresh and try again.")
        if any(item["id"] == "xdg:" + app["id"] or app["identity"] and item.get("appKey") == app["identity"]
               for item in self.items):
            raise Error("This application already has a startup source. Manage its existing entry instead.")
        destination = self.roots.autostart / app["id"]
        problem = self.store.writable(destination)
        if problem:
            raise Error(problem)
        before = snapshot(destination)
        if before["type"] != "absent":
            raise Error("An autostart entry already exists; it will not be overwritten.")
        text = app["_desktop"].with_keys({"Hidden": "false"})
        self.store.transact("xdg:" + app["id"], [(destination, before, file_value(text.encode()))],
                            after=lambda: self.runner(["systemctl", "--user", "daemon-reload"]))

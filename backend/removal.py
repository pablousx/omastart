"""Remove disabled items from the list without undoing startup suppression."""
from __future__ import annotations

import base64
import json
from pathlib import Path

from .common import Error, digest, file_value, snapshot


def path_for(roots, app_id):
    return roots.config / "omastart/removed" / (digest(app_id) + ".json")


def disabled(app):
    return bool(app["sources"]) and all(s["enabled"] is False for s in app["sources"])


def partition(applications, roots, store, warnings):
    visible, removed = [], []
    for app in applications:
        app["canRemove"] = False
        path = path_for(roots, app["id"])
        try:
            before = snapshot(path)
            marker = None
            if before["type"] == "file":
                marker = json.loads(base64.b64decode(before["data"]))
                if not isinstance(marker, dict) or marker.get("id") != app["id"] or not isinstance(marker.get("revision"), str):
                    raise Error("Invalid removed-item record.")
            app["canRemove"] = disabled(app) and not store.writable(path)
            if marker and disabled(app) and marker["revision"] == app["revision"]:
                previous = store.previous("remove:" + app["id"])
                removed.append({"id": app["id"], "name": app["name"],
                                "revision": digest([app["revision"], before]),
                                "canUndo": bool(previous and not store.writable(path) and
                                                all(snapshot(Path(e["path"])) == e["after"] for e in previous["entries"]))})
                continue
        except (Error, OSError, ValueError) as exc:
            warnings.append("Could not read a removed startup item: " + str(exc))
        visible.append(app)
    return visible, removed


def changes(app, roots, store):
    if not disabled(app) or not app.get("canRemove"):
        raise Error("Only fully disabled startup items can be removed from the list.")
    path = path_for(roots, app["id"])
    problem = store.writable(path)
    if problem:
        raise Error(problem)
    value = {"version": 1, "id": app["id"], "revision": app["revision"]}
    return [(path, snapshot(path), file_value(json.dumps(value).encode(), 0o600))]


def restore_changes(app, roots, store):
    path = path_for(roots, app["id"])
    problem = store.writable(path)
    if problem:
        raise Error(problem)
    return [(path, snapshot(path), {"type": "absent"})]

"""Fixtures never read a real configuration or contact a session bus."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from backend.common import Error, Roots
from backend.engine import Engine
from backend.systemd import fields, native_path


class FakeSystemd:
    def __init__(self, roots):
        self.roots = roots
        self.overrides = {}
        self.calls = []
        self.unavailable = False
        self.fail_reload = False

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if argv == ["luac", "-p", "-"]:
            # A real syntax-only compiler, with fixture content exclusively on stdin.
            result = subprocess.run(["/usr/bin/luac", "-p", "-"], input=kwargs["input"],
                                    text=True, capture_output=True)
            if result.returncode:
                raise Error(result.stderr)
            return ""
        if argv == ["systemctl", "--user", "daemon-reload"]:
            if self.fail_reload:
                raise Error("simulated reload failure")
            return ""
        if argv[:2] != ["systemctl", "--user"]:
            raise AssertionError("Unexpected command: " + repr(argv))
        if self.unavailable:
            raise Error("simulated inaccessible bus")
        names = sorted({p.name for d in self.roots.unit_dirs for p in d.glob("*.service")})
        if argv[2] == "list-unit-files":
            return json.dumps([{"unit_file": n, "state": "disabled"} for n in names])
        if argv[2] != "show":
            raise AssertionError("Mutation escaped the fake runner: " + repr(argv))
        result = []
        for name in names:
            path = native_path(self.roots, name)
            if not path:
                continue
            mask = self.roots.user_units / name
            masked = mask.is_symlink() and os.readlink(mask) == "/dev/null"
            props = {"Id": name, "Names": name, "FragmentPath": str(path),
                     "UnitFileState": "masked" if masked else "disabled", "ActiveState": "active"}
            if "generator" in str(path.parent):
                props.update(UnitFileState="generated", SourcePath=" ".join(fields(path.read_text()).get("Unit.SourcePath", [])))
            props.update(self.overrides.get(name, {}))
            result.append("\n".join(k + "=" + v for k, v in props.items()))
        return "\n\n".join(result)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="omastart-test-")
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        home = base / "home"
        home.mkdir()
        config = home / "config"
        config.mkdir()
        runtime = base / "runtime"
        self.vendor = base / "vendor/systemd/user"
        self.global_units = base / "etc/systemd/user"
        self.data = base / "share"
        self.etc = base / "etc/xdg"
        self.roots = Roots(home, config, home / "state/omastart", (self.etc,), (self.data,),
                           (config / "systemd/user", self.global_units, self.vendor, runtime / "systemd/generator.late"), runtime)
        self.runner = FakeSystemd(self.roots)
        self.engine = Engine(self.roots, self.runner)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def desktop(self, key, command=None, extra="", *, system=False, catalog=False, name=None):
        folder = self.data / "applications" if catalog else self.etc / "autostart" if system else self.roots.autostart
        return self.write(folder / (key + ".desktop"),
                          f"[Desktop Entry]\nType=Application\nName={name or key}\nIcon={key}\nExec={command or key}\n{extra}")

    def unit(self, name, command=None, *, global_enabled=False, local_enabled=False, user=False, extra=""):
        path = (self.roots.user_units if user else self.vendor) / (name + ".service")
        self.write(path, f"[Unit]\nDescription={name}\nPartOf=graphical-session.target\n[Service]\nExecStart={command or name}\n[Install]\nWantedBy=graphical-session.target\n{extra}")
        for active, root in ((global_enabled, self.global_units), (local_enabled, self.roots.user_units)):
            if active:
                link = root / "graphical-session.target.wants" / path.name
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(path)
        return path

    def item(self, item_id):
        self.engine.scan()
        return next(i for i in self.engine.items if i["id"] == item_id)

    def toggle(self, item_id, enabled):
        item = self.item(item_id)
        return self.engine.request({"action": "toggle", "id": item_id, "revision": item["revision"], "enabled": enabled})

#!/usr/bin/env python3
"""UI-only acceptance in the real shell. Never invokes backend mutations.

Opens/searches/expands the panel on each display, captures only its rectangle,
and checks startup-file fingerprints around the run. Invoke explicitly; this
script is intentionally separate from the isolated test suite.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

project = Path(__file__).resolve().parent.parent
output = project / ".verification"
output.mkdir(exist_ok=True)
plugin_id = "io.github.pablousx.omastart"
env = {**os.environ, "OMARCHY_SHELL_IPC_TIMEOUT": "10s"}


def run(args):
    return subprocess.run(args, check=True, text=True, capture_output=True, env=env).stdout.strip()


def ipc(method, *args):
    return run(["omarchy-shell", plugin_id, method, *args])


def state():
    return json.loads(ipc("inspect"))


def focus_monitor(name):
    # Current Hyprland uses Lua dispatchers. Connector names are validated
    # before insertion into this constant expression, passed without a shell.
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", name):
        raise RuntimeError("Unsupported monitor connector name")
    run(["hyprctl", "dispatch", 'hl.dsp.focus({ monitor = "' + name + '" })'])
    time.sleep(0.3)  # The shell receives the compositor's focus event asynchronously.


def wait_for(predicate):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        current = state()
        if predicate(current):
            return current
        time.sleep(0.15)
    raise RuntimeError("Panel did not reach the expected UI state: " + json.dumps(current))


def capture(current, path):
    # An outside click or focus handoff may dismiss a native panel during a
    # check on an active desktop. Reopen our own widget and restore UI-only
    # state before capturing; never synthesize clicks near startup switches.
    for attempt in range(3):
        actual = state()
        if not actual["opened"] or actual["geometry"]["screen"] != current["geometry"]["screen"]:
            ipc("openOnScreen", current["geometry"]["screen"])
            ipc("search", current["query"])
            ipc("expand", current["expandedId"])
        time.sleep(0.25)
        actual = state()
        if actual["opened"] and actual["query"] == current["query"] and actual["geometry"]["screen"] == current["geometry"]["screen"]:
            break
    else:
        raise RuntimeError("Desktop interaction repeatedly dismissed the panel during capture")
    current = actual
    geometry = current["geometry"]
    monitor = next(m for m in monitors if m["name"] == geometry["screen"])
    assert geometry["width"] <= monitor["width"] / monitor["scale"]
    assert geometry["height"] + geometry["y"] <= monitor["height"] / monitor["scale"]
    region = f"{int(monitor['x'] + geometry['x'])},{int(monitor['y'] + geometry['y'])} {int(geometry['width'])}x{int(geometry['height'])}"
    run(["grim", "-g", region, str(path)])


before = json.loads(run([sys.executable, str(project / "scripts/capture_startup.py")]))
monitors = json.loads(run(["hyprctl", "monitors", "-j"]))
original_monitor = next(m["name"] for m in monitors if m["focused"])
results = []
ux_checks = []
try:
    for monitor in monitors:
        focus_monitor(monitor["name"])
        assert run(["omarchy-shell", "shell", "summon", plugin_id, "{}"]) == "ok"
        ipc("openOnScreen", monitor["name"])
        current = wait_for(lambda s: s["opened"] and s["loaded"] and not s["busy"] and s["geometry"]["screen"] == monitor["name"])
        assert not current["error"]
        ipc("picker", "false")
        ipc("filterOptions", "false")
        ipc("filters", "all", "all", "false")
        ipc("search", "")
        ipc("expand", "")
        current = state()
        expected = {"Vicinae": "xdg", "Synergy": "systemd", "hyprsunset": "hyprland"}
        for name, kind in expected.items():
            row = next(r for r in current["rows"] if r["name"] == name)
            assert row["status"] == "Enabled", row
            assert any(s["kind"] == kind and s["enabled"] and not s["readOnly"] for s in row["sources"]), row
        capture(current, output / (monitor["name"] + "-overview.png"))
        for name in expected:
            ipc("search", name)
            ipc("expand", name.lower())
            current = wait_for(lambda s: len(s["rows"]) == 1 and s["rows"][0]["name"] == name)
            row = current["rows"][0]
            if name == "Vicinae":
                xdg = next(s for s in row["sources"] if s["kind"] == "xdg")
                assert xdg["generatedUnits"] == ["app-vicinae@autostart.service"]
                assert len(row["sources"]) == 2
            if name in ("Vicinae", "hyprsunset"):
                assert any(s["kind"] == "systemd" and not s["enabled"] for s in row["sources"])
            capture(current, output / (monitor["name"] + "-" + name.lower() + ".png"))
            results.append({"monitor":monitor["name"], "application":name, "state":row})
        # Common UX states: direct status selection, useful empty state,
        # advanced filters, and a picker that restores the original search.
        ipc("expand", "")
        ipc("search", "")
        ipc("filters", "all", "disabled", "false")
        assert all(row["status"] == "Disabled" for row in state()["rows"])
        capture(state(), output / (monitor["name"] + "-disabled.png"))
        ipc("filters", "all", "all", "false")
        ipc("search", "omastart-no-match-fixture")
        assert not state()["rows"]
        capture(state(), output / (monitor["name"] + "-empty.png"))
        ipc("search", "Vicinae")
        ipc("picker", "true")
        assert state()["adding"] and not state()["query"]
        choices = state()["choices"]
        assert choices, "Installed application picker is empty"
        choice = next((app for app in choices if not app["exists"]), choices[0])
        ipc("search", choice["name"])
        assert any(app["id"] == choice["id"] for app in state()["choices"])
        capture(state(), output / (monitor["name"] + "-picker.png"))
        ipc("picker", "false")
        assert state()["query"] == "Vicinae" and not state()["adding"]
        ipc("search", "")
        ipc("filterOptions", "true")
        capture(state(), output / (monitor["name"] + "-filters.png"))
        ipc("filterOptions", "false")
        ux_checks.append({"monitor": monitor["name"], "passed": ["status filter", "empty results", "installed picker search", "picker return", "advanced filters"]})
        ipc("search", "pipewire")
        assert not state()["rows"]
        ipc("filters", "all", "all", "true")
        protected = state()["rows"]
        assert protected and all(s["readOnly"] for r in protected for s in r["sources"])
        ipc("filters", "all", "all", "false")
        ipc("search", "")
        ipc("expand", "")
        run(["omarchy-shell", "shell", "hide", plugin_id])
    focus_monitor(original_monitor)
    run(["omarchy-shell", "shell", "summon", plugin_id, "{}"])
    ipc("openOnScreen", original_monitor)
    current = wait_for(lambda s: s["opened"] and s["loaded"] and not s["busy"])
    ipc("picker", "false")
    ipc("filterOptions", "false")
    ipc("filters", "all", "all", "false")
    ipc("search", "")
    ipc("expand", "")
    current = wait_for(lambda s: s["opened"] and s["query"] == "" and s["expandedId"] == "")
    capture(current, project / "preview.png")
finally:
    focus_monitor(original_monitor)

after = json.loads(run([sys.executable, str(project / "scripts/capture_startup.py")]))
changed = [key for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)]
report = {"checks":results, "uxChecks":ux_checks, "startupChangesDuringAcceptance":changed,
          "preview":"preview.png", "completed":time.strftime("%Y-%m-%dT%H:%M:%S%z")}
(output / "live-acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
if changed:
    raise RuntimeError("Startup files changed during acceptance; inspect external changes: " + ", ".join(changed))
print(f"Live acceptance passed: {len(results)} application/display checks, {sum(len(check['passed']) for check in ux_checks)} UX checks; startup configuration unchanged.")

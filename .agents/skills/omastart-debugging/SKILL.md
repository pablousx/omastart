---
name: omastart-debugging
description: Diagnose omastart discovery, save/undo/recovery, native UI, installation, or crash problems using isolated reproductions and scoped live evidence. Use for this plugin, not unrelated desktop customization.
---

# Debug omastart

Read [AGENTS.md](../../../AGENTS.md). Identify the affected version and whether the
symptom concerns discovery, persistence, rendering, installed code, or the host
process. Start with read-only evidence and reproduce mutations in fixtures.
Do not toggle a real startup app to see what happens.

## Establish source, installation, and session

1. Inspect the checkout and relevant diff. Read the installed manifest under
   `~/.config/omarchy/plugins/io.github.pablousx.omastart/` and its `entryPoints`.
2. A native `omarchy plugin add` installation is a Git checkout and supports
   `omarchy plugin update`. `scripts/install.py` creates a snapshot without Git,
   with `runtime/<content-hash>/` entry points. Compare the code actually selected
   by the installed manifest; editing this repository does not update that copy.
   For an already-authorized update of a Git-managed installation, an agent can
   use `omarchy plugin update io.github.pablousx.omastart --yes`. Native Omarchy
   mutation commands otherwise require a confirmation terminal; `--yes` satisfies
   that CLI requirement, not missing user authorization. Use `scripts/install.py`
   for a local snapshot, rather than trying to pull into its generated runtime.
3. If IPC or screenshots fail after a compositor restart, run
   `hyprctl instances -j` and inspect the current process environment. An inherited
   `HYPRLAND_INSTANCE_SIGNATURE` or `WAYLAND_DISPLAY` may point to the old session.
   Select the user's active instance and scope corrected environment values to
   the diagnostic commands. Do not hard-code a historical socket or globally
   rewrite the user's environment.

Within the current desktop session:

```sh
python3 backend/omastart.py
omarchy-shell io.github.pablousx.omastart inspect
omarchy-shell io.github.pablousx.omastart instances
```

The first command scans this checkout; the others inspect installed UI state.
Scan output contains real app names, commands, and paths. Keep full results private
in ignored `.verification/` and redact before sharing. A nonzero backend exit
still returns an error JSON object; diagnostics belong on stderr. Do not strip
errors or silently treat a failed source scan as an empty inventory.

## Diagnose the right layer

| Symptom | Evidence to compare |
| --- | --- |
| Missing or duplicate application | Desktop identity, XDG precedence/eligibility, provider IDs, generated-unit association, system/source/status filters |
| Enabled differs from running | Persistent enablement and eligibility versus available systemd activity; do not infer a process from a Lua command |
| App toggle blocked or incomplete | Every source's `enabled`, `eligible`, `readOnly`, app revision and preferred method; inspect current aggregate-toggle code |
| Save/undo fails | JSON error, stale displayed revision, writable root/symlink checks, external edit, pending transaction, user-manager/luac result |
| Old UI after installing | Installed manifest URL, runtime hash, copied files, active widget instance, host logs |
| Blank panel or binding warning | Native import version, `Style`/`Color` member, loader injection, screen geometry, exact QML file/line |

Use `systemctl --user show`, `list-unit-files --output=json`, `is-enabled`, and
`cat` as read-only evidence when useful. Inspect global user-unit directories
without writing to them. A generated XDG unit is subordinate to its desktop
entry; fix its association, not the generated file. A per-user mask can override
global enablement and also blocks later manual starts.

Reproduce discovery and write failures through the existing `Roots`/runner test
fixtures. For transactions cover failure after partial progress, external edits,
shared files, restart recovery, and grouped undo as relevant. Preserve unknown and
read-only outcomes; do not bypass guards to resolve a displayed error.

## Local installation and live acceptance

When installing local work is within the task, use the installed Omarchy skill
and run the repository installer after relevant isolated checks:

```sh
python3 scripts/install.py
omarchy plugin validate ~/.config/omarchy/plugins/io.github.pablousx.omastart
omarchy-shell shell summon io.github.pablousx.omastart '{}'
```

The installer deploys the entire working snapshot, backs up the old plugin and
`shell.json`, preserves placement, and rescans the host. Its content-hash runtime
URLs avoid Qt's compiled-component cache. It may temporarily disable only this
widget when changing URLs. Do not install unrelated in-progress edits, replace a
Git-managed installation incidentally, or edit generated runtime copies instead
of their source. No whole-shell restart is normally needed.

For source edits already in an installed checkout, native hot reload should
apply them. `omarchy-shell shell rescanPlugins` refreshes discovery; it does not
prove that a stale cached URL loaded fresh code. Confirm the active instance.

Before and after UI-only live acceptance:

```sh
mkdir -p .verification
python3 scripts/capture_startup.py > .verification/startup-before.json
# Perform the scoped inspection/capture.
python3 scripts/capture_startup.py > .verification/startup-after.json
diff -u .verification/startup-before.json .verification/startup-after.json
```

Investigate differences without reverting unrelated user activity.
`scripts/verify_live.py` opens/focuses panels across connected monitors, checks
specific fixture-era apps (Vicinae, Synergy, hyprsunset), and overwrites root
`preview.png`. It is not a portable default test; inspect its assumptions and use
it only for an appropriate live acceptance task. `scripts/capture_ui.py`, if
present, is the safer fixture-based visual check and writes under `.verification/`.
Fixture captures do not prove real Wayland placement or multi-monitor behavior.

## Logs, crashes, and recovery

Locate the active `omarchy-shell`/Quickshell process and its current log; inspect
process arguments and `$XDG_RUNTIME_DIR/quickshell/` rather than relying on an old
log path. Correlate timestamps with backend stderr and the failing operation.
Do not suppress all host diagnostics or start a second production Quickshell.

If the shell or compositor crashed, use the installed `diagnose-crash` skill when
available. Read `coredumpctl`, boot-specific journal entries, and kernel GPU/reset
messages around the event. Distinguish a Python error, QML binding problem, host
crash, and compositor/driver failure. Temporal proximity alone does not establish
causation. Never reinstall the desktop, restart user apps, or reproduce a crash
on the live session merely to test a theory. Keep core dumps and full logs private.

Startup journals normally live in
`$XDG_STATE_HOME/omastart/transactions` (default `~/.local/state/omastart/transactions`).
Installation backups live in `~/.config/omarchy/omastart-install-backups/`.
These serve different purposes. Inspect pending records and current snapshots
before considering a restore. Undo/recovery mutates real configuration and must
be within the user's requested repair. Never delete a journal to dismiss an error
or copy old bytes over newer external edits. Use the guarded recovery path and
validate restored Lua/manager metadata as implemented in `Engine` and `Store`.

Report the confirmed cause or remaining uncertainty, the version/installed path,
checks performed, and any real state changes. Do not publish raw diagnostics.

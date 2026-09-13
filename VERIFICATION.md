# Verification — 0.2.1

Verified locally on September 12, 2026, against Omarchy 4.0.3-1 and the
installed Quattro shell. These results describe local validation of the plugin;
marketplace review is a separate process.

## Application toggle update

The current local update passes 98 Python tests, QML analysis, and 97 QML
fixture assertions. The additional checks cover disabling multiple providers
in one journal, selecting one eligible method on enable, grouped undo and
recovery, rollback after reload failure, edits during planning, removed methods,
protected sources, keyboard activation, progress, and app-level Undo feedback.
Read-only tab checks cover separation from editable tabs, enabled-before-disabled
ordering, protected system visibility, search/source filtering, and picker navigation.
The consolidated Applications tab is checked for combined enabled/disabled items,
preserved ordering and unknown states, and removal of the separate status tabs.
Opening-order checks cover enabled-first sorting, stable rows through app/source
toggles and refreshes, filter/tab/picker navigation, appended and removed items,
and sorting again after reopening.
Frame-separated layout checks also keep a scrolled list's viewport, scroll offset,
row height, title width, switch position, and feedback height unchanged through
saving, disabling, enabling, multiline feedback, and message dismissal.
Add/remove checks cover newest-added placement, keeping disabled desktop entries,
explicit list removal and Undo, persistent removal records, re-adding existing
methods, masks, stale revisions, symlinks, and interrupted-removal recovery.
Multiple Lua entries are edited against one snapshot and validated together.
The screenshot harness renders the real panel with isolated sample data.
No real startup switches are used by these checks.

Security-boundary checks cover absolute runtime tool identities, a closed
environment, stdout/stderr limits, deadlines while stdin or output is blocked,
process-group cleanup after timeout and normal parent exit, and panel-side stream
caps. Filesystem checks substitute a configuration parent during a transaction
and confirm that the pinned directory receives the complete atomic replacement
while the substituted path remains untouched. Installer contract checks require
descriptor-relative staging, backup, and destination renames.

## Isolated checks

- 98 Python `unittest` cases pass using disposable configuration trees and an
  injected systemd runner. Tests include lossless Lua/XDG round trips, global
  service masking, generated-unit association, stale revisions, injection
  strings, symlinks, atomic replacement, permission preservation, concurrent
  locking, failure rollback, interrupted recovery, and undo.
- 97 QML fixture assertions pass, including native widget/panel loading,
  source and status filters, case-insensitive search, expanded details,
  generated-unit labeling, infrastructure protection, picker behavior,
  keyboard typing/navigation/Escape, and failure-state preservation. The UX
  revision additionally checks direct status tabs, filter reset, search clearing,
  Ctrl+F, picker return/Manage navigation, row progress, contextual success,
  immediate Undo, invalidation after external edits, persistent failures, and
  exact keyboard-focus restoration after a background refresh.
- QML analysis passes with no unexpected diagnostics. The checker identifies
  known Omarchy dynamic-object and Quickshell enum metadata gaps separately;
  those interfaces are also checked at runtime.
- Omarchy's official `omarchy plugin validate` passes for both the source
  directory and the installed plugin.

The offscreen fixture replaces only the Wayland window container, since Qt's
offscreen platform has no layer-shell window backend. Real window behavior is
checked in the installed shell below.

## Installed UI acceptance

The native panel was opened and visually inspected on both DP-1 (2560×1440)
and HDMI-A-1 (1920×1080), using the current theme and actual monitor geometry.

| Application | Verified startup status | Independent sources |
| --- | --- | --- |
| Vicinae | Enabled through XDG autostart | Generated `app-vicinae@autostart.service` is merged into its desktop entry; the native `vicinae.service` is disabled |
| Synergy | Enabled globally through user systemd | `synergy.service`, linked from the global graphical-session target; source has a supported per-user toggle |
| hyprsunset | Enabled through Hyprland | `o.launch_on_start("hyprsunset")` in user `autostart.lua`; native service is disabled |

All six application/display checks and ten UX checks passed. The UX checks
cover direct status filtering, actionable empty results, installed picker
search, returning to the previous startup search, and advanced filters on
both monitors. Source expansion, system item filtering, panel bounds,
application icons, and startup/running-state separation were inspected. Current runtime logs contain no omastart warnings
or errors. The original live captures remain in local verification artifacts.
The 0.2.1 `preview.png` renders the actual panel with isolated sample data
using `scripts/capture_ui.py`; it contains no surrounding desktop.

No real startup toggles were invoked. File and symlink fingerprints were
identical before and after the live acceptance run. Comparing the wider build
session's initial baseline also showed an independently added
`wine-sni-bridge.service` and its enablement link; those external additions
were preserved. Original startup files and `smartalb.autostart` were unchanged.

The detailed local acceptance JSON and per-display screenshots are in the
ignored `.verification/` directory. They are not shipped as public test
fixtures. Use the test commands in README to reproduce isolated checks.

## Limits of verification

Future-login behavior is covered through provider fixtures and systemd's
persistent configuration semantics. The real session was not logged out and
no real application was started, stopped, enabled, disabled, or restarted for
testing. Unsupported activation mechanisms remain read-only as documented in
README.

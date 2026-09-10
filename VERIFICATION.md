# Verification — 0.1.0

Verified locally on September 10, 2026, against Omarchy 4.0.3-1 and the
installed Quattro shell. No remote repository or marketplace submission was
created.

## Isolated checks

- 56 Python `unittest` cases pass using disposable configuration trees and an
  injected systemd runner. Tests include lossless Lua/XDG round trips, global
  service masking, generated-unit association, stale revisions, injection
  strings, symlinks, atomic replacement, permission preservation, concurrent
  locking, failure rollback, interrupted recovery, and undo.
- 56 QML fixture assertions pass, including native widget/panel loading,
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
or errors. `preview.png` is a direct cropped capture of the real panel.

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

# Verification — 0.3.0

Verified locally on September 22, 2026, against Omarchy 4.0.4-1 and the
installed Quattro shell. These results describe local validation of the plugin;
GitHub checks and marketplace review are separate exact-commit processes.

## Compact panel and installer repair

The panel now uses a 400×620 logical content area with a compact native header,
icon actions for Add and Refresh, smaller application rows, native hover and
selection fills, section separators, and combined status/source subtitles. The
available controls retain accessible names, keyboard focus, stable list state,
and the existing startup-versus-running distinction.

The local installer now detects a plugin that remains in the generic plugin
registry but has fallen out of the bar layout. It disables that stale entry
before enabling the bar widget again. If a Pocket entry still names omastart as
a member, the repaired widget is inserted immediately before Pocket; ordinary
installations preserve their exact section, index, and widget settings.

Five installer unit tests cover direct placement, default placement, Pocket
members represented as strings and arrays, and stale generic registration.
The live verifier no longer assumes that this machine's application preferences
have historical enabled states; it checks the expected source representation
and reports the state it actually observes.

## Isolated checks

- 103 Python `unittest` cases pass using disposable HOME/XDG trees and injected
  systemd runners. No test contacts the real user manager or changes a real
  startup preference.
- 97 QML fixture assertions pass with the backend absent and the display, bus,
  HOME, config, cache, and runtime environments isolated.
- QML analysis passes for all eight QML files with no unexpected diagnostics.
  The 57 reported dynamic Omarchy/Quickshell metadata gaps are the known set
  covered by runtime checks.
- `omarchy plugin validate` passes for the source tree and installed snapshot.
- Repository configuration validation passes, as do all nine tests of the
  repository setup tooling. `git diff --check` reports no whitespace errors.

The offscreen QML process reports the expected lack of an IPC socket and window
mask support; it still reaches `OMASTART_QML_PASS 97 assertions` and exits
successfully.

## Installed UI acceptance

The candidate was installed with `scripts/install.py`, which created its normal
private backup and selected the content-hashed runtime. The native panel was
opened and visually inspected on DP-1 (2560×1440) and HDMI-A-1 (1920×1080), at
their actual scales and geometry.

| Application | Observed startup status | Represented sources |
| --- | --- | --- |
| Vicinae | Disabled | XDG autostart and user systemd |
| Synergy | Disabled for this user | User systemd, including its global-enable explanation |
| hyprsunset | Enabled | Hyprland enabled; user systemd disabled |

All six application/display checks and ten UX checks pass. The UX checks cover
the read-only view, actionable empty results, installed-app picker search,
returning from the picker, and advanced filters on both monitors. The compact
header, application icons, row subtitles, switches, chevrons, expanded source
details, scrolling, separators, and fixed feedback area were inspected in every
capture. No panel content extends outside its rectangle.

The public `preview.png` is a real installed-shell capture, restricted through
the panel's own search to the known hyprsunset row. It contains only the panel,
with no surrounding desktop, paths, logs, diagnostics, or unrelated application
names. Per-monitor and expanded-state captures remain in ignored
`.verification/` storage and are not distributed.

No startup toggle was invoked. File and symlink fingerprints captured before
installation and after both live acceptance runs are identical.

## Distribution and website

The versioned archive is built from the reviewed allowlist with fixed timestamps.
Its member list contains the plugin QML/JavaScript, backend, scripts, tests,
manifest, README, verification notes, license, and preview; it excludes Git
metadata, repository-agent instructions, website source, caches, private
verification artifacts, and user configuration. ZIP integrity, checksum,
extracted manifest, extracted-source tests, official validation, and a second
byte-identical rebuild are checked before release.

The website is checked from a loopback server with relative `/omastart/` paths.
The landing, privacy, and terms pages remain usable without JavaScript; desktop
and mobile layouts, both themes, keyboard interactions, reduced motion, links,
fragments, license, preview, versioned download, and checksum are reviewed.

## Limits of verification

Future-login behavior is covered through provider fixtures and persistent
configuration semantics. The real session was not logged out and no real
application was started, stopped, enabled, disabled, or restarted. Unsupported
activation mechanisms remain read-only as documented in the README. Automated
marketplace compatibility and security-baseline results apply only to the exact
post-merge commit submitted later and are not a security audit.

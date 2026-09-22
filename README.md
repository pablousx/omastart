# omastart

**Manage everything that starts with your Omarchy session.**

A native Omarchy Quattro startup-apps panel that brings Hyprland, XDG
autostart, and user systemd into one searchable application list.

![omastart startup applications panel](preview.png)

- **Plugin ID:** `io.github.pablousx.omastart`
- **Author:** pablousx
- **Version:** 0.3.0
- **License:** MIT

## Use

Click the launch-arrow bar widget. **Applications** shows editable items together,
whether enabled or disabled. Each time the panel opens, enabled apps appear first,
alphabetically within each group. The order stays fixed while changing settings,
refreshing, searching, or switching tabs. Apps added with **Add app** go to the top;
other newly discovered apps join the end. Reopening
the panel sorts it again using the latest startup states.
**Read-only** contains items whose startup methods are all
read-only, including protected system items. Enabled items come first and
disabled items last, preserving alphabetical order within each group.
Search by application, command, path, or startup source;
the clear button returns you to the list. **Filters** contains source choices
and **Include system items**. Active filters remain visible when collapsed,
and **Reset** clears them in one step. The compact header keeps Add and Refresh
available as icon buttons with accessible names and tooltips, while each row
combines status and source context beneath the application name.

An app's switch controls its startup methods together. Turning it off disables
every enabled method in one reversible change. Turning it on enables one
available, editable method that applies to the session: an existing Hyprland
entry first (preferring `o.launch_on_start`), then XDG autostart, then a user
systemd service. It does not create a method or enable duplicate launches.
The tooltip identifies the method that will be enabled. An unknown state or
an enabled read-only method blocks the app switch and explains why.

The affected row shows **Saving…**
until the confirmed configuration comes back. A message names the app and
result, with **Undo** for a reversible change. Undo pauses its dismissal while
you hover or focus the message and becomes unavailable if the source changes
elsewhere. Failed saves keep the previous displayed state and offer Refresh.

Click an app or its chevron for source controls. Apps with several independent
sources also expose each separately; turning one off reports if another remains
enabled. The chevron opens explanations for read-only items. Commands, paths, and running-state
metadata sit behind **Technical details**. Generated XDG systemd units belong
to their desktop entry and are never counted or edited twice.

**Add app** searches installed desktop applications. Choose **Add** to copy an
entry to your user autostart directory, preserving its command and actions.
The picker stays open so you can add several apps. Existing entries offer
**Manage**, which opens their startup settings. **Back** restores your previous
search, filters, selection, and scroll position if nothing was added. After adding,
Back shows the newest addition at the top of Applications. No app is launched by the picker.

Disabling an app keeps its startup entry in the list so it can be enabled again.
Once every method is disabled, **Remove** in its details removes it from the list
without deleting its startup configuration or lifting service masks. **Undo**
restores the disabled row. Installed apps can also be added back through **Add app**,
which reuses an eligible existing method when available. Removed-item records are
stored under `$XDG_CONFIG_HOME/omastart/removed`; changed startup configurations
reappear rather than being silently hidden.

The panel keeps a stable size during searches and updates. Expanding a row
brings its controls into view; background refresh preserves your list position.
Status labels and the feedback area reserve space so saving and Undo do not
resize the list.
Empty results explain what happened and offer a relevant action.

Keyboard interaction:

- **Ctrl+F** focuses and selects the search text; **Tab** moves between controls.
- **Down** enters the list; **Up** from the first row returns to search.
- **Enter** from search chooses the first result. In the list, **Enter/Space**
  expands an app, adds a picker choice, or manages an existing picker entry.
- **Left/Right** collapses or expands the selected app; focused switches use
  **Space/Enter** to change their setting.
- **Escape** clears search, returns from the picker, collapses details or
  filters, then closes the panel, in that order.

The status means configured to start at login. Running apps stay open when you
change a setting. Infrastructure is hidden by default and remains protected
when shown. Unsupported entries explain their limits in expanded details.

## Requirements

- Omarchy Quattro; developed against Omarchy 4.0.3-1 and its bundled Quickshell.
- Python 3.10 or newer (standard library only).
- `systemctl` with JSON unit-file listing support, and an accessible user bus.
- `luac` for syntax-only validation of Hyprland edits.
- Omarchy's native `qs.Ui` and `qs.Commons` modules.

No privileged operations, package installation, or external network service is
required. omastart is independent of `smartalb.autostart` and does not modify it.

## Installation

Install the published plugin through Omarchy:

```sh
omarchy plugin add https://github.com/pablousx/omastart.git --enable
```

The native installer clones the repository, validates the manifest, and enables
its bar widget after confirmation. No startup preferences change during
installation. Omarchy Quattro and the dependencies listed above must already be
available; no install hooks or package installation are required.

For a Git-managed installation, review and apply updates with:

```sh
omarchy plugin update io.github.pablousx.omastart
```

If you already installed a local snapshot with `scripts/install.py`, continue
using that installer to update it. The native `add` command deliberately refuses
to overwrite an existing plugin with the same ID. To switch to Git-managed
updates, disable and remove the existing plugin first, then run the native
installation command above. Startup settings and recovery records persist.

To disable or remove either installation:

```sh
omarchy plugin disable io.github.pablousx.omastart
omarchy plugin remove io.github.pablousx.omastart
```

Restore any startup preferences you want to change before removal. Removing the
plugin does not undo startup settings or erase recovery records.

[Website](https://pablousx.github.io/omastart/) ·
[Privacy policy](https://pablousx.github.io/omastart/privacy.html) ·
[Terms of service](https://pablousx.github.io/omastart/terms.html)

## Local installation and development

From the source directory, as your normal desktop user:

```sh
python3 -m unittest discover -v
python3 scripts/test_qml.py
python3 scripts/check_qml.py
omarchy plugin validate .
python3 scripts/install.py
omarchy-shell shell summon io.github.pablousx.omastart '{}'
```

The installer copies a validated snapshot into
`~/.config/omarchy/plugins/io.github.pablousx.omastart`, rescans the shell, and
enables the widget in the left section. It backs up the previous plugin and
`shell.json` under `~/.config/omarchy/omastart-install-backups/`. It creates no
Git remote and invokes no plugin install hooks. Re-run it to deploy local edits;
existing widget placement is preserved. Installed runtime files use a content
hash in their path so Quickshell cannot retain stale compiled QML on update.
If an interrupted shell update leaves the plugin registered but missing from
the bar, the installer repairs its placement. When Pocket still records the
widget as a member, omastart is restored immediately before that Pocket entry
instead of moving to the default section.

To remove the widget without changing startup preferences:

```sh
omarchy plugin disable io.github.pablousx.omastart
```

To uninstall its files, use Omarchy's plugin removal UI or
`omarchy plugin remove io.github.pablousx.omastart --yes`. Startup preferences
and recovery backups persist independently of the plugin. Restore any desired
startup preferences before uninstalling.

## Supported startup mechanisms

| Mechanism | Discovery | Changes |
| --- | --- | --- |
| Hyprland | User `autostart.lua`, literal calls and inspectable unsupported startup statements | Comment/uncomment standalone top-level `o.launch_on_start` and `o.exec_on_start` literal calls; validate syntax before atomic replacement |
| XDG | User/system autostart precedence, desktop eligibility, generated-unit association | Preserve desktop contents and use per-user `Hidden` overrides; reverse omastart changes without rewriting system files |
| User systemd | Graphical targets and enabled user applications attached to `default.target`; global and user links | Manage ordinary per-user enablement links; use a per-user mask to disable global enablement |

XDG locations honor `XDG_CONFIG_HOME`, `XDG_CONFIG_DIRS`, `XDG_DATA_HOME`, and
`XDG_DATA_DIRS`, including installed Flatpak and Snap desktop exports. Desktop
eligibility honors `OnlyShowIn`, `NotShowIn`, `TryExec`, and the systemd XDG
generator's skip/phase rules. `NoDisplay` does not mean startup is disabled.
GNOME's `X-GNOME-Autostart-enabled` is not the systemd generator's enablement
switch; omastart writes the standard `Hidden` key.

Application identity comes from installed desktop metadata, parsed executable
names, and narrow mappings for known applications such as Synergy. Different
interpreter commands are not merged merely because they share an interpreter.

## Safety and recovery

Configuration edits are per-user. No files under `/usr`, `/etc`, or
`/usr/share/omarchy` are written. Commands are passed as argument arrays;
startup commands and Lua configuration are never executed by the backend.

Every change takes a process lock, rescans its source, checks the displayed
revision, and journals the original file bytes or symlink before changing it.
Configuration and recovery parents are opened descriptor-relatively with
`O_NOFOLLOW` and remain pinned through compare, write, rollback, and replacement.
Files use same-directory temporary files, `fsync`, and atomic descriptor-relative
renames. The journal preserves file modes. Symlinked files and parent directories
that would make an edit ambiguous are read-only. The local installer applies the
same no-follow, pinned-directory boundary to staging, backups, and installation.

The panel invokes `/usr/bin/python3` in isolated mode through a small response
bridge. Both layers use a closed environment, bounded stdout/stderr, and hard
request deadlines. External `systemctl` and `luac` calls use fixed absolute paths,
bounded nonblocking pipes, and their own process groups; timeout and completion
clean up the complete process group, including lingering descendants.

Backups live under `$XDG_STATE_HOME/omastart/transactions` (by default
`~/.local/state/omastart/transactions`) as private JSON records. File contents
are base64-encoded; symlink targets are recorded verbatim. They may contain
private startup command arguments, so do not publish them.

An ordinary failure rolls back only content still matching what omastart wrote.
Concurrent external edits are preserved and reported. Interrupted transactions
remain recorded for recovery. **Undo last change** restores a source's latest
backup when it still matches the current configuration. **Undo app startup
change** restores all methods affected by an app switch together; those changes
are not offered as separate source undos. An interrupted change
offers **Restore interrupted change** when its files can safely be restored;
otherwise it explains that external edits need review. Further startup changes
are blocked until that interrupted transaction is resolved. Never blindly copy
a backup over newer changes.

Changes affect future logins. omastart never issues service start, stop,
restart, or `--now`. Updating XDG entries or systemd enablement reloads manager
metadata, so XDG units are regenerated even with a lingering user manager.
Running applications are not restarted. A per-user mask also prevents later manual or indirect
starts of that service until it is restored. Hyprland may automatically reload
its configuration when a file changes; Omarchy's startup callbacks run at
session startup, not at configuration reload.

## Deliberate limits

- Arbitrary Lua, computed arguments, and conditional startup blocks are
  inspectable but not editable. The shipped commented `my-service` example is
  classified as a protected template, not an installed app.
- Socket/timer activation, service templates, runtime-only activation, aliases,
  required dependencies, specifiers, and service drop-ins are protected.
- An externally created mask is not silently removed. A global service with
  an existing local unit file is protected if masking would overwrite it.
- Conditional XDG entries are shown without executing their conditions.
- Infrastructure and uncertain packaged services remain protected; there is
  no “unlock everything” switch.
- Process activity is reported when systemd provides it. Lua startup does not
  imply that a matching process is still running.
- Login-shell scripts, arbitrary Omarchy hooks, and application-internal
  startup preferences are outside this version's three-provider model.

## Tests and validation

`python3 -m unittest discover -v` builds disposable HOME/XDG fixtures and uses
an injected fake systemd runner. The only real helper used by mutation tests
is `luac -p -`, receiving fixture text on stdin. Tests never contact the real
user manager or edit real startup files.

`python3 scripts/test_qml.py` loads the actual panel and row components in a
separate offscreen Quickshell process, with fixture data and **no backend
present**. A geometry adapter replaces only the Wayland window container,
which has no offscreen backend; all other native controls remain in use.
Installed-shell acceptance separately verifies the real `KeyboardPanel`.

`python3 scripts/check_qml.py` resolves Omarchy imports in a temporary analysis
directory. `omarchy plugin validate .` is the official manifest validator.
The QML checker reports known dynamic Omarchy facade/type-metadata diagnostics
separately; runtime tests cover these members. Unexpected diagnostics fail.

For read-only live diagnostics:

```sh
python3 backend/omastart.py
omarchy-shell io.github.pablousx.omastart inspect
python3 scripts/capture_startup.py
```

The backend prints JSON. Capture fingerprints before and after live acceptance
to verify startup files and links stayed unchanged. The plugin's IPC methods
only inspect, search, filter, expand, and refresh the UI; they do not toggle apps.

`python3 scripts/verify_live.py` explicitly opens and captures the panel on each
connected display, checks Vicinae, Synergy, and hyprsunset, inspects protected
items, and compares startup fingerprints. It never invokes a startup toggle.
Its local report and per-display screenshots are written to `.verification/`;
the cropped public capture becomes `preview.png` after restricting the panel to
the known hyprsunset row. It is not part of the isolated test command and is
intended for this machine's acceptance run.

## Project website

The responsive landing page, privacy policy, and terms of service are in
[`docs/`](docs/README.md). Preview them locally with:

```sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory docs
```

GitHub Pages can publish `main` → `/docs` with no build step. The site includes
a downloadable source snapshot; refresh it with
`python3 scripts/build_site_download.py` after changing the plugin. See the
[website guide](docs/README.md) for publishing and maintenance details.

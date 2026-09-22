---
name: omastart-development
description: Develop and test this omastart repository's native Quattro UI, startup providers, transaction handling, or static website. Use for implementation and refactoring; use the debugging or publishing skill for those workflows.
---

# Develop omastart

Read [AGENTS.md](../../../AGENTS.md), the relevant source, and
[README.md](../../../README.md). Use the working implementation as the authority;
a previously released snapshot can differ from current development. Preserve
unrelated in-progress edits. Commands below run from the repository root.

## Choose the change boundary

| Change | Primary files and meaningful checks |
| --- | --- |
| Filtering, selection, feedback, picker | `Panel.qml`, `Model.js`, row/control QML; QML fixture and lint |
| Native hosting, bar icon, panel anchoring | `BarWidget.qml`, `LaunchIcon.qml`, `Panel.qml`; QML checks, then scoped native acceptance |
| Discovery, eligibility, application identity | `backend/desktop.py`, `hyprland.py`, `systemd.py`, `engine.py`; provider/application fixtures |
| Saving, multi-source changes, undo, recovery | `backend/common.py`, `engine.py`, provider planning functions; transaction/failure/concurrency fixtures |
| Static website or policies | `docs/*.html`, `docs/assets/site.css`, `site.js`; browser, links, actual data-handling claims |

Keep provider filesystem edits behind `Store`; inject `Roots` and a runner in
backend tests. `Engine.request` is the mutation boundary. Do not add alternate
CLI path overrides or use real HOME/user-bus requests to exercise mutations.

The current app switch disables all enabled methods together; enabling chooses
one existing editable, eligible method, preferring Hyprland (`launch_on_start`
first), then XDG, then user systemd. Source controls still act individually.
If this behavior changes intentionally, update the model, grouped transaction
and undo tests, QML feedback, README, and website together. Preserve revision
checks across the whole app; shared-file source changes must compose correctly.

## Native UI contracts

Use native controls, theme roles, font metrics, and `Style.space` sizing. Keep
startup state separate from process activity and expose read-only reasons.
Maintain stable panel geometry, search/filter state, list position, selected row,
and the actual focused control through refresh. Pending work belongs to the
specific row. Errors remain actionable; success and undo refer to the completed
operation and become invalid when the source revision changes.

The picker adds desktop entries without launching the app. Existing entries route
to Manage; Back restores the prior view. Exercise keyboard search, list entry,
activation, details, Escape backtracking, and focus after a row disappears.

Explicit additions go to the top; disabling preserves startup entries. Disabled
items can be removed from the list through `backend/removal.py`, which journals
per-item records under the user config without lifting startup suppression.
Cover removal Undo, re-addition, and stale records when changing these paths.

`LaunchIcon.qml` is the logo geometry authority. If changing the mark, synchronize
`docs/assets/favicon.svg` and the inline SVG copies in all three HTML pages.
Do not substitute a generic font arrow or redesign other branding incidentally.

## Run the appropriate checks

```sh
python3 -m unittest discover -v
python3 scripts/test_qml.py
python3 scripts/check_qml.py
omarchy plugin validate .
```

Backend tests need Python and `luac`; they inject fake systemd and temporary roots.
Native QML checks additionally need the installed Omarchy Quattro modules,
Quickshell, and Qt's `qmllint`. The plugin has no Python package-install step.
Use targeted tests while iterating, then the relevant complete suite before
finishing a behavioral change. Do not invent or retain old assertion totals.

The QML harness copies actual components but excludes the backend, replaces only
the window container, and isolates HOME/XDG, display, and bus environments. It is
an intentional test process, not a second production shell. Do not remove that
isolation to make a fixture pass. Expected offscreen IPC/window-mask limitations
are distinct from plugin warnings, missing pass markers, or failing assertions.
`check_qml.py` permits narrowly identified native type-metadata gaps; new warnings
need investigation rather than a broad suppression.

When available in the checkout, run GitHub baseline checks for changes to its
configuration or tooling, following `GITHUB_SETUP.md`:

```sh
python3 .github/scripts/check_repository.py
python3 -m unittest discover -s .github/tests -v
```

These require their documented developer dependencies (including PyYAML), not new
plugin runtime dependencies. Hosted Python CI does not replace local native UI
validation. Read current workflows and required check names before opening a PR.

For screenshots of new UI behavior, `scripts/capture_ui.py`, when present, captures
fixture data in the current theme without the backend. Inspect the images and
identify them as fixture captures. For installed-shell validation or installing
local edits, continue with [omastart-debugging](../omastart-debugging/SKILL.md).

## Website changes

Follow [docs/README.md](../../../docs/README.md). Preview on loopback:

```sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory docs
```

Use relative asset/navigation paths so `/omastart/` works on GitHub Pages. Keep
all three pages usable without JavaScript. Test the changed flows on a narrow
mobile screen and desktop, both Tokyo Night and Everforest when styling changes,
keyboard focus, reduced motion, and no horizontal overflow. For interactive
changes, check undo, filters, disappearing-row focus, theme storage failures,
clipboard failure, and download links as applicable. Use available browser and
accessibility tools; discover their paths rather than relying on old `/tmp` tools.

The site has no trackers, remote fonts, accounts, or connection to the desktop
backend. `omastart-theme` is an optional browser preference; demo state is memory
only. Keep the privacy policy synchronized with actual behavior and distinguish
GitHub hosting from local plugin data. Preserve MIT permissions in the terms.

Do not run the archive builder simply to update website styles or agent guidance.
It packages current source bytes, including uncommitted code, into the versioned
ZIP. Refresh downloads as part of an intentional release using
[omastart-publishing](../omastart-publishing/SKILL.md).

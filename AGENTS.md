# Maintaining omastart

omastart is a native Omarchy Quattro startup-app manager. Its permanent plugin
ID is `io.github.pablousx.omastart`; repository and author are `pablousx/omastart`
and `pablousx`. `manifest.json` is the version authority. Runtime code is QML,
JavaScript, and Python standard library; the website is static HTML/CSS/JS.

## Project skills

Read the skill relevant to the task before making changes. These repository-local
skills travel with the project; if skill discovery is unavailable, open the linked
`SKILL.md` directly. Read only the references needed for the current operation.

| Task | Skill |
| --- | --- |
| Features, provider changes, native UI, tests, website | [omastart-development](.agents/skills/omastart-development/SKILL.md) |
| Wrong startup state, failed saves, stale UI, logs, crashes, recovery | [omastart-debugging](.agents/skills/omastart-debugging/SKILL.md) |
| Release preparation, GitHub Pages, marketplace submission or update | [omastart-publishing](.agents/skills/omastart-publishing/SKILL.md) |

For desktop configuration or user-facing Omarchy commands, also use the installed
Omarchy skill when available. Package-owned `/usr/share/omarchy/` is reference
material, not this project's edit target.

## Start with the actual checkout

Inspect `git status -sb`, the diff, and relevant files. Other work may be in
progress: preserve unrelated edits and do not stage, stash, reset, or publish them
as part of this task. Read `CONTRIBUTING.md`, `GITHUB_SETUP.md`, the PR template,
and `.github/workflows/` when present. Remote policy or release changes can be
newer than this checkout; inspect them before integrating or publishing.

[README.md](README.md) defines user behavior and supported sources;
[VERIFICATION.md](VERIFICATION.md) records measured acceptance, not a permanent
test count. [docs/README.md](docs/README.md) describes the website and archive.
Do not treat this file or a skill as authorization to publish, merge, install,
change real startup settings, or contact maintainers. Follow the user's current
scope and already-given authorization without asking for routine re-confirmation.

## Architecture and invariants

- `BarWidget.qml` owns the native bar entry, panel loader, and UI-only IPC.
  `Panel.qml` owns state, focus, filters, and backend requests. Row/control QML
  files render state; `Model.js` supports view logic. Use Omarchy's native
  `qs.Ui`, `qs.Commons`, `Style`, and `Color` rather than hard-coded theme values.
- `backend/omastart.py` handles one JSON request per process. `engine.py` groups
  applications, dispatches mutations, and coordinates providers. `common.py`
  owns roots, bounded subprocess/file access, locking, journaling, and recovery.
  `desktop.py`, `hyprland.py`, and `systemd.py` implement the three providers.
- Startup configuration and running state are different facts. Changes target
  future logins. The backend never executes parsed startup commands or Lua,
  never invokes a shell, and never starts/stops/restarts services or uses `--now`.
  `systemctl --user daemon-reload` refreshes metadata; `luac -p -` validates syntax.
- Writes stay in discovered per-user destinations and use the transaction store:
  lock, fresh scan, revision check, journal, compare-before-write, atomic update,
  and conditional rollback. Preserve modes, original bytes, external edits, and
  symlink boundaries. Multi-source app changes must remain one undoable operation.
- Generated XDG systemd units belong to the desktop source. Do not count or edit
  them twice. Global service disablement uses a per-user mask; communicate its
  effect on subsequent manual/indirect starts. Never remove an unrelated mask.
- Unknown, conditional, unsupported, and protected states are not interchangeable
  with Disabled. Do not relax protection just to make an app switch work.
- Keep backend stdout exclusively JSON, diagnostics on stderr, and Python bytecode
  disabled in watched installed paths. Do not add runtime dependencies casually.

## Validation and live work

Use checks appropriate to the change; commands and prerequisites are in the
[development skill](.agents/skills/omastart-development/SKILL.md). Tests use
injected roots and fake systemd runners. The QML harness deliberately has no
backend. Never test mutation requests against the real session as a substitute
for fixtures. A real startup change needs task-specific user authorization.

Live installation, native panel capture, and process-crash investigation are
separate operations. Use the [debugging skill](.agents/skills/omastart-debugging/SKILL.md)
for their side effects, current-session discovery, and diagnostic boundaries.
Keep logs, state snapshots, core dumps, and private captures in ignored
`.verification/`. Recovery JSON may contain private command arguments; base64 is
not encryption. Publish only a reviewed crop of the plugin as `preview.png`.

## Completion and maintenance

Report what changed, checks actually run, and any remaining dependency on user or
marketplace action. Update user documentation when behavior changes. Update these
skills when architecture, scripts, or publishing rules change. Validate changed
skill frontmatter with the available skill-creator validator and check relative
references and invocation metadata. Do not regenerate
release archives or change the manifest version for an instructions-only edit.

For a release, use the publishing skill before pushing: every change to the
published branch, including docs or GitHub configuration, changes the commit
covered by marketplace review. A GitHub release, deployed project website, and
approved marketplace snapshot are three separately verified outcomes.

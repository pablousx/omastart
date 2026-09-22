# Release and website procedure

Use for an authorized release or for preparing a reviewable release candidate.
All shell examples assume the repository root. Substitute actual values before
executing commands; never derive a release from unrelated dirty work.

## Prepare the source

1. Inspect `git status -sb`, remotes, tags, and the diff. Fetch current refs when
   appropriate; reconcile with the default branch without discarding concurrent
   work. Follow the current repository rules and PR template. Normal maintenance
   uses a branch, passing required checks, and squash merge; the owner's bypass
   is not the default workflow.
2. Read `manifest.json` and the existing GitHub releases. Choose a new version for
   changed released plugin code. Keep the permanent plugin ID and entry-point
   contract. Update README behavior, dependencies, removal/migration instructions,
   `VERIFICATION.md`, and affected site copy. Do not copy old test totals as if
   freshly run. Include the grouped application/source behavior actually shipping.
3. Validate the candidate using the development skill. Backend changes need the
   isolated Python suite; native changes need the QML harness, lint, and official
   validator. Run relevant GitHub configuration checks when changed. Install and
   visually inspect local code only when that live action is in scope.
4. If capturing a new root preview, inspect the image before packaging. Do not
   expose the surrounding desktop, private paths, startup journals, or diagnostics.
   Keep `preview.png` and `docs/assets/panel.png` synchronized through the builder.

## Package a versioned download

`python3 scripts/build_site_download.py` reads the current working tree, not a Git
commit. Its allowlist includes root QML/JS, backend/scripts/tests Python and QML,
README, verification notes, manifest, license, and preview. It excludes website
content, `.git`, `.agents`, and private `.verification` artifacts. It copies the
license and preview to site assets and writes the source ZIP and `SHA256SUMS.txt`.
The builder is stdlib-only and uses fixed timestamps for reproducible archives.

Before running it, make sure only the intended release source will be packaged.
Update the manifest version and all visible/link references first:

```sh
rg -n '0\.[0-9]+\.[0-9]+|omastart-.*\.zip|v[0-9]' manifest.json README.md VERIFICATION.md docs
python3 scripts/build_site_download.py
```

For the chosen version, validate ZIP integrity, its SHA-256, and the extracted
manifest. Run isolated tests from the extracted source when packaging changes.
Check archive members for missing fixture/helper files and unexpected material;
new non-Python/non-QML resources may require an explicit builder update.
The same source should rebuild to identical archive bytes.

Keep old released archives immutable. When retiring an old site download, inspect
links first; release assets remain available on GitHub. Do not use a blanket ZIP
removal or rebuild the old version with new code. Instructions-only changes need
no archive refresh or version bump, but a later merged commit still affects
marketplace SHA coverage.

## Commit, merge, and publish

Prepare release notes describing user-visible behavior, dependencies, meaningful
validation, and limitations. Put multiline PR/release/issue text in a file and use
`--body-file` or `--notes-file`. Stage only this change. Review the staged diff and
whitespace, pass the current required checks, and merge through the authorized
repository workflow. If required checks or authorization are missing, finish the
candidate and report that concrete boundary instead of bypassing protections.

After merge, obtain and compare the full published SHA:

```sh
gh api repos/pablousx/omastart/git/ref/heads/main --jq .object.sha
git ls-remote origin refs/heads/main
```

Use the full SHA returned above as the release target, not a PR branch SHA or an
abbreviated commit. The release API rejected a short SHA during initial release.
Example shape, with real version/SHA and prepared note-file path substituted:

```sh
gh release create vX.Y.Z docs/assets/omastart-X.Y.Z.zip docs/assets/SHA256SUMS.txt --repo pablousx/omastart --target FULL_40_CHARACTER_SHA --title 'omastart X.Y.Z' --notes-file /tmp/omastart-release-notes.md
```

Inspect an existing tag/release before retrying a failed API call; creation and
asset upload may have partially succeeded. Never overwrite an unrelated release
or silently move a tag. Verify the release is published rather than draft, the
tag resolves to the intended SHA, and downloaded asset bytes match local hashes.
A fresh public clone should validate with `omarchy plugin validate`; there is no
need to install it over the user's existing plugin to check distribution.

## GitHub Pages

The project already uses branch publication from `main` and `/docs`; `.nojekyll`
and relative links support the project path. Do not recreate Pages or change its
hosting mode just to deploy a new revision. Merging/pushing the approved site
change triggers deployment. Inspect settings and progress:

```sh
gh api repos/pablousx/omastart/pages --jq '{html_url,source,status}'
gh api repos/pablousx/omastart/pages/builds/latest --jq '{status,error,commit}'
gh run list --repo pablousx/omastart --limit 5
```

Confirm the deployed commit, HTTP success, and actual contents of the landing
page, `privacy.html`, `terms.html`, shared assets, and versioned download. Inspect
mobile/desktop layouts and changed interactive flows. Keep legal text consistent
with real local data handling and hosting; do not promise tracker-free behavior
if new code sends data elsewhere.

For a site-only release, avoid changing the plugin version/ZIP unless its source
or advertised download is intentionally changing. Nevertheless, the repository's
new default-branch SHA can make marketplace evidence stale: follow the marketplace
reference for pending-submission refresh or listed-plugin update as authorized.

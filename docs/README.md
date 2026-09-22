# omastart website

A self-contained HTML/CSS/JavaScript site, inspired by the published
[omadocs site](https://pablousx.github.io/omadocs/). Tokyo Night and Everforest
palettes, the plugin's own launch-arrow mark, and native desktop proportions
connect the two projects. No framework, build service, remote fonts, or analytics.

## Preview

From the repository root:

```sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory docs
```

Open `http://localhost:8000`. The pages also work directly from disk; clipboard
support depends on browser permissions and a secure context. Navigation,
downloads, FAQ, and all policy content work without JavaScript. JavaScript adds
the simulated startup controls, copy command, and optional saved theme.

## Publish with GitHub Pages

The site is published at <https://pablousx.github.io/omastart/>. Its publishing
configuration is:

1. Push the repository to `pablousx/omastart` on GitHub.
2. In **Settings → Pages**, choose **Deploy from a branch**.
3. Select **main**, then **/docs**, and save.
4. Check the deployment and visit `https://pablousx.github.io/omastart/`.

These are GitHub's supported [branch publishing settings](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).
The `.nojekyll` file keeps these plain static assets out of Jekyll processing.
All navigation and asset URLs are relative, including the policy pages, so the
site works under the `/omastart/` project prefix. Canonical and Open Graph URLs
assume the address above; update them in all three HTML pages for another host.
Updates to `main` automatically rebuild the published site.

## Update the downloadable source

The website ships a self-contained source ZIP alongside the public
[repository](https://github.com/pablousx/omastart). The README also documents
native installation and updates through `omarchy plugin`.
The ZIP contains the plugin, installer, documentation, license, and Python checks.
It excludes this website, local verification artifacts, Git metadata, and user
configuration. The ZIP does not install or execute anything when downloaded.

After changing the plugin or its README, run from the repository root:

```sh
python3 scripts/build_site_download.py
```

This refreshes the ZIP, SHA-256 checksum, reviewed installed-panel screenshot,
and license.
The archive has fixed timestamps for reproducibility. If the manifest version
changes, update the visible version and ZIP links in `index.html`, and remove the
superseded ZIP only when it was never published; retain every released archive.
The launch-arrow favicon and
inline SVGs use `LaunchIcon.qml` geometry; keep them in sync if the logo changes.

## Privacy and terms

`privacy.html` describes actual local plugin behavior and website hosting.
`terms.html` preserves the MIT License. Both have an effective date of September
10, 2026. Keep the text accurate if data handling, hosting, or project contact
options change. Browser theme storage uses only `omastart-theme`; demo changes
stay in memory. No personal data, real startup backups, or diagnostics are
bundled. The screenshot is cropped to the installed panel and filtered to a
known public hyprsunset row; it contains no surrounding desktop or unrelated
startup names.

The styling follows the sibling site without importing any of its Google account,
OAuth, file-upload, or retention behavior.

## Verification

Checked in Chromium on September 22, 2026 from a loopback server:

- 30 page/theme/viewport combinations cover all three pages, Tokyo Night and
  Everforest, and widths of 320, 390, 768, 1024, and 1440 pixels. None has
  horizontal page overflow, browser errors, or third-party requests.
- Mobile and desktop captures of the landing, privacy, and terms pages were
  visually inspected. Text, navigation, controls, policy content, and the
  compact Applications/Read-only demo remain legible and contained.
- Four browser scenarios cover demo switches and Undo, the read-only view,
  theme persistence, denied clipboard/storage access, reduced motion, cookies,
  no-JavaScript rendering, local links, fragments, version text, license,
  preview, source download, and checksum.
- The 127,609-byte download hashes to
  `3e04762e16e09a9c96f8a8cc2cf3928fd239fc5a941446f04e1d58b23329a428`.
  The extracted source passes all 103 Python tests, 97 QML assertions, QML
  analysis, and Omarchy's official manifest validator.

These automated, keyboard, semantic, and visual checks are not a claim of
complete accessibility certification. Local reports and screenshots remain in
the ignored `.verification/site/` directory.

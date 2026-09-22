---
name: omastart-publishing
description: Prepare and publish omastart releases, its GitHub Pages website, and exact-commit Omarchy marketplace submissions or updates. Use for release readiness and maintenance of published versions; preparation alone does not authorize external publication.
---

# Publish or update omastart

Read [AGENTS.md](../../../AGENTS.md) and inspect the current Git and marketplace
state. Follow existing user authorization; do not ask again for an action already
approved. Publishing a prior release does not authorize unrelated future releases.
Prepare a concrete release or issue before requesting any missing approval.

## Stable identity and authoritative sources

- Repository: <https://github.com/pablousx/omastart>
- Permanent manifest ID: `io.github.pablousx.omastart`
- Website: <https://pablousx.github.io/omastart/>, GitHub Pages `main` → `/docs`
- Initial submission: <https://github.com/omacom/omarchy-plugin-marketplace/issues/6135>
- [Publishing guide](https://plugins.omarchy.org/publish.html)
- [CLI submission rules](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SUBMISSION.md)
- [Verification and update rules](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/VERIFICATION.md)
- [Security-baseline policy](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SECURITY.md)

Re-read the current guide and issue template before each submission/update. Rules,
headings, labels, and exact-commit requirements can change. `gh` is the established
CLI; check authentication without printing credentials. Do not create a duplicate
repository, listing, or issue from the historical links above.

## Select the intended outcome

| Task/state | Required route |
| --- | --- |
| Prepare changes locally | Tests, documentation, version/archive review; no push or release by implication |
| Release a new plugin version | [Release workflow](references/release.md), then assess marketplace state |
| Publish only website changes | Release workflow's website section; still account for changed branch HEAD |
| Existing initial submission is still pending | Update/revalidate that issue; do not request an update for an unlisted plugin |
| Already listed, newer upstream commit | [Marketplace workflow](references/marketplace.md): newer-commit verification request |
| Re-verify existing listed snapshot | Same workflow, recorded snapshot SHA; no promotion of newer code |
| Update this computer's installed plugin | [Debugging skill](../omastart-debugging/SKILL.md): distinguish Git checkout and local snapshot |

As of the initial September 10, 2026 submission, 0.1.0 was released, the website
was live, and issue #6135 passed compatibility at `207b7f4` with manual review
required for `installer` and `service-management`, with no baseline findings.
This is historical context, not today's status or a reusable verification claim.

## Release boundaries

Keep the ID permanent. Use the manifest version consistently in the README,
website, source ZIP, release title/tag, and checksums. Inspect existing release
tags before choosing the next version. Do not overwrite a published version's
archive with different plugin code or move an existing release tag.

Freeze the full final default-branch SHA after merge, including all documentation,
GitHub configuration, generated assets, and release metadata changes. Squash merge
creates a different SHA from the feature branch. The current `omarchy plugin add`
and `update` commands follow mutable upstream; a GitHub tag alone neither pins
those installs nor updates the marketplace's verified snapshot.

Run the relevant checks, publish only the authorized artifacts, then verify the
public source/release/download/Pages outcomes separately. Submit that exact full
40-character default-branch SHA for marketplace promotion. Do not advance HEAD
again while expecting an earlier pending scan to remain current.

## Submission authorization and completion

The marketplace's CLI AI instructions require showing the completed issue title
and body and obtaining owner approval of the checklist before creating the issue.
Use already-given approval of that exact submission; otherwise request it once,
with the finished body and a link to the actual rule. Do not invent ownership
attestations or add a new approval gate to routine local preparation.

Creating/editing a public issue is external communication. A request to publish
or update a marketplace listing can authorize it, subject to the applicable
owner-attestation step. Do not post comments merely because they might be useful.
Never apply marketplace maintainer approval labels yourself on the author's behalf.

After submission, read the bot reports. Fix actionable failures within the
approved scope and retry the same issue with current evidence. Stop after a
repeated unchanged external failure and report the required action; do not open
duplicates, spam edits, or loop indefinitely. Successful compatibility plus
`security-review-required` normally means wait for marketplace maintainer review.
Do not remove legitimate capabilities to evade it.

Finish with links and distinct statuses: GitHub release, project website,
marketplace request, and marketplace approval/deployment. A successful workflow
step or retained approval label alone is not proof the listing is published.

# Marketplace submission, refresh, and update

The stable source is `pablousx/omastart`, plugin ID
`io.github.pablousx.omastart`. Other authors have similarly named plugins; match
repository and permanent ID, not the human name alone.

## Read current state and rules

Read the marketplace's current `SUBMISSION.md`, `VERIFICATION.md`, `SECURITY.md`,
and the relevant issue template before preparing a request. The [update form](https://github.com/omacom/omarchy-plugin-marketplace/issues/new?template=verify-plugin.yml)
is shared by several distinct actions; do not choose by title alone.

Useful read-only commands:

```sh
gh issue view 6135 --repo omacom/omarchy-plugin-marketplace --comments
gh issue list --repo omacom/omarchy-plugin-marketplace --author pablousx --state all --search 'omastart in:title' --json number,title,state,url
gh api repos/pablousx/omastart/git/ref/heads/main --jq .object.sha
gh api -H 'Accept: application/vnd.github.raw+json' repos/omacom/omarchy-plugin-marketplace/contents/registry.json > /tmp/omastart-marketplace-registry.json
```

Inspect the registry entry matching the exact repository/ID, including
`listingValidatedCommit`, and compare its full SHA with upstream. The registry
can exceed GitHub's inline contents limit: request raw JSON as above rather than
base64-decoding an empty `.content` response. Search active requests as well as
closed ones. An issue being closed or an approval label being present is not by
itself proof of a deployed listing; inspect bot publication reports and registry.

## Initial submission is pending

Issue #6135 is the original request; verify its live state. If it remains unlisted,
keep using that issue. A new branch HEAD, including documentation-only changes,
requires a fresh compatibility/baseline report before it can be approved.

For an authorized refresh, read the current issue body, update truthful version,
behavior, and validation notes, preserve the six required headings/checklist, and
edit the same issue with `gh issue edit ... --body-file ...`. Do not replace the
body with a stale local template or silently add unapproved ownership claims.
An actual corrected body edit triggers submission detection again. Do not create
a `[Verify]` newer-commit request until the plugin has an existing listed snapshot.

Only if there is no submission/listing for the exact source, use the current
submission form/CLI guide: title `[Plugin]: omastart`, category `System`, one to
three allowed tags (initially `bar, hyprland, system`), and the guide's exact
headings and checklist. Show the completed body and honor its owner-approval
requirement, reusing explicit approval already given for that submission.

## Publish a newer listed commit

Once the source is listed and the authorized release is merged/published:

1. Freeze the full current default-branch SHA. Keep the exact plugin ID set.
2. Check for an existing open update request for that source. Update it when
   appropriate instead of filing a duplicate.
3. Compare the current upstream issue template with
   [update-issue.md](update-issue.md). Set **Verification action** to
   `Verify and publish a newer upstream commit`; fill the target with the full
   current HEAD SHA, not the old `listingValidatedCommit`, a tag, or a PR SHA.
4. Obtain any missing approval of the completed public request and acknowledgment,
   mark the acknowledgment checked only when confirmed, and replace the SHA
   placeholder. Never submit the template unchanged. Then create/edit it using
   the completed body file. Example:

   ```sh
   gh issue create --repo omacom/omarchy-plugin-marketplace --title '[Verify]: omastart' --body-file /tmp/omastart-update-issue.md
   ```

5. Read compatibility and baseline comments for that SHA. A write-authorized
   marketplace maintainer applies `approved-and-verified` after reviewing the
   current reports. The workflow rescans the exact commit and promotes the
   snapshot, previews, evidence, and catalog only after its checks pass.
6. Confirm registry and deployment before reporting the update as listed. While
   review is pending, report the request URL and that the old snapshot remains
   authoritative. Do not imply the GitHub release has already updated the catalog.

## Re-verify the same snapshot

Use the same current form with action `Verify the currently listed snapshot` and
the exact registry `listingValidatedCommit`. This does not promote newer source.
The target must match the recorded snapshot even when upstream has advanced.
Read the live guide for automatic versus `maintainer-verified` review paths.
The optional **standard installation** action is a separate request to remove a
manual-install override, not part of ordinary plugin updates; do not select or
attest to it unless that is the actual task and its requirements are met.

## Interpret results and finish

For the initial omastart code the baseline detected `installer` and
`service-management`, without findings. Those are legitimate capabilities:
optional local snapshot installation and user-manager metadata/enablement work.
Do not rename files, hide `systemctl`, remove protections, or change facts to avoid
a capability review. New code may produce a different report; inspect it.

- Compatibility failure or actionable baseline finding: fix the actual problem,
  validate and publish a new candidate within scope, then refresh the existing
  request with its new SHA. Changed code needs new evidence.
- Complete `review-required`: maintainer acceptance is needed. An issue comment
  by the plugin author cannot grant verification.
- Incomplete scan, stale SHA, or policy mismatch: resolve the reported cause and
  retry the same request once evidence changes. Do not blindly rerun old approvals.
- Registry publication succeeded but deployment/finalization failed: report the
  failed phase for maintainer recovery. Do not resubmit or reapply approval labels.

Poll a bounded number of times, reading actual bot comments rather than relying
only on overall Actions success. When only maintainer review remains, stop and
report the URL/status. Verification covers the exact recorded commit and is not
a security audit. Native Omarchy install/update currently follows mutable HEAD;
changing a tag or releasing assets does not alter that boundary.

# SharePoint design artifacts

This directory is a **design artifact**, not executable infrastructure —
building the real site requires a SharePoint Online tenant, which is
REQUIRES CORPORATE ACCESS. It exists so setting the real site up later is a
matter of following exact, already-decided column definitions rather than
re-deriving them.

- `lists/Applications.json`, `lists/DocumentationJobs.json`,
  `lists/DocumentationVersions.json`, `lists/Configuration.json` — exact
  column names, types, choices, and notes for each list. These mirror
  `worker/models.py` field-for-field; keep both in sync if either changes.
- `provisioning/provision-lists.ps1` — a PnP PowerShell script that creates
  the lists and document library from the JSON definitions above. **Not run
  or validated in this repository** (REQUIRES CORPORATE ACCESS) — review it
  carefully and run it against a non-production site first.

## Document library

`PowerPlatformDocumentation/` with per-application, per-version
subfolders, matching `MockSharePointAdapter`'s local mirror exactly:

```
PowerPlatformDocumentation/
    <ApplicationName>/
        <version>/
            snapshot.json
            solution-info.json
            diff.json
            technical-documentation.md
            user-guide.md
    _jobs/
        <job-id>/
            copilot-prompt.md      (when using HumanReviewCopilotAdapter)
            context.json
    _templates/                    (reserved; not used by the MVP)
    _logs/                         (reserved; not used by the MVP — the
                                     worker logs locally, see SECURITY.md)
```

## Column-name discipline

Every column name here is treated as a stable contract with
`worker/adapters/sharepoint/`. If a real tenant naming convention forces a
different internal name (SharePoint sometimes mangles internal names,
e.g. spaces become `_x0020_`), record the mapping in
`docs/SHAREPOINT_SETUP.md` rather than changing the display names here.

## Permissions

The worker's service account needs Contribute on this site/these lists/this
library only — see SECURITY.md "Least privilege". Do not grant Full Control
or Site Collection Administrator "to be safe."

# SharePoint Setup

**Status: REQUIRES CORPORATE ACCESS.** Nothing here has been provisioned or
tested against a real SharePoint Online tenant. This document plus
`sharepoint/lists/*.json` and `sharepoint/provisioning/provision-lists.ps1`
are the complete, reviewed spec for doing so once access exists.

## Exact list/column definitions

See `sharepoint/lists/*.json` for the authoritative column names, types,
choices, and notes for `Applications`, `DocumentationJobs`,
`DocumentationVersions`, and (optional) `Configuration`. Do not improvise
different column names — `worker/adapters/sharepoint/real.py` will need to
match them exactly.

## Provisioning options, in order of preference

1. **PnP PowerShell script** (`sharepoint/provisioning/provision-lists.ps1`)
   — reads the JSON definitions and creates lists/columns/library via the
   [PnP.PowerShell](https://pnp.github.io/powershell/) module. Untested
   against a real tenant — review before running; run against a
   non-production/test site first.
2. **Manual creation** via the SharePoint UI, using the JSON files as your
   checklist. More tedious but zero script risk — reasonable for a
   first-time setup.

## Document library

Create a document library named `PowerPlatformDocumentation`. No special
column configuration needed beyond the default — the worker addresses files
by path (`<AppName>/<version>/<filename>`), not by library metadata
columns. Pre-create the `_jobs`, `_templates`, `_logs` folders (the
provisioning script does this).

## Internal name mangling

SharePoint sometimes rewrites a column's *internal* name (used by
CSOM/REST/Graph) differently from its *display* name — most commonly when
the display name contains a space (e.g. `Application Id` might become
internal name `Application_x0020_Id`). Use **single-word or PascalCase
display names with no spaces** for every custom column (already done in
`sharepoint/lists/*.json`) specifically to avoid this problem. If a mismatch
still occurs, record the actual internal name here:

| Display name | Internal name (fill in once known) |
|---|---|
| _(none identified yet — verify after first provisioning run)_ | |

## Claim/idempotency semantics for the real adapter

`MockSharePointAdapter.claim_job()` does a read-modify-write against a local
JSON file, which is atomic enough for a single mock process but is **not**
a substitute for real concurrency control. `RealSharePointAdapter.claim_job()`
must use SharePoint's optimistic concurrency (an `If-Match: <etag>`
conditional update, or Graph API's equivalent) so that if two worker
instances race to claim the same job, only one update succeeds and the
other observes a conflict and moves on. Verify the exact mechanism against
whichever client library is chosen (see below) before implementing.

## Client library choice — NOT decided yet

Do not pick a library before corporate access allows verifying what's
actually available/permitted. Candidates to evaluate once you have access:

- **Microsoft Graph API** (`/sites/{site-id}/lists/{list-id}/items`) via
  `msgraph-sdk` (Python) — likely the most future-proof, standard approach.
- A SharePoint REST API wrapper — viable if Graph access isn't granted for
  some reason.

Whichever is chosen, `RealSharePointAdapter` (see
`worker/adapters/sharepoint/real.py`) must implement the exact
`SharePointAdapter` interface so nothing above it changes.

## Permissions

See SECURITY.md "Least privilege". The worker's service account/app
registration needs Contribute (read+write items, read+write files) on this
one site's lists and library — nothing tenant-wide.

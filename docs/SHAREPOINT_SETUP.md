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

1. **`scripts/provision_sharepoint_graph.py`** — Python + Microsoft Graph,
   **verified working end-to-end** (2026-09) against a real SharePoint
   site on a personal test tenant. Created all 4 lists with exact columns,
   the cross-list `Application` lookup, the `PowerPlatformDocumentation`
   library, and its `_jobs`/`_templates`/`_logs` folders — idempotent,
   safe to re-run. Needs:
   - An Azure AD app registration: Entra admin center → App registrations
     → New → API permissions → Microsoft Graph → **Application
     permissions** → `Sites.Manage.All` → **Grant admin consent**. Create
     a client secret.
   - `pip install msal requests` (or `pip install -e ".[provisioning]"`).
   - A local, git-ignored `.env` at the repo root with `TENANT_ID`,
     `CLIENT_ID`, `CLIENT_SECRET`, `SHAREPOINT_SITE_URL` — never commit
     this file or paste its values anywhere.

   Known Graph API quirk (not a bug): `GET .../lists/{id}/columns`
   doesn't return the `hyperlinkOrPicture` facet for list-scoped columns
   even when the column was created correctly as that type — this is
   documented Graph behavior, not evidence of a failed creation.
2. **PnP PowerShell script** (`sharepoint/provisioning/provision-lists.ps1`)
   — reads the same JSON definitions and creates lists/columns/library via
   the [PnP.PowerShell](https://pnp.github.io/powershell/) module.
   Untested against a real tenant — review before running; run against a
   non-production/test site first.
3. **Manual creation** via the SharePoint UI, using the JSON files as your
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

## Claim/idempotency semantics — IMPLEMENTED and verified

`RealSharePointAdapter.claim_job()` (`worker/adapters/sharepoint/real.py`)
uses SharePoint's optimistic concurrency: it reads the job item's
`@odata.etag` and issues a conditional `PATCH` with `If-Match: <etag>`. If
another worker claimed the job first, the etag no longer matches and the
conditional update fails, which `claim_job()` treats as "already claimed"
(returns `False`) rather than raising. This was exercised in a live smoke
test (a second `claim_job()` call on an already-claimed job correctly
returned `False`), but a genuine concurrent-write race (two workers
claiming at the *same instant*) has not been reproduced — the logic is
correct per Graph's documented ETag semantics, not empirically raced.

## Client library — DECIDED and verified: Microsoft Graph

**Microsoft Graph** (`/sites/{site-id}/lists/{list-id}/items`, app-only
auth via `msal`) is what `RealSharePointAdapter` uses
(`worker/adapters/sharepoint/graph_client.py`), verified end-to-end
against a real personal test tenant — including a full real
`JobProcessor` pipeline run (see `ROADMAP.md` Milestone 6). Two real Graph
quirks found and worked around, documented in
`worker/adapters/sharepoint/real.py`'s module docstring:

- List-item writes with an explicit `null` for an unset `dateTime` field
  return an opaque `500` — omit unset fields from the write payload
  entirely instead (`_drop_none()` in `real.py`).
- Writing a "Hyperlink or Picture" column via the list-items API failed
  with every shape tried (plain string, and the documented
  `{"Url": ..., "Description": ...}` object, in both Pascal and lowercase
  key casing) — root cause not identified. Worked around by changing
  `EnvironmentUrl`/`TechnicalDocumentationUrl`/`UserDocumentationUrl` to
  plain "Single line of text" columns (`sharepoint/lists/Applications.json`
  updated to match) rather than continuing to guess.

**Person/Group column writes — now implemented and verified (2026-09).**
`GraphClient.find_user_lookup_id()` queries the site's hidden "User
Information List" (`GET /sites/{id}/lists?$filter=displayName eq 'User
Information List'`, then filtering its items by `fields/EMail eq
'<email>'`) to resolve an email to a SharePoint user id, then
`RealSharePointAdapter` writes `{ColumnName}LookupId` (e.g.
`OwnerLookupId`) — confirmed against a real `Applications` item. The real
caveat, also verified: a person who has never visited this specific
SharePoint site doesn't exist in that list yet, and no Graph "ensure user
ahead of time" endpoint was found — resolution then returns `None` and
`RealSharePointAdapter` silently omits that field rather than failing the
write (a job requester who's never opened the site is an expected case,
not an error). Read-back does not resolve `{Column}LookupId` back to an
email — `Owner`/`BusinessOwner`/`RequestedBy`/`CreatedBy` read as empty
strings even when set; nothing in the pipeline depends on reading these
back, so this is a display-only gap, not a functional one.

## Permissions

**Used for one-off provisioning/verification so far**: an app registration
with Microsoft Graph **Application permission** `Sites.Manage.All` (admin
consent granted) — broader than the production worker should run as
long-term. See SECURITY.md "Least privilege": narrow this once corporate
access allows setting up a dedicated, minimally-scoped service identity
(Contribute on this one site's lists/library only — evaluate `Sites.Selected`
for the company tenant, which grants access to only the specific site
rather than every site in the tenant).

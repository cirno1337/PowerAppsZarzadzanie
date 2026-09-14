# Power Automate design artifact

Standard-connector-only flow definitions. No HTTP, Premium, or custom
connectors — see CLAUDE.md's no-Premium constraint. This is a **design
document**; building/publishing the real flows requires a Power Platform
environment (REQUIRES CORPORATE ACCESS).

**Principle (ADR-003): these flows are notification-only. SharePoint list
state is the source of truth regardless of whether a flow runs, succeeds,
or is even enabled.**

## Flow 1 — Job status notification

**Trigger:** SharePoint "When an item is created or modified" on
`DocumentationJobs` (standard SharePoint connector).

**Condition:** `Status` changed to one of `COMPLETED`, `FAILED`,
`NEEDS_HUMAN_REVIEW` (compare trigger output's `Status` against a stored
previous value, or simply notify on every modification touching `Status` —
decide based on how noisy that proves in practice; document the final choice
here once built).

**Actions:**
1. Get the related `Applications` item (SharePoint "Get item", using the
   `Application` lookup's ID) to fetch `Title` and `Owner`.
2. Office 365 Outlook "Send an email (V2)" to `RequestedBy` (and `Owner` for
   FAILED/NEEDS_HUMAN_REVIEW), subject like
   `[Power Platform Docs] <Application Title> - <Action> - <Status>`, body
   summarizing `ResultSummary` or `ErrorMessage`. Never include `EnvironmentUrl`
   or any other REQUIRES TENANT CONFIGURATION value that hasn't been reviewed
   for sensitivity.

**Explicitly out of scope:** any HTTP action, any Premium connector, any
Dataverse action.

## Flow 2 — (optional) Stale job reminder

**Trigger:** Recurrence (standard), e.g. every 4 hours.

**Actions:**
1. SharePoint "Get items" on `DocumentationJobs` filtered to `Status eq
   'RUNNING'` and `StartedAt` older than a threshold (e.g. 2 hours) —
   catches a job whose worker crashed without updating status. Compute the
   filter/threshold using Power Automate expressions (`addHours(utcNow(),
   -2)`), all standard.
2. For each stale job: SharePoint "Update item" to reset `Status = PENDING`,
   clear `WorkerId`/`StartedAt` (mirrors the idempotent retry behavior the
   worker itself implements in `worker/job_processor.py`, as a Power
   Automate-level safety net if the worker process itself dies uncleanly).
3. Optional: Office 365 Outlook notification to an admin distribution list.

This flow is optional for MVP — the worker's own retry logic handles most
failure modes; this only helps if the worker process itself dies mid-job
without a chance to update its own status.

## Flow 3 — (optional) New application registered notification

**Trigger:** SharePoint "When an item is created" on `Applications`.

**Actions:** Office 365 Outlook notification to an admin group, so someone
reviews new registrations (naming, ownership) even though the Power App
lets any authorized user self-register an application.

## Connector inventory (for the no-Premium check)

| Connector | Type | Used for |
|---|---|---|
| SharePoint | Standard | Triggers + Get/Update item across all flows |
| Office 365 Outlook | Standard | Email notifications |
| Approvals | Standard | Not used by these flows (the *documented application's own* flows may use it — that's the application being documented, not this tool) |

No connector above requires Premium licensing.

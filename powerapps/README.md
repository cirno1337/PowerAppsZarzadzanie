# Power Apps design artifact

This is a **design document**, not a buildable `.msapp` — building and
publishing the real canvas app requires a Power Platform environment
(REQUIRES CORPORATE ACCESS / REQUIRES TENANT CONFIGURATION). Everything
below is concrete enough to build directly once an environment exists: every
screen, control, and Power Fx formula references the exact SharePoint
columns in `sharepoint/lists/*.json`.

**Principle (see CLAUDE.md): Power Apps never executes PowerShell and never
calls the worker directly. Every action below is a SharePoint list
write/read — nothing else.**

Connect the app to the four SharePoint lists as data sources:
`Applications`, `DocumentationJobs`, `DocumentationVersions`,
`Configuration` (optional).

## Screens

### 1. Dashboard

Landing screen. Shows counts and recent activity.

- Gallery `galRecentJobs`: `SortByColumns(DocumentationJobs, "RequestedAt", Descending)`, first 10.
- Label counts, e.g. pending jobs: `CountRows(Filter(DocumentationJobs, Status = "PENDING"))`.
- Label counts, e.g. apps needing attention: `CountRows(Filter(Applications, DocumentationStatus = "UPDATE_AVAILABLE"))`.
- Navigation buttons to Applications, Job History.

### 2. Applications

List of registered applications.

- Gallery `galApplications`: `SortByColumns(Filter(Applications, Active = true), "Title", Ascending)`.
- Search box `txtSearch`: wrap the gallery's `Items` in
  `Filter(Applications, Active = true, StartsWith(Title, txtSearch.Text) || StartsWith(SolutionName, txtSearch.Text))`.
- Selecting a row navigates to Application Details:
  `Navigate(ApplicationDetails, ScreenTransition.Cover, {SelectedApplication: ThisItem})`.
- Button "Register Application" → `Navigate(RegisterApplication)`.

### 3. Application Details

- Header shows `SelectedApplication.Title`, `.SolutionName`, `.Environment`,
  `.CurrentVersion`, `.DocumentationStatus`.
- Buttons:
  - "Request Documentation" (enabled when `DocumentationStatus =
    "NOT_DOCUMENTED"`) → `Navigate(RequestDocumentation, ScreenTransition.Cover, {SelectedApplication: SelectedApplication})`.
  - "Request Update" (enabled otherwise) → `Navigate(RequestUpdate, ScreenTransition.Cover, {SelectedApplication: SelectedApplication})`.
  - "Analyze current version" — creates an `ANALYZE_SOLUTION` job directly
    (no extra screen needed since it takes no additional input):
    ```
    Patch(DocumentationJobs, Defaults(DocumentationJobs), {
        Title: SelectedApplication.Title & " - ANALYZE_SOLUTION - " & Text(Now(), "yyyy-mm-dd-hh-mm-ss"),
        Application: SelectedApplication,
        Action: "ANALYZE_SOLUTION",
        RequestedBy: User(),
        RequestedAt: Now(),
        Status: "PENDING",
        RetryCount: 0
    });
    Notify("Analysis requested.", NotificationType.Success)
    ```
  - "Open Technical Documentation" → `Launch(SelectedApplication.TechnicalDocumentationUrl)`.
  - "Open User Documentation" → `Launch(SelectedApplication.UserDocumentationUrl)`.
  - "View Version History" → `Navigate(VersionHistory, ScreenTransition.Cover, {SelectedApplication: SelectedApplication})`.

### 4. Register Application

Form (`Edit` form or manual `Patch`) collecting: Title, ApplicationId,
SolutionName, Environment, EnvironmentUrl, Owner, BusinessOwner,
Description.

```
Patch(Applications, Defaults(Applications), {
    Title: txtTitle.Text,
    ApplicationId: txtApplicationId.Text,
    SolutionName: txtSolutionName.Text,
    Environment: ddEnvironment.Selected.Value,
    EnvironmentUrl: txtEnvironmentUrl.Text,
    Owner: {'@odata.type': "#Microsoft.Azure.Connectors.SharePoint.SPListExpandedUser", Claims: User().Email, ...},
    BusinessOwner: ...,
    Description: txtDescription.Text,
    DocumentationStatus: "NOT_DOCUMENTED",
    Active: true
})
```

_(The exact `Person` column patch shape depends on the connector version —
verify against the real environment; see docs/POWER_PLATFORM_SETUP.md.)_

### 5. Request Documentation

Confirms the request for an application whose `DocumentationStatus =
"NOT_DOCUMENTED"`. On submit, creates a `DOCUMENT_APPLICATION` job:

```
Patch(DocumentationJobs, Defaults(DocumentationJobs), {
    Title: SelectedApplication.Title & " - DOCUMENT_APPLICATION - " & Text(Now(), "yyyy-mm-dd-hh-mm-ss"),
    Application: SelectedApplication,
    Action: "DOCUMENT_APPLICATION",
    RequestedBy: User(),
    RequestedAt: Now(),
    Status: "PENDING",
    RetryCount: 0
});
Navigate(ApplicationDetails, ScreenTransition.Cover, {SelectedApplication: SelectedApplication})
```

### 6. Request Update

Same shape as Request Documentation but `Action: "UPDATE_DOCUMENTATION"`,
enabled for applications already documented.

### 7. Version History

- Gallery `galVersions`: `SortByColumns(Filter(DocumentationVersions, Application.Id = SelectedApplication.ID), "Created", Descending)`.
- Each row shows Version, ChangeSummary (first line), DocumentationImpact.
- Selecting a row shows the full `ChangeSummary` and links to
  `TechnicalDocumentationPath` / `UserDocumentationPath`.

### 8. Job History

- Gallery `galJobs`: `SortByColumns(Filter(DocumentationJobs, Application.Id = SelectedApplication.ID), "RequestedAt", Descending)`.
- Shows Action, Status, RequestedAt, CompletedAt, ErrorMessage (if FAILED).
- "Retry failed job" button, visible when `Status = "FAILED"`:
  ```
  Patch(DocumentationJobs, ThisItem, {Status: "PENDING", ErrorMessage: Blank(), RetryCount: 0})
  ```
  (Resets `RetryCount` deliberately — a manual retry from a human is a new
  attempt cycle, not a continuation of the automatic retry budget.)

### 9. Admin/Diagnostics

- Read-only view of `Configuration` list (if used).
- Counts of jobs by `Status` (a small chart or set of labels).
- Link to this repository's `docs/TROUBLESHOOTING.md` for support staff (as
  static text/documentation link, not a live fetch).

## What is NOT built here

No `.msapp` file, no published environment, no live data connections — all
REQUIRES CORPORATE ACCESS / REQUIRES TENANT CONFIGURATION. This document is
the complete, reviewed spec for building it once an environment exists.

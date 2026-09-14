# CLAUDE.md — Power Platform Documentation Manager

This file is the standing operating guide for any Claude Code session working
in this repository. The original project brief (the prompt that created this
repository) is preserved in git history as the initial commit and summarized
in `ARCHITECTURE.md` / `DECISIONS.md`. This file is intentionally the
*working* reference, not the brief itself.

## What this project is

An internal system that automatically documents and versions Microsoft Power
Platform applications/solutions. A Power App lets users register applications
and request documentation. SharePoint Online lists are the source of truth
for job state and application metadata. A Python worker polls SharePoint for
pending jobs, uses the Power Platform CLI to export/unpack solutions,
normalizes them into a deterministic JSON representation, computes a semantic
diff against the previous version, assesses documentation impact, optionally
calls Copilot (or falls back to a human-in-the-loop step), generates
Markdown technical documentation and a user guide, and writes everything back
to SharePoint.

**Hard constraint:** no Dataverse, no Premium/custom connectors, no HTTP
connector in Power Automate, no paid SaaS, no Azure services unless
explicitly opted into later. SharePoint Online + standard Power Automate
connectors + Power Apps + Power Platform CLI + PowerShell + a worker process
are the only assumed platform pieces.

**Hard requirement:** the entire system must build, run, and be tested on a
personal/offline machine with zero corporate network access, using mock
adapters. Real integration is added later behind the same interfaces.

## Repository structure

```
CLAUDE.md                  this file
ARCHITECTURE.md            system design, component responsibilities
DECISIONS.md               ADRs
ROADMAP.md                 milestones and status
SECURITY.md                security model
README.md                  project overview for GitHub
CONTRIBUTING.md            contribution/dev workflow notes

docs/                      deep-dive docs (see docs/ for the index)
worker/                    Python worker (the only executable backend code)
examples/mock_solution/    mock Power Platform export data, v1.0 and v1.1
scripts/                   setup/run/demo/test entry points (bash + PowerShell)
config/                    non-secret configuration templates
sharepoint/                list schemas + provisioning script (design artifact)
powerapps/                 screen/formula design artifacts (no real .msapp)
powerautomate/             flow design artifacts (no real flow package)
```

`worker/` internal layout:

```
worker/
    main.py                 polling loop entry point
    config.py                environment-based configuration, no secrets in code
    models.py                enums + dataclasses shared across the worker
    job_processor.py         orchestrates one job's lifecycle
    queue/                   thin job-queue wrapper over a SharePointAdapter
    adapters/
        powerplatform/       PowerPlatformAdapter: base + mock + real (placeholder)
        copilot/              CopilotAdapter: base + mock + human_review + real (placeholder)
        sharepoint/           SharePointAdapter: base + mock (local JSON) + real (placeholder)
    normalization/            raw export -> deterministic normalized schema
    diff/                     semantic diff engine + documentation impact rules
    versioning/               version-number policy
    documentation/            Markdown generation (technical doc, user guide, change summary)
    logging_setup.py          logging configuration, no secrets in log output
    tests/                    pytest suite (unit + integration pipeline test)
```

## Architectural principles

- **SharePoint is the source of truth for job state.** Email/Power Automate
  notifications are side effects, never the queue.
- **Every external system sits behind an adapter interface** with at least a
  mock implementation: `PowerPlatformAdapter`, `CopilotAdapter`,
  `SharePointAdapter`. Business logic in `worker/` never imports a vendor SDK
  or shells out to `pac`/PowerShell directly — it calls the adapter
  interface. Only the `real.py` module inside each adapter package is allowed
  to do that.
- **Copilot is optional, not required.** The worker must fully function with
  `HumanReviewCopilotAdapter` (or `MockCopilotAdapter` for local dev). Nothing
  in the pipeline may assume a specific Copilot product, API, or MCP
  availability — those are unverified until corporate access exists.
- **Never send raw solution ZIPs/arbitrary files to Copilot.** Only the
  normalized JSON representation (or a subset of it) goes into any prompt.
- **Normalization must be deterministic**: stable key ordering, stable list
  ordering (sort by name/id), no timestamps or GUIDs that change between
  identical exports. This is what makes diffs and version comparisons
  meaningful and makes `git diff` on snapshot files useful.
- **The diff engine is semantic, not textual.** It compares normalized
  structures field-by-field per component type and emits a structured diff
  (see `worker/diff/engine.py` and `ARCHITECTURE.md`), never a raw text diff
  of JSON.
- **Documentation impact analysis is rule-based and deterministic first.**
  Copilot may refine/override it, but the deterministic rules
  (`worker/diff/impact.py`) must produce a reasonable answer with zero AI
  involvement, because AI involvement is not guaranteed to be available.
- **Idempotency and safe retries are required**, not optional polish. A job
  re-picked up after a crash must not produce duplicate documentation
  versions or duplicate SharePoint writes.

## Coding conventions

- Python 3.11+, standard library first. Only add a dependency if the mock
  path genuinely needs it (currently: `pytest` for tests only — the worker
  runtime itself has zero third-party dependencies so it stays installable
  without network access). If a real adapter later needs an SDK (e.g. an
  Office365/Graph client, `pac` CLI), add it as an optional extra, not a hard
  dependency of the mock path.
- Adapters are plain classes implementing an `abc.ABC` base with explicit
  method signatures — no dependency-injection framework, no metaclass magic.
- Dataclasses (`@dataclass`) for all structured records (`Job`, `Application`,
  `DocumentationVersion`, normalized schema nodes, diff entries).
- No secrets, tenant IDs, SharePoint URLs, or environment names hard-coded
  anywhere in `worker/`, `config/`, `examples/`, or docs. Configuration comes
  from environment variables read in `worker/config.py`, with `.env.example`
  documenting the variable names only.
- Keep generated Markdown deterministic given the same inputs — tests assert
  on structure/section presence, not on exact prose, since Copilot-refined
  runs will vary but mock/deterministic runs should not.
- Every module that touches a real Microsoft service must have a module or
  class docstring stating whether it is `MOCKED`, `REQUIRES CORPORATE
  ACCESS`, `REQUIRES TENANT CONFIGURATION`, or `REQUIRES LICENSING
  VERIFICATION`.

## Testing requirements

- Run tests with `./scripts/run-tests.sh` (wraps `pytest worker/tests`).
- Every new adapter, normalization rule, diff rule, or impact rule needs a
  unit test.
- The integration test (`worker/tests/test_integration_pipeline.py`) must
  keep passing: register application → document v1.0 → detect v1.0→v1.1
  changes → compute impact → regenerate docs → update version history →
  produce a change summary. Do not weaken this test to make unrelated work
  pass; fix the underlying code instead.
- Never mark an integration with a real Microsoft service as tested unless it
  was actually exercised against that service. Mock-path tests prove the
  mock path only — say so in commit messages/PR descriptions.

## Security requirements

See `SECURITY.md` for the full model. In short: no credentials in Git,
config files, SharePoint list values, prompts, or generated docs; worker
config comes from environment variables or an OS-level secret store; log
output must never contain secrets or full solution contents; least-privilege
SharePoint/Power Platform permissions for the worker's service account.

## Working with mock data

- `examples/mock_solution/<AppName>/v1.0/` and `v1.1/` are the canonical mock
  export fixtures. `v1.1` must contain realistic, intentional changes from
  `v1.0` (see `examples/mock_solution/README.md` for the change list) so the
  diff/impact/versioning pipeline has something real to detect.
- `MockPowerPlatformAdapter` reads directly from `examples/mock_solution/`
  and treats each version directory as an already-unpacked solution (no real
  zip handling needed for the mock path).
- `MockSharePointAdapter` persists lists and the document library as local
  JSON/Markdown files under a runtime data directory (default
  `.local_data/`, git-ignored). It is a faithful enough stand-in that
  `job_processor.py` cannot tell it apart from a future real adapter at the
  interface level.
- `./scripts/demo.sh` runs the full mock pipeline end-to-end and prints a
  summary. Use it to sanity-check changes quickly.

## Working with real Power Platform (when corporate access exists)

- Do not implement `real.py` adapter internals speculatively. Follow
  `docs/CORPORATE_SETUP.md` to gather real facts first (environment URLs,
  SharePoint site, licensing, permissions).
- The real Power Platform adapter should wrap the actual `pac` CLI
  (authenticate, solution export/unpack, metadata extraction) via
  `subprocess`, translating CLI output into the same return types the mock
  adapter produces, so `job_processor.py` and everything above it needs zero
  changes.
- The real SharePoint adapter should use an approach validated against the
  actual tenant (e.g. Microsoft Graph or a supported SharePoint REST/CSOM
  library) — do not guess the client library before corporate access
  confirms what's permitted/available.
- Switching from mock to real must be a configuration change
  (`PPDM_ENVIRONMENT=real` or similar in `worker/config.py`), never a code
  change to `job_processor.py` or anything in `normalization/`, `diff/`,
  `versioning/`, or `documentation/`.

## What must NEVER be assumed

- That Dataverse, Premium connectors, or an HTTP connector are available —
  they are explicitly out of scope unless the user gives explicit approval.
- That any specific Copilot product, API, or MCP server is licensed or
  reachable. This is unverified until confirmed in the corporate tenant
  (see `docs/COPILOT_INTEGRATION.md`).
- That a specific worker execution host (VM, server, scheduled task, service
  account) will be used in production. Keep worker startup/config host-
  agnostic (`worker/main.py` + `worker/config.py`, no OS-specific paths
  outside `scripts/*.ps1` vs `scripts/*.sh`).
- That the corporate tenant's SharePoint site URL, list internal names, app
  IDs, or environment URLs are known. All of these are placeholders read
  from configuration, never literals in code or docs (docs use `<placeholder>`
  syntax explicitly).
- That a real integration "probably works" because the mock path works. Mock
  passing tests prove the mock path only.

## How Copilot integration is isolated

`worker/adapters/copilot/base.py` defines `CopilotAdapter` with
`analyze_changes()`, `generate_technical_documentation()`,
`generate_user_documentation()`, `generate_change_summary()`. Three
implementations exist:

1. `MockCopilotAdapter` — deterministic, template-based, no network calls.
   Used for local development and tests.
2. `HumanReviewCopilotAdapter` — writes a ready-to-run prompt file to the
   local output directory (and, via `SharePointAdapter`, to
   `_jobs/<job-id>/copilot-prompt.md`), sets the job to
   `NEEDS_HUMAN_REVIEW`, and exposes a method to ingest a human-pasted result
   to resume processing.
3. `RealCopilotAdapter` — placeholder only. Raises `NotImplementedError`
   with a message pointing at `docs/COPILOT_INTEGRATION.md`. Do not implement
   its body until that document's verification checklist has been completed
   against the real tenant.

`job_processor.py` selects the adapter via `worker/config.py`
(`PPDM_COPILOT_MODE=mock|human_review|real`), defaulting to `mock` for local
development.

## How SharePoint is used

- **Applications list**: one row per registered Power Platform
  application/solution; current version, documentation status, and links to
  the latest generated docs live here.
- **DocumentationJobs list**: the job queue. Power Apps creates rows here;
  the worker polls for `Status = PENDING`, claims a row by setting `Status =
  RUNNING` + `WorkerId` + `StartedAt`, and updates it through to
  `COMPLETED`/`FAILED`/`NEEDS_HUMAN_REVIEW`.
- **DocumentationVersions list**: one row per generated documentation
  version per application, with the change summary and paths into the
  document library.
- **Document library** (`PowerPlatformDocumentation/<AppName>/<version>/`):
  `snapshot.json` (normalized representation), `solution-info.json` (raw
  metadata), `diff.json`, `technical-documentation.md`, `user-guide.md`. See
  `docs/SHAREPOINT_SETUP.md` for exact column definitions.
- The mock adapter reproduces this exact shape locally so the worker code
  path is identical between mock and real.

## How jobs are processed

See `worker/job_processor.py` and `ARCHITECTURE.md` for the full sequence
diagram. Summary: poll → claim (idempotent, atomic status transition) → run
action-specific pipeline → save artifacts → update SharePoint metadata and
version history → set terminal status → notify. Failures set `FAILED` with a
sanitized error message and increment `RetryCount`; jobs under the retry
limit are returned to `PENDING`, others stay `FAILED` for human attention.

## How versioning works

See `worker/versioning/version.py` and `ARCHITECTURE.md`. Summary: no
detected changes → no new version. Any detected change with impact `LOW`,
`MEDIUM`, or `HIGH` → minor version bump (`1.0` → `1.1` → `1.2`). A major
version bump (`x.0`) is a deliberate decision, not automatically derived from
diff heuristics — it is triggered explicitly (e.g. an administrator marking a
release as major), because inferring "this deserves a new major version"
purely from a diff is unreliable. Document any change to this policy in
`DECISIONS.md`.

## How to update documentation generation

- Section lists for technical documentation and the user guide are fixed by
  the project brief (see `ARCHITECTURE.md`); do not silently drop a required
  section even if content is thin — write "Not applicable" rather than
  omitting the heading, so downstream consumers can rely on a stable
  structure.
- Prefer improving `normalization/` or `diff/` to get better input data over
  adding special-casing inside `documentation/generator.py`.

## How to make architectural decisions

- If a decision changes the no-Premium constraint, adds a new external
  dependency, or changes an adapter interface, write an ADR in
  `DECISIONS.md` before implementing it.
- Prefer the smallest change that keeps the mock and real paths behind the
  same interface.

## When to ask the user questions

- Before doing large, expensive, or hard-to-reverse work whose shape isn't
  already specified here or in `ROADMAP.md`.
- Before adding a new third-party dependency, especially anything that would
  require network access to install, or anything that touches the
  no-Premium constraint.
- Before committing to a specific real-world SharePoint/Power Platform CLI
  library choice — that should follow the corporate verification checklist,
  not a guess made offline.

## When to stop and request corporate information

Stop and create a documented placeholder (never guess) when a task requires:
tenant IDs, SharePoint site URLs, environment URLs, actual license/SKU
information, actual Copilot product availability, actual PAC CLI output
against a real environment, or any credential. Continue building/testing the
mock path in the same session rather than blocking.

## How to avoid breaking the no-Premium requirement

- Before adding any Power Automate action, check it against the standard
  connector list (SharePoint, Office 365 Outlook, Approvals, Teams,
  scheduled/recurrence triggers are safe; anything requiring an HTTP,
  Premium, or custom connector is not).
- Before adding any Power Platform capability, ask "does this require
  Dataverse?" If yes, stop and get explicit approval first.
- Azure services (Key Vault, Functions, Logic Apps, etc.) are optional
  extensions only, always clearly marked as such, never required for the
  MVP to function.

## Do not do

DO NOT:
- introduce Dataverse without explicit user approval
- introduce Premium or custom connectors, or an HTTP connector in Power
  Automate, without explicit user approval
- hard-code tenant IDs, SharePoint site URLs, or environment URLs anywhere
  (code, docs, tests, examples) — use `<placeholder>` in docs and
  environment variables in code
- store credentials or secrets in Git, config files, README, SharePoint list
  values, prompts, or generated documentation
- invent undocumented Microsoft APIs or endpoints
- assume a specific Copilot API, Copilot Studio availability, or MCP server
  exists before it's verified in the corporate tenant
- assume VPN/corporate network is required for local development or tests
- couple business logic (normalization, diff, impact, versioning,
  documentation generation) directly to Power Apps or to a specific adapter
  implementation
- weaken or delete the mock integration test to make something else pass
- claim a real integration works without having actually exercised it

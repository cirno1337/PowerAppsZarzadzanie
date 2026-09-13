# Roadmap

Status legend: ✅ done and tested · 🚧 in progress · ⏳ not started · 🔒 blocked
on corporate access. Nothing is marked ✅ until it has actually been run
(tests passing, or `scripts/demo.sh` producing real output).

## Milestone 0 — Foundations

✅ Repository structure, `CLAUDE.md`, `ARCHITECTURE.md`, `DECISIONS.md`,
`SECURITY.md`, `ROADMAP.md` (this file), `README.md`, `CONTRIBUTING.md`.

## Milestone 1 — Mock architecture + vertical slice ✅ complete

Goal: a single command demonstrates the full pipeline end-to-end against
mock data with passing tests. `./scripts/demo.sh` does this; `./scripts/
run-tests.sh` runs 62 passing tests covering every item below.

- ✅ Data model (`worker/models.py`): `Job`, `Application`,
  `DocumentationVersion`, enums for action/status/impact.
- ✅ `PowerPlatformAdapter` interface + `MockPowerPlatformAdapter` (+
  `RealPowerPlatformAdapter` documented placeholder).
- ✅ `CopilotAdapter` interface + `MockCopilotAdapter` +
  `HumanReviewCopilotAdapter` (+ `RealCopilotAdapter` documented
  placeholder).
- ✅ `SharePointAdapter` interface + `MockSharePointAdapter` (local JSON +
  document library mirror) (+ `RealSharePointAdapter` documented
  placeholder).
- ✅ Normalization schema + normalizer.
- ✅ Semantic diff engine.
- ✅ Documentation impact analysis rules (matches all 5 worked examples in
  the project brief — see `worker/tests/test_impact_analysis.py`).
- ✅ Versioning policy.
- ✅ Documentation generator (technical doc, user guide, change summary).
- ✅ Job processor (poll/claim/execute/idempotency/retry) covering all 8
  job actions.
- ✅ Mock fixture data: `examples/mock_solution/InvoiceApproval/v1.0` and
  `v1.1` with realistic changes (10 distinct change types).
- ✅ Unit tests for every module above (54 unit tests).
- ✅ Integration test: v1.0 documented → v1.1 changes detected → impact
  computed → docs regenerated → version history updated → change summary
  produced (`worker/tests/test_integration_pipeline.py`).
- ✅ `scripts/setup.sh`, `scripts/demo.sh`, `scripts/run-tests.sh`,
  `scripts/run-worker.sh` + PowerShell equivalents for all four.

## Milestone 2 — SharePoint / Power Apps / Power Automate design artifacts ✅ complete

- ✅ `sharepoint/lists/*.json` — exact column definitions for `Applications`,
  `DocumentationJobs`, `DocumentationVersions`, `Configuration`.
- ✅ `sharepoint/README.md` + provisioning script placeholder (PnP PowerShell)
  — REQUIRES CORPORATE ACCESS to run.
- ✅ `powerapps/README.md` — screen-by-screen design with Power Fx formulas
  referencing the SharePoint schema above.
- ✅ `powerautomate/README.md` — standard-connector-only flow definitions
  (notification flow at minimum).

## Milestone 3 — Corporate bridge documentation ✅ complete

- ✅ `docs/CORPORATE_SETUP.md` — the 9-phase checklist for when VPN/tenant
  access returns.
- ✅ `docs/COPILOT_INTEGRATION.md` — what to verify before implementing
  `RealCopilotAdapter`.
- ✅ `docs/GETTING_STARTED.md`, `docs/LOCAL_DEVELOPMENT.md`,
  `docs/POWER_PLATFORM_SETUP.md`, `docs/SHAREPOINT_SETUP.md`,
  `docs/WORKER_SETUP.md`, `docs/DEPLOYMENT.md`, `docs/TROUBLESHOOTING.md`.

## Milestone 4 — Hardening the mock worker (not started)

⏳ Candidates once Milestones 1-3 land and are reviewed:

- ⏳ A continuous polling mode for `worker/main.py` with graceful shutdown,
  vs. the current single-pass mode used by the demo.
- ⏳ Structured logging with correlation IDs per job, still secret-free.
- ⏳ Configurable retry backoff and a dead-letter concept for jobs that
  exhaust retries.
- ⏳ More mock solutions/components (e.g. a second app) to stress-test the
  diff engine beyond the single fixture pair.
- ⏳ CI workflow (e.g. GitHub Actions) running `scripts/run-tests.sh` — only
  if/when the repo is pushed to a Git host; ask before adding, since it
  touches CI/CD config per the destructive-action guidance.

## Milestone 5 — Real Power Platform CLI integration 🚧 partially complete

🚧 `pac` CLI installed and verified interactively against a real,
non-production **personal test tenant** (2026-09) — see
`docs/POWER_PLATFORM_SETUP.md` "Real export structure — verified
findings" and `docs/CORPORATE_SETUP.md` Phase 2. `RealPowerPlatformAdapter`
now shells out to `pac` for `authenticate`/`list_solutions`/
`export_solution`/`unpack_solution` (`worker/adapters/powerplatform/
pac_cli.py`), and parses the real, verified export structure for
`get_solution_metadata` and part of `get_application_metadata` (flows,
environment variables, connection references —
`worker/adapters/powerplatform/xml_parsing.py`, unit tested against
synthetic fixtures mirroring the verified shape).

⏳ Still open: canvas apps/screens, Dataverse tables, security roles, and
generic components in `get_application_metadata` are **NOT YET VERIFIED**
against a real export (left as empty lists, not guessed — see
`worker/adapters/powerplatform/real.py` module docstring). 🔒 Full
production verification against the **company's actual tenant** (not the
personal test tenant used above) is still blocked on corporate access —
the personal-tenant verification proves the CLI/format facts but not the
company's specific environment names, permissions, or auth method (see
`docs/CORPORATE_SETUP.md` Phase 1).

✅ **Capstone validation**: ran the full `JobProcessor` pipeline with this
adapter (plus `RealSharePointAdapter`, see Milestone 6) end-to-end twice
against the real tenant — real export → unpack → normalize → diff →
version bump → doc generation → real SharePoint save, `COMPLETED` both
times. Found and fixed three real bugs this only surfaces against a real
`pac` CLI (all now covered by regression tests):
- `job_processor.py` was passing `Application.environment` (a label) to
  `export_solution()` instead of `Application.environment_url`, which
  `pac` actually needs.
- `authenticate()` always ran `pac auth create` (a fresh login) instead of
  reusing an existing matching auth profile — would hang a headless
  worker waiting on an interactive login with nowhere to complete. Fixed
  with `pac_cli.ensure_authenticated()` (`pac auth list` + `pac auth
  select`, falling back to `pac auth create` only if no profile matches).
- `pac solution export` errors if the output path already exists (no
  overwrite by default) — breaks idempotent re-runs/retries. Fixed by
  passing `--overwrite`.
- Flow display names retained part of the GUID (`rsplit("-", 1)` doesn't
  fully strip a real GUID, which contains its own internal hyphens) —
  fixed with a proper trailing-GUID regex.

## Milestone 6 — Real SharePoint integration ✅ implemented and verified end-to-end (personal test tenant)

✅ `RealSharePointAdapter` (`worker/adapters/sharepoint/real.py`) is fully
implemented on Microsoft Graph (app-only auth,
`worker/adapters/sharepoint/graph_client.py`) and verified against a real
site: application registry, job queue (create/claim/idempotent-reject/
update/get_pending), version history (create/list/sort/latest), and
document library upload/read — all proven via a live smoke test, not just
unit tests against a fake (35 unit tests total across both files, all
against a fake Graph client; separately, a live run against the real site
exercised every method for real). `claim_job` uses SharePoint's
`@odata.etag` for optimistic concurrency (an `If-Match` conditional PATCH)
— the mechanism `docs/SHAREPOINT_SETUP.md` called for.

**Capstone result**: ran the full `JobProcessor` pipeline —
register → create job → claim → **real `pac` CLI export/unpack** → real
XML/JSON parsing → normalize → diff against the previous **real** stored
snapshot → impact → version bump → generate docs (mock Copilot) →
**real** SharePoint save (snapshot/diff/docs to the document library,
`Applications`/`DocumentationVersions` list updates) → job `COMPLETED` —
twice, producing `1.0` then a correctly-detected `1.1`. This is the first
genuinely real, non-mocked run of the entire pipeline end-to-end (Copilot
excepted — see Milestone 7).

Known gaps, documented not guessed (see `worker/adapters/sharepoint/real.py`
module docstring): Person/Group columns (`Owner`, `BusinessOwner`,
`RequestedBy`, `CreatedBy`) are not populated — writing them via Graph
needs a separate, unverified user-resolution call. `EnvironmentUrl`/
`TechnicalDocumentationUrl`/`UserDocumentationUrl` were changed from
"Hyperlink or Picture" to plain "Single line of text" after every
attempted Graph write shape for the Hyperlink type failed (500 or 400,
no useful detail) — documented as an unresolved Graph quirk, not silently
worked around.

🔒 Still blocked on the **company's actual tenant** (this was all verified
against a personal test tenant) and a decision on the worker's long-term
service identity — the `Sites.Manage.All` app registration used here is
appropriate for one-off setup, not as the production worker's permanent
credential (see SECURITY.md "Least privilege").

## Milestone 7 — Real Copilot integration 🚧 implemented, blocked on tenant billing

🚧 `RealCopilotAdapter` (`worker/adapters/copilot/real.py`) is now fully
**IMPLEMENTED**: it builds the same prompt `HumanReviewCopilotAdapter`
uses, sends it via a real Direct Line client
(`worker/adapters/copilot/direct_line.py` — token exchange, conversation,
message post, watermark-based polling for the reply), and parses the
agent's delimited reply back into technical doc / user guide / change
summary. 18 new unit tests, all passing, using a mocked `requests`/
`direct_line` — no real tenant dependency for the test suite. Not the
newer Microsoft 365 Agents SDK — confirmed unsuitable since it lacks
unattended service-principal auth (see `docs/COPILOT_INTEGRATION.md`).

An agent on the personal test tenant was given real instructions matching
`RealCopilotAdapter`'s expected reply format, and a real Direct Line
secret was configured (by the tenant owner, via their own local `.env` —
never seen by Claude).

🔒 **Blocked on the tenant's Copilot Studio billing/capacity, not code**:
publishing the agent (required for Direct Line to serve anything beyond
the maker's own draft test chat) is disabled with a billing error on this
tenant. Empirically confirmed with `RealCopilotAdapter`'s own client:
token generation succeeds (the secret is valid) but starting a
conversation 404s, because the bot isn't actually running unpublished.
This is a distinct blocker from the earlier expired-trial one (that gated
configuration UI; this gates runtime capacity) — see
`docs/COPILOT_INTEGRATION.md` "Second blocker found". Resolving it is a
billing/procurement action for whoever administers the tenant, not
something to work around in code. May still resolve to "human-in-the-loop
is the permanent mode" if the company tenant's Copilot Studio capacity
doesn't support this — that remains an acceptable outcome, not a failure
state.

## Milestone 8 — Production deployment 🔒

🔒 Blocked on a company-approved execution host being chosen. Tracked in
`docs/DEPLOYMENT.md` and `docs/CORPORATE_SETUP.md` Phase 9.

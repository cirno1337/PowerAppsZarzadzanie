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

## Milestone 5 — Real Power Platform CLI integration 🔒

🔒 Blocked on corporate access. Tracked in `docs/CORPORATE_SETUP.md` Phase 2.
Implements `RealPowerPlatformAdapter` against a real, non-production
environment first.

## Milestone 6 — Real SharePoint integration 🔒

🔒 Blocked on corporate access + a decision on client library (Graph API vs.
another supported approach), made only after `docs/CORPORATE_SETUP.md`
Phase 1/3 are complete.

## Milestone 7 — Real Copilot integration 🔒

🔒 Blocked on licensing verification. Tracked in
`docs/COPILOT_INTEGRATION.md`. May resolve to "human-in-the-loop is the
permanent mode" rather than a programmatic adapter — that is an acceptable
outcome, not a failure state.

## Milestone 8 — Production deployment 🔒

🔒 Blocked on a company-approved execution host being chosen. Tracked in
`docs/DEPLOYMENT.md` and `docs/CORPORATE_SETUP.md` Phase 9.

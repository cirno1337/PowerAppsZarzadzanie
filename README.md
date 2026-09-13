# Power Platform Documentation Manager

An internal system for automatically documenting and versioning Microsoft
Power Platform applications and solutions — designed to run on **standard
Power Platform licensing (no Premium)** and to be **fully developable and
testable offline**, with every external integration isolated behind an
adapter interface.

> **Status: MVP / vertical slice.** The mock pipeline (registration →
> export → normalize → diff → impact analysis → documentation generation →
> version history) is implemented and tested end-to-end. Real Power
> Platform, SharePoint, and Copilot integrations are documented interfaces
> and placeholders — see "What's real vs. mocked" below.

## Why this exists

Power Platform applications tend to accumulate undocumented flows,
connections, and business logic over time. This tool automates the tedious
part — noticing what changed between versions and drafting documentation
from it — while keeping a human in the loop wherever full automation isn't
available (which, for a shop without Premium licensing and unverified
Copilot API access, is an explicit, first-class scenario rather than an
edge case).

## Architecture

```
Power Apps → SharePoint Online (source of truth for job/app state)
           → Power Automate (standard connectors, notification only)
           → Worker (Python)
                → Power Platform CLI (export/unpack)
                → Normalizer (deterministic JSON snapshot)
                → Diff Engine (semantic, not textual)
                → Documentation Impact Analysis (deterministic rules)
                → CopilotAdapter (Mock / HumanReview / Real-placeholder)
                → Documentation Engine (Markdown)
           → SharePoint Documentation Library
           → Power Automate notification → email
```

Full detail in [`ARCHITECTURE.md`](ARCHITECTURE.md); decisions and
trade-offs in [`DECISIONS.md`](DECISIONS.md).

## The no-Premium constraint

This project explicitly avoids Dataverse, Premium/custom connectors, the
HTTP connector in Power Automate, and Azure services (unless opted into
later). SharePoint Online lists are the "database"; a standalone worker
process does everything Power Apps/Power Automate can't. See ADR-001 in
`DECISIONS.md` for the reasoning.

## Copilot integration

No Copilot API is assumed to exist. `CopilotAdapter` is an interface with
three implementations: `MockCopilotAdapter` (deterministic, for local dev),
`HumanReviewCopilotAdapter` (writes a ready-to-paste prompt, marks the job
`NEEDS_HUMAN_REVIEW`, resumes once a human supplies the result — a fully
supported permanent mode, not a stopgap), and `RealCopilotAdapter` (an
unimplemented placeholder pending licensing verification — see
[`docs/COPILOT_INTEGRATION.md`](docs/COPILOT_INTEGRATION.md)).

## What's real vs. mocked

| Piece | Status |
|---|---|
| Normalization, diff engine, impact analysis, versioning, documentation generation, job processing (retries/idempotency) | **IMPLEMENTED** — real logic, tested |
| Power Platform CLI integration | **MOCKED** (reads local fixtures) — real adapter is a documented placeholder, REQUIRES CORPORATE ACCESS |
| SharePoint integration | **MOCKED** (local JSON + file mirror) — real adapter is a documented placeholder, REQUIRES CORPORATE ACCESS |
| Copilot integration | **MOCKED** + **human-in-the-loop implemented** — real adapter is a documented placeholder, REQUIRES LICENSING VERIFICATION |
| Power Apps / Power Automate | **Design artifacts only** (`powerapps/`, `powerautomate/`) — no environment exists to build/publish them yet |

Nothing here claims a real Microsoft integration works when it hasn't been
exercised against a real tenant.

## Quickstart (fully offline)

```bash
git clone <this-repo>
cd PowerAppsZarzadzanie
./scripts/setup.sh       # or scripts/setup.ps1 on Windows
./scripts/run-tests.sh    # 62 tests, ~1s
./scripts/demo.sh          # registers a mock app, documents v1.0, then v1.1
```

No network access, VPN, Microsoft account, or credentials required for any
of the above. See [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) for
more.

## Demo

`./scripts/demo.sh` runs the full pipeline against a realistic mock
"Invoice Approval" solution:

```
Register application
        ↓
Create documentation job (v1.0)
        ↓
Mock Power Platform export → normalize → generate docs
        ↓
Create update job (v1.1) → diff v1.0 vs v1.1 → analyze impact
        ↓
Mock Copilot → regenerate docs → update version history
        ↓
Print change summary + artifact paths
```

Sample change summary it produces:

```
Version: 1.1 (previous: 1.0)

Changes:
- Added screen "Invoice Approval App / EscalationScreen"
- Changed screen "Invoice Approval App / HomeScreen": controls changed ...
- Added flow "Invoice Escalation"
- Changed flow "Invoice Approval": timeout changed from 24h to 48h
- Added environment variable "EscalationTimeoutHours"
- Changed environment variable "ApprovalTimeoutHours": default value changed from '24' to '48'
- Added connection reference "shared_teams"
- Added dependency "Microsoft Teams"
- Added security role "Invoice Escalation Manager"
- Added component "EscalationBanner"
```

## Corporate deployment

When you regain access to your company's Power Platform/SharePoint tenant,
follow [`docs/CORPORATE_SETUP.md`](docs/CORPORATE_SETUP.md) — a 9-phase
checklist from "gather information" through "production readiness," written
so you never need to guess a real value offline.

## Security

See [`SECURITY.md`](SECURITY.md). Short version: no credentials in Git,
config, SharePoint values, prompts, or generated docs, ever; the worker's
service identity gets least-privilege access; logs never contain secrets or
full payloads.

## Limitations

- Real Power Platform CLI, SharePoint, and Copilot integrations are
  unimplemented placeholders pending corporate access/licensing
  verification (see the table above and `docs/CORPORATE_SETUP.md`).
- The mock SharePoint adapter's job-claiming is not a substitute for real
  optimistic-concurrency control needed with multiple worker instances
  against real SharePoint (documented in `docs/SHAREPOINT_SETUP.md`).
- Power Apps/Power Automate exist only as design documents — there's no
  Power Platform environment available to build/test them against yet.

## Roadmap

See [`ROADMAP.md`](ROADMAP.md) for milestones and status. Milestones 0-3
(foundations, mock vertical slice, SharePoint/Power Apps/Power Automate
design, corporate bridge docs) are complete; real integrations are tracked
as blocked-on-corporate-access milestones.

# Architectural Decision Records

## ADR-001: SharePoint instead of Dataverse

**Context.** The company does not hold Power Platform Premium licenses.
Dataverse-backed apps generally require Premium in this licensing
configuration. We still need structured, queryable storage for applications,
jobs, and version history, reachable from both Power Apps and a worker
process.

**Decision.** Use SharePoint Online lists (`Applications`, `DocumentationJobs`,
`DocumentationVersions`, optional `Configuration`) plus a SharePoint document
library for generated artifacts.

**Alternatives considered.**
- Dataverse: better relational modeling and delegation, but requires Premium
  — explicitly out of scope without approval.
- Azure SQL / Azure Table Storage: works, but pulls in an Azure dependency
  and a network path (VPN/firewall rules) that isn't guaranteed to exist;
  also a paid service running outside what's already licensed.
- Local database only (SQLite) with no cloud component: fails the
  requirement that Power Apps (a cloud-hosted client) can create job records
  without a custom API layer, which would itself require a premium/custom
  connector.

**Trade-offs.** SharePoint lists have weaker relational integrity, list
throttling limits, and less delegation power than Dataverse. Complex queries
(e.g. joins across lists) are harder. We accept this for MVP scale (a modest
number of applications and jobs).

**Consequences.** All list schemas must be designed for SharePoint's
column-type and lookup-column constraints (see `sharepoint/lists/*.json`).
If usage outgrows SharePoint list limits, revisit this ADR with a new one
rather than silently introducing Dataverse.

---

## ADR-002: Why a worker exists

**Context.** Power Apps/Power Automate (without Premium/HTTP connectors)
cannot invoke the Power Platform CLI, run PowerShell, do semantic diffing of
solution internals, or reliably call arbitrary AI services. That logic has
to run somewhere with a real OS process, filesystem, and CLI access.

**Decision.** Introduce a standalone worker process (initially Python) that
polls SharePoint for pending jobs and performs all heavy processing outside
the Power Platform sandbox.

**Alternatives considered.**
- Azure Functions/Logic Apps: would work but adds an Azure dependency
  explicitly marked optional/out-of-scope for MVP, and still can't easily
  shell out to `pac`/PowerShell in a locked-down consumption plan.
- Power Automate Desktop (RPA): plausible for UI automation but a poor fit
  for structured CLI/JSON processing; adds a licensing question of its own.

**Trade-offs.** Requires an always-or-periodically-running host somewhere
(a developer machine today, a company-approved host eventually) — this is
explicit, not hidden, per the deployment abstraction in `ARCHITECTURE.md`.

**Consequences.** The worker is the single place with real credentials for
Power Platform/SharePoint/Copilot, so it is also the single place security
requirements in `SECURITY.md` concentrate.

---

## ADR-003: Email is a notification mechanism, not the job queue

**Context.** It's tempting to trigger the worker via an incoming email or to
carry job state in an email body/subject.

**Decision.** SharePoint list state (`DocumentationJobs.Status`) is the only
source of truth for a job's state. Power Automate may send an email when a
job's status changes, purely as a courtesy notification to the requester.

**Alternatives considered.** Email-as-trigger: rejected — email delivery is
not guaranteed to be ordered/exactly-once, contains no atomic
claim/transition mechanism, and would require parsing free text to recover
structured state.

**Trade-offs.** None significant; email is strictly additive.

**Consequences.** The worker never reads job state from an inbox. Any
notification flow's failure must never be treated as a job failure and vice
versa — they are decoupled.

---

## ADR-004: Why Power Platform CLI access is isolated behind an adapter

**Context.** The worker must call `pac` (Power Platform CLI) commands
against a real environment eventually, but during development there is no
environment to call. We also want the ability to swap the underlying
mechanism (CLI vs. a future SDK) without touching business logic.

**Decision.** Define `PowerPlatformAdapter` as an abstract interface with
`MockPowerPlatformAdapter` (reads local fixture data) and a
`RealPowerPlatformAdapter` placeholder that documents intended `pac`
invocations but is not implemented against assumptions.

**Alternatives considered.** Calling `subprocess.run(["pac", ...])` directly
from job-processing code: rejected — makes the entire pipeline untestable
offline and couples business logic to a specific CLI's argument shape.

**Trade-offs.** An extra layer of indirection or two per call. Accepted —
this is exactly the seam that lets the project be built and tested without
corporate access, per the offline-first requirement.

**Consequences.** `RealPowerPlatformAdapter`'s method bodies are written
(and tested) only after corporate access allows verifying the actual `pac`
CLI behavior in the real tenant — see `docs/CORPORATE_SETUP.md` Phase 2.

---

## ADR-005: Why Copilot is isolated behind an adapter

**Context.** It is not yet known which Copilot product/API (if any) is
programmatically callable under the company's licensing. Building the
pipeline around an assumed API would likely be wrong and would block all
other development until that's verified.

**Decision.** Define `CopilotAdapter` with `MockCopilotAdapter`,
`HumanReviewCopilotAdapter`, and a `RealCopilotAdapter` placeholder. The
pipeline (diff → impact → docs) works completely without a real Copilot
call.

**Alternatives considered.** Assuming Microsoft Graph / Copilot Studio REST
API access and building against it now: rejected per explicit instruction —
"do not invent an unofficial API," and doing so risks building against a
product the company doesn't actually have licensed.

**Trade-offs.** Mock/human-review documentation quality is lower than a real
AI-refined pass would be. Accepted as an MVP trade-off; `docs/
COPILOT_INTEGRATION.md` defines exactly what to verify before implementing
`RealCopilotAdapter`.

**Consequences.** Nothing in `worker/` outside `adapters/copilot/` may
reference a specific Copilot product name or API shape.

---

## ADR-006: Why the system supports human-in-the-loop

**Context.** Even after corporate access exists, it may turn out no
programmatic Copilot invocation is available (e.g. only the Microsoft 365
Copilot chat UI is licensed, no agent/API access). The system must still be
useful in that world.

**Decision.** `HumanReviewCopilotAdapter` is a first-class, fully supported
mode — not a degraded fallback bolted on later. It generates a structured,
ready-to-paste prompt, marks the job `NEEDS_HUMAN_REVIEW`, and resumes
automatically once a human supplies the Copilot output.

**Alternatives considered.** Blocking the whole project on programmatic
Copilot access: rejected — violates "do not block development on corporate
access" and would make the tool useless if programmatic access turns out to
be unavailable.

**Trade-offs.** Slower turnaround per documentation update when this mode is
active (a human must run the prompt manually). Acceptable given the
alternative is no automation at all.

**Consequences.** The prompt format must be self-contained (includes
normalized data + diff + impact, not references to internal file paths a
human reviewer wouldn't have).

---

## ADR-007: Why normalized representations are used instead of raw ZIP diffs

**Context.** A Power Platform solution export is a ZIP of XML/JSON files
with non-deterministic ordering, GUIDs, and formatting noise unrelated to
actual functional changes. Diffing that directly (or feeding it to Copilot
directly) produces noisy, low-signal, and potentially oversized output.

**Decision.** Introduce a normalization layer (`worker/normalization/`) that
extracts only the semantically relevant fields into a deterministic JSON
schema, and diff/Copilot-feed that instead of the raw export.

**Alternatives considered.** Textual diff of unpacked XML/JSON: rejected —
produces changes like reordered attributes or regenerated GUIDs that have no
functional meaning, drowning out real changes. Sending the raw ZIP to
Copilot: explicitly rejected per project requirements (data volume, noise,
and potential sensitive-data exposure).

**Trade-offs.** Normalization must be maintained as Power Platform's export
format evolves, and anything not modeled in the normalized schema is
invisible to the diff engine. Accepted — the schema is designed to be
extended (see `ARCHITECTURE.md`), and gaps are a normalization bug to fix,
not a reason to fall back to raw diffing.

**Consequences.** `worker/normalization/normalizer.py` is the single place
that needs updating when a new Power Platform component type needs to be
tracked.

---

## ADR-008: Why the system is offline-first

**Context.** The developer currently has no corporate network access, and
the project must not stall because of that.

**Decision.** Every external dependency (Power Platform, SharePoint,
Copilot) has a mock implementation good enough to exercise the entire
pipeline end-to-end, with realistic fixture data
(`examples/mock_solution/v1.0`, `v1.1`) and a one-command demo
(`scripts/demo.sh`).

**Alternatives considered.** Building thin stubs that only satisfy type
signatures without real behavior: rejected — would not let the diff engine,
impact analysis, or documentation generation be meaningfully developed or
tested before corporate access exists.

**Trade-offs.** Mock implementations are additional code to write and
maintain, and must be kept behaviorally close enough to the real systems
that switching over doesn't reveal integration-shaped surprises. Mitigated
by keeping mocks behind the exact same interface as the real adapters.

**Consequences.** `docs/CORPORATE_SETUP.md` exists specifically to bridge
from "developed offline with mocks" to "connected to the real tenant" once
access returns, phase by phase, without redesigning the architecture.

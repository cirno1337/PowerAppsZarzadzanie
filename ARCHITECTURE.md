# Architecture — Power Platform Documentation Manager

## Status legend

Every capability below is tagged with one of:

- **IMPLEMENTED** — working code exists and is tested.
- **MOCKED** — working code exists, but only against a mock/fake backend.
- **REQUIRES CORPORATE ACCESS** — cannot be built/verified without the real
  tenant/network.
- **REQUIRES TENANT CONFIGURATION** — needs real values (site URLs, env
  names) that don't exist yet.
- **REQUIRES LICENSING VERIFICATION** — depends on which Microsoft 365 /
  Copilot / Power Platform license SKUs the company actually holds.

## System overview

```
Power Apps (thin client)
    |  writes job records
    v
SharePoint Online  <-- source of truth for job + application state
    |  standard trigger (item created/modified)
    v
Power Automate (standard connectors only)
    |  optional notification, NOT the queue
    v
Job Queue  == DocumentationJobs SharePoint list, Status column
    |  polled
    v
Worker (Python, runs locally or on a company host)
    |
    +--> PowerPlatformAdapter --> Power Platform CLI / PowerShell   [MOCKED locally, REQUIRES CORPORATE ACCESS for real]
    |
    +--> Normalizer            --> deterministic JSON snapshot       [IMPLEMENTED]
    |
    +--> Diff Engine           --> structured diff model             [IMPLEMENTED]
    |
    +--> Impact Analysis       --> NONE/LOW/MEDIUM/HIGH per doc type [IMPLEMENTED]
    |
    +--> CopilotAdapter        --> Mock / HumanReview / Real         [MOCKED + HUMAN REVIEW IMPLEMENTED; Real REQUIRES LICENSING VERIFICATION]
    |
    +--> Documentation Engine  --> technical-documentation.md,
    |                              user-guide.md, change summary      [IMPLEMENTED]
    |
    +--> SharePointAdapter     --> writes snapshot/diff/docs back,
                                    updates lists                     [MOCKED locally, REQUIRES CORPORATE ACCESS for real]
    |
    v
SharePoint Documentation Library
    |
    v
Power Automate notification (standard connector, e.g. Office 365 Outlook)
    |
    v
User email
```

## Component responsibilities

### Power Apps (design artifact only — `powerapps/`)

Thin client. Never executes PowerShell or calls the worker directly. Every
user action results in a SharePoint list write (new `DocumentationJobs` row,
or an update to `Applications`). Screens and Power Fx formulas are
documented as design artifacts in `powerapps/` because building/publishing
the actual `.msapp` requires a Power Platform environment (REQUIRES
CORPORATE ACCESS / REQUIRES TENANT CONFIGURATION). The formulas are still
concrete and copy-pasteable once an environment exists.

### SharePoint Online (design artifact — `sharepoint/`; runtime — `worker/adapters/sharepoint/`)

Three lists (`Applications`, `DocumentationJobs`, `DocumentationVersions`)
plus a document library (`PowerPlatformDocumentation/`). Exact column
definitions live in `sharepoint/lists/*.json` and `docs/SHAREPOINT_SETUP.md`.
SharePoint is the single source of truth for job and application state —
nothing else (not email, not the worker's own memory) is authoritative.

### Power Automate (design artifact — `powerautomate/`)

Standard-connector-only flows: (1) on `DocumentationJobs` item created/status
changed → send an Office 365 Outlook notification; (2) optionally, a
scheduled flow that pings the worker's health endpoint/file — kept optional
since polling by the worker itself is sufficient for MVP. No HTTP, Premium,
or custom connectors.

### Worker (`worker/`)

The only executable backend. A polling loop
(`worker/main.py` → `job_processor.py`) claims one `PENDING` job at a time,
executes the action-specific pipeline, and writes results back through
adapters. See "Job lifecycle" below.

### PowerPlatformAdapter (`worker/adapters/powerplatform/`)

```
authenticate() -> None
list_solutions(environment: str) -> list[str]
export_solution(solution_name: str, environment: str, output_dir: Path) -> Path
unpack_solution(package_path: Path) -> Path
get_solution_metadata(unpacked_dir: Path) -> dict
get_application_metadata(unpacked_dir: Path) -> dict
```

- `MockPowerPlatformAdapter` — **MOCKED**. Reads directly from
  `examples/mock_solution/<AppName>/<version>/`, treating each version
  directory as an already-unpacked export. No zip handling needed.
- `RealPowerPlatformAdapter` — **REQUIRES CORPORATE ACCESS**. Placeholder
  that documents the intended `pac` CLI commands per method
  (`pac auth create`, `pac solution list`, `pac solution export`,
  `pac solution unpack`, ...) but raises `NotImplementedError` until
  exercised against a real environment. See `docs/POWER_PLATFORM_SETUP.md`.

### Normalization (`worker/normalization/`)

Converts an adapter's raw metadata + unpacked directory into the
deterministic schema below. Deterministic = stable key order (Python dicts
preserve insertion order; we insert in a fixed order), stable list order
(sorted by `name`), and no volatile fields (timestamps, GUIDs that change
per export) unless they are semantically meaningful (e.g. a flow's logical
name, which is stable).

```json
{
  "solution": {"name": "...", "version": "1.4.0.0", "publisher": "...", "description": "..."},
  "applications": [{"name": "...", "type": "canvas", "screens": [{"name": "...", "controls_summary": "..."}]}],
  "flows": [{"name": "...", "trigger": "...", "actions": ["..."], "conditions": ["..."]}],
  "tables": [],
  "environment_variables": [{"name": "...", "type": "...", "default_value": "..."}],
  "connection_references": [{"name": "...", "connector": "..."}],
  "dependencies": [{"name": "...", "type": "..."}],
  "security": {"roles": ["..."]},
  "components": [{"name": "...", "type": "..."}]
}
```

`tables` stays empty for the no-Dataverse MVP; the field exists so the
schema doesn't need to change if Dataverse is explicitly approved later.

### Diff Engine (`worker/diff/engine.py`)

Compares two normalized snapshots component-category by component-category,
matching entries by `name`. Produces:

```json
{
  "version_from": "1.0",
  "version_to": "1.1",
  "changes": [
    {"type": "ADDED", "component": "flow", "name": "Invoice Escalation"},
    {"type": "MODIFIED", "component": "flow", "name": "Invoice Approval",
     "details": ["timeout changed from 24h to 48h"]}
  ]
}
```

`type` is one of `ADDED`, `REMOVED`, `MODIFIED`. `component` is one of
`solution`, `application`, `screen`, `flow`, `table`, `environment_variable`,
`connection_reference`, `dependency`, `component`.

### Documentation Impact Analysis (`worker/diff/impact.py`)

Deterministic rule table maps each diff entry to
`(technical_impact, user_impact)` in `{NONE, LOW, MEDIUM, HIGH}`; the overall
job impact is the maximum across all entries per axis. Copilot's
`analyze_changes()` may return a refined assessment, but the deterministic
result is always computed first and used whenever Copilot is unavailable
(mock/human-review modes without a completed human review).

### Versioning (`worker/versioning/version.py`)

- No changes detected → version unchanged, no new documentation version.
- Any changes (impact `LOW`/`MEDIUM`/`HIGH`) → minor bump (`1.0` → `1.1`).
- Major bump (`x.0`) is an explicit, manual decision — never inferred purely
  from diff size/impact (see DECISIONS.md ADR on versioning if amended).

### CopilotAdapter (`worker/adapters/copilot/`)

```
analyze_changes(diff: dict) -> dict            # refine/override impact
generate_technical_documentation(context: dict) -> str
generate_user_documentation(context: dict) -> str
generate_change_summary(diff: dict) -> str
```

- `MockCopilotAdapter` — **MOCKED**. Deterministic template rendering, no
  network calls, used for local dev/tests.
- `HumanReviewCopilotAdapter` — **IMPLEMENTED** (mechanism), depends on a
  human + real Copilot access to actually produce refined content. Writes a
  ready-to-run prompt file, sets job `Status = NEEDS_HUMAN_REVIEW`, and
  resumes when given a pasted-back result via `ingest_human_result()`.
- `RealCopilotAdapter` — **REQUIRES LICENSING VERIFICATION**. Placeholder
  only; see `docs/COPILOT_INTEGRATION.md`.

### Documentation Engine (`worker/documentation/generator.py`)

Renders three Markdown artifacts from normalized data + diff + impact +
(optional) Copilot output: `technical-documentation.md`, `user-guide.md`,
and a change summary. Required sections are fixed (see CLAUDE.md); a section
with no content still appears, with "Not applicable" as its body, so
consumers can rely on a stable document structure.

### SharePointAdapter (`worker/adapters/sharepoint/`)

```
get_pending_jobs() -> list[Job]
claim_job(job_id: str, worker_id: str) -> bool         # atomic-ish; False if already claimed
update_job(job_id: str, **fields) -> None
get_application(app_id: str) -> Application | None
list_applications() -> list[Application]
upsert_application(application: Application) -> None
create_version_record(version: DocumentationVersion) -> None
list_versions(app_id: str) -> list[DocumentationVersion]
upload_document(app_id: str, version: str, filename: str, content: str | bytes) -> str  # returns a path/URL
```

- `MockSharePointAdapter` — **MOCKED**. Backs all of the above with local
  JSON files (`.local_data/lists/*.json`) and a local mirror of the document
  library (`.local_data/PowerPlatformDocumentation/...`), git-ignored.
- `RealSharePointAdapter` — **REQUIRES CORPORATE ACCESS** +
  **REQUIRES TENANT CONFIGURATION**. Placeholder only; see
  `docs/SHAREPOINT_SETUP.md` and `docs/CORPORATE_SETUP.md`.

## Job lifecycle

```
PENDING --(claim_job succeeds)--> RUNNING --(success)--> COMPLETED
                                        |--(recoverable error, retries left)--> PENDING (RetryCount++)
                                        |--(unrecoverable / retries exhausted)--> FAILED
                                        |--(Copilot unavailable/human step required)--> NEEDS_HUMAN_REVIEW
NEEDS_HUMAN_REVIEW --(admin supplies Copilot result)--> RUNNING --> COMPLETED
any state --(admin action)--> CANCELLED
```

`claim_job` is the idempotency boundary: it only transitions a job it finds
in `PENDING`, writing `Status=RUNNING`, `WorkerId`, `StartedAt` in one
adapter call. A second worker (or a re-run after crash) that reads the same
job after this call sees `RUNNING` and does not reprocess it. Before
generating a new documentation version, the job processor also checks
whether a `DocumentationVersions` record for the target output version
already exists; if so, it treats the job as already completed rather than
regenerating (protects against a crash between "artifacts written" and
"status set to COMPLETED").

## Data flow example (v1.0 → v1.1)

1. `DOCUMENT_APPLICATION` job for "Invoice Approval" v1.0: export → normalize
   → no previous snapshot → impact is "initial" (treated as full HIGH/HIGH
   for both doc types, since everything is new) → generate both docs →
   store as version `1.0`.
2. `UPDATE_DOCUMENTATION` job later: export → normalize v1.1 → diff against
   stored v1.0 snapshot → detects: added flow "Invoice Escalation", modified
   flow "Invoice Approval" (timeout 24h→48h), etc. → impact computed →
   version bumps to `1.1` → docs regenerated → version history updated with
   the change summary.

## Deployment abstraction

The worker is a single Python process (`worker/main.py`) reading all
environment-specific configuration from environment variables
(`worker/config.py`). It has no assumption about its host: it can run
`python -m worker.main` in a terminal, under a scheduled task, as a Windows
service wrapper, or in a container — none of that is decided yet, and none
of `worker/`'s business logic depends on the choice. `scripts/run-worker.sh`
and `scripts/run-worker.ps1` are the two supported local entry points today;
production hosting is a `docs/DEPLOYMENT.md` decision made once a company
host is chosen.

## Primary documentation format

**Markdown** is the primary generated format for the MVP:
- Zero extra dependencies to generate or diff (`git diff` on `.md` files is
  meaningful; DOCX/HTML diffs are not).
- SharePoint renders Markdown reasonably and it's trivial to convert to
  HTML/DOCX later as a rendering step (e.g. via Pandoc) if leadership wants
  a nicer format — that becomes an additive "publish" step, not a rewrite of
  the generation engine.
- DOCX was rejected for MVP because generating/diffing DOCX requires an
  additional dependency (e.g. `python-docx`) and produces binary files that
  defeat the "deterministic, diffable snapshot" goal. It remains a valid
  future "publish/export" target layered on top of the Markdown source of
  truth.

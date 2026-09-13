You are acting as a senior Solution Architect, Power Platform architect,
DevOps engineer, automation engineer, and technical writer.

I want you to design and scaffold a complete project called:

"Power Platform Documentation Manager"

The goal is to build an internal system for automatically documenting and
versioning Microsoft Power Platform applications and solutions.

IMPORTANT CONTEXT
=================

My company uses Microsoft Power Platform, but we DO NOT have Power Platform
Premium licenses.

I DO have access to Microsoft Copilot through my company.

Therefore the architecture MUST prioritize standard Power Platform
capabilities and avoid requiring:

- Dataverse
- Premium connectors
- Custom connectors
- HTTP connectors from Power Automate
- Azure services unless explicitly marked as optional
- paid external SaaS services

SharePoint Online, Power Apps, standard Power Automate connectors,
Microsoft 365 services, Power Platform CLI, PowerShell, Git and a local/company
worker are acceptable.

The actual company tenant, SharePoint site, Power Platform environments,
authentication details and Copilot configuration are NOT available while
developing outside the corporate network.

Therefore the project must be fully developable and testable offline using
mock data.

DO NOT ask me for corporate credentials.

Instead, create adapters/configuration points so that real corporate
integration can be enabled later.

==================================================
MAIN BUSINESS CONCEPT
==================================================

A user opens a Power App.

The user can:

1. Register a Power Platform application/solution.
2. Request initial documentation.
3. Request documentation update.
4. Analyze changes since the previous documented version.
5. View documentation status.
6. View version history.
7. View previous changes.
8. Open generated technical documentation.
9. Open generated user documentation.

Power Apps creates a SharePoint Online item representing a job.

Example:

Action:
DOCUMENT_APPLICATION

Application:
Invoice Approval

Environment:
DEV

RequestedBy:
user@example.com

Status:
Pending

Power Apps may also trigger a standard Power Automate flow that sends an
email notification.

IMPORTANT:
Email is a notification mechanism, NOT the job queue.

SharePoint is the source of truth for job state.

A worker processes pending jobs.

The worker can:

- retrieve job information
- use Power Platform CLI
- export solutions
- unpack solutions
- normalize their contents
- create structured representations
- compare the current version with the previous snapshot
- calculate a meaningful diff
- prepare input for Copilot
- invoke Copilot/agent functionality if the company's available licensing
  and APIs support it
- otherwise create a human-in-the-loop task
- process the Copilot result
- generate technical documentation
- generate user documentation
- store snapshots
- store documentation
- update SharePoint metadata
- update version history
- send completion/failure notifications

==================================================
TARGET ARCHITECTURE
==================================================

Design the architecture approximately as:

Power Apps
    |
    v
SharePoint Online
    |
    v
Standard Power Automate
    |
    v
Job Queue
    |
    v
Company Worker
    |
    +--> Power Platform CLI
    |
    +--> PowerShell/scripts
    |
    +--> Solution parser
    |
    +--> Normalizer
    |
    +--> Diff engine
    |
    +--> Documentation engine
    |
    +--> Copilot / Copilot Agent
    |
    v
SharePoint Documentation Library
    |
    v
Power Automate notification
    |
    v
User email

The worker may initially run locally on my development machine.

The final production deployment may be:

- company Windows VM
- company server
- scheduled Windows worker
- service account/application identity
- or another company-approved execution host

DO NOT assume which one will be available.

Create a deployment abstraction.

==================================================
POWER APPS
==================================================

Design the Power App as a relatively thin frontend.

Suggested screens:

1. Dashboard
2. Applications
3. Application Details
4. Register Application
5. Request Documentation
6. Request Update
7. Version History
8. Job History
9. Admin/Diagnostics

Suggested actions:

- Register application
- Document application
- Analyze current version
- Compare versions
- Generate documentation
- Publish documentation
- Retry failed job

Power Apps should NOT execute PowerShell directly.

Power Apps should create SharePoint job records.

==================================================
SHAREPOINT
==================================================

Design SharePoint lists.

At minimum create:

1. Applications

Suggested columns:

- Title
- ApplicationId
- SolutionName
- Environment
- EnvironmentUrl
- Owner
- BusinessOwner
- Description
- CurrentVersion
- DocumentationStatus
- LastDocumented
- LastAnalyzed
- TechnicalDocumentationUrl
- UserDocumentationUrl
- Active
- Created
- Modified

2. DocumentationJobs

Suggested columns:

- Title / JobId
- Application
- Action
- RequestedBy
- RequestedAt
- Status
- InputVersion
- OutputVersion
- WorkerId
- StartedAt
- CompletedAt
- ErrorMessage
- ResultSummary
- CopilotStatus
- RetryCount

Actions should be enum-like values such as:

REGISTER_APPLICATION
EXPORT_SOLUTION
ANALYZE_SOLUTION
COMPARE_VERSION
GENERATE_DOCUMENTATION
PUBLISH_DOCUMENTATION
UPDATE_DOCUMENTATION

Statuses:

PENDING
RUNNING
COMPLETED
FAILED
NEEDS_HUMAN_REVIEW
CANCELLED

3. DocumentationVersions

Suggested columns:

- Application
- Version
- PreviousVersion
- ChangeSummary
- DocumentationImpact
- SnapshotPath
- DiffPath
- TechnicalDocumentationPath
- UserDocumentationPath
- CreatedBy
- CreatedAt

4. Configuration

Only if useful. Do not store secrets here.

==================================================
SHAREPOINT DOCUMENT LIBRARY
==================================================

Design a document library such as:

PowerPlatformDocumentation/

    ApplicationName/

        v1.0/

            snapshot.json
            solution-info.json
            diff.json
            technical-documentation.md
            user-guide.md

        v1.1/

            snapshot.json
            solution-info.json
            diff.json
            technical-documentation.md
            user-guide.md

Also consider:

    _jobs/
    _templates/
    _logs/

Do not store secrets in SharePoint.

Explain whether Markdown, DOCX or HTML should be the primary generated format.

Prefer simple formats during MVP development.

==================================================
POWER PLATFORM CLI
==================================================

Use Microsoft Power Platform CLI where appropriate.

The worker should support operations such as:

- authentication
- solution export
- solution unpack
- solution inspection
- canvas app inspection where applicable
- solution metadata extraction

Do NOT hard-code commands blindly.

Create an abstraction such as:

PowerPlatformAdapter

with methods conceptually similar to:

authenticate()
list_solutions()
export_solution()
unpack_solution()
get_solution_metadata()
get_application_metadata()

The implementation must clearly separate:

REAL PAC CLI implementation

from

MOCK implementation

The mock implementation must allow the entire system to work without access
to Microsoft Power Platform.

==================================================
NORMALIZATION
==================================================

Do NOT send raw ZIP files or arbitrary solution contents directly to Copilot.

Create a normalization layer.

Convert relevant Power Platform information into a structured representation.

For example:

{
  "solution": {
    "name": "...",
    "version": "1.4.0.0",
    "publisher": "...",
    "description": "..."
  },
  "applications": [],
  "flows": [],
  "tables": [],
  "environment_variables": [],
  "connection_references": [],
  "dependencies": [],
  "security": {},
  "components": []
}

Design this carefully.

The normalized representation should be deterministic so that Git diffs
and application version comparisons are useful.

==================================================
DIFF ENGINE
==================================================

Create a semantic diff engine.

It should detect things such as:

- added components
- removed components
- modified components
- changed flows
- changed triggers
- changed actions
- changed conditions
- changed environment variables
- changed connection references
- changed dependencies
- changed app screens
- changed navigation
- changed important business logic

Do not rely exclusively on textual diff.

Create a structured diff model.

Example:

{
  "version_from": "1.3",
  "version_to": "1.4",
  "changes": [
    {
      "type": "ADDED",
      "component": "flow",
      "name": "Invoice Escalation"
    },
    {
      "type": "MODIFIED",
      "component": "flow",
      "name": "Invoice Approval",
      "details": [
        "timeout changed from 24h to 48h"
      ]
    }
  ]
}

==================================================
DOCUMENTATION IMPACT ANALYSIS
==================================================

Before generating documentation, determine whether documentation actually
needs to change.

Create deterministic rules where possible.

Example:

Technical documentation impact:
NONE / LOW / MEDIUM / HIGH

User documentation impact:
NONE / LOW / MEDIUM / HIGH

Examples:

Adding a logging variable:
technical = LOW
user = NONE

Changing approval timeout:
technical = MEDIUM
user = HIGH

Adding a new user-facing screen:
technical = MEDIUM
user = HIGH

Changing internal error logging:
technical = LOW
user = NONE

Adding a new business process:
technical = HIGH
user = HIGH

Copilot should be able to refine this analysis.

==================================================
COPILOT INTEGRATION
==================================================

This is VERY IMPORTANT.

Do not invent an unofficial "POST prompt to Microsoft Copilot" API.

Research the current Microsoft documentation when implementing the real
integration.

Determine which of the following is actually available based on the
company's licensing:

- Microsoft 365 Copilot
- Copilot Studio
- Copilot agents
- agent APIs
- connectors
- MCP
- other officially supported automation mechanisms

The architecture must isolate Copilot behind an interface:

CopilotAdapter

For example:

analyze_changes()
generate_technical_documentation()
generate_user_documentation()
generate_change_summary()

Implement:

1. MockCopilotAdapter
2. HumanReviewCopilotAdapter
3. RealCopilotAdapter placeholder/interface

The real adapter should NOT be implemented based on assumptions.

Create a document:

docs/COPILOT_INTEGRATION.md

that explains:

- what must be verified in the corporate tenant
- which Copilot product is available
- required licensing
- required permissions
- whether API access exists
- whether MCP is available
- whether Copilot Studio is available
- whether an agent can be called programmatically
- how authentication works
- security considerations
- fallback if automation is unavailable

The project MUST remain usable with HumanReviewCopilotAdapter.

==================================================
HUMAN-IN-THE-LOOP FALLBACK
==================================================

If automatic Copilot invocation is not available, the worker should:

1. Prepare a structured analysis package.
2. Generate a ready-to-use Copilot prompt.
3. Save the prompt to SharePoint or local output.
4. Set job status to NEEDS_HUMAN_REVIEW.
5. Allow an administrator to run the prompt in approved corporate Copilot.
6. Allow the Copilot result to be pasted/uploaded back.
7. Continue processing automatically.

This fallback is important.

==================================================
DOCUMENTATION GENERATION
==================================================

Generate:

1. Technical Documentation
2. User Guide
3. Change Summary

Technical documentation should contain sections such as:

- Overview
- Architecture
- Components
- Power Apps
- Power Automate
- Data Sources
- Dependencies
- Environment Variables
- Connection References
- Security
- Business Logic
- Error Handling
- ALM
- Deployment
- Known Limitations

User guide:

- Purpose
- Who should use the application
- How to open it
- Main workflows
- Step-by-step usage
- Expected behavior
- Troubleshooting
- FAQ

==================================================
VERSIONING
==================================================

Use semantic-ish versioning where appropriate.

At minimum support:

1.0
1.1
1.2
2.0

Document how version numbers are determined.

A documentation update should produce something like:

Version: 1.4

Changes:
- Added invoice escalation flow
- Approval timeout increased from 24h to 48h
- Added escalation notification

Store the change summary in the SharePoint version history.

==================================================
WORKER
==================================================

Create a worker application.

Prefer Python for the initial MVP unless you have a strong reason to use
PowerShell/.NET.

However, PAC CLI and PowerShell commands must be callable by the worker.

Suggested architecture:

worker/
    main.py
    config.py
    queue/
    adapters/
    powerplatform/
    copilot/
    sharepoint/
    documentation/
    diff/
    normalization/
    logging/
    tests/

The worker should:

1. Poll SharePoint for PENDING jobs.
2. Lock/claim a job safely.
3. Execute the requested action.
4. Update status to RUNNING.
5. Perform the operation.
6. Save artifacts.
7. Update SharePoint.
8. Set status to COMPLETED.
9. Send notification.
10. On failure, set FAILED and store a safe error message.

Implement retry handling.

Avoid duplicate execution.

Design for idempotency.

==================================================
SECURITY
==================================================

Treat this as an internal enterprise application.

Document:

- authentication
- authorization
- secrets
- service accounts
- least privilege
- SharePoint permissions
- Power Platform permissions
- audit logging
- sensitive information
- credential storage
- logging policy

NEVER put credentials into:

- Git
- config files
- README
- SharePoint list values
- prompts
- generated documentation

Use environment variables or an appropriate secret store.

==================================================
MOCK ENVIRONMENT
==================================================

Create realistic mock Power Platform data.

Example:

examples/mock_solution/

with:

- solution metadata
- canvas app metadata
- flow definitions
- environment variables
- connection references
- dependencies

Create at least:

v1.0
v1.1

where v1.1 contains realistic changes.

The test suite must demonstrate that the system detects these changes.

==================================================
REPOSITORY STRUCTURE
==================================================

Create a professional repository.

Suggested:

README.md
CLAUDE.md
ARCHITECTURE.md
DECISIONS.md
ROADMAP.md
SECURITY.md
CONTRIBUTING.md

docs/
    GETTING_STARTED.md
    LOCAL_DEVELOPMENT.md
    CORPORATE_SETUP.md
    POWER_PLATFORM_SETUP.md
    SHAREPOINT_SETUP.md
    COPILOT_INTEGRATION.md
    WORKER_SETUP.md
    DEPLOYMENT.md
    TROUBLESHOOTING.md

src/
tests/
examples/
scripts/
config/
powerapps/
powerautomate/
sharepoint/

Adapt this structure if you have a better architecture.

==================================================
CLAUDE.md
==================================================

Create a comprehensive CLAUDE.md for yourself.

It must tell future Claude Code sessions:

- what the project does
- architectural principles
- repository structure
- coding conventions
- testing requirements
- security requirements
- how to work with mock data
- how to work with real Power Platform
- what must NEVER be assumed
- how Copilot integration is isolated
- how SharePoint is used
- how jobs are processed
- how versioning works
- how to update documentation
- how to make architectural decisions
- when to ask the user questions
- when to stop and request corporate information
- how to avoid breaking the no-Premium requirement

Also include a "Do not do" section.

Examples:

DO NOT:
- introduce Dataverse without explicit approval
- introduce Premium connectors without explicit approval
- hard-code tenant IDs
- hard-code SharePoint URLs
- store credentials
- invent Microsoft APIs
- assume Copilot APIs exist
- assume MCP is available
- require VPN for local development
- couple business logic directly to Power Apps

==================================================
CLAUDE SELF-DIRECTED DEVELOPMENT
==================================================

I want you to work in an agentic manner.

Before coding:

1. Inspect the repository.
2. Create an implementation plan.
3. Identify architectural risks.
4. Create/update CLAUDE.md.
5. Create/update ARCHITECTURE.md.
6. Create ROADMAP.md.
7. Break the project into milestones.

Then implement milestone by milestone.

After each milestone:

- run tests
- inspect failures
- fix them
- update documentation
- commit changes if Git is available

Do not pretend an integration works if it has not been tested.

Clearly mark:

IMPLEMENTED

MOCKED

REQUIRES CORPORATE ACCESS

REQUIRES TENANT CONFIGURATION

REQUIRES LICENSING VERIFICATION

==================================================
OFFLINE-FIRST DEVELOPMENT
==================================================

The project must be useful without:

- corporate VPN
- corporate Microsoft account
- Power Platform tenant
- SharePoint access
- Copilot access

Create mock adapters for all of them.

I should be able to clone the repository and run:

./scripts/setup.sh

and then something conceptually similar to:

./scripts/demo.sh

which demonstrates:

Register application
        ↓
Create documentation job
        ↓
Mock Power Platform export
        ↓
Normalize
        ↓
Compare v1.0 vs v1.1
        ↓
Analyze documentation impact
        ↓
Mock Copilot
        ↓
Generate documentation
        ↓
Store local artifacts
        ↓
Show final result

==================================================
CORPORATE SETUP GUIDE
==================================================

Create a VERY detailed:

docs/CORPORATE_SETUP.md

This document must be written for me personally when I eventually regain
access to my company's network.

It should contain a checklist like:

PHASE 1 — Gather information

[ ] Power Platform environment URLs
[ ] Environment names
[ ] Solution names
[ ] SharePoint site URL
[ ] SharePoint list names
[ ] SharePoint library name
[ ] Microsoft account used by worker
[ ] Worker machine
[ ] Network/VPN requirements
[ ] Power Platform permissions
[ ] SharePoint permissions
[ ] Copilot product/license
[ ] Copilot Studio availability
[ ] MCP availability
[ ] API availability
[ ] Security restrictions
[ ] Service account policy

PHASE 2 — Validate Power Platform CLI

Provide exact commands to:

- install/check PAC CLI
- authenticate
- list environments
- select environment
- list solutions
- export a test solution
- unpack it

But clearly separate commands that are safe to execute from commands that
could modify production.

PHASE 3 — SharePoint

Explain how to create:

Applications
DocumentationJobs
DocumentationVersions

and the document library.

Include exact column names and types.

PHASE 4 — Power Apps

Explain how to create/connect the app to SharePoint.

Describe each screen.

Describe each Power Fx operation.

PHASE 5 — Power Automate

Create the required standard flows.

Explain triggers, actions and conditions.

Avoid Premium connectors.

PHASE 6 — Worker

Explain:

- where to install it
- Python environment
- PAC CLI
- PowerShell
- configuration
- authentication
- permissions
- scheduling
- logging
- testing

PHASE 7 — Copilot

Give me a diagnostic checklist to determine exactly what Copilot product I
have.

Then tell me how to determine whether:

- API invocation is possible
- Copilot Studio agent invocation is possible
- MCP is possible
- human-in-the-loop is required

Do NOT invent undocumented procedures.

Link to official Microsoft documentation where relevant.

PHASE 8 — First real test

Provide a safe test procedure using a non-production Power Platform solution.

The first test must NOT modify production.

PHASE 9 — Production readiness

Checklist for:

- security
- permissions
- logging
- backups
- retries
- monitoring
- rollback
- documentation
- support
- ownership

==================================================
SETUP SCRIPT
==================================================

Create scripts that make local setup easy.

For example:

scripts/setup.sh
scripts/run-worker.sh
scripts/demo.sh
scripts/run-tests.sh

If Windows compatibility is important, also create:

scripts/setup.ps1
scripts/run-worker.ps1

Do not assume the user has Docker unless Docker is actually useful.

==================================================
TESTING
==================================================

Create unit tests for:

- normalization
- diff engine
- documentation impact analysis
- versioning
- job processing
- retry logic
- idempotency
- mock Power Platform adapter
- mock Copilot adapter

Create integration-style tests for the complete mock pipeline.

The following scenario MUST pass:

v1.0
→ documentation generated

v1.1
→ changes detected

→ documentation impact calculated

→ documentation regenerated

→ version history updated

→ change summary generated

==================================================
README
==================================================

Create a polished README suitable for GitHub.

It should explain:

- what this project is
- why it exists
- architecture
- no-Premium constraint
- Copilot integration
- screenshots/placeholders
- quickstart
- demo
- corporate deployment
- security
- limitations
- roadmap

Do NOT falsely claim that real Microsoft integrations are implemented.

Clearly distinguish MVP from production integration.

==================================================
ARCHITECTURAL DECISIONS
==================================================

Create DECISIONS.md and document important decisions.

At minimum:

ADR-001:
Why SharePoint instead of Dataverse

ADR-002:
Why a worker exists

ADR-003:
Why email is notification rather than job queue

ADR-004:
Why Power Platform CLI is isolated behind an adapter

ADR-005:
Why Copilot is isolated behind an adapter

ADR-006:
Why the system supports human-in-the-loop

ADR-007:
Why normalized representations are used instead of raw ZIP diffs

ADR-008:
Why the system is offline-first

For each decision explain:

Context
Decision
Alternatives
Trade-offs
Consequences

==================================================
IMPORTANT REAL-WORLD CONSTRAINT
==================================================

I want this to become a real internal tool eventually.

However, I currently cannot access the corporate environment.

Therefore:

DO NOT BLOCK DEVELOPMENT ON CORPORATE ACCESS.

Build the maximum possible amount using mocks.

Whenever a real integration cannot be implemented without corporate access,
create:

1. an interface
2. a mock implementation
3. configuration
4. documentation
5. a clear "when you get corporate access" checklist

==================================================
FIRST TASK
==================================================

Do NOT immediately start writing hundreds of lines of code.

First:

1. Inspect the repository.
2. Create the architecture.
3. Create CLAUDE.md.
4. Create the documentation structure.
5. Create the roadmap.
6. Create the mock architecture.
7. Create the first working vertical slice.
8. Run tests.
9. Show me what was implemented.
10. Identify the next milestone.

After that, continue implementing the project autonomously where safe.

When you encounter something requiring real corporate information, DO NOT
guess.

Create a clearly documented placeholder and continue with the mock path.

Your ultimate goal is to leave me with a repository that I can develop now
on my personal/offline machine and then connect to my company's actual
Power Platform environment once I have VPN/network access.
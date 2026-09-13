# Security Model

This is an internal enterprise tool. It handles company Power Platform
solution metadata (not customer data in the MVP scope) and, once real
adapters are enabled, credentials for SharePoint/Power Platform/Copilot
access. Treat every item below as a requirement, not a suggestion.

## Authentication

- **Power Apps → SharePoint**: standard Power Platform connection, using the
  signed-in user's own identity. No change needed from default Power Apps
  behavior.
- **Worker → SharePoint / Power Platform / Copilot**: REQUIRES CORPORATE
  ACCESS to finalize. The intended shape is a dedicated service account or
  application identity (app registration) with the minimum permissions
  needed (see "Least privilege" below), configured entirely through
  environment variables read by `worker/config.py`. Never through a value
  committed to the repository.
- Local/mock development requires no authentication at all — this is by
  design (offline-first).

## Authorization

- The worker's service identity should have write access only to the
  specific SharePoint site/lists/library this project uses, not tenant-wide
  access.
- Power Platform CLI authentication for the worker should be scoped to the
  specific environment(s) this project documents, not a global admin
  credential.
- Human reviewers who complete the `NEEDS_HUMAN_REVIEW` step should be the
  same people already authorized to use the company's Copilot product —
  this tool does not grant any new access, it only structures the prompt.

## Secrets

NEVER put credentials, API keys, tenant IDs used as secrets, or connection
strings into:

- Git (source, config files, fixtures, docs)
- `README.md` or any file under `docs/`
- SharePoint list column values
- Copilot prompts (mock or real) or generated documentation
- Log output

Worker configuration is environment-variable based (`worker/config.py`
documents every variable name; `.env.example` lists names with no values).
When a real deployment host is chosen, secrets should live in that host's
appropriate secret store (e.g. Windows Credential Manager, a company secrets
vault, or environment variables injected by the scheduler/service — never a
plaintext file checked into source control). This is a
REQUIRES TENANT CONFIGURATION / REQUIRES CORPORATE ACCESS decision to
finalize per `docs/CORPORATE_SETUP.md`.

## Service accounts

- Use a dedicated service/application identity for the worker, not a human's
  personal account, so access can be audited and revoked independently of
  any one person's employment status.
- Document the account's exact permission grants in
  `docs/CORPORATE_SETUP.md` once created — do not grant broader permissions
  "to be safe."

## Least privilege

- SharePoint: Contribute on the specific site/lists/library only.
- Power Platform: the minimum role needed to export solutions from the
  relevant environment(s) (e.g. Environment Maker or a custom role scoped to
  export), not System Administrator, unless nothing narrower is available —
  verify and document the actual minimum during `docs/CORPORATE_SETUP.md`
  Phase 1.
- Copilot: whatever license/role the human reviewers already hold; the
  worker itself should not hold a separate Copilot credential unless/until
  `RealCopilotAdapter` is implemented and its exact permission needs are
  verified (see `docs/COPILOT_INTEGRATION.md`).

## Audit logging

- Every job transition (claimed, completed, failed, needs review) is
  recorded in the `DocumentationJobs` list itself (`Status`, `WorkerId`,
  `StartedAt`, `CompletedAt`, `ErrorMessage`), which is inherently an audit
  trail backed by SharePoint's own versioning/history.
- Worker process logs (`worker/logging_setup.py`) record job IDs, actions,
  and outcomes, but never full solution contents, normalized snapshots, or
  credentials — log the fact that something happened, not its full payload.

## Sensitive information handling

- Solution metadata (flow logic, connection reference names, environment
  variable names) is treated as internal-confidential: fine to store in the
  company's own SharePoint site, not fine to paste into any third-party
  tool that isn't an approved, licensed Copilot product.
- `HumanReviewCopilotAdapter`'s generated prompt includes only the
  normalized representation and diff — never raw exported files, connection
  secrets, or environment variable *values* if any happen to be
  secret-shaped (the normalizer should ideally record variable names/types,
  not sensitive default values).

## Credential storage

- Local development: no credentials exist at all (mock adapters only). If a
  developer later wants to exercise a real adapter from a personal machine,
  credentials go in a local, git-ignored `.env` file, never `.env.example`
  or any tracked file.
- Production: per `docs/CORPORATE_SETUP.md`, decided once the actual host
  and company secret-management standard are known.

## Logging policy

- Log level defaults to INFO for job lifecycle events, DEBUG for adapter
  call details (still no secrets/full payloads at DEBUG either).
- Never log environment variable values, only their names, when logging
  configuration state.
- Never log full Copilot prompts/responses at INFO; DEBUG logging of prompt
  *metadata* (length, target job ID) is fine, full content is not, since
  logs may be retained/forwarded more broadly than the SharePoint document
  library.

## Reporting a concern

If you find a security issue in this repository (e.g. a place a secret could
leak, an overly broad permission request), open it as a normal issue/PR
comment — there is no separate disclosure program for this internal tool.

# Mock solution fixtures

`InvoiceApproval/v1.0/` and `InvoiceApproval/v1.1/` are hand-authored mock
exports of a fictional "Invoice Approval" Power Platform solution, used by
`MockPowerPlatformAdapter` and every test/demo that exercises the full
pipeline offline. Each version directory is treated as an already-unpacked
solution export (see `worker/adapters/powerplatform/mock.py`).

## Files per version

| File | Normalized category |
|---|---|
| `solution.json` | `solution` |
| `apps.json` | `applications` (canvas apps + screens) |
| `flows.json` | `flows` |
| `environment-variables.json` | `environment_variables` |
| `connection-references.json` | `connection_references` |
| `dependencies.json` | `dependencies` |
| `security.json` | `security.roles` |
| `components.json` | `components` |

`tables.json` is intentionally absent — the no-Dataverse MVP has no tables;
the normalized schema still reserves the field for when/if Dataverse is
explicitly approved (ADR-001).

## What changed between v1.0 and v1.1

This change set is intentionally realistic and exercises every diff/impact
rule documented in `ARCHITECTURE.md` / `worker/diff/impact.py`:

- **Added** flow "Invoice Escalation" (a new business process) — expected
  impact: technical HIGH, user HIGH.
- **Modified** flow "Invoice Approval": timeout changed from 24h to 48h —
  expected impact: technical MEDIUM, user HIGH.
- **Added** screen "EscalationScreen" — expected impact: technical MEDIUM,
  user HIGH.
- **Modified** screen "HomeScreen": controls changed (added an Escalate
  button) — expected impact: technical LOW, user MEDIUM.
- **Modified** environment variable "ApprovalTimeoutHours": default value
  24 -> 48 — keyword "timeout" -> expected impact: technical MEDIUM, user
  HIGH.
- **Added** environment variable "EscalationTimeoutHours" — keyword
  "timeout" -> expected impact: technical MEDIUM, user HIGH.
- **Added** connection reference "shared_teams" (Microsoft Teams, a
  standard connector) — expected impact: technical MEDIUM, user NONE.
- **Added** dependency "Microsoft Teams" — expected impact: technical
  MEDIUM, user NONE.
- **Added** security role "Invoice Escalation Manager" — expected impact:
  technical MEDIUM, user LOW.
- **Added** component "EscalationBanner" — expected impact: technical LOW,
  user LOW.

`worker/tests/test_integration_pipeline.py` asserts on this exact change
set to keep the fixture and the diff/impact engines honest against each
other.

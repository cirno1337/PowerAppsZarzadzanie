# Worker Setup

## Local (offline) setup

```bash
./scripts/setup.sh        # or scripts/setup.ps1 on Windows
./scripts/run-worker.sh --once
```

Defaults to `PPDM_POWERPLATFORM_MODE=mock`, `PPDM_SHAREPOINT_MODE=mock`,
`PPDM_COPILOT_MODE=mock` — no configuration needed.

## Configuration

All configuration is environment variables read by `worker/config.py`; see
`config/.env.example` for the full list of names (never commit a filled-in
`.env`). Key ones:

| Variable | Default | Meaning |
|---|---|---|
| `PPDM_POWERPLATFORM_MODE` | `mock` | `mock` \| `real` |
| `PPDM_SHAREPOINT_MODE` | `mock` | `mock` \| `real` |
| `PPDM_COPILOT_MODE` | `mock` | `mock` \| `human_review` \| `real` |
| `PPDM_LOCAL_DATA_DIR` | `.local_data` | Where the mock SharePoint adapter stores its lists/library |
| `PPDM_MOCK_SOLUTIONS_DIR` | `examples/mock_solution` | Fixture root for the mock Power Platform adapter |
| `PPDM_WORKER_ID` | `local-dev-worker` | Identifies this worker instance in job records |
| `PPDM_MAX_RETRIES` | `3` | Retry budget per job before it's marked FAILED |
| `PPDM_POLL_INTERVAL_SECONDS` | `5` | Sleep between polls when no job is pending |
| `PPDM_SHAREPOINT_SITE_URL` | _(empty)_ | REQUIRES TENANT CONFIGURATION |
| `PPDM_POWERPLATFORM_ENVIRONMENT_URL` | _(empty)_ | REQUIRES TENANT CONFIGURATION |

Setting any `*_MODE` to `real` before its adapter is implemented raises
`NotImplementedError` immediately with a pointer to the relevant setup doc
— this is intentional (see CLAUDE.md "what must never be assumed").

## Running continuously vs. once

```bash
python -m worker.main            # continuous polling loop (Ctrl+C to stop)
python -m worker.main --once     # process at most one pending job, then exit
```

`--once` is what you want for cron/Task Scheduler-style periodic invocation;
the continuous mode is for an always-on process (a systemd service, a
Windows service wrapper, etc.) — see `docs/DEPLOYMENT.md` for host options,
none of which are decided yet.

## Authentication (real mode — REQUIRES CORPORATE ACCESS)

Not implemented. See `docs/CORPORATE_SETUP.md` Phase 1/6 and SECURITY.md.

## Permissions (real mode)

See SECURITY.md "Least privilege".

## Scheduling (production — REQUIRES CORPORATE ACCESS / a chosen host)

Not decided. See `docs/DEPLOYMENT.md` and ROADMAP.md Milestone 8.

## Logging

`worker/logging_setup.py` configures `logging.basicConfig`; set
`PPDM_VERBOSE_LOGGING=true` for DEBUG-level adapter call details. Never logs
secrets or full payloads — see SECURITY.md "Logging policy".

## Testing

```bash
./scripts/run-tests.sh
```

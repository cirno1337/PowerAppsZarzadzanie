# Deployment

**Status: no production host is decided.** Per CLAUDE.md and ADR-002/the
project brief, the worker must not assume which host it runs on. This
document tracks the options and the decision once made — it does not
prescribe one.

## What's already host-agnostic

- `worker/main.py` reads all configuration from environment variables — no
  hard-coded paths, no OS-specific assumptions in `worker/` business logic.
- `scripts/run-worker.sh` / `scripts/run-worker.ps1` cover the two obvious
  local-execution shells; both just set env vars and invoke
  `python -m worker.main`.
- The mock/real adapter split means the worker doesn't need network access
  to be useful — a production deployment only changes `PPDM_*_MODE` values
  and injects real credentials via the host's secret mechanism.

## Candidate production hosts (undecided — pick one when you have corporate context)

| Option | Pros | Cons |
|---|---|---|
| Company Windows VM, scheduled task (`schtasks` / Task Scheduler) running `run-worker.ps1 ... --once` on a timer | Simple, matches "PowerShell/Windows" comfort zone | Manual scaling/monitoring |
| Company Windows VM, always-on via `python -m worker.main` under NSSM or a native Windows service wrapper | Continuous polling, simpler operational model than a scheduled task per run | Needs a service account with a persistent login |
| Company Linux server, systemd service or cron | Same trade-offs as Windows equivalents, if a Linux host is available | Depends on company standards |
| Container (e.g. on an internal container platform, if one exists) | Portable, easy to redeploy | Only sensible if the company already runs container infrastructure — do not introduce Docker/K8s purely for this project without approval |

## Decision record

Fill in once chosen:

- **Chosen host:** _TBD_
- **Scheduling mechanism:** _TBD_
- **Service account / identity:** _TBD_ — see SECURITY.md "Service accounts"
- **Secret storage on this host:** _TBD_
- **Monitoring/alerting:** _TBD_ — at minimum, alert on `DocumentationJobs`
  items stuck in `FAILED` or `NEEDS_HUMAN_REVIEW` beyond some threshold.
- **Backup/retention:** _TBD_ — SharePoint's own versioning/retention
  policies likely cover the document library and lists; confirm rather than
  assume.
- **Rollback plan:** _TBD_ — since the worker only ever writes new
  documentation versions (never mutates prior ones), "rollback" mostly means
  "stop the worker" and, if a bad documentation version was published,
  manually mark it superseded — there is no automatic version deletion by
  design (documentation is an append-only history).

## Production readiness checklist

See `docs/CORPORATE_SETUP.md` Phase 9 for the full checklist (security,
permissions, logging, backups, retries, monitoring, rollback, documentation,
support, ownership).

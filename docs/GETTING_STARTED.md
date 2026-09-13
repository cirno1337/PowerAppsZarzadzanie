# Getting Started

Everything below works fully offline — no corporate VPN, Microsoft account,
Power Platform tenant, SharePoint access, or Copilot access required.

## 1. Clone and set up

```bash
git clone <this-repo>
cd PowerAppsZarzadzanie
./scripts/setup.sh
```

This creates a local Python virtual environment (`.venv/`, with access to
system site-packages so it can reuse an already-installed `pytest` if you
have no network access to fetch it fresh) and installs test dependencies.

Windows: `.\scripts\setup.ps1`.

## 2. Run the tests

```bash
./scripts/run-tests.sh
```

62 tests should pass, covering normalization, the diff engine, impact
analysis, versioning, the mock adapters, job processing (including retries
and idempotency), and the full v1.0→v1.1 integration scenario.

## 3. Run the demo

```bash
./scripts/demo.sh
```

This registers a mock application ("Invoice Approval"), documents it at
version 1.0, then processes an update to version 1.1, printing the
generated change summary and the paths to every artifact it wrote under
`.local_data/demo/`. Open the generated Markdown files directly:

```bash
cat .local_data/demo/PowerPlatformDocumentation/Invoice-Approval/1.1/technical-documentation.md
cat .local_data/demo/PowerPlatformDocumentation/Invoice-Approval/1.1/user-guide.md
```

## 4. Run the worker directly

```bash
./scripts/run-worker.sh --once   # process one pending job (mock adapters) and exit
./scripts/run-worker.sh          # continuous polling loop; Ctrl+C to stop
```

With no jobs queued, `--once` reports "No pending jobs." — you'd normally
queue one via a script/test or (eventually) the real Power App.

## Where to go next

- `ARCHITECTURE.md` — how the whole system fits together.
- `CLAUDE.md` — conventions and rules for working in this repository.
- `docs/LOCAL_DEVELOPMENT.md` — day-to-day development workflow.
- `docs/CORPORATE_SETUP.md` — the checklist for connecting to your real
  company Power Platform tenant once you have access again.

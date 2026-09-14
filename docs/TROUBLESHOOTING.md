# Troubleshooting

## Tests fail with `ModuleNotFoundError: No module named 'worker'`

Run pytest from the repository root (or via `./scripts/run-tests.sh`, which
`cd`s there for you). `pyproject.toml` sets `pythonpath = ["."]` for pytest,
but only when pytest is invoked from the repo root.

## `./scripts/setup.sh` can't install pytest (no network)

If `pytest` is already installed system-wide, the venv is created with
`--system-site-packages` specifically so it can see it — check with
`python3 -c "import pytest"` outside the venv. If it's genuinely
unavailable, install it once you have network access; there is no other way
to run the test suite (it's the project's only dependency).

## `MockPowerPlatformAdapter` raises `FileNotFoundError: No mock fixture versions found`

The solution name passed doesn't match a directory under
`examples/mock_solution/`. Check `Application.solution_name` against the
actual fixture directory names (case-sensitive) — currently only
`InvoiceApproval` exists.

## A job stays `PENDING` forever when running the worker continuously

Check `PPDM_POLL_INTERVAL_SECONDS` — the worker sleeps that long between
empty polls. Also confirm the job was actually created via
`SharePointAdapter.create_job()` (or, once real, actually appears in the
`DocumentationJobs` list with `Status = PENDING`).

## A job is stuck `NEEDS_HUMAN_REVIEW`

This is by design when using `PPDM_COPILOT_MODE=human_review` (or when
`RealCopilotAdapter` isn't available) — see `docs/COPILOT_INTEGRATION.md`
"Fallback if automation is unavailable". Retrieve the prompt (locally: read
`.local_data/.../_jobs/<job-id>/copilot-prompt.md`; on real SharePoint: the
document library's `_jobs/<job-id>/copilot-prompt.md`), run it in an
approved corporate Copilot product, then call
`JobProcessor.resume_needs_human_review(job_id, human_result)` with the
three required keys (`technical_documentation`, `user_documentation`,
`change_summary`).

## A job keeps failing and retrying

Check `DocumentationJobs.ErrorMessage` (or the mock adapter's
`.local_data/.../lists/documentation_jobs.json`) for the sanitized error.
After `PPDM_MAX_RETRIES` attempts it becomes `FAILED` and stops retrying
automatically — fix the underlying cause, then manually reset `Status` to
`PENDING` and `RetryCount` to `0` to try again.

## The integration test fails after I changed the mock fixtures

`worker/tests/test_integration_pipeline.py` and
`examples/mock_solution/README.md`'s change list are meant to stay in sync.
If you intentionally changed `examples/mock_solution/InvoiceApproval/v1.1/`,
update both the test's assertions and the README's change list to match —
do not weaken the test to make it pass (see CLAUDE.md "Testing
requirements").

## "Which adapter mode am I actually running with?"

`worker/main.py` logs the three modes at startup
(`powerplatform=..., sharepoint=..., copilot=...`). Also check
`config/.env.example` variable names against your actual environment (never
against a value in this repo — nothing here is a real value).

## Something requires corporate information I don't have

Stop — do not guess a tenant ID, site URL, or credential. Create/keep a
documented placeholder (`REQUIRES CORPORATE ACCESS` /
`REQUIRES TENANT CONFIGURATION` / `REQUIRES LICENSING VERIFICATION` in the
relevant file) and continue on the mock path. See CLAUDE.md "When to stop
and request corporate information".

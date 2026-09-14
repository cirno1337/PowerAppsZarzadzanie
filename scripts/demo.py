#!/usr/bin/env python3
"""Runs the full mock pipeline end-to-end and prints a summary.

Register application -> document v1.0 -> mock export -> normalize ->
compare v1.0 vs v1.1 -> analyze documentation impact -> mock Copilot ->
generate documentation -> store local artifacts -> show final result.

Entirely offline: no network, no corporate access, no credentials.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from worker.adapters.copilot.mock import MockCopilotAdapter  # noqa: E402
from worker.adapters.powerplatform.mock import MockPowerPlatformAdapter  # noqa: E402
from worker.adapters.sharepoint.mock import MockSharePointAdapter  # noqa: E402
from worker.job_processor import JobProcessor  # noqa: E402
from worker.models import Application, Job, JobAction  # noqa: E402

DEMO_DATA_DIR = REPO_ROOT / ".local_data" / "demo"


def _print_header(text: str) -> None:
    print(f"\n=== {text} ===")


def main() -> None:
    if DEMO_DATA_DIR.exists():
        shutil.rmtree(DEMO_DATA_DIR)

    sharepoint = MockSharePointAdapter(DEMO_DATA_DIR)
    powerplatform = MockPowerPlatformAdapter(REPO_ROOT / "examples" / "mock_solution")
    copilot = MockCopilotAdapter()
    processor = JobProcessor(
        powerplatform=powerplatform,
        sharepoint=sharepoint,
        copilot=copilot,
        worker_id="demo-worker",
        export_dir=DEMO_DATA_DIR / "_exports",
        copilot_mode="mock",
    )

    _print_header("1. Register application")
    application = Application(
        application_id="invoice-approval",
        title="Invoice Approval",
        solution_name="InvoiceApproval",
        environment="DEV",
        owner="app-owner@example.com",
        business_owner="finance-lead@example.com",
        description="Automates invoice approval requests submitted by employees.",
    )
    sharepoint.upsert_application(application)
    print(f"Registered '{application.title}' ({application.application_id}) in {application.environment}.")

    _print_header("2. Create documentation job (v1.0)")
    sharepoint.create_job(
        Job(
            job_id="demo-job-v1.0",
            application_id="invoice-approval",
            action=JobAction.DOCUMENT_APPLICATION,
            requested_by="demo-user@example.com",
            input_version="v1.0",
        )
    )
    print("Job created with Status=PENDING (SharePoint DocumentationJobs list, mocked).")

    _print_header("3-8. Worker processes the job (export -> normalize -> generate docs)")
    result = processor.process_job_id("demo-job-v1.0")
    print(f"Job {result.job_id}: {result.status.value}, output_version={result.output_version}")
    print(f"Result summary: {result.result_summary}")

    _print_header("9. Register an update request and compare v1.0 vs v1.1")
    sharepoint.create_job(
        Job(
            job_id="demo-job-v1.1",
            application_id="invoice-approval",
            action=JobAction.UPDATE_DOCUMENTATION,
            requested_by="demo-user@example.com",
            input_version="v1.1",
        )
    )
    update_result = processor.process_job_id("demo-job-v1.1")
    print(f"Job {update_result.job_id}: {update_result.status.value}, output_version={update_result.output_version}")

    _print_header("Final result")
    app = sharepoint.get_application("invoice-approval")
    print(f"Application: {app.title}")
    print(f"Current version: {app.current_version}")
    print(f"Documentation status: {app.documentation_status.value}")
    print(f"Technical documentation: {app.technical_documentation_url}")
    print(f"User guide: {app.user_documentation_url}")

    latest_version = sharepoint.get_latest_version_record("invoice-approval")
    print("\nChange summary for the latest version:\n")
    print(latest_version.change_summary)

    print(f"\nAll artifacts written under: {DEMO_DATA_DIR}")


if __name__ == "__main__":
    main()

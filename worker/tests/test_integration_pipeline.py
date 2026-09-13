"""The MUST-pass end-to-end scenario (see CLAUDE.md "Testing requirements"):

v1.0 -> documentation generated
v1.1 -> changes detected
      -> documentation impact calculated
      -> documentation regenerated
      -> version history updated
      -> change summary generated

Entirely against mock adapters — no network, no corporate access required.
"""

from __future__ import annotations

import json
from pathlib import Path

from worker.adapters.copilot.mock import MockCopilotAdapter
from worker.job_processor import JobProcessor
from worker.models import Application, Job, JobAction, JobStatus


def test_full_v1_0_to_v1_1_pipeline(sharepoint_adapter, powerplatform_adapter):
    application = Application(
        application_id="invoice-approval",
        title="Invoice Approval",
        solution_name="InvoiceApproval",
        environment="DEV",
        owner="app-owner@example.com",
        business_owner="finance-lead@example.com",
        description="Automates invoice approval requests.",
    )
    sharepoint_adapter.upsert_application(application)

    processor = JobProcessor(
        powerplatform=powerplatform_adapter,
        sharepoint=sharepoint_adapter,
        copilot=MockCopilotAdapter(),
        worker_id="test-worker",
        export_dir=Path("/tmp/unused"),
        copilot_mode="mock",
    )

    # --- Step 1: register + document v1.0 -----------------------------------
    sharepoint_adapter.create_job(
        Job(
            job_id="job-register",
            application_id="invoice-approval",
            action=JobAction.REGISTER_APPLICATION,
            requested_by="user@example.com",
        )
    )
    register_result = processor.process_job_id("job-register")
    assert register_result.status == JobStatus.COMPLETED

    sharepoint_adapter.create_job(
        Job(
            job_id="job-doc-v1",
            application_id="invoice-approval",
            action=JobAction.DOCUMENT_APPLICATION,
            requested_by="user@example.com",
            input_version="v1.0",
        )
    )
    v1_result = processor.process_job_id("job-doc-v1")
    assert v1_result.status == JobStatus.COMPLETED
    assert v1_result.output_version == "1.0"

    app_after_v1 = sharepoint_adapter.get_application("invoice-approval")
    assert app_after_v1.current_version == "1.0"
    assert app_after_v1.documentation_status.value == "DOCUMENTED"
    assert app_after_v1.technical_documentation_url
    assert app_after_v1.user_documentation_url
    assert Path(app_after_v1.technical_documentation_url).exists()
    assert Path(app_after_v1.user_documentation_url).exists()

    # --- Step 2: analyze + update to v1.1 -----------------------------------
    sharepoint_adapter.create_job(
        Job(
            job_id="job-analyze",
            application_id="invoice-approval",
            action=JobAction.ANALYZE_SOLUTION,
            requested_by="user@example.com",
            input_version="v1.1",
        )
    )
    analyze_result = processor.process_job_id("job-analyze")
    assert analyze_result.status == JobStatus.COMPLETED
    assert "change(s)" in analyze_result.result_summary
    assert sharepoint_adapter.get_application("invoice-approval").documentation_status.value == "UPDATE_AVAILABLE"

    sharepoint_adapter.create_job(
        Job(
            job_id="job-update-v1.1",
            application_id="invoice-approval",
            action=JobAction.UPDATE_DOCUMENTATION,
            requested_by="user@example.com",
            input_version="v1.1",
        )
    )
    v1_1_result = processor.process_job_id("job-update-v1.1")
    assert v1_1_result.status == JobStatus.COMPLETED
    assert v1_1_result.output_version == "1.1"

    # --- Assert: changes detected --------------------------------------------
    versions = sharepoint_adapter.list_versions("invoice-approval")
    assert [v.version for v in versions] == ["1.0", "1.1"]
    v1_1_record = versions[1]
    assert v1_1_record.previous_version == "1.0"

    diff = json.loads(Path(v1_1_record.diff_path).read_text())
    change_names = {(c["type"], c["component"], c["name"]) for c in diff["changes"]}
    assert ("ADDED", "flow", "Invoice Escalation") in change_names
    modified_flow = next(
        c for c in diff["changes"] if c["component"] == "flow" and c["name"] == "Invoice Approval"
    )
    assert "timeout changed from 24h to 48h" in modified_flow["details"]

    # --- Assert: documentation impact calculated ------------------------------
    assert "technical=HIGH" in v1_1_record.documentation_impact
    assert "user=HIGH" in v1_1_record.documentation_impact

    # --- Assert: documentation regenerated -------------------------------------
    technical_doc = Path(v1_1_record.technical_documentation_path).read_text()
    assert "Invoice Escalation" in technical_doc
    user_doc = Path(v1_1_record.user_documentation_path).read_text()
    assert "Invoice Escalation" in user_doc

    # --- Assert: version history updated with a change summary -----------------
    assert v1_1_record.change_summary.startswith("Version: 1.1")
    assert "Invoice Escalation" in v1_1_record.change_summary

    app_after_v1_1 = sharepoint_adapter.get_application("invoice-approval")
    assert app_after_v1_1.current_version == "1.1"
    assert app_after_v1_1.documentation_status.value == "DOCUMENTED"

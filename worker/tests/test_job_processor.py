from __future__ import annotations

from pathlib import Path

import pytest

from worker.adapters.copilot.human_review import HumanReviewCopilotAdapter
from worker.adapters.copilot.mock import MockCopilotAdapter
from worker.job_processor import JobProcessingError, JobProcessor
from worker.models import Application, Job, JobAction, JobStatus


def _make_application(sharepoint_adapter, app_id="app-1"):
    app = Application(
        application_id=app_id,
        title="Invoice Approval",
        solution_name="InvoiceApproval",
        environment="DEV",
        owner="owner@example.com",
        business_owner="biz@example.com",
    )
    sharepoint_adapter.upsert_application(app)
    return app


def _processor(powerplatform_adapter, sharepoint_adapter, copilot=None, max_retries=3):
    return JobProcessor(
        powerplatform=powerplatform_adapter,
        sharepoint=sharepoint_adapter,
        copilot=copilot or MockCopilotAdapter(),
        worker_id="test-worker",
        max_retries=max_retries,
        export_dir=Path("/tmp/unused"),
        copilot_mode="mock",
    )


def test_register_application_completes(sharepoint_adapter, powerplatform_adapter):
    _make_application(sharepoint_adapter)
    sharepoint_adapter.create_job(
        Job(job_id="job-1", application_id="app-1", action=JobAction.REGISTER_APPLICATION, requested_by="u")
    )
    result = _processor(powerplatform_adapter, sharepoint_adapter).process_job_id("job-1")
    assert result.status == JobStatus.COMPLETED


def test_full_pipeline_creates_initial_version_1_0(sharepoint_adapter, powerplatform_adapter):
    _make_application(sharepoint_adapter)
    sharepoint_adapter.create_job(
        Job(
            job_id="job-1", application_id="app-1", action=JobAction.DOCUMENT_APPLICATION,
            requested_by="u", input_version="v1.0",
        )
    )
    result = _processor(powerplatform_adapter, sharepoint_adapter).process_job_id("job-1")
    assert result.status == JobStatus.COMPLETED
    assert result.output_version == "1.0"

    app = sharepoint_adapter.get_application("app-1")
    assert app.current_version == "1.0"
    assert app.documentation_status.value == "DOCUMENTED"

    versions = sharepoint_adapter.list_versions("app-1")
    assert len(versions) == 1
    assert versions[0].version == "1.0"


def test_update_documentation_bumps_to_1_1_after_1_0(sharepoint_adapter, powerplatform_adapter):
    _make_application(sharepoint_adapter)
    processor = _processor(powerplatform_adapter, sharepoint_adapter)
    sharepoint_adapter.create_job(
        Job(job_id="job-1", application_id="app-1", action=JobAction.DOCUMENT_APPLICATION, requested_by="u", input_version="v1.0")
    )
    processor.process_job_id("job-1")

    sharepoint_adapter.create_job(
        Job(job_id="job-2", application_id="app-1", action=JobAction.UPDATE_DOCUMENTATION, requested_by="u", input_version="v1.1")
    )
    result = processor.process_job_id("job-2")

    assert result.status == JobStatus.COMPLETED
    assert result.output_version == "1.1"
    assert len(sharepoint_adapter.list_versions("app-1")) == 2


def test_rerunning_update_with_no_new_changes_is_idempotent(sharepoint_adapter, powerplatform_adapter):
    _make_application(sharepoint_adapter)
    processor = _processor(powerplatform_adapter, sharepoint_adapter)
    sharepoint_adapter.create_job(
        Job(job_id="job-1", application_id="app-1", action=JobAction.DOCUMENT_APPLICATION, requested_by="u", input_version="v1.0")
    )
    processor.process_job_id("job-1")

    # Same input version again -> no changes since v1.0 -> should not create a second version record.
    sharepoint_adapter.create_job(
        Job(job_id="job-2", application_id="app-1", action=JobAction.UPDATE_DOCUMENTATION, requested_by="u", input_version="v1.0")
    )
    result = processor.process_job_id("job-2")

    assert result.status == JobStatus.COMPLETED
    assert result.output_version == "1.0"
    assert len(sharepoint_adapter.list_versions("app-1")) == 1


class _FlakyPowerPlatformAdapter:
    """Wraps a real mock adapter, raising on the first N calls to export_solution."""

    def __init__(self, inner, fail_times: int):
        self._inner = inner
        self._fail_times = fail_times
        self._calls = 0

    def authenticate(self):
        return self._inner.authenticate()

    def list_solutions(self, environment):
        return self._inner.list_solutions(environment)

    def export_solution(self, *args, **kwargs):
        self._calls += 1
        if self._calls <= self._fail_times:
            raise RuntimeError("simulated transient export failure")
        return self._inner.export_solution(*args, **kwargs)

    def unpack_solution(self, package_path):
        return self._inner.unpack_solution(package_path)

    def get_solution_metadata(self, unpacked_dir):
        return self._inner.get_solution_metadata(unpacked_dir)

    def get_application_metadata(self, unpacked_dir):
        return self._inner.get_application_metadata(unpacked_dir)


def test_retry_then_success(sharepoint_adapter, powerplatform_adapter):
    _make_application(sharepoint_adapter)
    flaky = _FlakyPowerPlatformAdapter(powerplatform_adapter, fail_times=2)
    processor = _processor(flaky, sharepoint_adapter, max_retries=3)
    sharepoint_adapter.create_job(
        Job(job_id="job-1", application_id="app-1", action=JobAction.DOCUMENT_APPLICATION, requested_by="u", input_version="v1.0")
    )

    # Attempt 1: fails, goes back to PENDING with retry_count=1.
    result = processor.process_job_id("job-1")
    assert result.status == JobStatus.PENDING
    assert result.retry_count == 1

    # Attempt 2: fails again, retry_count=2.
    result = processor.process_job_id("job-1")
    assert result.status == JobStatus.PENDING
    assert result.retry_count == 2

    # Attempt 3: succeeds.
    result = processor.process_job_id("job-1")
    assert result.status == JobStatus.COMPLETED


def test_retry_exhausted_sets_failed(sharepoint_adapter, powerplatform_adapter):
    _make_application(sharepoint_adapter)
    flaky = _FlakyPowerPlatformAdapter(powerplatform_adapter, fail_times=99)
    processor = _processor(flaky, sharepoint_adapter, max_retries=1)
    sharepoint_adapter.create_job(
        Job(job_id="job-1", application_id="app-1", action=JobAction.DOCUMENT_APPLICATION, requested_by="u", input_version="v1.0")
    )

    result = processor.process_job_id("job-1")
    assert result.status == JobStatus.PENDING
    result = processor.process_job_id("job-1")
    assert result.status == JobStatus.FAILED
    assert "simulated transient export failure" in result.error_message


def test_error_message_never_contains_full_stack_trace(sharepoint_adapter, powerplatform_adapter):
    _make_application(sharepoint_adapter)
    flaky = _FlakyPowerPlatformAdapter(powerplatform_adapter, fail_times=99)
    processor = _processor(flaky, sharepoint_adapter, max_retries=0)
    sharepoint_adapter.create_job(
        Job(job_id="job-1", application_id="app-1", action=JobAction.DOCUMENT_APPLICATION, requested_by="u", input_version="v1.0")
    )
    result = processor.process_job_id("job-1")
    assert result.status == JobStatus.FAILED
    assert "Traceback" not in result.error_message
    assert len(result.error_message) <= 500


def test_human_review_flow_sets_needs_human_review_then_resumes(sharepoint_adapter, powerplatform_adapter):
    _make_application(sharepoint_adapter)
    copilot = HumanReviewCopilotAdapter(artifact_writer=sharepoint_adapter.upload_job_artifact)
    processor = _processor(powerplatform_adapter, sharepoint_adapter, copilot=copilot)
    processor.copilot_mode = "human_review"

    sharepoint_adapter.create_job(
        Job(job_id="job-1", application_id="app-1", action=JobAction.DOCUMENT_APPLICATION, requested_by="u", input_version="v1.0")
    )
    result = processor.process_job_id("job-1")

    assert result.status == JobStatus.NEEDS_HUMAN_REVIEW
    assert result.copilot_status.value == "PENDING_HUMAN_REVIEW"
    prompt = sharepoint_adapter.read_job_artifact("job-1", "copilot-prompt.md")
    assert "Invoice Approval" in prompt
    assert "<<<TECHNICAL_DOCUMENTATION>>>" in prompt

    human_result = {
        "technical_documentation": "# Technical Doc\n\nHuman written.",
        "user_documentation": "# User Guide\n\nHuman written.",
        "change_summary": "Version: 1.0\n\nChanges:\n- Initial documentation.\n",
    }
    resumed = processor.resume_needs_human_review("job-1", human_result)

    assert resumed.status == JobStatus.COMPLETED
    assert resumed.output_version == "1.0"
    app = sharepoint_adapter.get_application("app-1")
    assert app.documentation_status.value == "DOCUMENTED"


def test_unknown_application_raises_processing_error(sharepoint_adapter, powerplatform_adapter):
    sharepoint_adapter.create_job(
        Job(job_id="job-1", application_id="does-not-exist", action=JobAction.DOCUMENT_APPLICATION, requested_by="u")
    )
    processor = _processor(powerplatform_adapter, sharepoint_adapter, max_retries=0)
    result = processor.process_job_id("job-1")
    assert result.status == JobStatus.FAILED
    assert "does-not-exist" in result.error_message

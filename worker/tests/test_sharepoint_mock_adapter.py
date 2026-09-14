from __future__ import annotations

from worker.models import Application, DocumentationVersion, Job, JobAction


def _job(job_id="job-1", application_id="app-1"):
    return Job(job_id=job_id, application_id=application_id, action=JobAction.DOCUMENT_APPLICATION, requested_by="user@example.com")


def test_claim_job_only_succeeds_once(sharepoint_adapter):
    sharepoint_adapter.create_job(_job())
    assert sharepoint_adapter.claim_job("job-1", "worker-a") is True
    assert sharepoint_adapter.claim_job("job-1", "worker-b") is False
    job = sharepoint_adapter.get_job("job-1")
    assert job.status.value == "RUNNING"
    assert job.worker_id == "worker-a"


def test_claim_job_on_unknown_id_returns_false(sharepoint_adapter):
    assert sharepoint_adapter.claim_job("nope", "worker-a") is False


def test_get_pending_jobs_only_returns_pending(sharepoint_adapter):
    sharepoint_adapter.create_job(_job("job-1"))
    sharepoint_adapter.create_job(_job("job-2"))
    sharepoint_adapter.claim_job("job-1", "worker-a")
    pending = sharepoint_adapter.get_pending_jobs()
    assert [j.job_id for j in pending] == ["job-2"]


def test_application_roundtrip(sharepoint_adapter):
    app = Application(application_id="app-1", title="Invoice Approval", solution_name="InvoiceApproval", environment="DEV")
    sharepoint_adapter.upsert_application(app)
    loaded = sharepoint_adapter.get_application("app-1")
    assert loaded.title == "Invoice Approval"
    assert sharepoint_adapter.get_application("nope") is None


def test_document_library_layout_matches_brief(sharepoint_adapter):
    app = Application(application_id="app-1", title="Invoice Approval", solution_name="InvoiceApproval", environment="DEV")
    sharepoint_adapter.upsert_application(app)
    path = sharepoint_adapter.upload_document("app-1", "1.0", "technical-documentation.md", "# doc")
    assert path.endswith("PowerPlatformDocumentation/Invoice-Approval/1.0/technical-documentation.md")


def test_versions_are_sorted_and_latest_is_findable(sharepoint_adapter):
    for v, prev in [("1.0", None), ("1.2", "1.0"), ("1.1", "1.0")]:
        sharepoint_adapter.create_version_record(
            DocumentationVersion(
                application_id="app-1", version=v, previous_version=prev, change_summary="", documentation_impact="",
                snapshot_path="", diff_path="", technical_documentation_path="", user_documentation_path="", created_by="u",
            )
        )
    versions = sharepoint_adapter.list_versions("app-1")
    assert [v.version for v in versions] == ["1.0", "1.1", "1.2"]
    assert sharepoint_adapter.get_latest_version_record("app-1").version == "1.2"


def test_job_artifact_roundtrip(sharepoint_adapter):
    sharepoint_adapter.upload_job_artifact("job-1", "prompt.md", "hello")
    assert sharepoint_adapter.read_job_artifact("job-1", "prompt.md") == "hello"

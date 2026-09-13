"""Tests for RealSharePointAdapter against an in-memory fake Graph client
(implementing the same surface as GraphClient) -- no real tenant/HTTP
involved."""

from __future__ import annotations

import re

import pytest

from worker.adapters.sharepoint.graph_client import GraphError
from worker.adapters.sharepoint.real import APPLICATIONS_LIST, JOBS_LIST, VERSIONS_LIST, RealSharePointAdapter
from worker.models import Application, DocumentationVersion, Job, JobAction, JobStatus

_FILTER_RE = re.compile(r"fields/(\w+) eq '([^']*)'")


class FakeGraphClient:
    def __init__(self):
        self._next_id = 1
        self.items: dict[str, dict[str, dict]] = {APPLICATIONS_LIST: {}, JOBS_LIST: {}, VERSIONS_LIST: {}}
        self.files: dict[str, str] = {}

    def find_list_id(self, display_name: str) -> str:
        return display_name  # identity mapping is enough for tests

    def list_items(self, list_id: str, filter_expr: str | None = None) -> list[dict]:
        items = list(self.items[list_id].values())
        if filter_expr:
            match = _FILTER_RE.match(filter_expr)
            assert match, f"unsupported filter in test fake: {filter_expr}"
            field, value = match.groups()
            items = [i for i in items if i["fields"].get(field) == value]
        return items

    def create_item(self, list_id: str, fields: dict) -> dict:
        item_id = str(self._next_id)
        self._next_id += 1
        item = {"id": item_id, "fields": dict(fields), "@odata.etag": f'"{item_id}-v1"',
                "createdDateTime": "2026-01-01T00:00:00Z", "lastModifiedDateTime": "2026-01-01T00:00:00Z"}
        self.items[list_id][item_id] = item
        return item

    def update_item_fields(self, list_id: str, item_id: str, fields: dict, etag: str | None = None) -> dict:
        item = self.items[list_id][item_id]
        if etag is not None and item["@odata.etag"] != etag:
            raise GraphError("412 Precondition Failed (simulated)")
        item["fields"].update(fields)
        version = int(item["@odata.etag"].strip('"').split("-v")[1]) + 1
        item["@odata.etag"] = f'"{item_id}-v{version}"'
        return item

    def get_item(self, list_id: str, item_id: str) -> dict:
        return self.items[list_id][item_id]

    def upload_file(self, drive_path: str, content) -> dict:
        self.files[drive_path] = content if isinstance(content, str) else content.decode("utf-8")
        return {}

    def read_file(self, drive_path: str) -> str:
        if drive_path not in self.files:
            raise GraphError(f"404: {drive_path}")
        return self.files[drive_path]


@pytest.fixture
def adapter():
    real_adapter = RealSharePointAdapter.__new__(RealSharePointAdapter)
    real_adapter._graph = FakeGraphClient()
    real_adapter._list_ids = {}
    return real_adapter


def _application(app_id="app-1", title="Invoice Approval"):
    return Application(application_id=app_id, title=title, solution_name="Sol", environment="DEV")


def test_upsert_application_then_get(adapter):
    adapter.upsert_application(_application())
    loaded = adapter.get_application("app-1")
    assert loaded.title == "Invoice Approval"
    assert loaded.solution_name == "Sol"


def test_upsert_application_updates_existing_rather_than_duplicating(adapter):
    adapter.upsert_application(_application())
    app = _application()
    app.current_version = "1.1"
    adapter.upsert_application(app)

    assert len(adapter._graph.items[APPLICATIONS_LIST]) == 1
    assert adapter.get_application("app-1").current_version == "1.1"


def test_get_application_returns_none_when_missing(adapter):
    assert adapter.get_application("nope") is None


def test_create_job_and_claim_job_idempotency(adapter):
    adapter.upsert_application(_application())
    job = Job(job_id="job-1", application_id="app-1", action=JobAction.DOCUMENT_APPLICATION, requested_by="u")
    adapter.create_job(job)

    assert adapter.claim_job("job-1", "worker-a") is True
    assert adapter.claim_job("job-1", "worker-b") is False

    loaded = adapter.get_job("job-1")
    assert loaded.status == JobStatus.RUNNING
    assert loaded.worker_id == "worker-a"
    assert loaded.application_id == "app-1"  # recovered via the job artifact, not a Lookup field


def test_claim_job_returns_false_for_unknown_job(adapter):
    assert adapter.claim_job("nope", "worker-a") is False


def test_get_pending_jobs_excludes_claimed(adapter):
    adapter.upsert_application(_application())
    adapter.create_job(Job(job_id="job-1", application_id="app-1", action=JobAction.DOCUMENT_APPLICATION, requested_by="u"))
    adapter.create_job(Job(job_id="job-2", application_id="app-1", action=JobAction.DOCUMENT_APPLICATION, requested_by="u"))
    adapter.claim_job("job-1", "worker-a")

    pending = adapter.get_pending_jobs()
    assert [j.job_id for j in pending] == ["job-2"]


def test_update_job_maps_python_names_to_graph_field_names(adapter):
    adapter.upsert_application(_application())
    adapter.create_job(Job(job_id="job-1", application_id="app-1", action=JobAction.DOCUMENT_APPLICATION, requested_by="u"))

    adapter.update_job("job-1", status=JobStatus.COMPLETED, output_version="1.0", result_summary="done")

    loaded = adapter.get_job("job-1")
    assert loaded.status == JobStatus.COMPLETED
    assert loaded.output_version == "1.0"
    assert loaded.result_summary == "done"


def test_update_job_unknown_raises_keyerror(adapter):
    with pytest.raises(KeyError):
        adapter.update_job("nope", status=JobStatus.FAILED)


def test_version_crud_and_sorting(adapter):
    adapter.upsert_application(_application())
    for v, prev in [("1.0", None), ("1.2", "1.0"), ("1.1", "1.0")]:
        adapter.create_version_record(
            DocumentationVersion(
                application_id="app-1", version=v, previous_version=prev, change_summary="", documentation_impact="",
                snapshot_path="", diff_path="", technical_documentation_path="", user_documentation_path="", created_by="u",
            )
        )
    versions = adapter.list_versions("app-1")
    assert [v.version for v in versions] == ["1.0", "1.1", "1.2"]
    assert adapter.get_latest_version_record("app-1").version == "1.2"


def test_document_upload_and_snapshot_roundtrip(adapter):
    adapter.upsert_application(_application())
    path = adapter.upload_document("app-1", "1.0", "snapshot.json", '{"solution": {}}')
    assert path == "PowerPlatformDocumentation/Invoice Approval/1.0/snapshot.json"

    snapshot = adapter.get_snapshot("app-1", "1.0")
    assert snapshot == {"solution": {}}


def test_get_snapshot_missing_returns_none(adapter):
    adapter.upsert_application(_application())
    assert adapter.get_snapshot("app-1", "9.9") is None


def test_job_artifact_roundtrip(adapter):
    adapter.upload_job_artifact("job-1", "prompt.md", "hello")
    assert adapter.read_job_artifact("job-1", "prompt.md") == "hello"

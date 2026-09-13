"""REQUIRES CORPORATE ACCESS + REQUIRES TENANT CONFIGURATION.

Real SharePoint adapter placeholder. Do not pick a client library (Microsoft
Graph API, a SharePoint REST wrapper, CSOM, etc.) before corporate access
allows verifying what's actually permitted/supported — see
``docs/CORPORATE_SETUP.md`` Phase 1/3 and ``docs/SHAREPOINT_SETUP.md``.

Whatever library is eventually chosen, this class must expose exactly the
``SharePointAdapter`` interface so ``worker/job_processor.py`` needs zero
changes when switching from ``MockSharePointAdapter`` to this class.
"""

from __future__ import annotations

from worker.models import Application, DocumentationVersion, Job

from .base import SharePointAdapter

_NOT_IMPLEMENTED = (
    "RealSharePointAdapter is a placeholder. It requires a real SharePoint "
    "site (docs/CORPORATE_SETUP.md Phase 1/3) and a verified client library "
    "choice (docs/SHAREPOINT_SETUP.md) before implementation."
)


class RealSharePointAdapter(SharePointAdapter):
    """REQUIRES CORPORATE ACCESS. Not implemented — see module docstring."""

    def __init__(self, site_url: str):
        self.site_url = site_url

    def create_job(self, job: Job) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_job(self, job_id: str) -> Job | None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_pending_jobs(self) -> list[Job]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def claim_job(self, job_id: str, worker_id: str) -> bool:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def update_job(self, job_id: str, **fields) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_application(self, application_id: str) -> Application | None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def list_applications(self) -> list[Application]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def upsert_application(self, application: Application) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_latest_version_record(self, application_id: str) -> DocumentationVersion | None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def list_versions(self, application_id: str) -> list[DocumentationVersion]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def create_version_record(self, version: DocumentationVersion) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_snapshot(self, application_id: str, version: str) -> dict | None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def upload_document(self, application_id: str, version: str, filename: str, content: str) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def upload_job_artifact(self, job_id: str, filename: str, content: str) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def read_job_artifact(self, job_id: str, filename: str) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

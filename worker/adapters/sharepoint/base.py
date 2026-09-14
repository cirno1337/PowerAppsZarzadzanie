"""SharePointAdapter interface.

Mirrors the SharePoint lists documented in ``sharepoint/lists/*.json`` /
``docs/SHAREPOINT_SETUP.md`` and the document library layout documented in
``ARCHITECTURE.md``. Nothing outside this package should talk to SharePoint
(or its mock stand-in) directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from worker.models import Application, DocumentationVersion, Job


class SharePointAdapter(ABC):
    # --- DocumentationJobs (the job queue) ---------------------------------
    @abstractmethod
    def create_job(self, job: Job) -> None: ...

    @abstractmethod
    def get_job(self, job_id: str) -> Job | None: ...

    @abstractmethod
    def get_pending_jobs(self) -> list[Job]: ...

    @abstractmethod
    def claim_job(self, job_id: str, worker_id: str) -> bool:
        """Atomically transition a PENDING job to RUNNING for ``worker_id``.

        Returns False (without raising) if the job was not in PENDING state
        — this is the idempotency boundary described in ARCHITECTURE.md.
        """

    @abstractmethod
    def update_job(self, job_id: str, **fields) -> None: ...

    # --- Applications --------------------------------------------------------
    @abstractmethod
    def get_application(self, application_id: str) -> Application | None: ...

    @abstractmethod
    def list_applications(self) -> list[Application]: ...

    @abstractmethod
    def upsert_application(self, application: Application) -> None: ...

    # --- DocumentationVersions -------------------------------------------
    @abstractmethod
    def get_latest_version_record(self, application_id: str) -> DocumentationVersion | None: ...

    @abstractmethod
    def list_versions(self, application_id: str) -> list[DocumentationVersion]: ...

    @abstractmethod
    def create_version_record(self, version: DocumentationVersion) -> None: ...

    @abstractmethod
    def get_snapshot(self, application_id: str, version: str) -> dict | None:
        """Load the normalized snapshot JSON stored for ``version``, if any."""

    # --- Document library ----------------------------------------------------
    @abstractmethod
    def upload_document(self, application_id: str, version: str, filename: str, content: str) -> str:
        """Write an artifact under PowerPlatformDocumentation/<app>/<version>/ and
        return its path (mock) or URL (real)."""

    # --- Job-scoped artifacts (_jobs/) --------------------------------------
    @abstractmethod
    def upload_job_artifact(self, job_id: str, filename: str, content: str) -> str: ...

    @abstractmethod
    def read_job_artifact(self, job_id: str, filename: str) -> str: ...

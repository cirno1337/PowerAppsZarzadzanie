"""MOCKED SharePointAdapter.

Backs the three SharePoint lists with local JSON files and mirrors the
document library as a local directory tree, under a single git-ignored
runtime directory (default ``.local_data/``). This is a faithful enough
stand-in that ``worker/job_processor.py`` cannot tell it apart from a future
``RealSharePointAdapter`` at the interface level.

Concurrency note: ``claim_job`` here is a read-modify-write against a local
JSON file, which is atomic enough for a single-process mock/test run but is
NOT a substitute for real optimistic-concurrency handling (e.g. ETags)
needed against actual SharePoint with multiple worker instances — see
docs/SHAREPOINT_SETUP.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from worker.models import (
    Application,
    CopilotStatus,
    DocumentationStatus,
    DocumentationVersion,
    Job,
    JobAction,
    JobStatus,
    utcnow,
)

from .base import SharePointAdapter

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_folder_name(name: str) -> str:
    cleaned = _SAFE_NAME_RE.sub("-", name).strip("-")
    return cleaned or "unnamed"


def _job_to_row(job: Job) -> dict:
    return {
        "job_id": job.job_id,
        "application_id": job.application_id,
        "action": job.action.value,
        "requested_by": job.requested_by,
        "requested_at": job.requested_at,
        "status": job.status.value,
        "input_version": job.input_version,
        "output_version": job.output_version,
        "worker_id": job.worker_id,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "error_message": job.error_message,
        "result_summary": job.result_summary,
        "copilot_status": job.copilot_status.value,
        "retry_count": job.retry_count,
    }


def _job_from_row(row: dict) -> Job:
    return Job(
        job_id=row["job_id"],
        application_id=row["application_id"],
        action=JobAction(row["action"]),
        requested_by=row["requested_by"],
        requested_at=row["requested_at"],
        status=JobStatus(row["status"]),
        input_version=row.get("input_version"),
        output_version=row.get("output_version"),
        worker_id=row.get("worker_id"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        error_message=row.get("error_message"),
        result_summary=row.get("result_summary"),
        copilot_status=CopilotStatus(row.get("copilot_status", "NOT_REQUESTED")),
        retry_count=row.get("retry_count", 0),
    )


def _application_to_row(app: Application) -> dict:
    return {
        "application_id": app.application_id,
        "title": app.title,
        "solution_name": app.solution_name,
        "environment": app.environment,
        "environment_url": app.environment_url,
        "owner": app.owner,
        "business_owner": app.business_owner,
        "description": app.description,
        "current_version": app.current_version,
        "documentation_status": app.documentation_status.value,
        "last_documented": app.last_documented,
        "last_analyzed": app.last_analyzed,
        "technical_documentation_url": app.technical_documentation_url,
        "user_documentation_url": app.user_documentation_url,
        "active": app.active,
        "created": app.created,
        "modified": app.modified,
    }


def _application_from_row(row: dict) -> Application:
    return Application(
        application_id=row["application_id"],
        title=row["title"],
        solution_name=row["solution_name"],
        environment=row["environment"],
        environment_url=row.get("environment_url", ""),
        owner=row.get("owner", ""),
        business_owner=row.get("business_owner", ""),
        description=row.get("description", ""),
        current_version=row.get("current_version", ""),
        documentation_status=DocumentationStatus(row.get("documentation_status", "NOT_DOCUMENTED")),
        last_documented=row.get("last_documented"),
        last_analyzed=row.get("last_analyzed"),
        technical_documentation_url=row.get("technical_documentation_url", ""),
        user_documentation_url=row.get("user_documentation_url", ""),
        active=row.get("active", True),
        created=row.get("created", ""),
        modified=row.get("modified", ""),
    )


def _version_to_row(version: DocumentationVersion) -> dict:
    return {
        "application_id": version.application_id,
        "version": version.version,
        "previous_version": version.previous_version,
        "change_summary": version.change_summary,
        "documentation_impact": version.documentation_impact,
        "snapshot_path": version.snapshot_path,
        "diff_path": version.diff_path,
        "technical_documentation_path": version.technical_documentation_path,
        "user_documentation_path": version.user_documentation_path,
        "created_by": version.created_by,
        "created_at": version.created_at,
    }


def _version_from_row(row: dict) -> DocumentationVersion:
    return DocumentationVersion(
        application_id=row["application_id"],
        version=row["version"],
        previous_version=row.get("previous_version"),
        change_summary=row.get("change_summary", ""),
        documentation_impact=row.get("documentation_impact", ""),
        snapshot_path=row.get("snapshot_path", ""),
        diff_path=row.get("diff_path", ""),
        technical_documentation_path=row.get("technical_documentation_path", ""),
        user_documentation_path=row.get("user_documentation_path", ""),
        created_by=row.get("created_by", ""),
        created_at=row.get("created_at", ""),
    )


def _version_sort_key(version_str: str) -> tuple[int, int]:
    major, _, minor = version_str.partition(".")
    return int(major), int(minor or "0")


class MockSharePointAdapter(SharePointAdapter):
    def __init__(self, local_data_dir: Path):
        self.root = Path(local_data_dir)
        self.lists_dir = self.root / "lists"
        self.library_dir = self.root / "PowerPlatformDocumentation"
        self.jobs_artifacts_dir = self.root / "_jobs"
        for d in (self.lists_dir, self.library_dir, self.jobs_artifacts_dir):
            d.mkdir(parents=True, exist_ok=True)

    # --- generic JSON list helpers ------------------------------------------
    def _read_json(self, path: Path, default):
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    @property
    def _jobs_path(self) -> Path:
        return self.lists_dir / "documentation_jobs.json"

    @property
    def _applications_path(self) -> Path:
        return self.lists_dir / "applications.json"

    @property
    def _versions_path(self) -> Path:
        return self.lists_dir / "documentation_versions.json"

    # --- DocumentationJobs ---------------------------------------------------
    def create_job(self, job: Job) -> None:
        rows = self._read_json(self._jobs_path, {})
        rows[job.job_id] = _job_to_row(job)
        self._write_json(self._jobs_path, rows)

    def get_job(self, job_id: str) -> Job | None:
        rows = self._read_json(self._jobs_path, {})
        row = rows.get(job_id)
        return _job_from_row(row) if row else None

    def get_pending_jobs(self) -> list[Job]:
        rows = self._read_json(self._jobs_path, {})
        jobs = [_job_from_row(r) for r in rows.values() if r["status"] == JobStatus.PENDING.value]
        return sorted(jobs, key=lambda j: j.requested_at)

    def claim_job(self, job_id: str, worker_id: str) -> bool:
        rows = self._read_json(self._jobs_path, {})
        row = rows.get(job_id)
        if row is None or row["status"] != JobStatus.PENDING.value:
            return False
        row["status"] = JobStatus.RUNNING.value
        row["worker_id"] = worker_id
        row["started_at"] = utcnow()
        self._write_json(self._jobs_path, rows)
        return True

    def update_job(self, job_id: str, **fields) -> None:
        rows = self._read_json(self._jobs_path, {})
        if job_id not in rows:
            raise KeyError(f"Unknown job_id: {job_id}")
        row = rows[job_id]
        for key, value in fields.items():
            if hasattr(value, "value"):  # Enum
                value = value.value
            row[key] = value
        self._write_json(self._jobs_path, rows)

    # --- Applications --------------------------------------------------------
    def get_application(self, application_id: str) -> Application | None:
        rows = self._read_json(self._applications_path, {})
        row = rows.get(application_id)
        return _application_from_row(row) if row else None

    def list_applications(self) -> list[Application]:
        rows = self._read_json(self._applications_path, {})
        return [_application_from_row(r) for r in rows.values()]

    def upsert_application(self, application: Application) -> None:
        rows = self._read_json(self._applications_path, {})
        rows[application.application_id] = _application_to_row(application)
        self._write_json(self._applications_path, rows)

    # --- DocumentationVersions -------------------------------------------
    def list_versions(self, application_id: str) -> list[DocumentationVersion]:
        rows = self._read_json(self._versions_path, [])
        versions = [_version_from_row(r) for r in rows if r["application_id"] == application_id]
        return sorted(versions, key=lambda v: _version_sort_key(v.version))

    def get_latest_version_record(self, application_id: str) -> DocumentationVersion | None:
        versions = self.list_versions(application_id)
        return versions[-1] if versions else None

    def create_version_record(self, version: DocumentationVersion) -> None:
        rows = self._read_json(self._versions_path, [])
        rows.append(_version_to_row(version))
        self._write_json(self._versions_path, rows)

    def get_snapshot(self, application_id: str, version: str) -> dict | None:
        app_dir = self._app_library_dir(application_id)
        snapshot_path = app_dir / version / "snapshot.json"
        if not snapshot_path.exists():
            return None
        return json.loads(snapshot_path.read_text(encoding="utf-8"))

    # --- Document library ----------------------------------------------------
    def _app_library_dir(self, application_id: str) -> Path:
        application = self.get_application(application_id)
        folder_name = _safe_folder_name(application.title if application else application_id)
        return self.library_dir / folder_name

    def upload_document(self, application_id: str, version: str, filename: str, content: str) -> str:
        target = self._app_library_dir(application_id) / version / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

    # --- Job-scoped artifacts (_jobs/) --------------------------------------
    def upload_job_artifact(self, job_id: str, filename: str, content: str) -> str:
        target = self.jobs_artifacts_dir / job_id / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def read_job_artifact(self, job_id: str, filename: str) -> str:
        target = self.jobs_artifacts_dir / job_id / filename
        return target.read_text(encoding="utf-8")

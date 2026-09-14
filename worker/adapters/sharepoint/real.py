"""Real SharePoint adapter, backed by Microsoft Graph.

Status: **IMPLEMENTED for job/application/version CRUD and document
upload, REQUIRES CORPORATE ACCESS to verify against the company tenant.**
List/column/library provisioning was verified against a real personal test
tenant via ``scripts/provision_sharepoint_graph.py``; this adapter's item
CRUD reuses the same Graph auth pattern
(``worker/adapters/sharepoint/graph_client.py``).

Known gaps (documented, not guessed):

- **Person/Group columns are written, with a graceful-degradation caveat.**
  Verified (2026-09, real tenant): resolving an email to a SharePoint user
  id via the hidden "User Information List"
  (``GraphClient.find_user_lookup_id()``) and writing
  ``{ColumnName}LookupId`` works. The caveat: a person who has never
  visited this specific SharePoint site doesn't exist in that list yet,
  and no Graph "ensure user ahead of time" endpoint was found — if
  resolution fails, the field is silently left unset rather than failing
  the job (a job requester/owner who's never opened the site is a normal,
  expected case, not an error). Read-back does not resolve
  ``{Column}LookupId`` back to an email (would need one extra Graph call
  per person field per read) — ``Owner``/``BusinessOwner``/
  ``RequestedBy``/``CreatedBy`` read as empty strings even when set; this
  is a display-only gap, nothing in the pipeline depends on reading these
  back. None of the provisioned columns are marked server-side "required"
  (see ``scripts/provision_sharepoint_graph.py`` — the `required` flag
  from ``sharepoint/lists/*.json`` was intentionally not mapped into the
  Graph column payload for exactly this reason), so an unresolved person
  field does not block the write.
- **``EnvironmentUrl``/``TechnicalDocumentationUrl``/``UserDocumentationUrl``
  are plain "Single line of text" columns, not "Hyperlink or Picture."**
  Empirically (2026-09, real tenant): writing a Graph ``hyperlinkOrPicture``
  column via the list-items API failed regardless of shape tried (a plain
  string 500'd; the documented ``{"Url": ..., "Description": ...}`` object
  shape 400'd, with no further detail from Graph either time) — root
  cause not identified, possibly an undocumented Graph requirement or a
  provisioning-time quirk. Rather than keep guessing, these columns were
  changed to plain text (`sharepoint/lists/Applications.json` and the
  live test site both updated to match) — a URL still displays and
  launches fine from a text field. Revisit only if a real Hyperlink
  column is specifically required later.
- **claim_job's concurrency control uses SharePoint's ``@odata.etag``**
  (an ``If-Match`` conditional PATCH) rather than a bespoke locking
  scheme — this is the mechanism ``docs/SHAREPOINT_SETUP.md`` calls for,
  verified to at least be a valid Graph pattern, but multi-worker race
  behavior has not been exercised against a real concurrent-write test.
"""

from __future__ import annotations

import json

from worker.models import (
    Application,
    CopilotStatus,
    DocumentationStatus,
    DocumentationVersion,
    Job,
    JobAction,
    JobStatus,
)

from .base import SharePointAdapter
from .graph_client import GraphClient


def _drop_none(fields: dict) -> dict:
    """Graph's list-item write API returned a 500 (empirically, against a
    real tenant) when a dateTime-typed field was sent as an explicit
    ``null`` on create. Omitting unset fields entirely is accepted."""
    return {k: v for k, v in fields.items() if v is not None}


APPLICATIONS_LIST = "Applications"
JOBS_LIST = "DocumentationJobs"
VERSIONS_LIST = "DocumentationVersions"
LIBRARY_NAME = "PowerPlatformDocumentation"


def _application_to_fields(app: Application) -> dict:
    return _drop_none({
        "Title": app.title,
        "ApplicationId": app.application_id,
        "SolutionName": app.solution_name,
        "Environment": app.environment,
        "EnvironmentUrl": app.environment_url,
        "Description": app.description,
        "CurrentVersion": app.current_version,
        "DocumentationStatus": app.documentation_status.value,
        "LastDocumented": app.last_documented,
        "LastAnalyzed": app.last_analyzed,
        "TechnicalDocumentationUrl": app.technical_documentation_url,
        "UserDocumentationUrl": app.user_documentation_url,
        "Active": app.active,
    })


def _application_from_item(item: dict) -> Application:
    f = item["fields"]
    return Application(
        application_id=f.get("ApplicationId", ""),
        title=f.get("Title", ""),
        solution_name=f.get("SolutionName", ""),
        environment=f.get("Environment", ""),
        environment_url=f.get("EnvironmentUrl", "") or "",
        description=f.get("Description", "") or "",
        current_version=f.get("CurrentVersion", "") or "",
        documentation_status=DocumentationStatus(f.get("DocumentationStatus", "NOT_DOCUMENTED")),
        last_documented=f.get("LastDocumented"),
        last_analyzed=f.get("LastAnalyzed"),
        technical_documentation_url=f.get("TechnicalDocumentationUrl", "") or "",
        user_documentation_url=f.get("UserDocumentationUrl", "") or "",
        active=bool(f.get("Active", True)),
        created=item.get("createdDateTime", ""),
        modified=item.get("lastModifiedDateTime", ""),
    )


def _job_to_fields(job: Job) -> dict:
    return _drop_none({
        "Title": job.job_id,
        "Action": job.action.value,
        "RequestedAt": job.requested_at,
        "Status": job.status.value,
        "InputVersion": job.input_version,
        "OutputVersion": job.output_version,
        "WorkerId": job.worker_id,
        "StartedAt": job.started_at,
        "CompletedAt": job.completed_at,
        "ErrorMessage": job.error_message,
        "ResultSummary": job.result_summary,
        "CopilotStatus": job.copilot_status.value,
        "RetryCount": job.retry_count,
    })


def _job_from_item(item: dict, application_id: str) -> Job:
    f = item["fields"]
    return Job(
        job_id=f.get("Title", item["id"]),
        application_id=application_id,
        action=JobAction(f["Action"]),
        requested_by=f.get("RequestedBy", "") or "",
        requested_at=f.get("RequestedAt", ""),
        status=JobStatus(f["Status"]),
        input_version=f.get("InputVersion"),
        output_version=f.get("OutputVersion"),
        worker_id=f.get("WorkerId"),
        started_at=f.get("StartedAt"),
        completed_at=f.get("CompletedAt"),
        error_message=f.get("ErrorMessage"),
        result_summary=f.get("ResultSummary"),
        copilot_status=CopilotStatus(f.get("CopilotStatus", "NOT_REQUESTED")),
        retry_count=int(f.get("RetryCount", 0)),
    )


def _version_to_fields(version: DocumentationVersion) -> dict:
    return _drop_none({
        "Title": f"{version.application_id} v{version.version}",
        "Version": version.version,
        "PreviousVersion": version.previous_version,
        "ChangeSummary": version.change_summary,
        "DocumentationImpact": version.documentation_impact,
        "SnapshotPath": version.snapshot_path,
        "DiffPath": version.diff_path,
        "TechnicalDocumentationPath": version.technical_documentation_path,
        "UserDocumentationPath": version.user_documentation_path,
    })


def _version_from_item(item: dict, application_id: str) -> DocumentationVersion:
    f = item["fields"]
    return DocumentationVersion(
        application_id=application_id,
        version=f["Version"],
        previous_version=f.get("PreviousVersion"),
        change_summary=f.get("ChangeSummary", "") or "",
        documentation_impact=f.get("DocumentationImpact", "") or "",
        snapshot_path=f.get("SnapshotPath", "") or "",
        diff_path=f.get("DiffPath", "") or "",
        technical_documentation_path=f.get("TechnicalDocumentationPath", "") or "",
        user_documentation_path=f.get("UserDocumentationPath", "") or "",
        created_by="",
        created_at=item.get("createdDateTime", ""),
    )


def _version_sort_key(version_str: str) -> tuple[int, int]:
    major, _, minor = version_str.partition(".")
    return int(major), int(minor or "0")


class RealSharePointAdapter(SharePointAdapter):
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, site_url: str):
        self._graph = GraphClient(tenant_id, client_id, client_secret, site_url)
        self._list_ids: dict[str, str] = {}

    def _list_id(self, name: str) -> str:
        if name not in self._list_ids:
            self._list_ids[name] = self._graph.find_list_id(name)
        return self._list_ids[name]

    def _find_application_item(self, application_id: str) -> dict | None:
        items = self._graph.list_items(self._list_id(APPLICATIONS_LIST), filter_expr=f"fields/ApplicationId eq '{application_id}'")
        return items[0] if items else None

    def _find_job_item(self, job_id: str) -> dict | None:
        items = self._graph.list_items(self._list_id(JOBS_LIST), filter_expr=f"fields/Title eq '{job_id}'")
        return items[0] if items else None

    def _resolve_person_fields(self, emails_by_column: dict[str, str]) -> dict:
        """Resolve each ``{ColumnName: email}`` pair to
        ``{ColumnNameLookupId: <SharePoint user id>}``, silently dropping
        any that don't resolve (see module docstring "Known gaps") — never
        raises, since an unresolved person is an expected, non-fatal case."""
        resolved = {}
        for column, email in emails_by_column.items():
            if not email:
                continue
            user_id = self._graph.find_user_lookup_id(email)
            if user_id is not None:
                resolved[f"{column}LookupId"] = user_id
        return resolved

    # --- Applications --------------------------------------------------------
    def get_application(self, application_id: str) -> Application | None:
        item = self._find_application_item(application_id)
        return _application_from_item(item) if item else None

    def list_applications(self) -> list[Application]:
        items = self._graph.list_items(self._list_id(APPLICATIONS_LIST))
        return [_application_from_item(i) for i in items]

    def upsert_application(self, application: Application) -> None:
        existing = self._find_application_item(application.application_id)
        fields = _application_to_fields(application)
        fields.update(self._resolve_person_fields({"Owner": application.owner, "BusinessOwner": application.business_owner}))
        if existing:
            self._graph.update_item_fields(self._list_id(APPLICATIONS_LIST), existing["id"], fields)
        else:
            self._graph.create_item(self._list_id(APPLICATIONS_LIST), fields)

    # --- DocumentationJobs ---------------------------------------------------
    def create_job(self, job: Job) -> None:
        # NOTE: the Application lookup column is intentionally not set here
        # (see module docstring) -- application_id is recovered via the
        # job's Title (job_id) plus a parallel lookup when reading jobs
        # back, not via the SharePoint Lookup relationship, until Person/
        # lookup field writes are verified end-to-end.
        fields = _job_to_fields(job)
        fields.update(self._resolve_person_fields({"RequestedBy": job.requested_by}))
        item = self._graph.create_item(self._list_id(JOBS_LIST), fields)
        # Store application_id alongside the job via a job-scoped artifact,
        # since it isn't in a plain field on DocumentationJobs by design
        # (Application is a Lookup column -- see module docstring).
        self.upload_job_artifact(job.job_id, "_application_id.txt", job.application_id)
        del item  # id not otherwise needed by this method's contract

    def get_job(self, job_id: str) -> Job | None:
        item = self._find_job_item(job_id)
        if not item:
            return None
        application_id = self._read_job_application_id(job_id)
        return _job_from_item(item, application_id)

    def _read_job_application_id(self, job_id: str) -> str:
        try:
            return self.read_job_artifact(job_id, "_application_id.txt")
        except Exception:  # noqa: BLE001 -- best-effort; see module docstring
            return ""

    def get_pending_jobs(self) -> list[Job]:
        items = self._graph.list_items(self._list_id(JOBS_LIST), filter_expr=f"fields/Status eq '{JobStatus.PENDING.value}'")
        jobs = [_job_from_item(i, self._read_job_application_id(i["fields"]["Title"])) for i in items]
        return sorted(jobs, key=lambda j: j.requested_at)

    def claim_job(self, job_id: str, worker_id: str) -> bool:
        item = self._find_job_item(job_id)
        if not item or item["fields"].get("Status") != JobStatus.PENDING.value:
            return False
        from worker.models import utcnow

        etag = item.get("@odata.etag")
        try:
            self._graph.update_item_fields(
                self._list_id(JOBS_LIST),
                item["id"],
                {"Status": JobStatus.RUNNING.value, "WorkerId": worker_id, "StartedAt": utcnow()},
                etag=etag,
            )
        except Exception:  # noqa: BLE001 -- a 412 (etag mismatch) means someone else claimed it first
            return False
        return True

    def update_job(self, job_id: str, **fields) -> None:
        item = self._find_job_item(job_id)
        if not item:
            raise KeyError(f"Unknown job_id: {job_id}")
        graph_fields = {}
        for key, value in fields.items():
            field_name = key[0].upper() + key[1:]
            field_name = {
                "status": "Status", "output_version": "OutputVersion", "worker_id": "WorkerId",
                "started_at": "StartedAt", "completed_at": "CompletedAt", "error_message": "ErrorMessage",
                "result_summary": "ResultSummary", "copilot_status": "CopilotStatus", "retry_count": "RetryCount",
                "input_version": "InputVersion",
            }.get(key, field_name)
            graph_fields[field_name] = value.value if hasattr(value, "value") else value
        self._graph.update_item_fields(self._list_id(JOBS_LIST), item["id"], graph_fields)

    # --- DocumentationVersions -------------------------------------------
    def list_versions(self, application_id: str) -> list[DocumentationVersion]:
        # Filtered client-side rather than via OData $filter: the version
        # count per application is small, and this avoids relying on
        # unverified Graph OData function support (e.g. startswith) for a
        # non-indexed text column.
        items = self._graph.list_items(self._list_id(VERSIONS_LIST))
        prefix = f"{application_id} v"
        versions = [_version_from_item(i, application_id) for i in items if i["fields"].get("Title", "").startswith(prefix)]
        return sorted(versions, key=lambda v: _version_sort_key(v.version))

    def get_latest_version_record(self, application_id: str) -> DocumentationVersion | None:
        versions = self.list_versions(application_id)
        return versions[-1] if versions else None

    def create_version_record(self, version: DocumentationVersion) -> None:
        fields = _version_to_fields(version)
        fields.update(self._resolve_person_fields({"CreatedBy": version.created_by}))
        self._graph.create_item(self._list_id(VERSIONS_LIST), fields)

    def get_snapshot(self, application_id: str, version: str) -> dict | None:
        application = self.get_application(application_id)
        folder = application.title if application else application_id
        try:
            content = self._graph.read_file(f"{LIBRARY_NAME}/{folder}/{version}/snapshot.json")
        except Exception:  # noqa: BLE001
            return None
        return json.loads(content)

    # --- Document library ----------------------------------------------------
    def upload_document(self, application_id: str, version: str, filename: str, content: str) -> str:
        application = self.get_application(application_id)
        folder = application.title if application else application_id
        path = f"{LIBRARY_NAME}/{folder}/{version}/{filename}"
        self._graph.upload_file(path, content)
        return path

    def upload_job_artifact(self, job_id: str, filename: str, content: str) -> str:
        path = f"{LIBRARY_NAME}/_jobs/{job_id}/{filename}"
        self._graph.upload_file(path, content)
        return path

    def read_job_artifact(self, job_id: str, filename: str) -> str:
        return self._graph.read_file(f"{LIBRARY_NAME}/_jobs/{job_id}/{filename}")

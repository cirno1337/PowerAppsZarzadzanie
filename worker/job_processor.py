"""Orchestrates a single job's lifecycle: claim -> execute -> save -> complete.

This module is the one place that ties every other piece together
(adapters, normalization, diff, impact, versioning, documentation
generation). It must never import a concrete adapter implementation
directly — only the abstract base classes — so switching mock/human-review/
real adapters is purely a `worker/config.py` decision. See CLAUDE.md
"Architectural principles".
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from worker.adapters.copilot.base import CopilotAdapter
from worker.adapters.copilot.exceptions import HumanReviewRequired
from worker.adapters.powerplatform.base import PowerPlatformAdapter
from worker.adapters.sharepoint.base import SharePointAdapter
from worker.diff import engine as diff_engine
from worker.diff.impact import analyze_documentation_impact
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
from worker.normalization.normalizer import normalize
from worker.versioning.version import next_version

logger = logging.getLogger(__name__)


class JobProcessingError(Exception):
    """A recoverable-or-not job failure with a safe, user-presentable message."""


class _HumanReviewSignal(Exception):
    """Internal control-flow signal only: the job was already recorded as
    NEEDS_HUMAN_REVIEW by the handler that raised this, so the outer loop
    should not also mark it FAILED."""


class JobProcessor:
    def __init__(
        self,
        powerplatform: PowerPlatformAdapter,
        sharepoint: SharePointAdapter,
        copilot: CopilotAdapter,
        worker_id: str,
        max_retries: int = 3,
        export_dir: Path | None = None,
        copilot_mode: str = "mock",
    ):
        self.powerplatform = powerplatform
        self.sharepoint = sharepoint
        self.copilot = copilot
        self.worker_id = worker_id
        self.max_retries = max_retries
        self.export_dir = export_dir or Path(".local_data/_exports")
        self.copilot_mode = copilot_mode

    def process_next(self) -> Job | None:
        """Claim and process one pending job, if any."""
        for job in self.sharepoint.get_pending_jobs():
            if self.sharepoint.claim_job(job.job_id, self.worker_id):
                return self._process_claimed(job.job_id)
        return None

    def process_job_id(self, job_id: str) -> Job:
        """Claim and process a specific job (used by the demo/tests for determinism)."""
        if not self.sharepoint.claim_job(job_id, self.worker_id):
            raise JobProcessingError(f"Could not claim job {job_id} (not PENDING).")
        return self._process_claimed(job_id)

    def _process_claimed(self, job_id: str) -> Job:
        job = self.sharepoint.get_job(job_id)
        assert job is not None
        try:
            self._handler_for(job.action)(job)
        except _HumanReviewSignal:
            pass  # status already set to NEEDS_HUMAN_REVIEW by the handler
        except Exception as exc:  # noqa: BLE001 - intentional broad catch at the job boundary
            self._handle_failure(job, exc)
        return self.sharepoint.get_job(job_id)

    def _handler_for(self, action: JobAction):
        return {
            JobAction.REGISTER_APPLICATION: self._handle_register_application,
            JobAction.DOCUMENT_APPLICATION: self._handle_full_pipeline,
            JobAction.UPDATE_DOCUMENTATION: self._handle_full_pipeline,
            JobAction.GENERATE_DOCUMENTATION: self._handle_full_pipeline,
            JobAction.EXPORT_SOLUTION: self._handle_export_solution,
            JobAction.ANALYZE_SOLUTION: self._handle_analyze_solution,
            JobAction.COMPARE_VERSION: self._handle_compare_version,
            JobAction.PUBLISH_DOCUMENTATION: self._handle_publish_documentation,
        }[action]

    def _handle_failure(self, job: Job, exc: Exception) -> None:
        logger.error("Job %s failed: %s", job.job_id, exc)
        retry_count = job.retry_count + 1
        if retry_count <= self.max_retries:
            self.sharepoint.update_job(
                job.job_id,
                status=JobStatus.PENDING,
                retry_count=retry_count,
                error_message=_safe_error_message(exc),
                worker_id=None,
                started_at=None,
            )
        else:
            self.sharepoint.update_job(
                job.job_id,
                status=JobStatus.FAILED,
                retry_count=retry_count,
                error_message=_safe_error_message(exc),
                completed_at=utcnow(),
            )

    # ---- action handlers ----------------------------------------------------

    def _handle_register_application(self, job: Job) -> None:
        application = self.sharepoint.get_application(job.application_id)
        if application is None:
            raise JobProcessingError(
                f"REGISTER_APPLICATION job {job.job_id} references unknown application "
                f"{job.application_id}; the Applications list record must exist first "
                "(Power Apps creates it directly)."
            )
        self.sharepoint.update_job(
            job.job_id,
            status=JobStatus.COMPLETED,
            result_summary=f"Application '{application.title}' registered.",
            completed_at=utcnow(),
        )

    def _export_and_normalize(
        self, application: Application, version: str | None = None
    ) -> tuple[dict, dict, Path]:
        """``version`` selects which mock fixture snapshot to pull (e.g. "v1.1")
        — a mock-only convenience distinct from the documentation version
        number (e.g. "1.1") tracked in DocumentationVersions. See
        docs/SHAREPOINT_SETUP.md for the InputVersion/OutputVersion columns.
        """
        self.powerplatform.authenticate()
        # `environment_url` (not the friendly `environment` label like "DEV")
        # is what a real `pac` CLI needs for its --environment argument (a
        # URL, ID, or unique name) — the mock adapter ignores this parameter
        # entirely, which is why this distinction never surfaced until the
        # real adapter was implemented and checked against it.
        package_path = self.powerplatform.export_solution(
            application.solution_name, application.environment_url, self.export_dir, version=version
        )
        unpacked_dir = self.powerplatform.unpack_solution(package_path)
        solution_metadata = self.powerplatform.get_solution_metadata(unpacked_dir)
        application_metadata = self.powerplatform.get_application_metadata(unpacked_dir)
        normalized = normalize(solution_metadata, application_metadata)
        return solution_metadata, normalized, unpacked_dir

    def _compute_diff_and_impact(self, application: Application, normalized: dict):
        previous_version_record = self.sharepoint.get_latest_version_record(application.application_id)
        if previous_version_record is None:
            diff = diff_engine.diff_for_initial_version(normalized, version_to="1.0")
        else:
            previous_snapshot = self.sharepoint.get_snapshot(
                application.application_id, previous_version_record.version
            )
            diff = diff_engine.diff_snapshots(
                previous_snapshot,
                normalized,
                version_from=previous_version_record.version,
                version_to=None,
            )
        impact = analyze_documentation_impact(diff["changes"])
        return previous_version_record, diff, impact

    def _handle_full_pipeline(self, job: Job) -> None:
        application = self.sharepoint.get_application(job.application_id)
        if application is None:
            raise JobProcessingError(f"Unknown application {job.application_id}")

        _solution_metadata, normalized, _unpacked = self._export_and_normalize(
            application, version=job.input_version
        )
        previous_version_record, diff, impact = self._compute_diff_and_impact(application, normalized)
        from_version = previous_version_record.version if previous_version_record else None
        to_version = next_version(from_version, impact["technical_impact"], impact["user_impact"])
        diff["version_to"] = to_version

        # Idempotency: if this output version is already on record, either
        # nothing changed since last time, or a previous run already
        # completed the real work (crash between save and status update).
        # Either way, do not regenerate — just report the existing state.
        existing = next(
            (v for v in self.sharepoint.list_versions(application.application_id) if v.version == to_version),
            None,
        )
        if existing is not None:
            message = (
                "No changes detected since the last documented version."
                if from_version == to_version
                else f"Version {to_version} was already documented (idempotent re-run)."
            )
            self.sharepoint.update_job(
                job.job_id,
                status=JobStatus.COMPLETED,
                output_version=to_version,
                result_summary=message,
                completed_at=utcnow(),
            )
            return

        context = {
            "job_id": job.job_id,
            "app_record": application,
            "normalized": normalized,
            "diff": diff,
            "impact": impact,
            "from_version": from_version,
            "to_version": to_version,
        }

        refined_impact = self.copilot.analyze_changes(diff, impact)
        try:
            technical_doc = self.copilot.generate_technical_documentation(context)
            user_doc = self.copilot.generate_user_documentation(context)
            change_summary = self.copilot.generate_change_summary(context)
        except HumanReviewRequired as exc:
            self.sharepoint.upload_job_artifact(
                job.job_id, "context.json", _serialize_context(context, _solution_metadata)
            )
            self.sharepoint.update_job(
                job.job_id,
                status=JobStatus.NEEDS_HUMAN_REVIEW,
                copilot_status=CopilotStatus.PENDING_HUMAN_REVIEW,
                result_summary=f"Copilot review needed. Prompt: {exc.prompt_path}",
            )
            raise _HumanReviewSignal from exc

        self._save_documentation_artifacts(
            application=application,
            job=job,
            solution_metadata=_solution_metadata,
            normalized=normalized,
            diff=diff,
            impact=refined_impact,
            from_version=from_version,
            to_version=to_version,
            technical_doc=technical_doc,
            user_doc=user_doc,
            change_summary=change_summary,
        )

    def _save_documentation_artifacts(
        self,
        *,
        application: Application,
        job: Job,
        solution_metadata: dict,
        normalized: dict,
        diff: dict,
        impact: dict,
        from_version: str | None,
        to_version: str,
        technical_doc: str,
        user_doc: str,
        change_summary: str,
    ) -> None:
        snapshot_path = self.sharepoint.upload_document(
            application.application_id, to_version, "snapshot.json", json.dumps(normalized, indent=2)
        )
        self.sharepoint.upload_document(
            application.application_id, to_version, "solution-info.json", json.dumps(solution_metadata, indent=2)
        )
        diff_path = self.sharepoint.upload_document(
            application.application_id, to_version, "diff.json", json.dumps(diff, indent=2)
        )
        technical_doc_path = self.sharepoint.upload_document(
            application.application_id, to_version, "technical-documentation.md", technical_doc
        )
        user_doc_path = self.sharepoint.upload_document(
            application.application_id, to_version, "user-guide.md", user_doc
        )

        self.sharepoint.create_version_record(
            DocumentationVersion(
                application_id=application.application_id,
                version=to_version,
                previous_version=from_version,
                change_summary=change_summary,
                documentation_impact=f"technical={impact['technical_impact']} user={impact['user_impact']}",
                snapshot_path=snapshot_path,
                diff_path=diff_path,
                technical_documentation_path=technical_doc_path,
                user_documentation_path=user_doc_path,
                created_by=job.requested_by,
            )
        )

        application.current_version = to_version
        application.documentation_status = DocumentationStatus.DOCUMENTED
        application.last_documented = utcnow()
        application.last_analyzed = utcnow()
        application.technical_documentation_url = technical_doc_path
        application.user_documentation_url = user_doc_path
        application.modified = utcnow()
        self.sharepoint.upsert_application(application)

        copilot_status = CopilotStatus.MOCKED if self.copilot_mode == "mock" else CopilotStatus.COMPLETED
        self.sharepoint.update_job(
            job.job_id,
            status=JobStatus.COMPLETED,
            output_version=to_version,
            result_summary=change_summary.splitlines()[0] if change_summary else "Documentation generated.",
            copilot_status=copilot_status,
            completed_at=utcnow(),
        )

    def _handle_export_solution(self, job: Job) -> None:
        application = self.sharepoint.get_application(job.application_id)
        if application is None:
            raise JobProcessingError(f"Unknown application {job.application_id}")
        solution_metadata, normalized, _ = self._export_and_normalize(application, version=job.input_version)
        self.sharepoint.upload_job_artifact(job.job_id, "solution-info.json", json.dumps(solution_metadata, indent=2))
        self.sharepoint.upload_job_artifact(job.job_id, "snapshot.json", json.dumps(normalized, indent=2))
        self.sharepoint.update_job(
            job.job_id,
            status=JobStatus.COMPLETED,
            result_summary=f"Exported solution '{application.solution_name}'.",
            completed_at=utcnow(),
        )

    def _handle_analyze_solution(self, job: Job) -> None:
        application = self.sharepoint.get_application(job.application_id)
        if application is None:
            raise JobProcessingError(f"Unknown application {job.application_id}")
        _solution_metadata, normalized, _ = self._export_and_normalize(application, version=job.input_version)
        _previous, diff, impact = self._compute_diff_and_impact(application, normalized)

        has_changes = impact["technical_impact"] != "NONE" or impact["user_impact"] != "NONE"
        application.last_analyzed = utcnow()
        application.documentation_status = (
            DocumentationStatus.UPDATE_AVAILABLE if has_changes else DocumentationStatus.DOCUMENTED
        )
        application.modified = utcnow()
        self.sharepoint.upsert_application(application)

        self.sharepoint.update_job(
            job.job_id,
            status=JobStatus.COMPLETED,
            result_summary=(
                f"Analysis complete: {len(diff['changes'])} change(s), "
                f"technical={impact['technical_impact']}, user={impact['user_impact']}."
            ),
            completed_at=utcnow(),
        )

    def _handle_compare_version(self, job: Job) -> None:
        application = self.sharepoint.get_application(job.application_id)
        if application is None:
            raise JobProcessingError(f"Unknown application {job.application_id}")
        previous_version_record = self.sharepoint.get_latest_version_record(application.application_id)
        if previous_version_record is None:
            raise JobProcessingError(
                f"COMPARE_VERSION requires an existing documented version for {application.application_id}."
            )
        _solution_metadata, normalized, _ = self._export_and_normalize(application, version=job.input_version)
        _previous, diff, impact = self._compute_diff_and_impact(application, normalized)
        self.sharepoint.upload_job_artifact(job.job_id, "diff.json", json.dumps(diff, indent=2))
        self.sharepoint.update_job(
            job.job_id,
            status=JobStatus.COMPLETED,
            result_summary=(
                f"Compared against v{previous_version_record.version}: {len(diff['changes'])} change(s) "
                f"(technical={impact['technical_impact']}, user={impact['user_impact']})."
            ),
            completed_at=utcnow(),
        )

    def _handle_publish_documentation(self, job: Job) -> None:
        application = self.sharepoint.get_application(job.application_id)
        if application is None:
            raise JobProcessingError(f"Unknown application {job.application_id}")
        latest = self.sharepoint.get_latest_version_record(application.application_id)
        if latest is None:
            raise JobProcessingError(f"No documentation exists yet for {application.application_id} to publish.")
        application.documentation_status = DocumentationStatus.DOCUMENTED
        application.modified = utcnow()
        self.sharepoint.upsert_application(application)
        self.sharepoint.update_job(
            job.job_id,
            status=JobStatus.COMPLETED,
            output_version=latest.version,
            result_summary=f"Published documentation version {latest.version}.",
            completed_at=utcnow(),
        )

    # ---- resuming a NEEDS_HUMAN_REVIEW job -----------------------------------

    def resume_needs_human_review(self, job_id: str, human_result: dict) -> Job:
        """Continue a job after an administrator has run the saved prompt in an
        approved corporate Copilot product and supplies the result back.

        ``human_result`` must contain the keys ``technical_documentation``,
        ``user_documentation``, and ``change_summary``.
        """
        job = self.sharepoint.get_job(job_id)
        if job is None:
            raise JobProcessingError(f"Unknown job {job_id}")
        if job.status != JobStatus.NEEDS_HUMAN_REVIEW:
            raise JobProcessingError(f"Job {job_id} is not awaiting human review (status={job.status.value}).")

        context = json.loads(self.sharepoint.read_job_artifact(job_id, "context.json"))
        application = self.sharepoint.get_application(context["application_id"])
        context["app_record"] = application
        context["human_result"] = human_result

        technical_doc = self.copilot.generate_technical_documentation(context)
        user_doc = self.copilot.generate_user_documentation(context)
        change_summary = self.copilot.generate_change_summary(context)

        self._save_documentation_artifacts(
            application=application,
            job=job,
            solution_metadata=context.get("solution_metadata", {}),
            normalized=context["normalized"],
            diff=context["diff"],
            impact=context["impact"],
            from_version=context["from_version"],
            to_version=context["to_version"],
            technical_doc=technical_doc,
            user_doc=user_doc,
            change_summary=change_summary,
        )
        return self.sharepoint.get_job(job_id)


def _serialize_context(context: dict, solution_metadata: dict) -> str:
    serializable = {
        "job_id": context["job_id"],
        "application_id": context["app_record"].application_id,
        "solution_metadata": solution_metadata,
        "normalized": context["normalized"],
        "diff": context["diff"],
        "impact": context["impact"],
        "from_version": context["from_version"],
        "to_version": context["to_version"],
    }
    return json.dumps(serializable, indent=2)


def _safe_error_message(exc: Exception) -> str:
    """A short, credential-free error message safe to store in SharePoint."""
    return f"{type(exc).__name__}: {exc}"[:500]

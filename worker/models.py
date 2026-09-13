"""Shared enums and data records used across the worker.

These mirror the SharePoint list schemas documented in
``sharepoint/lists/*.json`` and ``docs/SHAREPOINT_SETUP.md``. Keep the two in
sync when either changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


def utcnow() -> str:
    """ISO-8601 UTC timestamp, second precision, for deterministic tests."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class JobAction(str, Enum):
    REGISTER_APPLICATION = "REGISTER_APPLICATION"
    DOCUMENT_APPLICATION = "DOCUMENT_APPLICATION"
    EXPORT_SOLUTION = "EXPORT_SOLUTION"
    ANALYZE_SOLUTION = "ANALYZE_SOLUTION"
    COMPARE_VERSION = "COMPARE_VERSION"
    GENERATE_DOCUMENTATION = "GENERATE_DOCUMENTATION"
    PUBLISH_DOCUMENTATION = "PUBLISH_DOCUMENTATION"
    UPDATE_DOCUMENTATION = "UPDATE_DOCUMENTATION"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
    CANCELLED = "CANCELLED"


class CopilotStatus(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    MOCKED = "MOCKED"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ImpactLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @property
    def rank(self) -> int:
        return {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}[self.value]

    @staticmethod
    def max(*levels: "ImpactLevel") -> "ImpactLevel":
        return max(levels, key=lambda lvl: lvl.rank) if levels else ImpactLevel.NONE


class DocumentationStatus(str, Enum):
    NOT_DOCUMENTED = "NOT_DOCUMENTED"
    DOCUMENTED = "DOCUMENTED"
    UPDATE_AVAILABLE = "UPDATE_AVAILABLE"
    DOCUMENTATION_FAILED = "DOCUMENTATION_FAILED"


MAX_RETRIES_DEFAULT = 3


@dataclass
class Application:
    """Mirrors the SharePoint ``Applications`` list."""

    application_id: str
    title: str
    solution_name: str
    environment: str
    environment_url: str = ""
    owner: str = ""
    business_owner: str = ""
    description: str = ""
    current_version: str = ""
    documentation_status: DocumentationStatus = DocumentationStatus.NOT_DOCUMENTED
    last_documented: Optional[str] = None
    last_analyzed: Optional[str] = None
    technical_documentation_url: str = ""
    user_documentation_url: str = ""
    active: bool = True
    created: str = field(default_factory=utcnow)
    modified: str = field(default_factory=utcnow)


@dataclass
class Job:
    """Mirrors the SharePoint ``DocumentationJobs`` list."""

    job_id: str
    application_id: str
    action: JobAction
    requested_by: str
    requested_at: str = field(default_factory=utcnow)
    status: JobStatus = JobStatus.PENDING
    input_version: Optional[str] = None
    output_version: Optional[str] = None
    worker_id: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    result_summary: Optional[str] = None
    copilot_status: CopilotStatus = CopilotStatus.NOT_REQUESTED
    retry_count: int = 0


@dataclass
class DocumentationVersion:
    """Mirrors the SharePoint ``DocumentationVersions`` list."""

    application_id: str
    version: str
    previous_version: Optional[str]
    change_summary: str
    documentation_impact: str  # technical/user impact rendered as text
    snapshot_path: str
    diff_path: str
    technical_documentation_path: str
    user_documentation_path: str
    created_by: str
    created_at: str = field(default_factory=utcnow)

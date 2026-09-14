"""Builds concrete adapters from ``WorkerConfig``.

This is the ONLY place that imports concrete adapter implementations
(Mock*/Real*/HumanReview*) — everything else in ``worker/`` depends only on
the abstract base classes. Switching mock -> real is a config change here,
never a code change elsewhere.
"""

from __future__ import annotations

from worker.adapters.copilot.base import CopilotAdapter
from worker.adapters.copilot.human_review import HumanReviewCopilotAdapter
from worker.adapters.copilot.mock import MockCopilotAdapter
from worker.adapters.copilot.real import RealCopilotAdapter
from worker.adapters.powerplatform.base import PowerPlatformAdapter
from worker.adapters.powerplatform.mock import MockPowerPlatformAdapter
from worker.adapters.powerplatform.real import RealPowerPlatformAdapter
from worker.adapters.sharepoint.base import SharePointAdapter
from worker.adapters.sharepoint.mock import MockSharePointAdapter
from worker.adapters.sharepoint.real import RealSharePointAdapter
from worker.config import WorkerConfig


def build_powerplatform_adapter(config: WorkerConfig) -> PowerPlatformAdapter:
    if config.powerplatform_mode == "mock":
        return MockPowerPlatformAdapter(config.mock_solutions_dir)
    if config.powerplatform_mode == "real":
        if not config.powerplatform_environment_url:
            raise ValueError("PPDM_POWERPLATFORM_ENVIRONMENT_URL must be set for PPDM_POWERPLATFORM_MODE=real")
        return RealPowerPlatformAdapter(environment_url=config.powerplatform_environment_url)
    raise ValueError(f"Unknown PPDM_POWERPLATFORM_MODE: {config.powerplatform_mode}")


def build_sharepoint_adapter(config: WorkerConfig) -> SharePointAdapter:
    if config.sharepoint_mode == "mock":
        return MockSharePointAdapter(config.local_data_dir)
    if config.sharepoint_mode == "real":
        missing = [
            name
            for name, value in (
                ("PPDM_SHAREPOINT_TENANT_ID", config.sharepoint_tenant_id),
                ("PPDM_SHAREPOINT_CLIENT_ID", config.sharepoint_client_id),
                ("PPDM_SHAREPOINT_CLIENT_SECRET", config.sharepoint_client_secret),
                ("PPDM_SHAREPOINT_SITE_URL", config.sharepoint_site_url),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"PPDM_SHAREPOINT_MODE=real requires: {', '.join(missing)}")
        return RealSharePointAdapter(
            tenant_id=config.sharepoint_tenant_id,
            client_id=config.sharepoint_client_id,
            client_secret=config.sharepoint_client_secret,
            site_url=config.sharepoint_site_url,
        )
    raise ValueError(f"Unknown PPDM_SHAREPOINT_MODE: {config.sharepoint_mode}")


def build_copilot_adapter(config: WorkerConfig, sharepoint: SharePointAdapter) -> CopilotAdapter:
    if config.copilot_mode == "mock":
        return MockCopilotAdapter()
    if config.copilot_mode == "human_review":
        return HumanReviewCopilotAdapter(artifact_writer=sharepoint.upload_job_artifact)
    if config.copilot_mode == "real":
        return RealCopilotAdapter()
    raise ValueError(f"Unknown PPDM_COPILOT_MODE: {config.copilot_mode}")

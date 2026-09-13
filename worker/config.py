"""Environment-based worker configuration.

No secrets or tenant-specific literals live in this file. Every value below
is read from an environment variable at runtime; the constants here are only
variable *names* and safe defaults for local/mock development.

REQUIRES TENANT CONFIGURATION: PPDM_SHAREPOINT_SITE_URL,
PPDM_POWERPLATFORM_ENVIRONMENT_URL, and any auth-related variables must be
supplied via the environment once a real deployment exists. Never hard-code
them here or anywhere else in this repository.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class WorkerConfig:
    # Adapter selection. "mock" requires no network/corporate access.
    # "real" is a REQUIRES CORPORATE ACCESS / REQUIRES LICENSING VERIFICATION
    # path — see docs/CORPORATE_SETUP.md and docs/COPILOT_INTEGRATION.md
    # before switching any of these to "real".
    powerplatform_mode: str = field(
        default_factory=lambda: os.environ.get("PPDM_POWERPLATFORM_MODE", "mock")
    )
    sharepoint_mode: str = field(
        default_factory=lambda: os.environ.get("PPDM_SHAREPOINT_MODE", "mock")
    )
    copilot_mode: str = field(
        default_factory=lambda: os.environ.get("PPDM_COPILOT_MODE", "mock")
    )

    # Local/mock data locations. Safe defaults, overridable for tests.
    local_data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("PPDM_LOCAL_DATA_DIR", ".local_data"))
    )
    mock_solutions_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("PPDM_MOCK_SOLUTIONS_DIR", "examples/mock_solution")
        )
    )

    # Worker identity/behavior.
    worker_id: str = field(
        default_factory=lambda: os.environ.get("PPDM_WORKER_ID", "local-dev-worker")
    )
    max_retries: int = field(
        default_factory=lambda: int(os.environ.get("PPDM_MAX_RETRIES", "3"))
    )
    poll_interval_seconds: float = field(
        default_factory=lambda: float(os.environ.get("PPDM_POLL_INTERVAL_SECONDS", "5"))
    )

    # REQUIRES TENANT CONFIGURATION — left blank on purpose. Populate via
    # environment variables only; never commit real values.
    sharepoint_site_url: str = field(
        default_factory=lambda: os.environ.get("PPDM_SHAREPOINT_SITE_URL", "")
    )
    powerplatform_environment_url: str = field(
        default_factory=lambda: os.environ.get("PPDM_POWERPLATFORM_ENVIRONMENT_URL", "")
    )

    verbose_logging: bool = field(
        default_factory=lambda: _env_bool("PPDM_VERBOSE_LOGGING", False)
    )

    def require_real_config_or_raise(self, mode_name: str, mode_value: str) -> None:
        if mode_value == "real":
            raise NotImplementedError(
                f"{mode_name} is set to 'real' but the real adapter is a "
                "placeholder pending corporate access/licensing verification. "
                "See docs/CORPORATE_SETUP.md and docs/COPILOT_INTEGRATION.md."
            )


def load_config() -> WorkerConfig:
    return WorkerConfig()

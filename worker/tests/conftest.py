from __future__ import annotations

from pathlib import Path

import pytest

from worker.adapters.powerplatform.mock import MockPowerPlatformAdapter
from worker.adapters.sharepoint.mock import MockSharePointAdapter
from worker.normalization.normalizer import normalize

REPO_ROOT = Path(__file__).resolve().parents[2]
MOCK_SOLUTIONS_DIR = REPO_ROOT / "examples" / "mock_solution"


@pytest.fixture
def powerplatform_adapter() -> MockPowerPlatformAdapter:
    return MockPowerPlatformAdapter(MOCK_SOLUTIONS_DIR)


@pytest.fixture
def sharepoint_adapter(tmp_path) -> MockSharePointAdapter:
    return MockSharePointAdapter(tmp_path / "local_data")


def normalized_snapshot(powerplatform_adapter: MockPowerPlatformAdapter, version: str) -> dict:
    package_path = powerplatform_adapter.export_solution(
        "InvoiceApproval", "DEV", Path("/tmp/unused"), version=version
    )
    unpacked = powerplatform_adapter.unpack_solution(package_path)
    solution_metadata = powerplatform_adapter.get_solution_metadata(unpacked)
    application_metadata = powerplatform_adapter.get_application_metadata(unpacked)
    return normalize(solution_metadata, application_metadata)


@pytest.fixture
def snapshot_v1_0(powerplatform_adapter) -> dict:
    return normalized_snapshot(powerplatform_adapter, "v1.0")


@pytest.fixture
def snapshot_v1_1(powerplatform_adapter) -> dict:
    return normalized_snapshot(powerplatform_adapter, "v1.1")

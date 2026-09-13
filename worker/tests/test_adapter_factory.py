"""Regression tests: build_*_adapter must actually construct the Real*
adapter for mode="real" once it's implemented, not fall through to
NotImplementedError forever. (This exact gap existed for
RealPowerPlatformAdapter after it was implemented but before factory.py
was updated to construct it.)
"""

from __future__ import annotations

import pytest

from worker.adapters.factory import build_copilot_adapter, build_powerplatform_adapter, build_sharepoint_adapter
from worker.adapters.copilot.mock import MockCopilotAdapter
from worker.adapters.copilot.real import RealCopilotAdapter
from worker.adapters.powerplatform.mock import MockPowerPlatformAdapter
from worker.adapters.powerplatform.real import RealPowerPlatformAdapter
from worker.adapters.sharepoint.mock import MockSharePointAdapter
from worker.adapters.sharepoint.real import RealSharePointAdapter
from worker.config import WorkerConfig


def _config(**overrides) -> WorkerConfig:
    config = WorkerConfig()
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def test_mock_powerplatform_adapter_built_for_mock_mode(tmp_path):
    config = _config(powerplatform_mode="mock", mock_solutions_dir=tmp_path)
    assert isinstance(build_powerplatform_adapter(config), MockPowerPlatformAdapter)


def test_real_powerplatform_adapter_built_for_real_mode():
    config = _config(powerplatform_mode="real", powerplatform_environment_url="https://example.crm.dynamics.com")
    adapter = build_powerplatform_adapter(config)
    assert isinstance(adapter, RealPowerPlatformAdapter)
    assert adapter.environment_url == "https://example.crm.dynamics.com"


def test_real_powerplatform_adapter_requires_environment_url():
    config = _config(powerplatform_mode="real", powerplatform_environment_url="")
    with pytest.raises(ValueError, match="PPDM_POWERPLATFORM_ENVIRONMENT_URL"):
        build_powerplatform_adapter(config)


def test_mock_copilot_adapter_built_for_mock_mode():
    config = _config(copilot_mode="mock")
    assert isinstance(build_copilot_adapter(config, sharepoint=None), MockCopilotAdapter)


def test_real_copilot_adapter_built_for_real_mode():
    config = _config(copilot_mode="real")
    assert isinstance(build_copilot_adapter(config, sharepoint=None), RealCopilotAdapter)


def test_mock_sharepoint_adapter_built_for_mock_mode(tmp_path):
    config = _config(sharepoint_mode="mock", local_data_dir=tmp_path)
    assert isinstance(build_sharepoint_adapter(config), MockSharePointAdapter)


def test_real_sharepoint_adapter_built_for_real_mode_with_full_config():
    config = _config(
        sharepoint_mode="real",
        sharepoint_tenant_id="tenant",
        sharepoint_client_id="client",
        sharepoint_client_secret="secret",
        sharepoint_site_url="https://example.sharepoint.com/sites/Test",
    )
    assert isinstance(build_sharepoint_adapter(config), RealSharePointAdapter)


def test_real_sharepoint_adapter_requires_full_config():
    config = _config(sharepoint_mode="real")  # tenant/client/secret/site_url all blank
    with pytest.raises(ValueError, match="PPDM_SHAREPOINT_MODE=real requires"):
        build_sharepoint_adapter(config)

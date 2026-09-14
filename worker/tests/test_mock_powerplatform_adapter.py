from __future__ import annotations

from pathlib import Path

import pytest


def test_list_solutions_finds_fixture(powerplatform_adapter):
    assert "InvoiceApproval" in powerplatform_adapter.list_solutions("DEV")


def test_export_solution_defaults_to_latest_version(powerplatform_adapter):
    path = powerplatform_adapter.export_solution("InvoiceApproval", "DEV", Path("/tmp/unused"))
    assert path.name == "v1.1"


def test_export_solution_can_select_a_specific_version(powerplatform_adapter):
    path = powerplatform_adapter.export_solution("InvoiceApproval", "DEV", Path("/tmp/unused"), version="v1.0")
    assert path.name == "v1.0"


def test_export_unknown_solution_raises_file_not_found(powerplatform_adapter):
    with pytest.raises(FileNotFoundError):
        powerplatform_adapter.export_solution("DoesNotExist", "DEV", Path("/tmp/unused"))


def test_unpack_is_identity_for_mock(powerplatform_adapter):
    path = powerplatform_adapter.export_solution("InvoiceApproval", "DEV", Path("/tmp/unused"), version="v1.0")
    assert powerplatform_adapter.unpack_solution(path) == path


def test_get_solution_metadata(powerplatform_adapter):
    path = powerplatform_adapter.export_solution("InvoiceApproval", "DEV", Path("/tmp/unused"), version="v1.0")
    metadata = powerplatform_adapter.get_solution_metadata(path)
    assert metadata["name"] == "InvoiceApproval"
    assert metadata["version"] == "1.0.0.0"


def test_get_application_metadata_has_all_categories(powerplatform_adapter):
    path = powerplatform_adapter.export_solution("InvoiceApproval", "DEV", Path("/tmp/unused"), version="v1.1")
    metadata = powerplatform_adapter.get_application_metadata(path)
    for key in (
        "applications",
        "flows",
        "environment_variables",
        "connection_references",
        "dependencies",
        "security",
        "components",
    ):
        assert key in metadata
    assert len(metadata["flows"]) == 2  # v1.1 added "Invoice Escalation"


def test_authenticate_is_a_no_op(powerplatform_adapter):
    powerplatform_adapter.authenticate()  # must not raise

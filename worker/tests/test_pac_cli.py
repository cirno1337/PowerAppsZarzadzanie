"""Tests for the pac CLI subprocess wrapper — subprocess.run is monkeypatched
so these run without a real `pac` binary or tenant."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from worker.adapters.powerplatform import pac_cli

SOLUTION_LIST_OUTPUT = """Connected as user@example.com
Connected to... contoso (default)

Listing all Solutions from the current Dataverse organization...
Unique Name                 Friendly Name                         Version Managed
ExampleSolution              Example Solution                      1.0.0.0 False
Default                      Default Solution                      1.0     False
"""


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_solution_list_parses_unique_names(monkeypatch):
    captured = {}

    def fake_run(args, capture_output, text):
        captured["args"] = args
        return _FakeCompletedProcess(stdout=SOLUTION_LIST_OUTPUT)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = pac_cli.solution_list("https://example.crm.dynamics.com")

    assert result == ["ExampleSolution", "Default"]
    assert captured["args"] == [
        "pac",
        "solution",
        "list",
        "--environment",
        "https://example.crm.dynamics.com",
    ]


def test_solution_list_with_no_solutions_returns_empty(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _FakeCompletedProcess(stdout="Connected as user@example.com\n")
    )
    assert pac_cli.solution_list("https://example.crm.dynamics.com") == []


def test_failed_command_raises_pac_cli_error(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _FakeCompletedProcess(returncode=1, stderr="boom")
    )
    with pytest.raises(pac_cli.PacCliError, match="boom"):
        pac_cli.solution_list("https://example.crm.dynamics.com")


def _capturing_run(captured):
    def fake_run(args, **kwargs):
        captured["args"] = args
        return _FakeCompletedProcess()

    return fake_run


def test_auth_create_builds_expected_command(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", _capturing_run(captured))
    pac_cli.auth_create("https://example.crm.dynamics.com")
    assert captured["args"] == ["pac", "auth", "create", "--environment", "https://example.crm.dynamics.com"]


AUTH_LIST_OUTPUT = """Index Active Kind      Name Friendly Name                   Url                                 User                                     Cloud  Type
[1]   *      UNIVERSAL      Personal Productivity (Default) https://x.crm.dynamics.com/         user@contoso.onmicrosoft.com             Public User
[2]                         Some Other Env                  https://y.crm4.dynamics.com/        user@contoso.onmicrosoft.com             Public User
"""


def test_find_auth_profile_index_matches_by_url(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompletedProcess(stdout=AUTH_LIST_OUTPUT))
    assert pac_cli.find_auth_profile_index("https://y.crm4.dynamics.com/") == "2"
    assert pac_cli.find_auth_profile_index("https://y.crm4.dynamics.com") == "2"  # trailing slash tolerant


def test_find_auth_profile_index_returns_none_when_not_found(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompletedProcess(stdout=AUTH_LIST_OUTPUT))
    assert pac_cli.find_auth_profile_index("https://nowhere.crm.dynamics.com/") is None


def test_ensure_authenticated_reuses_existing_profile(monkeypatch):
    captured = {"calls": []}

    def fake_run(args, **kwargs):
        captured["calls"].append(args)
        return _FakeCompletedProcess(stdout=AUTH_LIST_OUTPUT)

    monkeypatch.setattr(subprocess, "run", fake_run)
    pac_cli.ensure_authenticated("https://y.crm4.dynamics.com/")

    assert captured["calls"][0] == ["pac", "auth", "list"]
    assert captured["calls"][1] == ["pac", "auth", "select", "--index", "2"]


def test_ensure_authenticated_creates_new_profile_when_none_matches(monkeypatch):
    captured = {"calls": []}

    def fake_run(args, **kwargs):
        captured["calls"].append(args)
        return _FakeCompletedProcess(stdout=AUTH_LIST_OUTPUT)

    monkeypatch.setattr(subprocess, "run", fake_run)
    pac_cli.ensure_authenticated("https://nowhere.crm.dynamics.com/")

    assert captured["calls"][0] == ["pac", "auth", "list"]
    assert captured["calls"][1] == ["pac", "auth", "create", "--environment", "https://nowhere.crm.dynamics.com/"]


def test_solution_export_builds_expected_command(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(subprocess, "run", _capturing_run(captured))
    output_path = tmp_path / "Example.zip"
    result = pac_cli.solution_export("Example", "https://example.crm.dynamics.com", output_path)

    assert result == output_path
    assert captured["args"] == [
        "pac",
        "solution",
        "export",
        "--name",
        "Example",
        "--environment",
        "https://example.crm.dynamics.com",
        "--path",
        str(output_path),
        "--managed",
        "false",
        "--overwrite",
    ]


def test_solution_unpack_builds_expected_command(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(subprocess, "run", _capturing_run(captured))
    zip_path = tmp_path / "Example.zip"
    target_dir = tmp_path / "unpacked"
    result = pac_cli.solution_unpack(zip_path, target_dir)

    assert result == target_dir
    assert captured["args"] == [
        "pac",
        "solution",
        "unpack",
        "--zipfile",
        str(zip_path),
        "--folder",
        str(target_dir),
        "--packagetype",
        "Unmanaged",
    ]

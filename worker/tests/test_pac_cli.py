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

"""Thin subprocess wrapper around the real Power Platform CLI (`pac`).

Command shapes verified interactively against a real, non-production
personal test tenant in 2026-09 (see ``docs/POWER_PLATFORM_SETUP.md``
"Real export structure — verified findings"). Kept separate from
``RealPowerPlatformAdapter`` so command construction and output parsing are
unit-testable without a real `pac` binary or tenant — tests monkeypatch
``subprocess.run``.

REQUIRES CORPORATE ACCESS to re-verify against the company's own tenant;
`pac`'s exact output formatting can change between CLI versions.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class PacCliError(RuntimeError):
    """A `pac` CLI invocation failed.

    The message is the CLI's own stderr/stdout. `pac` does not print
    credentials on failure in normal operation, but callers should still
    follow SECURITY.md's logging policy (don't log this at a broad
    retention level without review) since it may contain environment
    names/URLs.
    """


def _run(args: list[str]) -> str:
    result = subprocess.run(["pac", *args], capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise PacCliError(f"pac {' '.join(args)} failed: {message}")
    return result.stdout


def auth_create(environment_url: str) -> None:
    """Select (or create) the auth profile for ``environment_url``.

    Does not pass credentials on the command line. This assumes `pac auth
    create` has already been run once out-of-band (interactively via
    device code, or non-interactively via a service principal — see
    docs/CORPORATE_SETUP.md Phase 1 for which the company allows) for this
    machine/service identity; calling this re-selects/verifies the profile
    points at the right environment before other commands run.
    """
    _run(["auth", "create", "--environment", environment_url])


def solution_list(environment_url: str) -> list[str]:
    """Return unique solution names for ``environment_url``.

    Parses `pac`'s human-readable table output because `pac` 2.12.2 has no
    machine-readable (e.g. --json) output option for this command (verified
    2026-09). This is inherently fragile across CLI versions/locales —
    revisit if/when a structured output option is added.
    """
    output = _run(["solution", "list", "--environment", environment_url])
    lines = [line for line in output.splitlines() if line.strip()]
    header_index = next((i for i, line in enumerate(lines) if line.startswith("Unique Name")), None)
    if header_index is None:
        return []
    names = []
    for line in lines[header_index + 1 :]:
        parts = line.split()
        if parts:
            names.append(parts[0])
    return names


def solution_export(solution_name: str, environment_url: str, output_path: Path) -> Path:
    """Export ``solution_name`` (unmanaged) to ``output_path``. Read-only
    with respect to the environment — does not modify it."""
    _run(
        [
            "solution",
            "export",
            "--name",
            solution_name,
            "--environment",
            environment_url,
            "--path",
            str(output_path),
            "--managed",
            "false",
        ]
    )
    return output_path


def solution_unpack(zip_path: Path, target_dir: Path) -> Path:
    """Unpack an exported solution zip into ``target_dir``. Local
    filesystem only — does not touch the environment."""
    _run(
        [
            "solution",
            "unpack",
            "--zipfile",
            str(zip_path),
            "--folder",
            str(target_dir),
            "--packagetype",
            "Unmanaged",
        ]
    )
    return target_dir

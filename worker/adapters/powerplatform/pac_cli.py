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
    """Create a NEW auth profile for ``environment_url``. This always
    starts a fresh login (interactive/device-code/service-principal,
    depending on how the caller's environment is set up) — it does NOT
    reuse an existing profile. Prefer ``ensure_authenticated`` in normal
    operation; use this directly only when a fresh profile is actually
    wanted."""
    _run(["auth", "create", "--environment", environment_url])


def find_auth_profile_index(environment_url: str) -> str | None:
    """Return the ``pac auth list`` index of a profile already pointed at
    ``environment_url``, or None if none exists.

    Parses human-readable table output (no machine-readable option exists
    as of `pac` 2.12.2 — same caveat as `solution_list`). Rather than
    parsing every whitespace-delimited column (fragile: the friendly
    environment name column can itself contain spaces), this only looks
    for a token that parses as the target URL, which is reliable since
    URLs never contain whitespace.
    """
    output = _run(["auth", "list"])
    target = environment_url.rstrip("/")
    for line in output.splitlines():
        tokens = line.split()
        if not tokens or not tokens[0].startswith("["):
            continue
        urls = [t for t in tokens if t.startswith("http")]
        if urls and urls[-1].rstrip("/") == target:
            return tokens[0].strip("[]")
    return None


def ensure_authenticated(environment_url: str) -> None:
    """Reuse an existing auth profile for ``environment_url`` if one
    exists (via `pac auth select`); otherwise create a new one. This is
    what `RealPowerPlatformAdapter.authenticate()` calls — avoids
    triggering a fresh interactive/device-code login on every job when a
    valid profile already exists, which would otherwise hang a headless
    worker waiting on a login that has nowhere to be completed.
    """
    index = find_auth_profile_index(environment_url)
    if index is not None:
        _run(["auth", "select", "--index", index])
    else:
        auth_create(environment_url)


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
    with respect to the environment — does not modify it.

    Passes ``--overwrite``: `pac` errors out by default if
    ``output_path`` already exists (found empirically — a job re-run,
    whether a retry or a later UPDATE_DOCUMENTATION job for the same
    solution, reuses the same export path). The export is a disposable
    working file, not a retained artifact — overwriting it is safe and
    required for idempotent re-runs.
    """
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
            "--overwrite",
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

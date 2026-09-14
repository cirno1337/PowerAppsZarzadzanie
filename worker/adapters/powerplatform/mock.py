"""MOCKED PowerPlatformAdapter.

Reads directly from ``examples/mock_solution/<SolutionName>/<version>/`` and
treats each version directory as an already-exported, already-unpacked
solution — no zip handling needed. This lets the entire pipeline run and be
tested with zero access to Microsoft Power Platform.

Expected fixture layout per version directory:

    solution.json
    apps.json
    flows.json
    environment-variables.json
    connection-references.json
    dependencies.json
    security.json
    components.json

Any missing file is treated as an empty list/dict.
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import PowerPlatformAdapter

_RAW_LIST_FILES = {
    "applications": "apps.json",
    "flows": "flows.json",
    "tables": "tables.json",
    "environment_variables": "environment-variables.json",
    "connection_references": "connection-references.json",
    "dependencies": "dependencies.json",
    "components": "components.json",
}


class MockPowerPlatformAdapter(PowerPlatformAdapter):
    def __init__(self, mock_solutions_dir: Path):
        self.mock_solutions_dir = Path(mock_solutions_dir)

    def authenticate(self) -> None:
        return None  # no-op: mock data requires no authentication

    def list_solutions(self, environment: str) -> list[str]:
        if not self.mock_solutions_dir.exists():
            return []
        return sorted(p.name for p in self.mock_solutions_dir.iterdir() if p.is_dir())

    def _available_versions(self, solution_name: str) -> list[str]:
        solution_dir = self.mock_solutions_dir / solution_name
        if not solution_dir.exists():
            return []
        return sorted(
            (p.name for p in solution_dir.iterdir() if p.is_dir()),
            key=lambda v: tuple(int(part) for part in v.lstrip("v").split(".")),
        )

    def export_solution(
        self,
        solution_name: str,
        environment: str,
        output_dir: Path,
        version: str | None = None,
    ) -> Path:
        versions = self._available_versions(solution_name)
        if not versions:
            raise FileNotFoundError(
                f"No mock fixture versions found for solution '{solution_name}' under "
                f"{self.mock_solutions_dir}"
            )
        chosen = version if version is not None else versions[-1]
        version_dir = self.mock_solutions_dir / solution_name / chosen
        if not version_dir.exists():
            raise FileNotFoundError(f"Mock fixture version '{chosen}' not found: {version_dir}")
        return version_dir

    def unpack_solution(self, package_path: Path) -> Path:
        return package_path  # mock fixtures are already "unpacked"

    def get_solution_metadata(self, unpacked_dir: Path) -> dict:
        solution_file = Path(unpacked_dir) / "solution.json"
        if not solution_file.exists():
            return {"name": "", "version": "", "publisher": "", "description": ""}
        return json.loads(solution_file.read_text(encoding="utf-8"))

    def get_application_metadata(self, unpacked_dir: Path) -> dict:
        unpacked_dir = Path(unpacked_dir)
        result: dict = {}
        for key, filename in _RAW_LIST_FILES.items():
            file_path = unpacked_dir / filename
            result[key] = json.loads(file_path.read_text(encoding="utf-8")) if file_path.exists() else []
        security_file = unpacked_dir / "security.json"
        result["security"] = (
            json.loads(security_file.read_text(encoding="utf-8")) if security_file.exists() else {"roles": []}
        )
        return result

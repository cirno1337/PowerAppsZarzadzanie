"""PowerPlatformAdapter interface.

Never call the Power Platform CLI or PowerShell directly from anywhere
outside a class implementing this interface — see CLAUDE.md and ADR-004.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class PowerPlatformAdapter(ABC):
    @abstractmethod
    def authenticate(self) -> None:
        """Establish (or verify) authentication against Power Platform."""

    @abstractmethod
    def list_solutions(self, environment: str) -> list[str]:
        """Return the names of solutions available in ``environment``."""

    @abstractmethod
    def export_solution(
        self,
        solution_name: str,
        environment: str,
        output_dir: Path,
        version: str | None = None,
    ) -> Path:
        """Export a solution and return the path to the exported package.

        ``version`` is a mock-only convenience for selecting which point in
        time to export (real exports always return "whatever is currently
        deployed"; there is no way to time-travel a real environment). Real
        implementations should ignore/reject an explicit ``version``.
        """

    @abstractmethod
    def unpack_solution(self, package_path: Path) -> Path:
        """Unpack an exported solution package and return the unpacked directory."""

    @abstractmethod
    def get_solution_metadata(self, unpacked_dir: Path) -> dict:
        """Return solution-level metadata: name, version, publisher, description."""

    @abstractmethod
    def get_application_metadata(self, unpacked_dir: Path) -> dict:
        """Return component-level metadata: applications, flows, tables,
        environment_variables, connection_references, dependencies,
        security, components — the raw input to normalization."""

"""REQUIRES CORPORATE ACCESS — real Power Platform CLI adapter placeholder.

Do not implement the method bodies below based on assumptions. Follow
``docs/CORPORATE_SETUP.md`` Phase 2 first to verify actual `pac` CLI
behavior against a real, non-production environment, then replace the
``NotImplementedError`` in each method with a ``subprocess`` call to `pac`,
translating its output into the exact same return shapes
``MockPowerPlatformAdapter`` produces so nothing above this adapter needs to
change.

Intended (unverified) command mapping, for reference only:

    authenticate()             -> pac auth create --environment <url> [--applicationId ... --tenant ...]
    list_solutions(env)        -> pac solution list --environment <url>
    export_solution(...)       -> pac solution export --name <solution> --path <output_dir> --environment <url>
    unpack_solution(pkg)       -> pac solution unpack --zipfile <pkg> --folder <dir>
    get_solution_metadata(dir) -> parse <dir>/Other/Solution.xml
    get_application_metadata() -> parse CanvasApps/*, Workflows/*, etc. under <dir>
"""

from __future__ import annotations

from pathlib import Path

from .base import PowerPlatformAdapter

_NOT_IMPLEMENTED = (
    "RealPowerPlatformAdapter is a placeholder. It requires corporate network "
    "access and a verified `pac` CLI workflow — see docs/CORPORATE_SETUP.md "
    "Phase 2 before implementing this method."
)


class RealPowerPlatformAdapter(PowerPlatformAdapter):
    """REQUIRES CORPORATE ACCESS. Not implemented — see module docstring."""

    def __init__(self, environment_url: str):
        self.environment_url = environment_url

    def authenticate(self) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def list_solutions(self, environment: str) -> list[str]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def export_solution(
        self,
        solution_name: str,
        environment: str,
        output_dir: Path,
        version: str | None = None,
    ) -> Path:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def unpack_solution(self, package_path: Path) -> Path:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_solution_metadata(self, unpacked_dir: Path) -> dict:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_application_metadata(self, unpacked_dir: Path) -> dict:
        raise NotImplementedError(_NOT_IMPLEMENTED)

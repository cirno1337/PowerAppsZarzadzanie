"""Real Power Platform CLI adapter.

Status per method — see ``docs/POWER_PLATFORM_SETUP.md`` "Real export
structure — verified findings" for what was actually checked and how:

- ``authenticate``, ``list_solutions``, ``export_solution``,
  ``unpack_solution``: **IMPLEMENTED**, shelling out to `pac` via
  ``pac_cli.py``. Command shapes were verified interactively against a
  real, non-production personal test tenant (2026-09) — see
  ``docs/CORPORATE_SETUP.md`` Phase 2. Still REQUIRES CORPORATE ACCESS to
  re-verify against the company's actual tenant/CLI version before trusting
  this in production, and REQUIRES TENANT CONFIGURATION for the real
  authentication method (device code was used for manual verification;
  the worker's own unattended auth method — service principal vs. managed
  identity — is still undecided, see SECURITY.md and
  ``docs/CORPORATE_SETUP.md`` Phase 1).
- ``get_solution_metadata``: **IMPLEMENTED** for the verified shape
  (``Other/Solution.xml``).
- ``get_application_metadata``: **PARTIALLY IMPLEMENTED**. Flows,
  environment variables, and connection references are implemented and
  verified against a real export. Canvas apps/screens, Dataverse tables,
  security roles, and generic components are **NOT YET VERIFIED** against
  a real export containing those — left as empty lists rather than
  guessed. REQUIRES CORPORATE ACCESS (or further personal-tenant
  exploration) with a solution containing a canvas app before those can be
  implemented for real; see ``worker/adapters/powerplatform/xml_parsing.py``
  for where to add them once verified.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import pac_cli, xml_parsing
from .base import PowerPlatformAdapter


class RealPowerPlatformAdapter(PowerPlatformAdapter):
    def __init__(self, environment_url: str):
        self.environment_url = environment_url

    def authenticate(self) -> None:
        pac_cli.ensure_authenticated(self.environment_url)

    def list_solutions(self, environment: str) -> list[str]:
        return pac_cli.solution_list(environment)

    def export_solution(
        self,
        solution_name: str,
        environment: str,
        output_dir: Path,
        version: str | None = None,
    ) -> Path:
        # `version` is a mock-only convenience (see base.py) — a real export
        # always returns whatever is currently deployed; there is no way to
        # time-travel a real environment, so it's accepted for interface
        # compatibility and otherwise ignored here.
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        zip_path = output_dir / f"{solution_name}.zip"
        return pac_cli.solution_export(solution_name, environment, zip_path)

    def unpack_solution(self, package_path: Path) -> Path:
        package_path = Path(package_path)
        target_dir = package_path.parent / package_path.stem
        return pac_cli.solution_unpack(package_path, target_dir)

    def get_solution_metadata(self, unpacked_dir: Path) -> dict:
        unpacked_dir = Path(unpacked_dir)
        return xml_parsing.parse_solution_manifest(unpacked_dir / "Other" / "Solution.xml")

    def get_application_metadata(self, unpacked_dir: Path) -> dict:
        unpacked_dir = Path(unpacked_dir)

        flows = []
        for flow_path in xml_parsing.find_flow_files(unpacked_dir / "Workflows"):
            flow_json = _read_json(flow_path)
            flows.append(xml_parsing.parse_flow_definition(flow_json, name=_flow_display_name(flow_path)))

        return {
            # NOT YET VERIFIED against a real canvas-app-containing export —
            # see module docstring.
            "applications": [],
            "flows": flows,
            "tables": [],
            "environment_variables": xml_parsing.parse_environment_variables(
                unpacked_dir / "environmentvariabledefinitions"
            ),
            "connection_references": xml_parsing.parse_connection_references(
                unpacked_dir / "Other" / "Customizations.xml"
            ),
            "dependencies": [],
            "security": {"roles": []},
            "components": [],
        }


def _read_json(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


_TRAILING_GUID_RE = re.compile(r"-[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$")


def _flow_display_name(flow_path: Path) -> str:
    # Real filenames look like "Button-Getitems-<guid>.json", where <guid>
    # is a full 8-4-4-4-12 hex GUID containing its own internal hyphens —
    # a naive rsplit("-", 1) only strips the last hyphen segment and
    # leaves most of the GUID behind (found empirically running this
    # against a real export — see docs/POWER_PLATFORM_SETUP.md). Strip the
    # whole trailing GUID with a regex instead. Not guaranteed identical
    # to the display name shown in the maker portal; good enough for
    # diffing purposes, which only need stability across exports of the
    # same flow, not a perfect match.
    stem = flow_path.stem
    return _TRAILING_GUID_RE.sub("", stem)

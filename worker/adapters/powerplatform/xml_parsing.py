"""Parsers for real (unpacked, unmanaged) Power Platform solution exports.

Verified against a real personal test tenant export (2026-09) — see
``docs/POWER_PLATFORM_SETUP.md`` "Real export structure — verified
findings". These are pure functions operating on already-read
files/dicts (only file I/O is a plain read), so they're fully unit
-testable with small synthetic fixtures that mimic the verified shape,
without needing `pac` CLI or a live tenant.

REQUIRES CORPORATE ACCESS to validate against a canvas-app-containing
solution and a managed export — only an unmanaged solution containing
flows/environment variables/connection references has been verified so far.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# Friendly names for common standard (non-Premium) connectors, keyed by the
# `shared_*` alias found in `connectorid`/`api.name`. Extend as new
# connectors are encountered — there is no built-in friendly-name mapping
# in the export itself.
_CONNECTOR_FRIENDLY_NAMES = {
    "shared_sharepointonline": "SharePoint",
    "shared_office365": "Office 365 Outlook",
    "shared_office365users": "Office 365 Users",
    "shared_approvals": "Approvals",
    "shared_teams": "Microsoft Teams",
    "shared_commondataserviceforapps": "Microsoft Dataverse",
    "shared_planner": "Planner",
}

# Environment variable type codes -> friendly name. Best-effort, based on
# codes actually observed in a real export plus community documentation —
# NOT independently verified against an authoritative Microsoft Learn type
# reference. Verify before trusting a code not covered here.
_ENV_VAR_TYPE_NAMES = {
    "100000000": "String",
    "100000001": "Number",
    "100000002": "Yes/No",
    "100000003": "JSON",
    "100000004": "Data source",
    "100000005": "Secret",
}

_ISO8601_HOURS_RE = re.compile(r"^PT(\d+)H$")


def friendly_connector_name(connector_id_or_alias: str) -> str:
    alias = connector_id_or_alias.rsplit("/", 1)[-1]
    return _CONNECTOR_FRIENDLY_NAMES.get(alias, alias)


def parse_solution_manifest(solution_xml_path: Path) -> dict:
    """Parse ``Other/Solution.xml`` into {name, version, publisher, description}."""
    if not solution_xml_path.exists():
        return {"name": "", "version": "", "publisher": "", "description": ""}
    root = ET.parse(solution_xml_path).getroot()
    manifest = root.find("SolutionManifest")
    if manifest is None:
        return {"name": "", "version": "", "publisher": "", "description": ""}
    description = ""
    desc_el = manifest.find("Descriptions/Description")
    if desc_el is not None:
        description = desc_el.get("description", "") or ""
    return {
        "name": manifest.findtext("UniqueName") or "",
        "version": manifest.findtext("Version") or "",
        "publisher": manifest.findtext("Publisher/UniqueName") or "",
        "description": description,
    }


def parse_connection_references(customizations_xml_path: Path) -> list[dict]:
    """Parse ``Other/Customizations.xml``'s ``<connectionreferences>`` into
    ``[{"name", "connector"}, ...]``."""
    if not customizations_xml_path.exists():
        return []
    root = ET.parse(customizations_xml_path).getroot()
    result = []
    for cr in root.findall(".//connectionreferences/connectionreference"):
        logical_name = cr.get("connectionreferencelogicalname", "")
        display_name = cr.findtext("connectionreferencedisplayname") or logical_name
        connector_id = cr.findtext("connectorid") or ""
        result.append({"name": display_name, "connector": friendly_connector_name(connector_id)})
    return result


def parse_environment_variables(environmentvariabledefinitions_dir: Path) -> list[dict]:
    """Parse ``environmentvariabledefinitions/<schemaname>/`` subfolders
    (each holding ``environmentvariabledefinition.xml`` +
    ``environmentvariablevalues.json``) into
    ``[{"name", "type", "default_value"}, ...]``."""
    if not environmentvariabledefinitions_dir.exists():
        return []
    result = []
    for var_dir in sorted(p for p in environmentvariabledefinitions_dir.iterdir() if p.is_dir()):
        definition_path = var_dir / "environmentvariabledefinition.xml"
        if not definition_path.exists():
            continue
        root = ET.parse(definition_path).getroot()
        schema_name = root.get("schemaname", var_dir.name)
        display_name = ""
        label_el = root.find("displayname/label")
        if label_el is not None:
            display_name = label_el.get("description", "") or ""
        type_code = root.findtext("type") or ""
        type_name = _ENV_VAR_TYPE_NAMES.get(type_code, f"Unknown ({type_code})")

        default_value = ""
        values_path = var_dir / "environmentvariablevalues.json"
        if values_path.exists():
            values = json.loads(values_path.read_text(encoding="utf-8"))
            default_value = (
                values.get("environmentvariablevalues", {})
                .get("environmentvariablevalue", {})
                .get("value", "")
            )
        result.append(
            {"name": display_name or schema_name, "type": type_name, "default_value": default_value}
        )
    return result


def _humanize_step_name(name: str) -> str:
    return name.replace("_", " ").strip()


def _order_actions_by_run_after(actions: dict) -> list[str]:
    """Topologically sort a Logic Apps-style ``actions`` dict by its
    ``runAfter`` dependency graph (there is no implicit array order in the
    real format — order is a DAG). Ties broken alphabetically for
    determinism; a cyclic/malformed graph falls back to alphabetical order
    for whatever's left rather than looping forever."""
    remaining = {name: set(body.get("runAfter", {}).keys()) for name, body in actions.items()}
    satisfied: set[str] = set()
    ordered: list[str] = []
    while remaining:
        ready = sorted(name for name, deps in remaining.items() if deps <= satisfied)
        if not ready:
            ordered.extend(sorted(remaining.keys()))
            break
        for name in ready:
            ordered.append(name)
            satisfied.add(name)
            del remaining[name]
    return ordered


def _extract_timeout(actions: dict) -> str:
    for body in actions.values():
        timeout = body.get("limit", {}).get("timeout")
        if timeout:
            match = _ISO8601_HOURS_RE.match(timeout)
            return f"{match.group(1)}h" if match else timeout
    return ""


def parse_flow_definition(flow_json: dict, name: str) -> dict:
    """Parse a ``Workflows/<name>-<guid>.json`` Logic Apps-style flow
    definition into the normalized ``{"name", "trigger", "actions",
    "conditions", "timeout"}`` shape.

    Conditions are approximated as any ``If``/``Switch`` step — the real
    condition *expressions* are richer than our normalized schema's plain
    strings, so this is intentionally a lossy summary for diffing/
    documentation purposes, not a full translation of the flow's logic.
    """
    definition = flow_json.get("properties", {}).get("definition", {})
    triggers = definition.get("triggers", {})
    trigger_desc = ""
    if triggers:
        trigger_name, trigger_body = next(iter(triggers.items()))
        trigger_desc = _humanize_step_name(trigger_name)
        recurrence = trigger_body.get("recurrence")
        if recurrence:
            frequency = str(recurrence.get("frequency", "")).lower()
            trigger_desc += f" (every {recurrence.get('interval')} {frequency}(s))"

    actions = definition.get("actions", {})
    ordered_names = _order_actions_by_run_after(actions)
    condition_names = {n for n in ordered_names if actions[n].get("type") in ("If", "Switch")}

    return {
        "name": name,
        "trigger": trigger_desc,
        "actions": [_humanize_step_name(n) for n in ordered_names if n not in condition_names],
        "conditions": [_humanize_step_name(n) for n in ordered_names if n in condition_names],
        "timeout": _extract_timeout(actions),
    }


def find_flow_files(workflows_dir: Path) -> list[Path]:
    """Return the flow definition JSON files under ``Workflows/`` (excludes
    the sibling ``*.json.data.xml`` metadata files)."""
    if not workflows_dir.exists():
        return []
    return sorted(p for p in workflows_dir.glob("*.json") if not p.name.endswith(".data.xml"))

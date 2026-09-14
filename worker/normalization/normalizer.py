"""Builds a deterministic normalized snapshot from raw adapter metadata.

Input shapes (as produced by any ``PowerPlatformAdapter``):

- ``solution_metadata``: dict with keys ``name``, ``version``, ``publisher``,
  ``description`` (from ``get_solution_metadata``).
- ``application_metadata``: dict with keys ``applications``, ``flows``,
  ``tables``, ``environment_variables``, ``connection_references``,
  ``dependencies``, ``security``, ``components`` (from
  ``get_application_metadata``). Any missing key defaults to an empty
  list/dict — real exports won't always populate every category.
"""

from __future__ import annotations

from .schema import SCHEMA_VERSION, sort_by_name


def _screen(raw: dict) -> dict:
    return {
        "name": raw["name"],
        "controls_summary": raw.get("controls_summary", ""),
    }


def _application(raw: dict) -> dict:
    return {
        "name": raw["name"],
        "type": raw.get("type", "canvas"),
        "screens": sort_by_name([_screen(s) for s in raw.get("screens", [])]),
    }


def _flow(raw: dict) -> dict:
    return {
        "name": raw["name"],
        "trigger": raw.get("trigger", ""),
        "actions": list(raw.get("actions", [])),
        "conditions": list(raw.get("conditions", [])),
        "timeout": raw.get("timeout", ""),
    }


def _table(raw: dict) -> dict:
    return {
        "name": raw["name"],
        "type": raw.get("type", ""),
    }


def _environment_variable(raw: dict) -> dict:
    return {
        "name": raw["name"],
        "type": raw.get("type", ""),
        "default_value": raw.get("default_value", ""),
    }


def _connection_reference(raw: dict) -> dict:
    return {
        "name": raw["name"],
        "connector": raw.get("connector", ""),
    }


def _dependency(raw: dict) -> dict:
    return {
        "name": raw["name"],
        "type": raw.get("type", ""),
    }


def _component(raw: dict) -> dict:
    return {
        "name": raw["name"],
        "type": raw.get("type", ""),
    }


def normalize(solution_metadata: dict, application_metadata: dict) -> dict:
    """Produce the deterministic normalized snapshot.

    Both arguments are plain dicts as returned by a ``PowerPlatformAdapter``
    (mock or real) — this function never touches the filesystem or an
    adapter directly, keeping it trivially unit-testable.
    """
    security_raw = application_metadata.get("security", {}) or {}

    return {
        "schema_version": SCHEMA_VERSION,
        "solution": {
            "name": solution_metadata.get("name", ""),
            "version": solution_metadata.get("version", ""),
            "publisher": solution_metadata.get("publisher", ""),
            "description": solution_metadata.get("description", ""),
        },
        "applications": sort_by_name(
            [_application(a) for a in application_metadata.get("applications", [])]
        ),
        "flows": sort_by_name([_flow(f) for f in application_metadata.get("flows", [])]),
        "tables": sort_by_name([_table(t) for t in application_metadata.get("tables", [])]),
        "environment_variables": sort_by_name(
            [_environment_variable(v) for v in application_metadata.get("environment_variables", [])]
        ),
        "connection_references": sort_by_name(
            [_connection_reference(c) for c in application_metadata.get("connection_references", [])]
        ),
        "dependencies": sort_by_name(
            [_dependency(d) for d in application_metadata.get("dependencies", [])]
        ),
        "security": {"roles": sorted(security_raw.get("roles", []))},
        "components": sort_by_name(
            [_component(c) for c in application_metadata.get("components", [])]
        ),
    }

"""Semantic diff engine.

Compares two normalized snapshots (see ``worker/normalization/schema.py``)
field-by-field per component category and produces the structured diff model
described in ``ARCHITECTURE.md``:

    {
      "version_from": "1.0",
      "version_to": "1.1",
      "changes": [
        {"type": "ADDED", "component": "flow", "name": "Invoice Escalation"},
        {"type": "MODIFIED", "component": "flow", "name": "Invoice Approval",
         "details": ["timeout changed from 24h to 48h"]}
      ]
    }

This never falls back to a textual/line diff — every comparison here is
field-aware. See ADR-007 in DECISIONS.md.
"""

from __future__ import annotations

from worker.normalization.schema import empty_normalized_snapshot


def compare_flow(old: dict, new: dict) -> list[str]:
    details: list[str] = []
    if old["trigger"] != new["trigger"]:
        details.append(f"trigger changed from '{old['trigger']}' to '{new['trigger']}'")
    if old["timeout"] != new["timeout"]:
        details.append(f"timeout changed from {old['timeout']} to {new['timeout']}")
    for action in new["actions"]:
        if action not in old["actions"]:
            details.append(f"action added: '{action}'")
    for action in old["actions"]:
        if action not in new["actions"]:
            details.append(f"action removed: '{action}'")
    for condition in new["conditions"]:
        if condition not in old["conditions"]:
            details.append(f"condition added: '{condition}'")
    for condition in old["conditions"]:
        if condition not in new["conditions"]:
            details.append(f"condition removed: '{condition}'")
    return details


def compare_screen(old: dict, new: dict) -> list[str]:
    if old["controls_summary"] != new["controls_summary"]:
        return [
            f"controls changed from '{old['controls_summary']}' to '{new['controls_summary']}'"
        ]
    return []


def compare_application(old: dict, new: dict) -> list[str]:
    if old["type"] != new["type"]:
        return [f"type changed from {old['type']} to {new['type']}"]
    return []


def compare_table(old: dict, new: dict) -> list[str]:
    if old["type"] != new["type"]:
        return [f"type changed from {old['type']} to {new['type']}"]
    return []


def compare_environment_variable(old: dict, new: dict) -> list[str]:
    details: list[str] = []
    if old["type"] != new["type"]:
        details.append(f"type changed from {old['type']} to {new['type']}")
    if old["default_value"] != new["default_value"]:
        details.append(
            f"default value changed from '{old['default_value']}' to '{new['default_value']}'"
        )
    return details


def compare_connection_reference(old: dict, new: dict) -> list[str]:
    if old["connector"] != new["connector"]:
        return [f"connector changed from {old['connector']} to {new['connector']}"]
    return []


def compare_dependency(old: dict, new: dict) -> list[str]:
    if old["type"] != new["type"]:
        return [f"type changed from {old['type']} to {new['type']}"]
    return []


def compare_component(old: dict, new: dict) -> list[str]:
    if old["type"] != new["type"]:
        return [f"type changed from {old['type']} to {new['type']}"]
    return []


def _diff_named_list(
    component: str,
    old_items: list[dict],
    new_items: list[dict],
    compare,
    name_prefix: str = "",
) -> list[dict]:
    old_by_name = {item["name"]: item for item in old_items}
    new_by_name = {item["name"]: item for item in new_items}
    changes: list[dict] = []

    for name in sorted(set(new_by_name) - set(old_by_name)):
        changes.append({"type": "ADDED", "component": component, "name": f"{name_prefix}{name}"})
    for name in sorted(set(old_by_name) - set(new_by_name)):
        changes.append({"type": "REMOVED", "component": component, "name": f"{name_prefix}{name}"})
    for name in sorted(set(old_by_name) & set(new_by_name)):
        details = compare(old_by_name[name], new_by_name[name])
        if details:
            changes.append(
                {
                    "type": "MODIFIED",
                    "component": component,
                    "name": f"{name_prefix}{name}",
                    "details": details,
                }
            )
    return changes


def _diff_solution(old: dict, new: dict) -> list[dict]:
    details = []
    if old["name"] != new["name"]:
        details.append(f"name changed from '{old['name']}' to '{new['name']}'")
    if old["publisher"] != new["publisher"]:
        details.append(f"publisher changed from '{old['publisher']}' to '{new['publisher']}'")
    if old["description"] != new["description"]:
        details.append("description changed")
    if not details:
        return []
    return [
        {
            "type": "MODIFIED",
            "component": "solution",
            "name": new["name"] or old["name"],
            "details": details,
        }
    ]


def _diff_applications_and_screens(old_apps: list[dict], new_apps: list[dict]) -> list[dict]:
    changes: list[dict] = []
    old_by_name = {app["name"]: app for app in old_apps}
    new_by_name = {app["name"]: app for app in new_apps}

    for name in sorted(set(new_by_name) - set(old_by_name)):
        changes.append({"type": "ADDED", "component": "application", "name": name})
    for name in sorted(set(old_by_name) - set(new_by_name)):
        changes.append({"type": "REMOVED", "component": "application", "name": name})
    for name in sorted(set(old_by_name) & set(new_by_name)):
        old_app, new_app = old_by_name[name], new_by_name[name]
        details = compare_application(old_app, new_app)
        if details:
            changes.append(
                {"type": "MODIFIED", "component": "application", "name": name, "details": details}
            )
        changes.extend(
            _diff_named_list(
                "screen",
                old_app["screens"],
                new_app["screens"],
                compare_screen,
                name_prefix=f"{name} / ",
            )
        )
    return changes


def _diff_security(old_security: dict, new_security: dict) -> list[dict]:
    old_roles = set(old_security.get("roles", []))
    new_roles = set(new_security.get("roles", []))
    changes = []
    for role in sorted(new_roles - old_roles):
        changes.append({"type": "ADDED", "component": "security_role", "name": role})
    for role in sorted(old_roles - new_roles):
        changes.append({"type": "REMOVED", "component": "security_role", "name": role})
    return changes


def diff_snapshots(old: dict, new: dict, version_from: str | None, version_to: str) -> dict:
    """Compute the structured diff between two normalized snapshots."""
    changes: list[dict] = []
    changes.extend(_diff_solution(old["solution"], new["solution"]))
    changes.extend(_diff_applications_and_screens(old["applications"], new["applications"]))
    changes.extend(_diff_named_list("flow", old["flows"], new["flows"], compare_flow))
    changes.extend(_diff_named_list("table", old["tables"], new["tables"], compare_table))
    changes.extend(
        _diff_named_list(
            "environment_variable",
            old["environment_variables"],
            new["environment_variables"],
            compare_environment_variable,
        )
    )
    changes.extend(
        _diff_named_list(
            "connection_reference",
            old["connection_references"],
            new["connection_references"],
            compare_connection_reference,
        )
    )
    changes.extend(
        _diff_named_list("dependency", old["dependencies"], new["dependencies"], compare_dependency)
    )
    changes.extend(_diff_security(old["security"], new["security"]))
    changes.extend(
        _diff_named_list("component", old["components"], new["components"], compare_component)
    )
    return {"version_from": version_from, "version_to": version_to, "changes": changes}


def diff_for_initial_version(new_snapshot: dict, version_to: str = "1.0") -> dict:
    """Diff against an empty snapshot — used when there is no previous version.

    Every component in ``new_snapshot`` shows up as ADDED, which is the
    correct semantic for "this is the first time we've documented this
    application."
    """
    return diff_snapshots(empty_normalized_snapshot(), new_snapshot, version_from=None, version_to=version_to)

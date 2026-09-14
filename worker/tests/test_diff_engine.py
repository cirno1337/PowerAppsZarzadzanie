from __future__ import annotations

from worker.diff.engine import diff_for_initial_version, diff_snapshots
from worker.normalization.normalizer import normalize


def _snapshot(**overrides):
    base = {
        "flows": [],
        "applications": [],
        "environment_variables": [],
        "connection_references": [],
        "dependencies": [],
        "security": {"roles": []},
        "components": [],
    }
    base.update(overrides)
    return normalize({"name": "S", "version": "1.0.0.0", "publisher": "P", "description": "D"}, base)


def test_added_flow_is_detected():
    old = _snapshot()
    new = _snapshot(flows=[{"name": "New Flow", "trigger": "t", "actions": [], "conditions": [], "timeout": ""}])
    diff = diff_snapshots(old, new, version_from="1.0", version_to="1.1")
    assert {"type": "ADDED", "component": "flow", "name": "New Flow"} in diff["changes"]


def test_removed_flow_is_detected():
    old = _snapshot(flows=[{"name": "Gone", "trigger": "t", "actions": [], "conditions": [], "timeout": ""}])
    new = _snapshot()
    diff = diff_snapshots(old, new, version_from="1.0", version_to="1.1")
    assert {"type": "REMOVED", "component": "flow", "name": "Gone"} in diff["changes"]


def test_modified_flow_timeout_detail_matches_expected_wording():
    old = _snapshot(flows=[{"name": "Invoice Approval", "trigger": "t", "actions": [], "conditions": [], "timeout": "24h"}])
    new = _snapshot(flows=[{"name": "Invoice Approval", "trigger": "t", "actions": [], "conditions": [], "timeout": "48h"}])
    diff = diff_snapshots(old, new, version_from="1.0", version_to="1.1")
    changes = [c for c in diff["changes"] if c["component"] == "flow"]
    assert len(changes) == 1
    assert changes[0]["type"] == "MODIFIED"
    assert "timeout changed from 24h to 48h" in changes[0]["details"]


def test_no_changes_yields_empty_diff():
    snap = _snapshot(flows=[{"name": "F", "trigger": "t", "actions": ["a"], "conditions": [], "timeout": "1h"}])
    diff = diff_snapshots(snap, snap, version_from="1.0", version_to="1.0")
    assert diff["changes"] == []


def test_added_and_modified_screen_within_application():
    old = _snapshot(applications=[{"name": "App", "type": "canvas", "screens": [{"name": "Home", "controls_summary": "old"}]}])
    new = _snapshot(
        applications=[
            {
                "name": "App",
                "type": "canvas",
                "screens": [
                    {"name": "Home", "controls_summary": "new"},
                    {"name": "New Screen", "controls_summary": "x"},
                ],
            }
        ]
    )
    diff = diff_snapshots(old, new, version_from="1.0", version_to="1.1")
    screen_changes = [c for c in diff["changes"] if c["component"] == "screen"]
    assert {"type": "ADDED", "component": "screen", "name": "App / New Screen"} in screen_changes
    modified = next(c for c in screen_changes if c["name"] == "App / Home")
    assert modified["type"] == "MODIFIED"
    assert "controls changed from 'old' to 'new'" in modified["details"]


def test_environment_variable_default_value_change():
    old = _snapshot(environment_variables=[{"name": "Timeout", "type": "Number", "default_value": "24"}])
    new = _snapshot(environment_variables=[{"name": "Timeout", "type": "Number", "default_value": "48"}])
    diff = diff_snapshots(old, new, version_from="1.0", version_to="1.1")
    change = next(c for c in diff["changes"] if c["component"] == "environment_variable")
    assert "default value changed from '24' to '48'" in change["details"]


def test_connection_reference_and_dependency_added():
    old = _snapshot()
    new = _snapshot(
        connection_references=[{"name": "shared_teams", "connector": "Microsoft Teams"}],
        dependencies=[{"name": "Microsoft Teams", "type": "connector"}],
    )
    diff = diff_snapshots(old, new, version_from="1.0", version_to="1.1")
    assert {"type": "ADDED", "component": "connection_reference", "name": "shared_teams"} in diff["changes"]
    assert {"type": "ADDED", "component": "dependency", "name": "Microsoft Teams"} in diff["changes"]


def test_security_role_added_and_removed():
    old = _snapshot(security={"roles": ["A", "B"]})
    new = _snapshot(security={"roles": ["B", "C"]})
    diff = diff_snapshots(old, new, version_from="1.0", version_to="1.1")
    role_changes = {(c["type"], c["name"]) for c in diff["changes"] if c["component"] == "security_role"}
    assert ("ADDED", "C") in role_changes
    assert ("REMOVED", "A") in role_changes


def test_diff_for_initial_version_marks_everything_as_added():
    new = _snapshot(flows=[{"name": "F", "trigger": "t", "actions": [], "conditions": [], "timeout": ""}])
    diff = diff_for_initial_version(new, version_to="1.0")
    assert diff["version_from"] is None
    assert diff["version_to"] == "1.0"
    assert {"type": "ADDED", "component": "flow", "name": "F"} in diff["changes"]


def test_diff_never_produces_a_raw_text_diff_field():
    old = _snapshot()
    new = _snapshot(flows=[{"name": "F", "trigger": "t", "actions": [], "conditions": [], "timeout": ""}])
    diff = diff_snapshots(old, new, version_from="1.0", version_to="1.1")
    assert set(diff.keys()) == {"version_from", "version_to", "changes"}
    for change in diff["changes"]:
        assert set(change.keys()) <= {"type", "component", "name", "details"}

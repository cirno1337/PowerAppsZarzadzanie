from __future__ import annotations

from worker.normalization.normalizer import normalize
from worker.normalization.schema import empty_normalized_snapshot


def test_normalize_produces_fixed_key_order_and_sorted_lists():
    solution_metadata = {"name": "X", "version": "1.0.0.0", "publisher": "Contoso", "description": "d"}
    application_metadata = {
        "applications": [],
        "flows": [
            {"name": "Zeta Flow", "trigger": "t", "actions": ["a"], "conditions": [], "timeout": "1h"},
            {"name": "Alpha Flow", "trigger": "t", "actions": ["a"], "conditions": [], "timeout": "1h"},
        ],
        "environment_variables": [],
        "connection_references": [],
        "dependencies": [],
        "security": {"roles": ["Zeta", "Alpha"]},
        "components": [],
    }

    normalized = normalize(solution_metadata, application_metadata)

    assert list(normalized.keys()) == [
        "schema_version",
        "solution",
        "applications",
        "flows",
        "tables",
        "environment_variables",
        "connection_references",
        "dependencies",
        "security",
        "components",
    ]
    assert [f["name"] for f in normalized["flows"]] == ["Alpha Flow", "Zeta Flow"]
    assert normalized["security"]["roles"] == ["Alpha", "Zeta"]


def test_normalize_defaults_missing_categories_to_empty():
    normalized = normalize({}, {})
    assert normalized["applications"] == []
    assert normalized["flows"] == []
    assert normalized["tables"] == []
    assert normalized["environment_variables"] == []
    assert normalized["connection_references"] == []
    assert normalized["dependencies"] == []
    assert normalized["security"] == {"roles": []}
    assert normalized["components"] == []
    assert normalized["solution"] == {"name": "", "version": "", "publisher": "", "description": ""}


def test_normalize_is_deterministic_regardless_of_input_key_order():
    application_metadata_a = {"flows": [{"name": "F", "trigger": "t", "actions": [], "conditions": [], "timeout": ""}]}
    application_metadata_b = {"flows": [{"conditions": [], "name": "F", "actions": [], "timeout": "", "trigger": "t"}]}

    result_a = normalize({"name": "S"}, application_metadata_a)
    result_b = normalize({"name": "S"}, application_metadata_b)

    assert result_a == result_b


def test_flow_actions_and_conditions_preserve_authored_order():
    application_metadata = {
        "flows": [
            {
                "name": "F",
                "trigger": "t",
                "actions": ["third", "first", "second"],
                "conditions": ["c2", "c1"],
                "timeout": "",
            }
        ]
    }
    normalized = normalize({}, application_metadata)
    assert normalized["flows"][0]["actions"] == ["third", "first", "second"]
    assert normalized["flows"][0]["conditions"] == ["c2", "c1"]


def test_screens_are_sorted_within_an_application():
    application_metadata = {
        "applications": [
            {
                "name": "App",
                "type": "canvas",
                "screens": [{"name": "Zeta"}, {"name": "Alpha"}],
            }
        ]
    }
    normalized = normalize({}, application_metadata)
    assert [s["name"] for s in normalized["applications"][0]["screens"]] == ["Alpha", "Zeta"]


def test_empty_normalized_snapshot_matches_normalize_of_nothing():
    assert empty_normalized_snapshot() == normalize({}, {})

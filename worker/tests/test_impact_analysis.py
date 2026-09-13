from __future__ import annotations

from worker.diff.impact import analyze_documentation_impact, assess_change_impact


def test_adding_a_logging_variable_is_low_technical_none_user():
    change = {"type": "ADDED", "component": "environment_variable", "name": "EnableVerboseLogging"}
    technical, user = assess_change_impact(change)
    assert technical.value == "LOW"
    assert user.value == "NONE"


def test_changing_approval_timeout_is_medium_technical_high_user():
    change = {
        "type": "MODIFIED",
        "component": "environment_variable",
        "name": "ApprovalTimeoutHours",
        "details": ["default value changed from '24' to '48'"],
    }
    technical, user = assess_change_impact(change)
    assert technical.value == "MEDIUM"
    assert user.value == "HIGH"


def test_adding_a_new_user_facing_screen_is_medium_technical_high_user():
    change = {"type": "ADDED", "component": "screen", "name": "App / EscalationScreen"}
    technical, user = assess_change_impact(change)
    assert technical.value == "MEDIUM"
    assert user.value == "HIGH"


def test_changing_internal_error_logging_is_low_technical_none_user():
    change = {
        "type": "MODIFIED",
        "component": "flow",
        "name": "Some Flow",
        "details": ["action added: 'Log error details'"],
    }
    technical, user = assess_change_impact(change)
    assert technical.value == "LOW"
    assert user.value == "NONE"


def test_adding_a_new_business_process_is_high_technical_high_user():
    change = {"type": "ADDED", "component": "flow", "name": "Invoice Escalation"}
    technical, user = assess_change_impact(change)
    assert technical.value == "HIGH"
    assert user.value == "HIGH"


def test_analyze_documentation_impact_aggregates_by_maximum():
    changes = [
        {"type": "ADDED", "component": "flow", "name": "A"},  # HIGH/HIGH
        {"type": "ADDED", "component": "environment_variable", "name": "LogThing"},  # LOW/NONE
    ]
    result = analyze_documentation_impact(changes)
    assert result["technical_impact"] == "HIGH"
    assert result["user_impact"] == "HIGH"
    assert len(result["per_change"]) == 2


def test_analyze_documentation_impact_with_no_changes_is_none():
    result = analyze_documentation_impact([])
    assert result["technical_impact"] == "NONE"
    assert result["user_impact"] == "NONE"
    assert result["per_change"] == []

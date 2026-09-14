from __future__ import annotations

import pytest

from worker.adapters.copilot import direct_line
from worker.adapters.copilot.real import RealCopilotAdapter, parse_agent_reply
from worker.models import Application

SAMPLE_REPLY = """Sure, here you go.

<<<TECHNICAL_DOCUMENTATION>>>
# Technical Doc
Some technical content.
<<<END_TECHNICAL_DOCUMENTATION>>>

<<<USER_DOCUMENTATION>>>
# User Guide
Some user content.
<<<END_USER_DOCUMENTATION>>>

<<<CHANGE_SUMMARY>>>
Version: 1.1

Changes:
- Added a flow
<<<END_CHANGE_SUMMARY>>>
"""


def test_parse_agent_reply_extracts_all_three_sections():
    sections = parse_agent_reply(SAMPLE_REPLY)
    assert sections["technical_documentation"] == "# Technical Doc\nSome technical content."
    assert sections["user_documentation"] == "# User Guide\nSome user content."
    assert sections["change_summary"] == "Version: 1.1\n\nChanges:\n- Added a flow"


def test_parse_agent_reply_missing_section_is_empty_string():
    sections = parse_agent_reply("no delimiters here at all")
    assert sections == {"technical_documentation": "", "user_documentation": "", "change_summary": ""}


def _context():
    return {
        "job_id": "job-1",
        "app_record": Application(application_id="app-1", title="App", solution_name="Sol", environment="DEV"),
        "normalized": {"solution": {"name": "Sol", "version": "1.0", "publisher": "", "description": ""},
                       "applications": [], "flows": [], "environment_variables": [], "connection_references": []},
        "diff": {"version_from": "1.0", "version_to": "1.1", "changes": []},
        "impact": {"technical_impact": "LOW", "user_impact": "NONE", "per_change": []},
        "from_version": "1.0",
        "to_version": "1.1",
    }


def test_generate_technical_documentation_calls_direct_line_once_and_caches(monkeypatch):
    calls = []

    def fake_converse(secret, message, timeout):
        calls.append(secret)
        return SAMPLE_REPLY

    monkeypatch.setattr(direct_line, "converse", fake_converse)
    monkeypatch.setenv("PPDM_COPILOT_DIRECTLINE_SECRET", "shh")

    adapter = RealCopilotAdapter()
    context = _context()

    tech = adapter.generate_technical_documentation(context)
    user = adapter.generate_user_documentation(context)
    summary = adapter.generate_change_summary(context)

    assert "Technical Doc" in tech
    assert "User Guide" in user
    assert summary.startswith("Version: 1.1")
    assert calls == ["shh"]  # only one Direct Line round trip for all three calls


def test_missing_secret_raises_clear_error(monkeypatch):
    monkeypatch.delenv("PPDM_COPILOT_DIRECTLINE_SECRET", raising=False)
    adapter = RealCopilotAdapter()
    with pytest.raises(RuntimeError, match="PPDM_COPILOT_DIRECTLINE_SECRET"):
        adapter.generate_technical_documentation(_context())


def test_analyze_changes_passes_through_deterministic_impact():
    adapter = RealCopilotAdapter()
    impact = {"technical_impact": "HIGH", "user_impact": "HIGH", "per_change": []}
    assert adapter.analyze_changes({"changes": []}, impact) is impact

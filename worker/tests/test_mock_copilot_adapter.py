from __future__ import annotations

from worker.adapters.copilot.mock import MockCopilotAdapter
from worker.models import Application
from worker.diff.impact import analyze_documentation_impact


def _context(normalized, diff):
    impact = analyze_documentation_impact(diff["changes"])
    return {
        "job_id": "job-1",
        "app_record": Application(
            application_id="app-1",
            title="Invoice Approval",
            solution_name="InvoiceApproval",
            environment="DEV",
        ),
        "normalized": normalized,
        "diff": diff,
        "impact": impact,
        "from_version": diff["version_from"],
        "to_version": diff["version_to"] or "1.0",
    }


def test_analyze_changes_passes_through_deterministic_impact():
    adapter = MockCopilotAdapter()
    impact = {"technical_impact": "HIGH", "user_impact": "HIGH", "per_change": []}
    assert adapter.analyze_changes({"changes": []}, impact) is impact


def test_generate_technical_documentation_contains_required_sections(snapshot_v1_1):
    from worker.diff.engine import diff_for_initial_version

    diff = diff_for_initial_version(snapshot_v1_1, version_to="1.0")
    context = _context(snapshot_v1_1, diff)
    doc = MockCopilotAdapter().generate_technical_documentation(context)
    for section in (
        "Overview", "Architecture", "Components", "Power Apps", "Power Automate", "Data Sources",
        "Dependencies", "Environment Variables", "Connection References", "Security", "Business Logic",
        "Error Handling", "ALM", "Deployment", "Known Limitations",
    ):
        assert f"## {section}" in doc
    assert "MockCopilotAdapter" in doc


def test_generate_user_documentation_contains_required_sections(snapshot_v1_1):
    from worker.diff.engine import diff_for_initial_version

    diff = diff_for_initial_version(snapshot_v1_1, version_to="1.0")
    context = _context(snapshot_v1_1, diff)
    doc = MockCopilotAdapter().generate_user_documentation(context)
    for section in (
        "Purpose", "Who should use this application", "How to open it", "Main workflows",
        "Step-by-step usage", "Expected behavior", "Troubleshooting", "FAQ",
    ):
        assert f"## {section}" in doc


def test_generate_change_summary_matches_expected_format(snapshot_v1_0, snapshot_v1_1):
    from worker.diff.engine import diff_snapshots

    diff = diff_snapshots(snapshot_v1_0, snapshot_v1_1, version_from="1.0", version_to="1.1")
    context = _context(snapshot_v1_1, diff)
    summary = MockCopilotAdapter().generate_change_summary(context)
    assert summary.startswith("Version: 1.1")
    assert "Changes:" in summary
    assert "Invoice Escalation" in summary

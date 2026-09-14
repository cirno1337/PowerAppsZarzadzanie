"""Deterministic documentation impact analysis.

Maps each diff entry to a (technical_impact, user_impact) pair in
``{NONE, LOW, MEDIUM, HIGH}`` using fixed rules — no AI call required. This
must produce a sensible answer with zero Copilot involvement, because
Copilot availability is never guaranteed (see CLAUDE.md). A
``CopilotAdapter.analyze_changes()`` call may refine this later, but the
deterministic result here is always computed first and is authoritative
whenever Copilot refinement isn't available.

The rules below are written to match the worked examples in the project
brief exactly:

- "Adding a logging variable" -> technical=LOW, user=NONE
- "Changing approval timeout" -> technical=MEDIUM, user=HIGH
- "Adding a new user-facing screen" -> technical=MEDIUM, user=HIGH
- "Changing internal error logging" -> technical=LOW, user=NONE
- "Adding a new business process" (a new flow) -> technical=HIGH, user=HIGH
"""

from __future__ import annotations

from worker.models import ImpactLevel

NONE, LOW, MEDIUM, HIGH = (
    ImpactLevel.NONE,
    ImpactLevel.LOW,
    ImpactLevel.MEDIUM,
    ImpactLevel.HIGH,
)

_LOGGING_KEYWORDS = ("log", "error", "diagnostic", "telemetry")
_HIGH_USER_KEYWORDS = ("timeout", "approval", "escalat", "notification")


def _detail_text(change: dict) -> str:
    return " ".join(change.get("details", [])).lower()


def assess_change_impact(change: dict) -> tuple[ImpactLevel, ImpactLevel]:
    """Return (technical_impact, user_impact) for a single diff entry."""
    component = change["component"]
    change_type = change["type"]
    text = f"{change['name'].lower()} {_detail_text(change)}"

    if component == "flow":
        if change_type in ("ADDED", "REMOVED"):
            return HIGH, HIGH  # a whole business process appearing/disappearing
        # MODIFIED
        if any(k in text for k in _LOGGING_KEYWORDS):
            return LOW, NONE
        if any(k in text for k in _HIGH_USER_KEYWORDS):
            return MEDIUM, HIGH
        if "trigger" in text or "condition" in text:
            return MEDIUM, MEDIUM
        if "action added" in text or "action removed" in text:
            return MEDIUM, LOW
        return LOW, LOW

    if component == "screen":
        if change_type in ("ADDED", "REMOVED"):
            return MEDIUM, HIGH
        return LOW, MEDIUM

    if component == "application":
        if change_type in ("ADDED", "REMOVED"):
            return HIGH, HIGH
        return LOW, LOW

    if component == "environment_variable":
        if any(k in text for k in _LOGGING_KEYWORDS):
            return LOW, NONE
        if any(k in text for k in _HIGH_USER_KEYWORDS):
            return MEDIUM, HIGH
        if change_type == "MODIFIED":
            return LOW, LOW
        return LOW, NONE

    if component == "connection_reference":
        return (MEDIUM, NONE) if change_type in ("ADDED", "REMOVED") else (LOW, NONE)

    if component == "dependency":
        return (MEDIUM, NONE) if change_type in ("ADDED", "REMOVED") else (LOW, NONE)

    if component == "security_role":
        return MEDIUM, LOW

    if component == "table":
        if change_type in ("ADDED", "REMOVED"):
            return HIGH, MEDIUM
        return MEDIUM, LOW

    if component == "component":
        return (LOW, LOW) if change_type in ("ADDED", "REMOVED") else (LOW, NONE)

    if component == "solution":
        return LOW, NONE

    # Unknown/future component type: default to a conservative middle ground
    # rather than silently under-reporting impact.
    return MEDIUM, LOW


def analyze_documentation_impact(changes: list[dict]) -> dict:
    """Aggregate per-change impact into an overall assessment.

    Returns:
        {
          "technical_impact": "MEDIUM",
          "user_impact": "HIGH",
          "per_change": [{"type", "component", "name", "technical_impact", "user_impact"}, ...]
        }
    """
    per_change = []
    technical_levels = [NONE]
    user_levels = [NONE]

    for change in changes:
        technical, user = assess_change_impact(change)
        technical_levels.append(technical)
        user_levels.append(user)
        per_change.append(
            {
                "type": change["type"],
                "component": change["component"],
                "name": change["name"],
                "technical_impact": technical.value,
                "user_impact": user.value,
            }
        )

    return {
        "technical_impact": ImpactLevel.max(*technical_levels).value,
        "user_impact": ImpactLevel.max(*user_levels).value,
        "per_change": per_change,
    }

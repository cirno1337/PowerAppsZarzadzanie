"""REQUIRES LICENSING VERIFICATION — real Copilot adapter placeholder.

Do NOT implement this against an assumed API. Which Copilot product (if
any) the company can call programmatically — Microsoft 365 Copilot,
Copilot Studio, an agent API, MCP, or nothing at all — is unknown until
verified against the real tenant. See docs/COPILOT_INTEGRATION.md for the
full verification checklist and ADR-005 in DECISIONS.md for why this
isolation exists.

The project remains fully usable with ``HumanReviewCopilotAdapter`` if it
turns out no programmatic access exists — that is an acceptable permanent
outcome, not a stopgap.
"""

from __future__ import annotations

from .base import CopilotAdapter

_NOT_IMPLEMENTED = (
    "RealCopilotAdapter is a placeholder. Implementing it requires completing "
    "the verification checklist in docs/COPILOT_INTEGRATION.md against the "
    "real corporate tenant — do not implement against an assumed API."
)


class RealCopilotAdapter(CopilotAdapter):
    """REQUIRES LICENSING VERIFICATION. Not implemented — see module docstring."""

    def analyze_changes(self, diff: dict, deterministic_impact: dict) -> dict:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def generate_technical_documentation(self, context: dict) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def generate_user_documentation(self, context: dict) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def generate_change_summary(self, context: dict) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

"""CopilotAdapter interface.

Nothing outside ``worker/adapters/copilot/`` may reference a specific
Copilot product, API, or MCP server — see CLAUDE.md and ADR-005.

``context`` dicts passed to the ``generate_*`` methods follow the shape
documented in ``worker/documentation/generator.py``. Implementations may
add a ``"human_result"`` key to that dict once a human has supplied Copilot
output (see ``HumanReviewCopilotAdapter``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class CopilotAdapter(ABC):
    @abstractmethod
    def analyze_changes(self, diff: dict, deterministic_impact: dict) -> dict:
        """Optionally refine the deterministic impact assessment.

        Must return a dict with the same shape as ``deterministic_impact``
        (see ``worker/diff/impact.py``). Implementations that cannot refine
        the analysis should simply return ``deterministic_impact`` unchanged
        — refinement is a best-effort improvement, never a requirement.
        """

    @abstractmethod
    def generate_technical_documentation(self, context: dict) -> str:
        """Return the technical documentation Markdown for this job."""

    @abstractmethod
    def generate_user_documentation(self, context: dict) -> str:
        """Return the user guide Markdown for this job."""

    @abstractmethod
    def generate_change_summary(self, context: dict) -> str:
        """Return the change summary Markdown/text for this job."""

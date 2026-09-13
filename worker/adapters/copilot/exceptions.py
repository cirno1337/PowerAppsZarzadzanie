"""Exceptions raised by CopilotAdapter implementations."""

from __future__ import annotations


class HumanReviewRequired(Exception):
    """Raised by a CopilotAdapter when it cannot produce a result without a
    human running a prompt in an approved corporate Copilot product first.

    ``prompt_path`` points at the ready-to-run prompt the job processor
    should surface (via the job's ``result_summary``) so an administrator
    knows where to find it.
    """

    def __init__(self, prompt_path: str):
        super().__init__(f"Human review required. Prompt available at: {prompt_path}")
        self.prompt_path = prompt_path

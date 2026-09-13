"""Real Copilot adapter — Copilot Studio via the Direct Line API.

Status: **IMPLEMENTED, REQUIRES LICENSING VERIFICATION for the company
tenant.** The Direct Line mechanism is verified against official Microsoft
docs and structurally confirmed (secrets, "Require secured access") against
a personal test tenant — see ``docs/COPILOT_INTEGRATION.md``. A full
end-to-end message round-trip against the company's own Copilot Studio
agent has not been run; do that before relying on this in production.

Deliberately NOT the newer Microsoft 365 Agents SDK — that SDK doesn't
support unattended service-principal authentication, which this worker
needs since it has no interactive user to sign in (see
``docs/COPILOT_INTEGRATION.md`` "Follow-up after extending the trial").

The Direct Line secret is read from an environment variable
(``PPDM_COPILOT_DIRECTLINE_SECRET`` by default) and never logged or
returned from any method here.
"""

from __future__ import annotations

import os
import re

from . import direct_line
from .base import CopilotAdapter
from .human_review import build_human_prompt

DEFAULT_SECRET_ENV_VAR = "PPDM_COPILOT_DIRECTLINE_SECRET"

_SECTION_PATTERNS = {
    "technical_documentation": re.compile(
        r"<<<TECHNICAL_DOCUMENTATION>>>(.*?)<<<END_TECHNICAL_DOCUMENTATION>>>", re.DOTALL
    ),
    "user_documentation": re.compile(r"<<<USER_DOCUMENTATION>>>(.*?)<<<END_USER_DOCUMENTATION>>>", re.DOTALL),
    "change_summary": re.compile(r"<<<CHANGE_SUMMARY>>>(.*?)<<<END_CHANGE_SUMMARY>>>", re.DOTALL),
}


def parse_agent_reply(reply_text: str) -> dict:
    """Extract the three delimited sections `build_human_prompt()` asks
    for. A missing section becomes an empty string rather than raising —
    the caller (job processor) will surface an obviously-incomplete
    document rather than crash the job on a slightly-off agent reply."""
    return {key: (m.group(1).strip() if (m := pattern.search(reply_text)) else "") for key, pattern in _SECTION_PATTERNS.items()}


class RealCopilotAdapter(CopilotAdapter):
    def __init__(self, secret_env_var: str = DEFAULT_SECRET_ENV_VAR, timeout: float = 60.0):
        self._secret_env_var = secret_env_var
        self._timeout = timeout
        self._sections_by_job: dict[str, dict] = {}

    def _secret(self) -> str:
        secret = os.environ.get(self._secret_env_var)
        if not secret:
            raise RuntimeError(
                f"{self._secret_env_var} is not set — the Direct Line secret must be provided via "
                "environment variable, never hard-coded (see SECURITY.md)."
            )
        return secret

    def analyze_changes(self, diff: dict, deterministic_impact: dict) -> dict:
        # Refining the deterministic impact assessment via the agent is not
        # implemented — the deterministic result is always authoritative
        # per CLAUDE.md, and adding this would double every job's Direct
        # Line round trips for marginal benefit.
        return deterministic_impact

    def _ensure_sections(self, context: dict) -> dict:
        job_id = context["job_id"]
        if job_id not in self._sections_by_job:
            prompt = build_human_prompt(context)
            reply = direct_line.converse(self._secret(), prompt, timeout=self._timeout)
            self._sections_by_job[job_id] = parse_agent_reply(reply)
        return self._sections_by_job[job_id]

    def generate_technical_documentation(self, context: dict) -> str:
        return self._ensure_sections(context)["technical_documentation"]

    def generate_user_documentation(self, context: dict) -> str:
        return self._ensure_sections(context)["user_documentation"]

    def generate_change_summary(self, context: dict) -> str:
        return self._ensure_sections(context)["change_summary"]

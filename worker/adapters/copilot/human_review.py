"""HumanReviewCopilotAdapter — the fully-supported fallback (ADR-006).

When no programmatic Copilot access is available, this adapter prepares a
self-contained, ready-to-paste prompt, raises ``HumanReviewRequired`` so the
job processor can set the job to ``NEEDS_HUMAN_REVIEW``, and later accepts a
human-supplied result (placed into ``context["human_result"]``) to resume
processing. See the "HUMAN-IN-THE-LOOP FALLBACK" section of the project
brief and ADR-006 in DECISIONS.md.

The prompt only ever contains the normalized representation, diff, and
impact assessment — never a raw solution export, and never credentials (see
SECURITY.md "Sensitive information handling").
"""

from __future__ import annotations

import json
import textwrap
from typing import Callable

from .base import CopilotAdapter
from .exceptions import HumanReviewRequired

ArtifactWriter = Callable[[str, str, str], str]  # (job_id, filename, content) -> path

_REQUIRED_TECHNICAL_SECTIONS = (
    "Overview, Architecture, Components, Power Apps, Power Automate, Data Sources, "
    "Dependencies, Environment Variables, Connection References, Security, Business Logic, "
    "Error Handling, ALM, Deployment, Known Limitations"
)
_REQUIRED_USER_SECTIONS = (
    "Purpose, Who should use the application, How to open it, Main workflows, "
    "Step-by-step usage, Expected behavior, Troubleshooting, FAQ"
)


def build_human_prompt(context: dict) -> str:
    app = context["app_record"]
    normalized = context["normalized"]
    diff = context["diff"]
    impact = context["impact"]

    return textwrap.dedent(
        f"""\
        # Copilot documentation request — {app.title}

        You are documenting a Microsoft Power Platform application named
        "{app.title}" (environment: {app.environment}). Use ONLY the structured
        data below. Do not invent details that aren't present in it.

        Documentation version being produced: {context['to_version']}
        {'Previous version: ' + context['from_version'] if context.get('from_version') else '(this is the first documented version)'}

        ## Normalized application snapshot (JSON)

        ```json
        {json.dumps(normalized, indent=2)}
        ```

        ## Detected changes since the previous version (JSON)

        ```json
        {json.dumps(diff, indent=2)}
        ```

        ## Deterministic documentation impact assessment (JSON)

        ```json
        {json.dumps(impact, indent=2)}
        ```

        ## What to produce

        Reply with three clearly delimited Markdown sections, in this exact
        order, using the delimiters shown:

        <<<TECHNICAL_DOCUMENTATION>>>
        (technical documentation Markdown here, covering: {_REQUIRED_TECHNICAL_SECTIONS})
        <<<END_TECHNICAL_DOCUMENTATION>>>

        <<<USER_DOCUMENTATION>>>
        (user guide Markdown here, covering: {_REQUIRED_USER_SECTIONS})
        <<<END_USER_DOCUMENTATION>>>

        <<<CHANGE_SUMMARY>>>
        (change summary Markdown here, in the form "Version: {context['to_version']}" followed by a bulleted "Changes:" list)
        <<<END_CHANGE_SUMMARY>>>

        Do not include any credentials, tenant IDs, or URLs beyond what is
        already present in the data above.
        """
    )


class HumanReviewCopilotAdapter(CopilotAdapter):
    def __init__(self, artifact_writer: ArtifactWriter):
        self._artifact_writer = artifact_writer
        self._written_prompts: dict[str, str] = {}

    def analyze_changes(self, diff: dict, deterministic_impact: dict) -> dict:
        # Refinement requires a human-supplied result, which isn't available
        # at analysis time. The deterministic assessment is authoritative.
        return deterministic_impact

    def _ensure_prompt_written(self, context: dict) -> str:
        job_id = context["job_id"]
        if job_id in self._written_prompts:
            return self._written_prompts[job_id]
        prompt_text = build_human_prompt(context)
        path = self._artifact_writer(job_id, "copilot-prompt.md", prompt_text)
        self._written_prompts[job_id] = path
        return path

    def _resolve(self, context: dict, human_result_key: str) -> str:
        human_result = context.get("human_result")
        if human_result and human_result_key in human_result:
            return human_result[human_result_key]
        prompt_path = self._ensure_prompt_written(context)
        raise HumanReviewRequired(prompt_path)

    def generate_technical_documentation(self, context: dict) -> str:
        return self._resolve(context, "technical_documentation")

    def generate_user_documentation(self, context: dict) -> str:
        return self._resolve(context, "user_documentation")

    def generate_change_summary(self, context: dict) -> str:
        return self._resolve(context, "change_summary")

"""Deterministic Markdown documentation generation.

These renderers are the baseline used directly by ``MockCopilotAdapter`` and
available to any future ``RealCopilotAdapter`` as a fallback/skeleton. They
never call out to a network service — see CLAUDE.md on why Copilot must
remain optional.
"""

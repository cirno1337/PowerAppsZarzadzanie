"""The normalized representation schema.

This is the ONLY shape of Power Platform data that ever reaches the diff
engine or a Copilot prompt — never a raw solution export. See ADR-007 in
DECISIONS.md for why.

The schema mirrors the example in the project brief:

    {
      "solution": {"name", "version", "publisher", "description"},
      "applications": [{"name", "type", "screens": [{"name", "controls_summary"}]}],
      "flows": [{"name", "trigger", "actions": [...], "conditions": [...], "timeout"}],
      "tables": [],
      "environment_variables": [{"name", "type", "default_value"}],
      "connection_references": [{"name", "connector"}],
      "dependencies": [{"name", "type"}],
      "security": {"roles": [...]},
      "components": [{"name", "type"}]
    }

Determinism rules (see CLAUDE.md "Normalization must be deterministic"):
- every named list is sorted by "name"
- ordered lists that represent a sequence of steps (a flow's actions/
  conditions) are NOT re-sorted — their authored order is semantically
  meaningful
- every dict is built with an explicit, fixed key order regardless of the
  order keys appeared in the raw input
"""

from __future__ import annotations

SCHEMA_VERSION = 1

NAMED_LIST_CATEGORIES = (
    "applications",
    "flows",
    "tables",
    "environment_variables",
    "connection_references",
    "dependencies",
    "components",
)


def sort_by_name(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda item: item["name"])


def empty_normalized_snapshot() -> dict:
    """The normalized shape for a solution with no components at all."""
    return {
        "schema_version": SCHEMA_VERSION,
        "solution": {"name": "", "version": "", "publisher": "", "description": ""},
        "applications": [],
        "flows": [],
        "tables": [],
        "environment_variables": [],
        "connection_references": [],
        "dependencies": [],
        "security": {"roles": []},
        "components": [],
    }

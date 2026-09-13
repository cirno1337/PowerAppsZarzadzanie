"""Documentation version numbering.

Policy (see CLAUDE.md "How versioning works" and ARCHITECTURE.md):

- The very first documented version of an application is always ``1.0``.
- No detected changes since the last documented version -> version stays
  the same, no new documentation version is created.
- Any detected change (impact LOW, MEDIUM, or HIGH on either axis) -> minor
  version bump (``1.0`` -> ``1.1`` -> ``1.2`` -> ...).
- A major version bump (``x.0``) is a deliberate, explicit decision
  (``major=True``), never inferred automatically from diff size or impact
  level. Automatically guessing "this deserves a new major version" from a
  diff alone was judged unreliable — see DECISIONS.md if this policy is
  ever revisited.

Versions are represented as ``"<major>.<minor>"`` strings.
"""

from __future__ import annotations

INITIAL_VERSION = "1.0"


def parse_version(version: str) -> tuple[int, int]:
    major_str, _, minor_str = version.partition(".")
    return int(major_str), int(minor_str or "0")


def format_version(major: int, minor: int) -> str:
    return f"{major}.{minor}"


def bump_minor(version: str) -> str:
    major, minor = parse_version(version)
    return format_version(major, minor + 1)


def bump_major(version: str) -> str:
    major, _minor = parse_version(version)
    return format_version(major + 1, 0)


def has_changes(overall_technical: str, overall_user: str) -> bool:
    return overall_technical != "NONE" or overall_user != "NONE"


def next_version(
    current_version: str | None,
    overall_technical: str,
    overall_user: str,
    major: bool = False,
) -> str:
    """Compute the next documentation version.

    ``current_version`` is ``None`` for a brand-new application (always
    yields ``INITIAL_VERSION`` regardless of impact, since everything is new
    by definition). Otherwise, returns ``current_version`` unchanged when no
    changes were detected.
    """
    if current_version is None:
        return INITIAL_VERSION
    if not has_changes(overall_technical, overall_user):
        return current_version
    return bump_major(current_version) if major else bump_minor(current_version)

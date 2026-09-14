from __future__ import annotations

import pytest

from worker.versioning.version import bump_major, bump_minor, next_version, parse_version


def test_parse_version():
    assert parse_version("1.4") == (1, 4)
    assert parse_version("2") == (2, 0)


def test_bump_minor_and_major():
    assert bump_minor("1.0") == "1.1"
    assert bump_minor("1.4") == "1.5"
    assert bump_major("1.4") == "2.0"


def test_initial_version_is_always_1_0_regardless_of_impact():
    assert next_version(None, "HIGH", "HIGH") == "1.0"
    assert next_version(None, "NONE", "NONE") == "1.0"


def test_no_changes_keeps_version_unchanged():
    assert next_version("1.3", "NONE", "NONE") == "1.3"


@pytest.mark.parametrize("technical,user", [("LOW", "NONE"), ("NONE", "LOW"), ("MEDIUM", "HIGH"), ("HIGH", "HIGH")])
def test_any_detected_change_bumps_minor_version(technical, user):
    assert next_version("1.0", technical, user) == "1.1"


def test_explicit_major_flag_bumps_major_version():
    assert next_version("1.4", "HIGH", "HIGH", major=True) == "2.0"


def test_sequential_minor_bumps_match_brief_examples():
    version = "1.0"
    for _ in range(3):
        version = next_version(version, "MEDIUM", "LOW")
    assert version == "1.3"

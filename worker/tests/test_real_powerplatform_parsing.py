"""Tests for the real-export parsers in worker/adapters/powerplatform/xml_parsing.py.

Fixtures here are synthetic — hand-written to mirror the real shape
verified against an actual (personal, non-production) tenant export (see
docs/POWER_PLATFORM_SETUP.md), but with invented names/GUIDs rather than
any real tenant's data.
"""

from __future__ import annotations

import json

from worker.adapters.powerplatform.xml_parsing import (
    find_flow_files,
    friendly_connector_name,
    parse_connection_references,
    parse_environment_variables,
    parse_flow_definition,
    parse_solution_manifest,
)

SOLUTION_XML = """<?xml version="1.0" encoding="utf-8"?>
<ImportExportXml>
  <SolutionManifest>
    <UniqueName>ExampleSolution</UniqueName>
    <Version>1.2.0.0</Version>
    <Managed>0</Managed>
    <Publisher><UniqueName>ExamplePublisher</UniqueName></Publisher>
    <Descriptions>
      <Description description="An example solution" languagecode="1033" />
    </Descriptions>
  </SolutionManifest>
</ImportExportXml>
"""

CUSTOMIZATIONS_XML = """<?xml version="1.0" encoding="utf-8"?>
<ImportExportXml>
  <connectionreferences>
    <connectionreference connectionreferencelogicalname="new_testSharePoint">
      <connectionreferencedisplayname>testSharePoint</connectionreferencedisplayname>
      <connectorid>/providers/Microsoft.PowerApps/apis/shared_sharepointonline</connectorid>
    </connectionreference>
    <connectionreference connectionreferencelogicalname="new_testTeams">
      <connectionreferencedisplayname>testTeams</connectionreferencedisplayname>
      <connectorid>/providers/Microsoft.PowerApps/apis/shared_teams</connectorid>
    </connectionreference>
  </connectionreferences>
</ImportExportXml>
"""

ENV_VAR_DEFINITION_XML = """<environmentvariabledefinition schemaname="new_testTimeout">
  <displayname default="testTimeout"><label description="testTimeout" languagecode="1033" /></displayname>
  <type>100000001</type>
</environmentvariabledefinition>"""

ENV_VAR_VALUES_JSON = json.dumps(
    {"environmentvariablevalues": {"environmentvariablevalue": {"value": "24"}}}
)


def test_parse_solution_manifest(tmp_path):
    path = tmp_path / "Solution.xml"
    path.write_text(SOLUTION_XML, encoding="utf-8")
    result = parse_solution_manifest(path)
    assert result == {
        "name": "ExampleSolution",
        "version": "1.2.0.0",
        "publisher": "ExamplePublisher",
        "description": "An example solution",
    }


def test_parse_solution_manifest_missing_file_returns_empty(tmp_path):
    result = parse_solution_manifest(tmp_path / "does-not-exist.xml")
    assert result == {"name": "", "version": "", "publisher": "", "description": ""}


def test_parse_connection_references(tmp_path):
    path = tmp_path / "Customizations.xml"
    path.write_text(CUSTOMIZATIONS_XML, encoding="utf-8")
    result = parse_connection_references(path)
    assert result == [
        {"name": "testSharePoint", "connector": "SharePoint"},
        {"name": "testTeams", "connector": "Microsoft Teams"},
    ]


def test_friendly_connector_name_falls_back_to_alias_for_unknown_connector():
    assert friendly_connector_name("/providers/Microsoft.PowerApps/apis/shared_somethingnew") == (
        "shared_somethingnew"
    )


def test_parse_environment_variables(tmp_path):
    var_dir = tmp_path / "new_testTimeout"
    var_dir.mkdir()
    (var_dir / "environmentvariabledefinition.xml").write_text(ENV_VAR_DEFINITION_XML, encoding="utf-8")
    (var_dir / "environmentvariablevalues.json").write_text(ENV_VAR_VALUES_JSON, encoding="utf-8")

    result = parse_environment_variables(tmp_path)
    assert result == [{"name": "testTimeout", "type": "Number", "default_value": "24"}]


def test_parse_environment_variables_missing_dir_returns_empty(tmp_path):
    assert parse_environment_variables(tmp_path / "nope") == []


def test_parse_flow_definition_button_trigger():
    flow_json = {
        "properties": {
            "definition": {
                "triggers": {"manual": {"type": "Request", "kind": "Button", "inputs": {}}},
                "actions": {
                    "Get_items": {"type": "OpenApiConnection", "runAfter": {}},
                    "Send_email": {"type": "OpenApiConnection", "runAfter": {"Get_items": ["Succeeded"]}},
                },
            }
        }
    }
    result = parse_flow_definition(flow_json, name="Example Flow")
    assert result == {
        "name": "Example Flow",
        "trigger": "manual",
        "actions": ["Get items", "Send email"],
        "conditions": [],
        "timeout": "",
    }


def test_parse_flow_definition_recurrence_trigger_and_condition():
    flow_json = {
        "properties": {
            "definition": {
                "triggers": {
                    "Recurrence": {"type": "Recurrence", "recurrence": {"interval": 1, "frequency": "Day"}}
                },
                "actions": {
                    "Check_status": {"type": "If", "runAfter": {}},
                    "Notify": {
                        "type": "OpenApiConnection",
                        "runAfter": {"Check_status": ["Succeeded"]},
                        "limit": {"timeout": "PT24H"},
                    },
                },
            }
        }
    }
    result = parse_flow_definition(flow_json, name="Escalation Flow")
    assert result["trigger"] == "Recurrence (every 1 day(s))"
    assert result["actions"] == ["Notify"]
    assert result["conditions"] == ["Check status"]
    assert result["timeout"] == "24h"


def test_parse_flow_definition_orders_actions_by_run_after_not_dict_order():
    flow_json = {
        "properties": {
            "definition": {
                "triggers": {},
                "actions": {
                    "Third": {"type": "OpenApiConnection", "runAfter": {"Second": ["Succeeded"]}},
                    "First": {"type": "OpenApiConnection", "runAfter": {}},
                    "Second": {"type": "OpenApiConnection", "runAfter": {"First": ["Succeeded"]}},
                },
            }
        }
    }
    result = parse_flow_definition(flow_json, name="F")
    assert result["actions"] == ["First", "Second", "Third"]


def test_find_flow_files_excludes_data_xml_siblings(tmp_path):
    workflows_dir = tmp_path / "Workflows"
    workflows_dir.mkdir()
    (workflows_dir / "Flow-ABCDEFGH.json").write_text("{}", encoding="utf-8")
    (workflows_dir / "Flow-ABCDEFGH.json.data.xml").write_text("<x/>", encoding="utf-8")

    result = find_flow_files(workflows_dir)
    assert [p.name for p in result] == ["Flow-ABCDEFGH.json"]


def test_find_flow_files_missing_dir_returns_empty(tmp_path):
    assert find_flow_files(tmp_path / "nope") == []

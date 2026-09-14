from __future__ import annotations

import json
from pathlib import Path

from worker.adapters.powerplatform import pac_cli
from worker.adapters.powerplatform.real import RealPowerPlatformAdapter, _flow_display_name

SOLUTION_XML = """<?xml version="1.0" encoding="utf-8"?>
<ImportExportXml>
  <SolutionManifest>
    <UniqueName>ExampleSolution</UniqueName>
    <Version>1.0.0.0</Version>
    <Managed>0</Managed>
    <Publisher><UniqueName>ExamplePublisher</UniqueName></Publisher>
  </SolutionManifest>
</ImportExportXml>
"""

FLOW_JSON = {
    "properties": {
        "definition": {
            "triggers": {"manual": {"type": "Request", "kind": "Button"}},
            "actions": {"Get_items": {"type": "OpenApiConnection", "runAfter": {}}},
        }
    }
}


def _build_fake_unpacked_dir(tmp_path: Path) -> Path:
    unpacked = tmp_path / "unpacked"
    (unpacked / "Other").mkdir(parents=True)
    (unpacked / "Other" / "Solution.xml").write_text(SOLUTION_XML, encoding="utf-8")
    (unpacked / "Workflows").mkdir()
    # Real filenames carry a full 8-4-4-4-12 GUID (with its own internal
    # hyphens) -- this fixture matches that shape deliberately, since a
    # shorter fake GUID previously hid a real bug in name extraction.
    (unpacked / "Workflows" / "Example-Flow-53E8B648-3F25-EE11-9965-6045BD0D0CC5.json").write_text(
        json.dumps(FLOW_JSON), encoding="utf-8"
    )
    return unpacked


def test_flow_display_name_strips_full_guid_with_internal_hyphens():
    # Regression test: found by running this adapter against a real
    # export, where a naive rsplit("-", 1) left most of the GUID behind.
    path = Path("Button-Getitems-53E8B648-3F25-EE11-9965-6045BD0D0CC5.json")
    assert _flow_display_name(path) == "Button-Getitems"


def test_flow_display_name_leaves_non_guid_names_unchanged():
    assert _flow_display_name(Path("Plain-Flow-Name.json")) == "Plain-Flow-Name"


def test_get_solution_metadata_uses_real_xml_parser(tmp_path):
    adapter = RealPowerPlatformAdapter(environment_url="https://example.crm.dynamics.com")
    unpacked = _build_fake_unpacked_dir(tmp_path)
    metadata = adapter.get_solution_metadata(unpacked)
    assert metadata["name"] == "ExampleSolution"
    assert metadata["version"] == "1.0.0.0"
    assert metadata["publisher"] == "ExamplePublisher"


def test_get_application_metadata_parses_flows_from_workflows_dir(tmp_path):
    adapter = RealPowerPlatformAdapter(environment_url="https://example.crm.dynamics.com")
    unpacked = _build_fake_unpacked_dir(tmp_path)
    metadata = adapter.get_application_metadata(unpacked)

    assert len(metadata["flows"]) == 1
    assert metadata["flows"][0]["name"] == "Example-Flow"
    assert metadata["flows"][0]["trigger"] == "manual"
    # This fixture has no CanvasApps/ folder, so no canvas apps to find.
    # Tables/security roles are not yet verified against a real export —
    # see worker/adapters/powerplatform/real.py module docstring.
    assert metadata["applications"] == []
    assert metadata["tables"] == []
    assert metadata["security"] == {"roles": []}


CANVAS_APP_META_XML = """<?xml version="1.0" encoding="utf-8"?>
<CanvasApp xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Name>new_exampleapp_a2eff</Name>
  <DisplayName>Example App</DisplayName>
  <DocumentUri>/CanvasApps/new_exampleapp_a2eff_DocumentUri.msapp</DocumentUri>
</CanvasApp>
"""


def test_get_application_metadata_includes_canvas_apps(tmp_path, monkeypatch):
    unpacked = _build_fake_unpacked_dir(tmp_path)
    canvas_dir = unpacked / "CanvasApps"
    canvas_dir.mkdir()
    (canvas_dir / "new_exampleapp_a2eff.meta.xml").write_text(CANVAS_APP_META_XML, encoding="utf-8")
    (canvas_dir / "new_exampleapp_a2eff_DocumentUri.msapp").write_bytes(b"fake msapp contents")

    def fake_canvas_unpack(msapp_path, sources_dir, layout="Experimental"):
        sources_dir.mkdir(parents=True, exist_ok=True)
        (sources_dir / "CanvasManifest.json").write_text(json.dumps({"ScreenOrder": ["Screen1"]}), encoding="utf-8")
        (sources_dir / "Src").mkdir()
        (sources_dir / "Src" / "Screen1.fx.yaml").write_text(
            "Screen1 As screen:\n    Button1 As Button:\n        Text: =\"Go\"\n", encoding="utf-8"
        )
        return sources_dir

    monkeypatch.setattr(pac_cli, "canvas_unpack", fake_canvas_unpack)
    adapter = RealPowerPlatformAdapter(environment_url="https://example.crm.dynamics.com")
    metadata = adapter.get_application_metadata(unpacked)

    assert len(metadata["applications"]) == 1
    app = metadata["applications"][0]
    assert app["name"] == "Example App"
    assert app["type"] == "canvas"
    assert app["screens"] == [{"name": "Screen1", "controls_summary": "Button1 (Button)"}]


def test_get_application_metadata_degrades_gracefully_on_unparseable_canvas_app(tmp_path, monkeypatch):
    unpacked = _build_fake_unpacked_dir(tmp_path)
    canvas_dir = unpacked / "CanvasApps"
    canvas_dir.mkdir()
    (canvas_dir / "new_exampleapp_a2eff.meta.xml").write_text(CANVAS_APP_META_XML, encoding="utf-8")
    (canvas_dir / "new_exampleapp_a2eff_DocumentUri.msapp").write_bytes(b"fake msapp contents")

    def failing_canvas_unpack(msapp_path, sources_dir, layout="Experimental"):
        raise pac_cli.PacCliError("MSAppStructureVersion 2.0 is below the minimum supported version 2.4.0.")

    monkeypatch.setattr(pac_cli, "canvas_unpack", failing_canvas_unpack)
    adapter = RealPowerPlatformAdapter(environment_url="https://example.crm.dynamics.com")
    metadata = adapter.get_application_metadata(unpacked)

    # Degrades to an app entry with no screens rather than failing the
    # whole job over one unparseable canvas app.
    assert metadata["applications"] == [{"name": "Example App", "type": "canvas", "screens": []}]


def test_authenticate_delegates_to_ensure_authenticated(monkeypatch):
    captured = {}
    monkeypatch.setattr(pac_cli, "ensure_authenticated", lambda url: captured.setdefault("url", url))
    adapter = RealPowerPlatformAdapter(environment_url="https://example.crm.dynamics.com")
    adapter.authenticate()
    assert captured["url"] == "https://example.crm.dynamics.com"


def test_list_solutions_delegates_to_pac_cli(monkeypatch):
    monkeypatch.setattr(pac_cli, "solution_list", lambda env: ["A", "B"])
    adapter = RealPowerPlatformAdapter(environment_url="https://example.crm.dynamics.com")
    assert adapter.list_solutions("https://example.crm.dynamics.com") == ["A", "B"]


def test_export_solution_ignores_mock_only_version_argument(monkeypatch, tmp_path):
    captured = {}

    def fake_export(name, env, path):
        captured["name"] = name
        captured["env"] = env
        return path

    monkeypatch.setattr(pac_cli, "solution_export", fake_export)
    adapter = RealPowerPlatformAdapter(environment_url="https://example.crm.dynamics.com")
    result = adapter.export_solution("Example", "https://example.crm.dynamics.com", tmp_path, version="v1.0")

    assert captured["name"] == "Example"
    assert result == tmp_path / "Example.zip"


def test_unpack_solution_delegates_to_pac_cli(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(
        pac_cli, "solution_unpack", lambda zip_path, target: captured.setdefault("target", target) or target
    )
    adapter = RealPowerPlatformAdapter(environment_url="https://example.crm.dynamics.com")
    zip_path = tmp_path / "Example.zip"
    result = adapter.unpack_solution(zip_path)
    assert result == tmp_path / "Example"
    assert captured["target"] == tmp_path / "Example"

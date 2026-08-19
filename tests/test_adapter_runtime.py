import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rolo.adapter_runtime import activate_release, invoke_adapter, publish_release
from rolo.cli import app
from rolo.core.config import get_settings
from rolo.core.hashing import sha256_file
from rolo.core.models import ToolDescriptor
from rolo.stages.adapt.models import AdapterBundleManifest, ToolCatalog
from rolo.stages.adapt.operation_registry import canonical_operation_registry


def _publish_demo_release(tmp_path: Path) -> Path:
    definition = next(
        item
        for item in canonical_operation_registry().operations
        if item.operation == "app.camera.snapshot"
    )
    source = tmp_path / "source"
    source.mkdir()
    package = source / "demo_adapter.py"
    package.write_text(
        "import json, sys\n"
        "OPS = {'app.camera.snapshot': 'camera_snapshot'}\n"
        "if sys.argv[1] == 'describe':\n"
        "    print(json.dumps({'operations': OPS}))\n"
        "elif sys.argv[1] == 'invoke':\n"
        "    payload = json.load(sys.stdin)\n"
        "    print(json.dumps({'status': 'SUCCEEDED', 'camera': payload['camera']}))\n",
        encoding="utf-8",
    )
    bundle = AdapterBundleManifest(
        bundle_id="demo-camera",
        bundle_version="1.0.0",
        robot_id="demo",
        discovery_id="disc-1",
        package_file=package.name,
        package_sha256=sha256_file(package),
        operations=[
            {
                "operation": "app.camera.snapshot",
                "entrypoint": "camera_snapshot",
                "contract_version": definition.contract_version,
                "contract_sha256": definition.contract_sha256,
            }
        ],
    )
    bundle_path = source / "adapter-manifest.json"
    bundle_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    catalog = ToolCatalog(
        robot_id="demo",
        discovery_id="disc-1",
        contract_catalog_sha256=canonical_operation_registry().contract_catalog_sha256,
        tools=[
            ToolDescriptor(
                operation="app.camera.snapshot",
                canonical_cli=[
                    "robotctl",
                    "tool",
                    "invoke",
                    "app.camera.snapshot",
                    "--robot",
                    "ROBOT_ID",
                    "--input",
                    "JSON",
                ],
                layer="app",
                description="Read one bounded camera frame",
                availability="VERIFIED",
                adapter="bundle:demo-camera#camera_snapshot",
                contract_lifecycle=definition.contract_lifecycle.value,
                contract_version=definition.contract_version,
                contract_sha256=definition.contract_sha256,
                input_schema={
                    "type": "object",
                    "properties": {"camera": {"type": "string"}},
                    "required": ["camera"],
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "camera": {"type": "string"},
                    },
                    "required": ["status", "camera"],
                    "additionalProperties": False,
                },
            )
        ],
    )
    catalog_path = source / "tool-catalog.json"
    catalog_path.write_text(catalog.model_dump_json(indent=2), encoding="utf-8")
    generic = '{"robot_id":"demo","discovery_id":"disc-1","nodes":[],"edges":[]}'
    state_graph = source / "state-graph.json"
    state_graph.write_text(
        '{"schema_version":"robot-state-graph/v1",' + generic[1:], encoding="utf-8"
    )
    conformance = source / "conformance-report.json"
    conformance.write_text(
        '{"schema_version":"robot-adapter-conformance/v1",'
        '"robot_id":"demo","discovery_id":"disc-1","operations":[]}',
        encoding="utf-8",
    )
    gate = source / "gate-report.json"
    gate.write_text('{"status":"PASSED"}', encoding="utf-8")
    output = tmp_path / "output"
    publish_release(
        output_root=output,
        robot_id="demo",
        release_id="release-1",
        discovery_id="disc-1",
        bundle_manifest_path=bundle_path,
        adapter_package_path=package,
        tool_catalog_path=catalog_path,
        state_graph_path=state_graph,
        conformance_path=conformance,
        gate_report_path=gate,
    )
    activate_release(output, "demo", "release-1")
    return output


def test_runtime_invokes_only_the_entrypoint_bound_in_active_catalog(tmp_path: Path) -> None:
    output = _publish_demo_release(tmp_path)

    result = invoke_adapter(
        output,
        "demo",
        "app.camera.snapshot",
        {"camera": "front_camera"},
    )

    assert result == {"status": "SUCCEEDED", "camera": "front_camera"}


def test_runtime_rejects_a_tampered_adapter_package(tmp_path: Path) -> None:
    output = _publish_demo_release(tmp_path)
    package = output / "robots/demo/releases/release-1/adapter/demo_adapter.py"
    package.write_text("tampered", encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        invoke_adapter(output, "demo", "app.camera.snapshot", {"camera": "front"})


def test_runtime_rejects_operation_missing_from_active_catalog(tmp_path: Path) -> None:
    output = _publish_demo_release(tmp_path)

    with pytest.raises(ValueError, match="not in the active Tool Catalog"):
        invoke_adapter(output, "demo", "app.navigation.start", {})


def test_runtime_enforces_registered_input_field_types(tmp_path: Path) -> None:
    output = _publish_demo_release(tmp_path)

    with pytest.raises(ValueError, match="adapter input.camera has wrong type"):
        invoke_adapter(output, "demo", "app.camera.snapshot", {"camera": 7})


def test_generic_tool_invoke_cli_routes_through_active_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _publish_demo_release(tmp_path)
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(output))
    get_settings.cache_clear()

    result = CliRunner().invoke(
        app,
        [
            "tool",
            "invoke",
            "app.camera.snapshot",
            "--robot",
            "demo",
            "--input",
            '{"camera":"front_camera"}',
        ],
    )

    get_settings.cache_clear()
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "status": "SUCCEEDED",
        "camera": "front_camera",
    }

import getpass
import json
import os
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rolo.adapter_runner import AdapterProcessResult
from rolo.adapter_runtime import (
    activate_release,
    adapter_command,
    invoke_adapter,
    operation_route_binding_document,
    probe_adapter_package,
    publish_release,
    resolve_route_binding,
)
from rolo.cli import app
from rolo.core.config import get_settings
from rolo.core.hashing import sha256_file
from rolo.core.models import (
    DiscoveryReport,
    DiscoveryStatus,
    OperationCandidate,
    ProbeResult,
    RouteEvidence,
    ToolDescriptor,
)
from rolo.stages.adapt.models import AdapterBundleManifest, StateGraphBaseline, ToolCatalog
from rolo.stages.adapt.operation_registry import canonical_operation_registry
from rolo.stages.adapt.state_graph import build_state_graph_baseline
from rolo.stages.adapt.target_fingerprint import target_fingerprint_sha256


def _target_report() -> DiscoveryReport:
    route = RouteEvidence(
        resource_id="ros_topic:/camera/image_raw",
        kind="ros_topic",
        endpoint="/camera/image_raw",
        interface_type="sensor_msgs/msg/Image",
        evidence_origin="OBSERVED_RUNTIME",
        source="runtime_probe:ros",
    )
    return DiscoveryReport(
        discovery_id="disc-1",
        robot_id="demo",
        status=DiscoveryStatus.SUCCEEDED,
        platform={},
        capability_manifest={},
        probes={
            "ros": ProbeResult(
                layer="ros",
                status=DiscoveryStatus.SUCCEEDED,
                data={
                    "route_evidence": [route.model_dump(mode="json")],
                    "runtime_environment": {},
                },
            )
        },
        operation_candidates=[
            OperationCandidate(
                operation="app.camera.snapshot",
                evidence=["/camera/image_raw"],
                route_evidence=[route],
            )
        ],
    )


def _multi_route_graph() -> StateGraphBaseline:
    return StateGraphBaseline(
        robot_id="demo",
        discovery_id="disc-1",
        owner="ROLO_GATE",
        nodes=[
            {"id": "operation:camera", "kind": "operation", "operation": "camera"},
            {
                "id": "route:b",
                "kind": "route",
                "resource_id": "ros_topic:/camera/rear",
                "route_kind": "ros_topic",
                "endpoint": "/camera/rear",
                "semantic_bindings": ["camera.rear"],
            },
            {
                "id": "route:a",
                "kind": "route",
                "resource_id": "ros_topic:/camera/front",
                "route_kind": "ros_topic",
                "endpoint": "/camera/front",
                "semantic_bindings": ["camera.front"],
            },
        ],
        edges=[
            {"source": "operation:camera", "target": "route:b", "relation": "routes_to"},
            {"source": "operation:camera", "target": "route:a", "relation": "routes_to"},
        ],
    )


def test_route_binding_document_is_deterministic_and_fail_closed() -> None:
    document = operation_route_binding_document(_multi_route_graph(), "camera")

    assert document["schema_version"] == "rolo-target-route-bindings/v1"
    assert [item["route_id"] for item in document["bindings"]] == ["route:a", "route:b"]
    assert document["semantic_bindings"] == ["camera.front", "camera.rear"]
    assert resolve_route_binding(document, {"endpoint": "/camera/rear"})["route_id"] == "route:b"
    assert resolve_route_binding(document, {"camera": "front"})["route_id"] == "route:a"
    with pytest.raises(ValueError, match="explicit route selector"):
        resolve_route_binding(document, {})
    with pytest.raises(ValueError, match="does not match"):
        resolve_route_binding(document, {"endpoint": "/camera/unknown"})


def test_route_binding_document_rejects_semantic_binding_mismatch() -> None:
    with pytest.raises(ValueError, match="semantic binding mismatch"):
        operation_route_binding_document(
            _multi_route_graph(), "camera", semantic_bindings=["camera.only"]
        )


def test_package_probe_runs_describe_without_crossing_invoke_boundary(
    tmp_path: Path,
) -> None:
    definition = next(
        item
        for item in canonical_operation_registry().operations
        if item.operation == "app.camera.list"
    )
    package = tmp_path / "adapter.py"
    package.write_text("# protocol probe fixture\n", encoding="utf-8")
    manifest = AdapterBundleManifest(
        bundle_id="camera-list",
        bundle_version="1.0.0",
        robot_id="demo",
        discovery_id="disc-1",
        package_file=package.name,
        package_sha256=sha256_file(package),
        files=[
            {
                "path": package.name,
                "sha256": sha256_file(package),
                "role": "ENTRYPOINT",
            }
        ],
        operations=[
            {
                "operation": definition.operation,
                "entrypoint": "camera_list",
                "contract_version": definition.contract_version,
                "contract_sha256": definition.contract_sha256,
            }
        ],
    )

    class DescribeOnlyRunner:
        def __init__(self) -> None:
            self.commands: list[list[str]] = []

        def run(self, command: list[str], **kwargs: object) -> AdapterProcessResult:
            del kwargs
            self.commands.append(command)
            if command[-1] == "describe":
                return AdapterProcessResult(
                    returncode=0,
                    stdout=json.dumps(
                        {"operations": {definition.operation: "camera_list"}}
                    ),
                    stderr="",
                )
            raise AssertionError("promotion must not execute adapter invoke")

    runner = DescribeOnlyRunner()
    probe_adapter_package(package, manifest, runner=runner)

    assert len(runner.commands) == 1
    assert runner.commands[0][-1] == "describe"


def test_package_probe_rejects_cli_with_missing_shebang_interpreter(
    tmp_path: Path,
) -> None:
    definition = next(
        item
        for item in canonical_operation_registry().operations
        if item.operation == "app.camera.list"
    )
    package = tmp_path / "adapter.py"
    package.write_text("# protocol probe fixture\n", encoding="utf-8")
    manifest = AdapterBundleManifest(
        bundle_id="camera-list",
        bundle_version="1.0.0",
        robot_id="demo",
        discovery_id="disc-1",
        package_file=package.name,
        package_sha256=sha256_file(package),
        files=[
            {"path": package.name, "sha256": sha256_file(package), "role": "ENTRYPOINT"}
        ],
        operations=[
            {
                "operation": definition.operation,
                "entrypoint": "camera_list",
                "contract_version": definition.contract_version,
                "contract_sha256": definition.contract_sha256,
            }
        ],
    )
    graph = StateGraphBaseline(
        robot_id="demo",
        discovery_id="disc-1",
        owner="ROLO_GATE",
        nodes=[
            {
                "id": "operation:app.camera.list",
                "kind": "operation",
                "operation": "app.camera.list",
            },
            {
                "id": "route:camera",
                "kind": "route",
                "route_kind": "cli",
                "endpoint": "lerobot-list-cameras-readonly",
            },
        ],
        edges=[
            {
                "source": "operation:app.camera.list",
                "target": "route:camera",
                "relation": "routes_to",
            }
        ],
    )

    class VisibilityRunner:
        def __init__(self) -> None:
            self.commands: list[list[str]] = []

        def run(self, command: list[str], **kwargs: object) -> AdapterProcessResult:
            self.commands.append(command)
            if command[-1] == "describe":
                return AdapterProcessResult(
                    returncode=0,
                    stdout=json.dumps({"operations": {definition.operation: "camera_list"}}),
                    stderr="",
                )
            if "validate-binding" in command:
                return AdapterProcessResult(
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "schema_version": "robot-adapter-binding-validation/v1",
                            "operation": definition.operation,
                            "entrypoint": "camera_list",
                            "status": "VALID",
                        }
                    ),
                    stderr="",
                )
            if command == ["lerobot-list-cameras-readonly", "--help"]:
                return AdapterProcessResult(
                    returncode=0,
                    stdout="usage: lerobot-list-cameras-readonly",
                    stderr="",
                )
            assert command[1] == "-c"
            assert json.loads(str(kwargs["stdin"])) == ["lerobot-list-cameras-readonly"]
            return AdapterProcessResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "lerobot-list-cameras-readonly": {
                            "path": "/target/bin/lerobot-list-cameras-readonly",
                            "interpreter": "/target/venv/bin/python",
                            "interpreter_visible": False,
                        }
                    }
                ),
                stderr="",
            )

    runner = VisibilityRunner()
    with pytest.raises(ValueError, match="interpreter is not resolvable"):
        probe_adapter_package(
            package,
            manifest,
            runner=runner,
            runtime_environment={"PATH": "/target/bin"},
            state_graph=graph,
        )

    assert any(
        len(command) >= 2 and command[1] == "-c" for command in runner.commands
    )


def test_package_probe_runs_bounded_help_for_gated_cli_routes(tmp_path: Path) -> None:
    definition = next(
        item
        for item in canonical_operation_registry().operations
        if item.operation == "app.camera.list"
    )
    package = tmp_path / "adapter.py"
    package.write_text("# protocol probe fixture\n", encoding="utf-8")
    manifest = AdapterBundleManifest(
        bundle_id="camera-list",
        bundle_version="1.0.0",
        robot_id="demo",
        discovery_id="disc-1",
        package_file=package.name,
        package_sha256=sha256_file(package),
        files=[
            {"path": package.name, "sha256": sha256_file(package), "role": "ENTRYPOINT"}
        ],
        operations=[
            {
                "operation": definition.operation,
                "entrypoint": "camera_list",
                "contract_version": definition.contract_version,
                "contract_sha256": definition.contract_sha256,
            }
        ],
    )
    graph = StateGraphBaseline(
        robot_id="demo",
        discovery_id="disc-1",
        owner="ROLO_GATE",
        nodes=[
            {
                "id": f"operation:{definition.operation}",
                "kind": "operation",
                "operation": definition.operation,
            },
            {
                "id": "route:cli",
                "kind": "route",
                "resource_id": "cli:camera-list",
                "route_kind": "cli",
                "endpoint": "camera-list",
                "semantic_bindings": [],
            },
        ],
        edges=[
            {
                "source": f"operation:{definition.operation}",
                "target": "route:cli",
                "relation": "routes_to",
            }
        ],
    )

    class HelpRunner:
        def __init__(self) -> None:
            self.commands: list[list[str]] = []

        def run(self, command: list[str], **kwargs: object) -> AdapterProcessResult:
            del kwargs
            self.commands.append(command)
            if command[-1] == "describe":
                return AdapterProcessResult(
                    returncode=0,
                    stdout=json.dumps({"operations": {definition.operation: "camera_list"}}),
                    stderr="",
                )
            if len(command) >= 2 and command[1] == "-c":
                return AdapterProcessResult(
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "camera-list": {
                                "path": "C:/target/bin/camera-list",
                                "interpreter": None,
                                "interpreter_visible": None,
                            }
                        }
                    ),
                    stderr="",
                )
            assert command == ["camera-list", "--help"]
            return AdapterProcessResult(returncode=0, stdout="usage: camera-list", stderr="")

    runner = HelpRunner()
    probe_adapter_package(package, manifest, runner=runner, state_graph=graph)

    assert runner.commands[0] == [sys.executable, str(package), "describe"]
    assert runner.commands[1] == ["camera-list", "--help"]
    assert runner.commands[2][0] == sys.executable
    assert runner.commands[2][1] == "-c"


def test_package_probe_rejects_failed_cli_help_probe(tmp_path: Path) -> None:
    definition = next(
        item
        for item in canonical_operation_registry().operations
        if item.operation == "app.camera.list"
    )
    package = tmp_path / "adapter.py"
    package.write_text("# protocol probe fixture\n", encoding="utf-8")
    manifest = AdapterBundleManifest(
        bundle_id="camera-list",
        bundle_version="1.0.0",
        robot_id="demo",
        discovery_id="disc-1",
        package_file=package.name,
        package_sha256=sha256_file(package),
        files=[
            {"path": package.name, "sha256": sha256_file(package), "role": "ENTRYPOINT"}
        ],
        operations=[
            {
                "operation": definition.operation,
                "entrypoint": "camera_list",
                "contract_version": definition.contract_version,
                "contract_sha256": definition.contract_sha256,
            }
        ],
    )
    graph = StateGraphBaseline(
        robot_id="demo",
        discovery_id="disc-1",
        owner="ROLO_GATE",
        nodes=[
            {
                "id": f"operation:{definition.operation}",
                "kind": "operation",
                "operation": definition.operation,
            },
            {
                "id": "route:cli",
                "kind": "route",
                "resource_id": "cli:camera-list",
                "route_kind": "cli",
                "endpoint": "camera-list",
                "semantic_bindings": [],
            },
        ],
        edges=[
            {
                "source": f"operation:{definition.operation}",
                "target": "route:cli",
                "relation": "routes_to",
            }
        ],
    )

    class FailingHelpRunner:
        def run(self, command: list[str], **kwargs: object) -> AdapterProcessResult:
            del kwargs
            if command[-1] == "describe":
                return AdapterProcessResult(
                    returncode=0,
                    stdout=json.dumps({"operations": {definition.operation: "camera_list"}}),
                    stderr="",
                )
            return AdapterProcessResult(returncode=2, stdout="", stderr="unsupported")

    with pytest.raises(ValueError, match="target CLI help probe failed.*camera-list"):
        probe_adapter_package(package, manifest, runner=FailingHelpRunner(), state_graph=graph)


def test_python_zipapp_uses_interpreter_launcher(tmp_path: Path) -> None:
    package = tmp_path / "adapter.pyz"

    assert adapter_command(package) == [sys.executable, str(package)]


@pytest.fixture(autouse=True)
def _latest_target_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "rolo.stages.adapt.discovery.load_latest_report", lambda *_: _target_report()
    )


def _publish_demo_release(
    tmp_path: Path,
    *,
    target_report: DiscoveryReport | None = None,
    release_id: str = "release-1",
    activate: bool = True,
    runtime_environment: dict[str, str] | None = None,
) -> Path:
    definition = next(
        item
        for item in canonical_operation_registry().operations
        if item.operation == "app.camera.snapshot"
    )
    source = tmp_path / f"source-{release_id}"
    source.mkdir()
    helper = source / "demo_support.py"
    helper.write_text(
        "def result(payload):\n"
        "    return {'status': 'SUCCEEDED', 'camera': payload['camera']}\n",
        encoding="utf-8",
    )
    package = source / "demo_adapter.py"
    package.write_text(
        "import json, sys\n"
        "from demo_support import result\n"
        "OPS = {'app.camera.snapshot': 'camera_snapshot'}\n"
        "if sys.argv[1] == 'describe':\n"
        "    print(json.dumps({'operations': OPS}))\n"
        "elif sys.argv[1] == 'invoke':\n"
        "    args = dict(zip(sys.argv[2::2], sys.argv[3::2]))\n"
        "    operation = args.get('--operation')\n"
        "    if operation not in OPS or args.get('--entrypoint') != OPS[operation]:\n"
        "        print(json.dumps({'error': {'code': 'INVALID_INPUT'}}))\n"
        "        raise SystemExit(1)\n"
        "    payload = json.load(sys.stdin)\n"
        "    print(json.dumps(result(payload)))\n",
        encoding="utf-8",
    )
    bundle = AdapterBundleManifest(
        bundle_id="demo-camera",
        bundle_version="1.0.0",
        robot_id="demo",
        discovery_id="disc-1",
        package_file=package.name,
        package_sha256=sha256_file(package),
        files=[
            {
                "path": package.name,
                "sha256": sha256_file(package),
                "role": "ENTRYPOINT",
            },
            {
                "path": helper.name,
                "sha256": sha256_file(helper),
                "role": "SUPPORT",
            },
        ],
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
                data_classification=definition.data_classification.value,
                result_semantics=definition.result_semantics.value,
                observation_overhead=definition.observation_overhead.value,
                execution_mode=definition.execution_mode.value,
                paired_operation=definition.paired_operation,
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
    report = target_report or _target_report()
    state_graph = source / "state-graph.json"
    state_graph.write_text(
        build_state_graph_baseline(report, bundle)
        .model_copy(update={"schema_version": "robot-state-graph/v1"})
        .model_dump_json(indent=2),
        encoding="utf-8",
    )
    conformance = source / "conformance-report.json"
    conformance.write_text(
        '{"schema_version":"robot-adapter-conformance/v1",'
        '"robot_id":"demo","discovery_id":"disc-1","operations":[]}',
        encoding="utf-8",
    )
    gate = source / "gate-report.json"
    gate.write_text(
        json.dumps(
            {
                "schema_version": "robot-adapt-gate/v1",
                "run_id": release_id,
                "robot_id": "demo",
                "discovery_id": "disc-1",
                "status": "PASSED",
                "checks": [],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output"
    publish_release(
        output_root=output,
        robot_id="demo",
        release_id=release_id,
        discovery_id="disc-1",
        target_fingerprint_sha256=target_fingerprint_sha256(
            report, operations=["app.camera.snapshot"]
        ),
        runtime_environment=runtime_environment or {},
        bundle_manifest_path=bundle_path,
        adapter_package_path=package,
        adapter_files=[
            (package.name, package, "ENTRYPOINT"),
            (helper.name, helper, "SUPPORT"),
        ],
        tool_catalog_path=catalog_path,
        state_graph_path=state_graph,
        conformance_path=conformance,
        gate_report_path=gate,
    )
    if activate:
        activate_release(output, "demo", release_id, artifact_root=tmp_path)
    return output


def test_publish_release_preserves_target_executable_path(tmp_path: Path) -> None:
    target_bin = tmp_path / "target-bin"
    target_bin.mkdir()
    target_src = tmp_path / "target-src"
    target_src.mkdir()

    output = _publish_demo_release(
        tmp_path,
        activate=False,
        runtime_environment={"PATH": str(target_bin), "PYTHONPATH": str(target_src)},
    )

    release = json.loads(
        (output / "robots/demo/releases/release-1/manifest.json").read_text(encoding="utf-8")
    )
    assert release["runtime_environment"]["PATH"] == str(target_bin)
    assert release["runtime_environment"]["PYTHONPATH"] == str(target_src)


def _sensitive_access(
    tmp_path: Path, *, allowed_user: str | None = None
) -> tuple[Path, Path]:
    policy = tmp_path / "invocation-policy.yaml"
    policy.write_text(
        "schema_version: rolo-invocation-policy/v1\n"
        "sensitive:\n"
        f"  allowed_users: [{json.dumps(allowed_user or getpass.getuser())}]\n"
        "  allowed_groups: []\n",
        encoding="utf-8",
    )
    if os.name == "posix":
        policy.chmod(0o600)
    return policy, tmp_path / "invocation-audit.jsonl"


def test_runtime_invokes_only_the_entrypoint_bound_in_active_catalog(tmp_path: Path) -> None:
    output = _publish_demo_release(tmp_path)
    policy, audit = _sensitive_access(tmp_path)

    result = invoke_adapter(
        output,
        "demo",
        "app.camera.snapshot",
        {"camera": "front_camera"},
        artifact_root=tmp_path,
        policy_path=policy,
        audit_path=audit,
    )

    assert result == {"status": "SUCCEEDED", "camera": "front_camera"}
    lines = audit.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    execution = [
        record
        for record in records
        if record["schema_version"] == "rolo-adapter-execution-audit/v1"
    ]
    assert [record["outcome"] for record in execution] == ["STARTED", "SUCCEEDED"]
    assert execution[0]["invocation_id"] == execution[1]["invocation_id"]
    assert execution[1]["release_id"] == "release-1"
    assert "result_sha256" in execution[1]
    assert "front_camera" not in audit.read_text(encoding="utf-8")


def test_runtime_injects_gated_route_binding_document(tmp_path: Path) -> None:
    class CaptureRunner:
        def __init__(self) -> None:
            self.environment: dict[str, str] | None = None

        def run(self, command: list[str], **kwargs: object) -> AdapterProcessResult:
            assert command[-1] == "camera_snapshot"
            self.environment = kwargs["runtime_environment"]  # type: ignore[assignment]
            return AdapterProcessResult(
                returncode=0,
                stdout=json.dumps({"status": "SUCCEEDED", "camera": "front_camera"}),
                stderr="",
            )

    output = _publish_demo_release(tmp_path)
    policy, audit = _sensitive_access(tmp_path)
    runner = CaptureRunner()

    invoke_adapter(
        output,
        "demo",
        "app.camera.snapshot",
        {"camera": "front_camera"},
        artifact_root=tmp_path,
        policy_path=policy,
        audit_path=audit,
        runner=runner,
    )

    assert runner.environment is not None
    document = json.loads(runner.environment["ROLO_TARGET_ROUTE_BINDINGS_JSON"])
    assert document["schema_version"] == "rolo-target-route-bindings/v1"
    assert document["operation"] == "app.camera.snapshot"
    assert document["selected_route_id"].startswith("route:")


def test_runtime_denies_sensitive_operation_without_protected_policy(tmp_path: Path) -> None:
    output = _publish_demo_release(tmp_path)
    audit = tmp_path / "invocation-audit.jsonl"

    with pytest.raises(ValueError, match="policy is missing"):
        invoke_adapter(
            output,
            "demo",
            "app.camera.snapshot",
            {"camera": "front_camera"},
            artifact_root=tmp_path,
            audit_path=audit,
        )

    record = json.loads(audit.read_text(encoding="utf-8"))
    assert record["outcome"] == "DENIED"
    assert "front_camera" not in audit.read_text(encoding="utf-8")


def test_runtime_audits_invalid_adapter_result(tmp_path: Path) -> None:
    class InvalidResultRunner:
        def run(self, command: list[str], **kwargs: object) -> AdapterProcessResult:
            del command, kwargs
            return AdapterProcessResult(returncode=0, stdout="not-json", stderr="")

    output = _publish_demo_release(tmp_path)
    policy, audit = _sensitive_access(tmp_path)

    with pytest.raises(RuntimeError, match="invalid JSON"):
        invoke_adapter(
            output,
            "demo",
            "app.camera.snapshot",
            {"camera": "front_camera"},
            artifact_root=tmp_path,
            policy_path=policy,
            audit_path=audit,
            runner=InvalidResultRunner(),
        )

    records = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    execution = [
        record
        for record in records
        if record["schema_version"] == "rolo-adapter-execution-audit/v1"
    ]
    assert [record["outcome"] for record in execution] == ["STARTED", "INVALID_RESULT"]
    assert execution[-1]["error_code"] == "INVALID_RESULT"


def test_runtime_denies_sensitive_operation_for_unlisted_os_identity(tmp_path: Path) -> None:
    output = _publish_demo_release(tmp_path)
    policy, audit = _sensitive_access(tmp_path, allowed_user="not-the-current-user")

    with pytest.raises(ValueError, match="host principal is not authorized"):
        invoke_adapter(
            output,
            "demo",
            "app.camera.snapshot",
            {"camera": "front_camera"},
            artifact_root=tmp_path,
            policy_path=policy,
            audit_path=audit,
        )

    record = json.loads(audit.read_text(encoding="utf-8"))
    assert record["outcome"] == "DENIED"


def test_runtime_rejects_a_tampered_adapter_package(tmp_path: Path) -> None:
    output = _publish_demo_release(tmp_path)
    package = output / "robots/demo/releases/release-1/adapter/demo_adapter.py"
    package.write_text("tampered", encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        invoke_adapter(
            output,
            "demo",
            "app.camera.snapshot",
            {"camera": "front"},
            artifact_root=tmp_path,
        )


def test_runtime_rejects_a_tampered_adapter_support_file(tmp_path: Path) -> None:
    output = _publish_demo_release(tmp_path)
    support = output / "robots/demo/releases/release-1/adapter/demo_support.py"
    support.write_text("tampered", encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        invoke_adapter(
            output,
            "demo",
            "app.camera.snapshot",
            {"camera": "front"},
            artifact_root=tmp_path,
        )


def test_activation_rejects_tampered_candidate_and_preserves_current(
    tmp_path: Path,
) -> None:
    output = _publish_demo_release(tmp_path, release_id="release-1")
    _publish_demo_release(tmp_path, release_id="release-2", activate=False)
    candidate_support = (
        output / "robots/demo/releases/release-2/adapter/demo_support.py"
    )
    candidate_support.write_text("tampered", encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        activate_release(output, "demo", "release-2", artifact_root=tmp_path)

    current = json.loads((output / "robots/demo/current.json").read_text(encoding="utf-8"))
    assert current["release_id"] == "release-1"


def test_activation_compare_and_swap_preserves_newer_current(tmp_path: Path) -> None:
    output = _publish_demo_release(tmp_path, release_id="release-1")
    _publish_demo_release(tmp_path, release_id="release-2", activate=False)

    with pytest.raises(ValueError, match="changed before activation"):
        activate_release(
            output,
            "demo",
            "release-2",
            artifact_root=tmp_path,
            expected_current_release_id="stale-release",
        )

    current = json.loads((output / "robots/demo/current.json").read_text(encoding="utf-8"))
    assert current["release_id"] == "release-1"


def test_runtime_rejects_legacy_release_without_mandatory_freshness(
    tmp_path: Path,
) -> None:
    output = _publish_demo_release(tmp_path)
    release_manifest = output / "robots/demo/releases/release-1/manifest.json"
    release = json.loads(release_manifest.read_text(encoding="utf-8"))
    release["schema_version"] = "robot-adapter-release/v1"
    release["target_fingerprint_sha256"] = None
    release_manifest.write_text(json.dumps(release), encoding="utf-8")
    current_path = output / "robots/demo/current.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    current["manifest_sha256"] = sha256_file(release_manifest)
    current_path.write_text(json.dumps(current), encoding="utf-8")

    with pytest.raises(ValueError, match="legacy adapter releases cannot be loaded"):
        invoke_adapter(
            output,
            "demo",
            "app.camera.snapshot",
            {"camera": "front"},
            artifact_root=tmp_path,
        )


def test_runtime_rejects_release_when_latest_target_fingerprint_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _target_report()
    output = _publish_demo_release(tmp_path, target_report=report)
    changed = report.model_copy(update={"platform": {"architecture": "different"}})
    monkeypatch.setattr("rolo.stages.adapt.discovery.load_latest_report", lambda *_: changed)

    with pytest.raises(ValueError, match="release is stale"):
        invoke_adapter(
            output,
            "demo",
            "app.camera.snapshot",
            {"camera": "front"},
            artifact_root=tmp_path,
        )


def test_runtime_keeps_release_for_equivalent_rediscovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _target_report()
    output = _publish_demo_release(tmp_path, target_report=report)
    equivalent = report.model_copy(update={"discovery_id": "disc-2"})
    monkeypatch.setattr(
        "rolo.stages.adapt.discovery.load_latest_report", lambda *_: equivalent
    )
    policy, audit = _sensitive_access(tmp_path)

    assert invoke_adapter(
        output,
        "demo",
        "app.camera.snapshot",
        {"camera": "front"},
        policy_path=policy,
        audit_path=audit,
        artifact_root=tmp_path,
    )["status"] == "SUCCEEDED"


def test_runtime_rejects_operation_missing_from_active_catalog(tmp_path: Path) -> None:
    output = _publish_demo_release(tmp_path)

    with pytest.raises(ValueError, match="not in the active Tool Catalog"):
        invoke_adapter(
            output,
            "demo",
            "app.navigation.start",
            {},
            artifact_root=tmp_path,
        )


def test_runtime_enforces_registered_input_field_types(tmp_path: Path) -> None:
    output = _publish_demo_release(tmp_path)
    policy, audit = _sensitive_access(tmp_path)

    with pytest.raises(ValueError, match="adapter input.camera has wrong type"):
        invoke_adapter(
            output,
            "demo",
            "app.camera.snapshot",
            {"camera": 7},
            artifact_root=tmp_path,
            policy_path=policy,
            audit_path=audit,
        )


def test_generic_tool_invoke_cli_routes_through_active_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _target_report()
    output = _publish_demo_release(tmp_path, target_report=report)
    policy, audit = _sensitive_access(tmp_path)
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(output))
    monkeypatch.setenv("ROLO_INVOCATION_POLICY", str(policy))
    monkeypatch.setenv("ROLO_INVOCATION_AUDIT_LOG", str(audit))
    monkeypatch.setattr("rolo.stages.adapt.discovery.load_latest_report", lambda *_: report)
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


def test_state_graph_cli_reads_only_the_active_gated_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _target_report()
    output = _publish_demo_release(tmp_path, target_report=report)
    policy, audit = _sensitive_access(tmp_path)
    monkeypatch.setenv("ROLO_OUTPUT_DIR", str(output))
    monkeypatch.setenv("ROLO_INVOCATION_POLICY", str(policy))
    monkeypatch.setenv("ROLO_INVOCATION_AUDIT_LOG", str(audit))
    monkeypatch.setattr("rolo.stages.adapt.discovery.load_latest_report", lambda *_: report)
    get_settings.cache_clear()

    snapshot = CliRunner().invoke(app, ["state", "graph", "snapshot", "--robot", "demo"])
    query = CliRunner().invoke(
        app, ["state", "graph", "query", "camera", "--robot", "demo"]
    )

    get_settings.cache_clear()
    assert snapshot.exit_code == 0, snapshot.output
    assert json.loads(snapshot.output)["schema_version"] == "robot-state-graph/v1"
    assert query.exit_code == 0, query.output
    assert json.loads(query.output)["query"] == "camera"

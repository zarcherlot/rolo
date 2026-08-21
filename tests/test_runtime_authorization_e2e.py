import getpass
import json
import os
from pathlib import Path

import pytest

from rolo.adapter_runtime import activate_release, invoke_adapter, publish_release
from rolo.core.hashing import sha256_file
from rolo.core.models import ToolDescriptor
from rolo.stages.adapt.models import AdapterBundleManifest, ToolCatalog
from rolo.stages.adapt.operation_registry import canonical_operation_registry

_OPERATIONS = (
    "app.localization.status",
    "app.camera.snapshot",
    "linux.service.restart",
    "app.parameter.set",
    "app.teleop.velocity",
    "app.camera.stream.start",
    "app.camera.stream.stop",
    "app.navigation.start",
    "app.navigation.cancel",
    "linux.config.apply",
    "linux.config.rollback",
)


def _publish_runtime_matrix(tmp_path: Path) -> Path:
    definitions = {
        item.operation: item for item in canonical_operation_registry().operations
    }
    source = tmp_path / "s"
    source.mkdir()
    results = {
        "app.localization.status": {"status": "SUCCEEDED"},
        "app.camera.snapshot": {"status": "SUCCEEDED"},
        "linux.service.restart": {
            "status": "SUCCEEDED",
            "target": "service:controller",
            "observed_at": "2026-01-01T00:00:00Z",
        },
        "app.parameter.set": {
            "status": "SUCCEEDED",
            "id": "controller.gain",
            "revision": "revision-2",
            "rollback_token": "rollback://parameter/change-1",
            "observed_at": "2026-01-01T00:00:00Z",
        },
        "app.teleop.velocity": {"status": "SUCCEEDED"},
        "app.camera.stream.start": {
            "status": "SUCCEEDED",
            "session_id": "session-1",
            "expires_at": "2026-01-01T00:01:00Z",
        },
        "app.camera.stream.stop": {"status": "SUCCEEDED", "session_id": "session-1"},
        "app.navigation.start": {
            "status": "SUCCEEDED",
            "run_id": "run-1",
            "observed_at": "2026-01-01T00:00:00Z",
        },
        "app.navigation.cancel": {
            "status": "SUCCEEDED",
            "run_id": "run-1",
            "observed_at": "2026-01-01T00:00:01Z",
        },
        "linux.config.apply": {
            "status": "SUCCEEDED",
            "target": "config:controller",
            "rollback_token": "rollback://config/change-1",
            "observed_at": "2026-01-01T00:00:00Z",
        },
        "linux.config.rollback": {
            "status": "SUCCEEDED",
            "target": "config:controller",
            "observed_at": "2026-01-01T00:00:01Z",
        },
    }
    entrypoints = {operation: operation.replace(".", "_") for operation in _OPERATIONS}
    package = source / "a.py"
    package.write_text(
        "import json, sys\n"
        f"ENTRYPOINTS = {entrypoints!r}\n"
        f"RESULTS = {results!r}\n"
        "if sys.argv[1] == 'describe':\n"
        "    print(json.dumps({'operations': ENTRYPOINTS}))\n"
        "elif sys.argv[1] == 'invoke':\n"
        "    operation = sys.argv[sys.argv.index('--operation') + 1]\n"
        "    json.load(sys.stdin)\n"
        "    print(json.dumps(RESULTS[operation]))\n",
        encoding="utf-8",
    )
    bundle = AdapterBundleManifest(
        bundle_id="m",
        bundle_version="1.0.0",
        robot_id="r",
        discovery_id="d",
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
                "operation": operation,
                "entrypoint": entrypoints[operation],
                "contract_version": definitions[operation].contract_version,
                "contract_sha256": definitions[operation].contract_sha256,
            }
            for operation in _OPERATIONS
        ],
    )
    bundle_path = source / "adapter-manifest.json"
    bundle_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    descriptors = []
    for operation in _OPERATIONS:
        definition = definitions[operation]
        descriptors.append(
            ToolDescriptor(
                operation=operation,
                canonical_cli=definition.canonical_cli,
                layer=definition.layer,
                description=definition.description,
                risk=definition.risk,
                access=definition.access,
                idempotent=definition.idempotent,
                cancelable=definition.cancelable,
                max_duration_s=definition.max_duration_s,
                availability="VERIFIED",
                adapter=f"bundle:m#{entrypoints[operation]}",
                contract_lifecycle=definition.contract_lifecycle.value,
                contract_version=definition.contract_version,
                contract_sha256=definition.contract_sha256,
                data_classification=definition.data_classification.value,
                result_semantics=definition.result_semantics.value,
                execution_mode=definition.execution_mode.value,
                paired_operation=definition.paired_operation,
                compensation_operation=definition.compensation_operation,
                requires_quiescence=definition.requires_quiescence,
                error_codes=definition.error_codes,
                input_schema=definition.input_schema,
                output_schema=definition.output_schema,
            )
        )
    catalog = ToolCatalog(
        robot_id="r",
        discovery_id="d",
        contract_catalog_sha256=canonical_operation_registry().contract_catalog_sha256,
        tools=descriptors,
    )
    catalog_path = source / "tool-catalog.json"
    catalog_path.write_text(catalog.model_dump_json(indent=2), encoding="utf-8")
    state_graph = source / "state-graph.json"
    state_graph.write_text(
        '{"schema_version":"robot-state-graph/v1","robot_id":"r",'
        '"discovery_id":"d","nodes":[],"edges":[]}',
        encoding="utf-8",
    )
    conformance = source / "conformance-report.json"
    conformance.write_text(
        '{"schema_version":"robot-adapter-conformance/v3","owner":"ADAPTER_AGENT",'
        '"coverage":"BUNDLE_CANDIDATES_ONLY","robot_id":"r",'
        '"discovery_id":"d","operations":[]}',
        encoding="utf-8",
    )
    gate = source / "gate-report.json"
    gate.write_text('{"status":"PASSED"}', encoding="utf-8")
    output = tmp_path / "o"
    publish_release(
        output_root=output,
        robot_id="r",
        release_id="x",
        discovery_id="d",
        bundle_manifest_path=bundle_path,
        adapter_package_path=package,
        tool_catalog_path=catalog_path,
        state_graph_path=state_graph,
        conformance_path=conformance,
        gate_report_path=gate,
    )
    activate_release(output, "r", "x")
    return output


def _policy(tmp_path: Path, operations: list[str]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    policy = tmp_path / f"policy-{len(operations)}.yaml"
    policy.write_text(
        json.dumps(
            {
                "schema_version": "rolo-invocation-policy/v1",
                "sensitive": {
                    "allowed_users": [getpass.getuser()],
                    "allowed_groups": [],
                },
                "writes": {
                    "allowed_users": [getpass.getuser()],
                    "allowed_groups": [],
                    "allowed_operations": operations,
                },
                "content_resources": [],
            }
        ),
        encoding="utf-8",
    )
    if os.name == "posix":
        policy.chmod(0o600)
    return policy


def test_published_runtime_closes_the_authorization_and_compensation_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _publish_runtime_matrix(tmp_path)
    audit = tmp_path / "runtime-audit.jsonl"
    allowed_writes = [
        "linux.service.restart",
        "app.parameter.set",
        "app.camera.stream.start",
        "app.camera.stream.stop",
        "app.navigation.cancel",
        "linux.config.apply",
        "linux.config.rollback",
    ]
    policy = _policy(tmp_path, allowed_writes)
    denied_policy = _policy(tmp_path / "denied", [])
    r3_provider = Path("tests/fixtures/providers/r3_authorizer.py").resolve()
    quiescence_provider = Path("tests/fixtures/providers/quiescence_provider.py").resolve()
    monkeypatch.setattr(
        "rolo.invocation_policy.validate_protected_file",
        lambda path, **kwargs: path,
    )

    assert invoke_adapter(
        output, "r", "app.localization.status", {}
    ) == {"status": "SUCCEEDED"}

    with pytest.raises(ValueError, match="SENSITIVE invocation policy is missing"):
        invoke_adapter(
            output,
            "r",
            "app.camera.snapshot",
            {"camera": "private-camera-id"},
            audit_path=audit,
        )
    assert invoke_adapter(
        output,
        "r",
        "app.camera.snapshot",
        {"camera": "private-camera-id"},
        policy_path=policy,
        audit_path=audit,
    )["status"] == "SUCCEEDED"

    service_payload = {"resource_id": "service:controller", "timeout_s": 5.0}
    with pytest.raises(ValueError, match="not present in the protected allowlist"):
        invoke_adapter(
            output,
            "r",
            "linux.service.restart",
            service_payload,
            policy_path=denied_policy,
            audit_path=audit,
        )
    assert invoke_adapter(
        output,
        "r",
        "linux.service.restart",
        service_payload,
        policy_path=policy,
        audit_path=audit,
    )["status"] == "SUCCEEDED"

    parameter_result = invoke_adapter(
        output,
        "r",
        "app.parameter.set",
        {
            "id": "controller.gain",
            "value": {"type": "number", "value_json": "1.0"},
            "expected_current_revision": "revision-1",
        },
        policy_path=policy,
        audit_path=audit,
        quiescence_provider_path=quiescence_provider,
    )
    assert parameter_result["rollback_token"].startswith("rollback://")

    assert invoke_adapter(
        output,
        "r",
        "app.teleop.velocity",
        {"linear_x_mps": 0.1, "angular_z_radps": 0.0},
        audit_path=audit,
        r3_authorizer_path=r3_provider,
    )["status"] == "SUCCEEDED"

    session = invoke_adapter(
        output,
        "r",
        "app.camera.stream.start",
        {"camera": "front", "ttl_s": 30.0, "max_bytes": 4096},
        policy_path=policy,
        audit_path=audit,
    )
    assert invoke_adapter(
        output,
        "r",
        "app.camera.stream.stop",
        {"session_id": session["session_id"]},
        policy_path=policy,
        audit_path=audit,
    )["session_id"] == session["session_id"]

    navigation = invoke_adapter(
        output,
        "r",
        "app.navigation.start",
        {
            "plan_id": "plan-1",
            "map_id": "map-1",
            "execution_profile_id": "profile-1",
            "max_run_duration_s": 60.0,
        },
        policy_path=policy,
        audit_path=audit,
        r3_authorizer_path=r3_provider,
    )
    assert invoke_adapter(
        output,
        "r",
        "app.navigation.cancel",
        {"run_id": navigation["run_id"], "reason": "test cancellation"},
        policy_path=policy,
        audit_path=audit,
    )["run_id"] == navigation["run_id"]

    artifact = tmp_path / "artifacts" / "config" / "controller.yaml"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("controller: safe\n", encoding="utf-8")
    applied = invoke_adapter(
        output,
        "r",
        "linux.config.apply",
        {
            "target_resource_id": "config:controller",
            "artifact_ref": "artifact://config/controller.yaml",
            "artifact_sha256": sha256_file(artifact),
            "format": "yaml",
            "max_bytes": 4096,
        },
        policy_path=policy,
        audit_path=audit,
        artifact_root=artifact.parents[1],
    )
    assert invoke_adapter(
        output,
        "r",
        "linux.config.rollback",
        {
            "target_resource_id": "config:controller",
            "rollback_token": applied["rollback_token"],
        },
        policy_path=policy,
        audit_path=audit,
    )["status"] == "SUCCEEDED"

    audit_text = audit.read_text(encoding="utf-8")
    records = [json.loads(line) for line in audit_text.splitlines()]
    assert {"data", "write", "r3", "quiescence"} <= {
        record["policy_domain"] for record in records
    }
    assert "private-camera-id" not in audit_text
    assert "controller.gain" not in audit_text
    assert "rollback://" not in audit_text
    assert all("payload" not in record and "input" not in record for record in records)

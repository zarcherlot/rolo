import json
from pathlib import Path
from unittest.mock import patch

import pytest

from rolo.core.artifacts import ArtifactStore
from rolo.core.hashing import sha256_file
from rolo.core.models import ProbeResult, utc_now
from rolo.core.registry import RobotRegistry
from rolo.stages.adapt.conformance import (
    AdapterPromotionService,
    validate_adapter_handoff,
)
from rolo.stages.adapt.discovery import DiscoveryService
from rolo.stages.adapt.models import AdapterAgentResult, AdapterAgentRun
from rolo.stages.adapt.operation_registry import (
    canonical_operation_registry,
    required_conformance_operations,
)


def _prepare_promotion(
    artifact_root: Path,
    workspace: Path,
    *,
    include_write_operation: bool = False,
    runtime_ready: bool = True,
    route_observed: bool = True,
) -> tuple[str, AdapterAgentRun]:
    (workspace / "pyproject.toml").write_text(
        '[project]\nname = "demo-adapter"\n\n[project.scripts]\ndemo-adapter = "demo:main"\n',
        encoding="utf-8",
    )
    if include_write_operation:
        (workspace / "driver.py").write_text(
            'node.create_publisher(Twist, "/cmd_vel", 10)\n', encoding="utf-8"
        )
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()
    ros_probe = ProbeResult(
        layer="ros",
        status="SUCCEEDED" if runtime_ready else "UNAVAILABLE",
        data={
            "ros_distro": "test",
            "installed_distros": ["test"],
            "domain_id": "0",
            "rmw": "test",
            "nodes": [],
            "topics": (
                ["/cmd_vel"]
                if runtime_ready and route_observed
                else ["/cmd_vel_extra"]
                if runtime_ready
                else []
            ),
            "services": [],
            "actions": [],
        },
    )
    with patch("rolo.stages.adapt.discovery.RosProbe.run", return_value=ros_probe):
        report, _ = DiscoveryService(ArtifactStore(artifact_root)).run(
            robot=registry.get("demo_diff"),
            urdf_path=Path("tests/fixtures/profiles/differential_drive.urdf"),
            source_roots=[workspace],
        )
    definitions = {
        item.operation: item for item in canonical_operation_registry().operations
    }
    bundle_operations = [
        {
            "operation": candidate.operation,
            "entrypoint": candidate.operation.replace(".", "_"),
            "contract_version": definitions[candidate.operation].contract_version,
            "contract_sha256": definitions[candidate.operation].contract_sha256,
        }
        for candidate in report.operation_candidates
    ]
    operation_map = {item["operation"]: item["entrypoint"] for item in bundle_operations}
    package_path = workspace / "demo_adapter.py"
    package_path.write_text(
        "import json, sys\n"
        f"OPERATIONS = {operation_map!r}\n"
        "if sys.argv[1] == 'describe':\n"
        "    print(json.dumps({'operations': OPERATIONS}))\n"
        "elif sys.argv[1] == 'invoke':\n"
        "    print(json.dumps({'status': 'SUCCEEDED'}))\n",
        encoding="utf-8",
    )
    (workspace / "adapter-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "robot-adapter-bundle/v1",
                "bundle_id": "demo-adapter",
                "bundle_version": "1.0.0",
                "robot_id": "demo_diff",
                "discovery_id": report.discovery_id,
                "runtime_protocol": "robot-adapter-rpc/v1",
                "package_file": package_path.name,
                "package_sha256": sha256_file(package_path),
                "operations": bundle_operations,
            }
        ),
        encoding="utf-8",
    )
    (workspace / "state_graph.json").write_text(
        json.dumps(
            {
                "schema_version": "robot-state-graph/v1",
                "robot_id": "demo_diff",
                "discovery_id": report.discovery_id,
                "nodes": [],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    operations = []
    for operation in sorted(required_conformance_operations(report)):
        operations.append(
            {
                "operation": operation,
                "schema_valid": True,
                "errors_valid": True,
                "idempotency_valid": True,
                "cancellation_valid": True,
                "validation_scopes": ["LOCAL_STATIC"],
                "evidence": ["artifact://evidence/result.json"],
            }
        )
    (workspace / "conformance.json").write_text(
        json.dumps(
            {
                "schema_version": "robot-adapter-conformance/v2",
                "robot_id": "demo_diff",
                "discovery_id": report.discovery_id,
                "operations": operations,
            }
        ),
        encoding="utf-8",
    )
    result = AdapterAgentResult(
        schema_version="robot-adapter-agent-result/v1",
        summary="adapter outputs prepared",
        completed_tasks=[],
        changed_files=[],
        validation=[],
        blockers=[],
        handoff_ready=True,
        outputs={
            "adapter_manifest": "adapter-manifest.json",
            "adapter_package": "demo_adapter.py",
            "state_graph": "state_graph.json",
            "conformance_report": "conformance.json",
        },
    )
    store = ArtifactStore(artifact_root)
    result_path = store.write_json(
        "adapt/demo_diff/runs/run-test/result.json",
        result.model_dump(mode="json"),
    )
    now = utc_now()
    run = AdapterAgentRun(
        run_id="run-test",
        robot_id="demo_diff",
        source_discovery_id=report.discovery_id,
        provider="codex",
        status="SUCCEEDED",
        workspace=str(workspace),
        command=["codex", "exec"],
        prompt_ref="artifact://prompt",
        event_log_ref="artifact://events",
        stderr_ref="artifact://stderr",
        final_message_ref="artifact://final",
        result_ref=f"artifact://{result_path.relative_to(artifact_root).as_posix()}",
        started_at=now,
        completed_at=now,
        duration_s=0,
    )
    return report.discovery_id, run


def test_promotion_publishes_only_independently_validated_handoff(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    discovery_id, run = _prepare_promotion(artifact_root, workspace)

    service = AdapterPromotionService(ArtifactStore(artifact_root), tmp_path / "output")
    snapshot, _ = service.snapshot(run)
    assert not hasattr(snapshot, "tool_catalog_ref")
    handoff, path, _, _ = service.promote_run(run, snapshot)

    assert path.is_file()
    assert handoff.source_discovery_id == discovery_id
    assert (
        validate_adapter_handoff(artifact_root, "demo_diff", output_root=tmp_path / "output")
        == handoff
    )
    assert (tmp_path / "output/robots/demo_diff/current.json").is_file()


def test_promotion_rejects_incomplete_conformance_coverage(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _, run = _prepare_promotion(artifact_root, workspace)
    payload = json.loads((workspace / "conformance.json").read_text(encoding="utf-8"))
    payload["operations"].pop()
    (workspace / "conformance.json").write_text(json.dumps(payload), encoding="utf-8")

    service = AdapterPromotionService(ArtifactStore(artifact_root), tmp_path / "output")
    with pytest.raises(ValueError, match="coverage"):
        snapshot, _ = service.snapshot(run)
        service.promote_run(run, snapshot)


def test_promotion_uses_frozen_snapshot_after_workspace_changes(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _, run = _prepare_promotion(artifact_root, workspace)
    service = AdapterPromotionService(ArtifactStore(artifact_root), tmp_path / "output")
    snapshot, _ = service.snapshot(run)

    (workspace / "state_graph.json").write_text("{}", encoding="utf-8")
    (workspace / "conformance.json").write_text("{}", encoding="utf-8")

    handoff, path, gate, _ = service.promote_run(run, snapshot)

    assert path.is_file()
    assert gate.status == "PASSED"
    assert handoff.source_agent_run_id == run.run_id


def test_v1_conformance_runtime_and_physical_claims_are_ignored(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _, run = _prepare_promotion(artifact_root, workspace, include_write_operation=True)
    service = AdapterPromotionService(ArtifactStore(artifact_root), tmp_path / "output")

    payload = json.loads((workspace / "conformance.json").read_text(encoding="utf-8"))
    payload["schema_version"] = "robot-adapter-conformance/v1"
    for operation in payload["operations"]:
        operation["physical_result_valid"] = False
        operation["safety_valid"] = False
        operation["validation_scopes"] = ["LOCAL_STATIC", "TARGET_RUNTIME", "PHYSICAL"]
    (workspace / "conformance.json").write_text(json.dumps(payload), encoding="utf-8")
    snapshot, _ = service.snapshot(run)

    _, _, gate, _ = service.promote_run(run, snapshot)

    assert gate.status == "PASSED"
    assert "product-owned operation contracts" in gate.checks
    assert "Adapter Agent local-static declarations (advisory)" in gate.checks
    assert "target route existence without outcome execution" in gate.checks


def test_runtime_presence_without_candidate_route_cannot_be_promoted(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _, run = _prepare_promotion(
        artifact_root,
        workspace,
        include_write_operation=True,
        route_observed=False,
    )
    service = AdapterPromotionService(ArtifactStore(artifact_root), tmp_path / "output")
    snapshot, _ = service.snapshot(run)

    with pytest.raises(ValueError, match="route was not observed"):
        service.promote_run(run, snapshot)


def test_unavailable_runtime_probe_cannot_be_promoted_by_agent_claim(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _, run = _prepare_promotion(
        artifact_root, workspace, include_write_operation=True, runtime_ready=False
    )
    service = AdapterPromotionService(ArtifactStore(artifact_root), tmp_path / "output")
    snapshot, _ = service.snapshot(run)

    with pytest.raises(ValueError, match="target runtime evidence is unavailable"):
        service.promote_run(run, snapshot)


def test_failed_handoff_validation_removes_unactivated_release(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    output_root = tmp_path / "output"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _, run = _prepare_promotion(artifact_root, workspace)
    service = AdapterPromotionService(ArtifactStore(artifact_root), output_root)
    snapshot, _ = service.snapshot(run)

    with (
        patch(
            "rolo.stages.adapt.conformance.validate_adapter_handoff",
            side_effect=ValueError("forced handoff failure"),
        ),
        pytest.raises(ValueError, match="forced handoff failure"),
    ):
        service.promote_run(run, snapshot)

    assert not (output_root / "robots/demo_diff/releases/run-test").exists()
    assert not (output_root / "robots/demo_diff/current.json").exists()


def test_failure_after_activation_restores_both_indexes(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    output_root = tmp_path / "output"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _, run = _prepare_promotion(artifact_root, workspace)
    service = AdapterPromotionService(ArtifactStore(artifact_root), output_root)
    snapshot, _ = service.snapshot(run)

    with (
        patch(
            "rolo.stages.adapt.conformance.validate_adapter_handoff",
            side_effect=[None, ValueError("forced post-activation failure")],
        ),
        pytest.raises(ValueError, match="post-activation failure"),
    ):
        service.promote_run(run, snapshot)

    assert not (output_root / "robots/demo_diff/current.json").exists()
    assert not (artifact_root / "adapt/demo_diff/latest.json").exists()
    assert not (output_root / "robots/demo_diff/releases/run-test").exists()

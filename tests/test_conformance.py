import json
from pathlib import Path

import pytest

from rolo.core.artifacts import ArtifactStore
from rolo.core.models import utc_now
from rolo.core.registry import RobotRegistry
from rolo.stages.adapt.conformance import (
    AdapterPromotionService,
    validate_adapter_handoff,
)
from rolo.stages.adapt.discovery import DiscoveryService
from rolo.stages.adapt.models import AdapterAgentResult, AdapterAgentRun


def _prepare_promotion(
    artifact_root: Path, workspace: Path
) -> tuple[str, AdapterAgentRun]:
    (workspace / "pyproject.toml").write_text(
        '[project]\nname = "demo-adapter"\n\n[project.scripts]\ndemo-adapter = "demo:main"\n',
        encoding="utf-8",
    )
    registry = RobotRegistry(Path("tests/fixtures/robots"))
    registry.load()
    report, _ = DiscoveryService(ArtifactStore(artifact_root)).run(
        robot=registry.get("demo_diff"),
        urdf_path=Path("tests/fixtures/profiles/differential_drive.urdf"),
        source_roots=[workspace],
    )
    tools = [tool.model_dump(mode="json") for tool in report.tool_catalog]
    for tool in tools:
        tool["availability"] = "VERIFIED"
    (workspace / "tool_catalog.json").write_text(
        json.dumps(
            {
                "schema_version": "robot-tool-catalog/v1",
                "robot_id": "demo_diff",
                "discovery_id": report.discovery_id,
                "tools": tools,
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
    for tool in report.tool_catalog:
        physical = tool.risk == "R3" or tool.access == "write"
        operations.append(
            {
                "operation": tool.operation,
                "schema_valid": True,
                "errors_valid": True,
                "idempotency_valid": True,
                "cancellation_valid": True,
                "safety_valid": True,
                "physical_result_valid": True if physical else None,
                "evidence": ["artifact://evidence/result.json"] if physical else [],
            }
        )
    (workspace / "conformance.json").write_text(
        json.dumps(
            {
                "schema_version": "robot-adapter-conformance/v1",
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
            "tool_catalog": "tool_catalog.json",
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

    service = AdapterPromotionService(ArtifactStore(artifact_root))
    snapshot, _ = service.snapshot(run)
    handoff, path, _, _ = service.promote_run(run, snapshot)

    assert path.is_file()
    assert handoff.source_discovery_id == discovery_id
    assert validate_adapter_handoff(artifact_root, "demo_diff") == handoff


def test_promotion_rejects_incomplete_conformance_coverage(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _, run = _prepare_promotion(artifact_root, workspace)
    payload = json.loads((workspace / "conformance.json").read_text(encoding="utf-8"))
    payload["operations"].pop()
    (workspace / "conformance.json").write_text(json.dumps(payload), encoding="utf-8")

    service = AdapterPromotionService(ArtifactStore(artifact_root))
    with pytest.raises(ValueError, match="coverage"):
        snapshot, _ = service.snapshot(run)
        service.promote_run(run, snapshot)


def test_promotion_uses_frozen_snapshot_after_workspace_changes(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _, run = _prepare_promotion(artifact_root, workspace)
    service = AdapterPromotionService(ArtifactStore(artifact_root))
    snapshot, _ = service.snapshot(run)

    (workspace / "tool_catalog.json").write_text("{}", encoding="utf-8")
    (workspace / "state_graph.json").write_text("{}", encoding="utf-8")
    (workspace / "conformance.json").write_text("{}", encoding="utf-8")

    handoff, path, gate, _ = service.promote_run(run, snapshot)

    assert path.is_file()
    assert gate.status == "PASSED"
    assert handoff.source_agent_run_id == run.run_id

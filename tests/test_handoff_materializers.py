from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rolo.agent_tools import native_catalog_sha256, reduced_agent_native_catalog
from rolo.agent_tools.rollout import (
    NativeToolRolloutDecision,
    NativeToolRunSummary,
)
from rolo.core.artifacts import ArtifactStore
from rolo.core.hashing import sha256_file
from rolo.stages import handoffs
from rolo.stages.adapt.conformance import _validate_native_tool_bindings
from rolo.stages.adapt.models import (
    AdapterAgentRun,
    AdapterAgentRunStatus,
    AdapterHandoff,
)


def test_result_guards_reject_release_claims_and_empty_evidence() -> None:
    try:
        handoffs.validate_diagnosis_result(
            {"speed": 0.2}, {"release_decision": "RELEASED"}
        )
    except ValueError as exc:
        assert "release" in str(exc)
    else:
        raise AssertionError("diagnosis release claims must fail closed")

    try:
        handoffs.validate_verification_result({"passed": 1}, {"notes": "looks good"})
    except ValueError as exc:
        assert "evidence" in str(exc)
    else:
        raise AssertionError("prose-only evidence must not complete Verify")


def test_result_guards_accept_explicitly_absent_release_authority() -> None:
    handoffs.validate_verification_result(
        {"status": "INCONCLUSIVE"},
        {"artifacts": [], "release_authority": "none"},
    )


def test_result_guards_reject_positive_release_authority() -> None:
    try:
        handoffs.validate_verification_result(
            {"status": "INCONCLUSIVE"},
            {"artifacts": [], "release_authority": "approved"},
        )
    except ValueError as exc:
        assert "release" in str(exc)
    else:
        raise AssertionError("positive release authority must fail closed")


def test_result_guards_do_not_confuse_verified_safety_evidence_with_release() -> None:
    handoffs.validate_verification_result(
        {"status": "PASS", "case_results": [{"case_id": "safe", "status": "PASS"}]},
        {"checks": [{"safe_stop": "VERIFIED", "rollback": "VERIFIED"}]},
    )


def test_diagnosis_materializer_freezes_and_binds_outputs(tmp_path: Path, monkeypatch) -> None:
    adapter = tmp_path / "adapt" / "robot-1" / "runs" / "adapt-1" / "handoff.json"
    adapter.parent.mkdir(parents=True)
    adapter.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        "rolo.stages.adapt.conformance.latest_adapter_handoff_path",
        lambda root, robot_id: adapter,
    )
    monkeypatch.setattr(
        "rolo.stages.adapt.conformance.validate_adapter_handoff", lambda *args: None
    )
    monkeypatch.setattr(handoffs, "validate_diagnosis_handoff", lambda *args, **kwargs: None)

    result = handoffs.commit_diagnosis_handoff(
        tmp_path,
        "robot-1",
        frozen_config={"max_speed": 0.2},
        diagnosis_report={"status": "validated"},
        run_id="diagnose-1",
    )

    assert result.source_adapter_handoff_sha256 == sha256_file(adapter)
    frozen = tmp_path / result.frozen_config_ref.removeprefix("artifact://")
    report = tmp_path / result.diagnosis_report_ref.removeprefix("artifact://")
    assert frozen.read_text(encoding="utf-8").find("max_speed") >= 0
    assert report.is_file()
    assert (tmp_path / "diagnose/robot-1/latest/handoff.json").is_file()


def test_verification_materializer_binds_diagnosis_and_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    diagnosis = tmp_path / "diagnose" / "robot-1" / "latest" / "handoff.json"
    diagnosis.parent.mkdir(parents=True)
    diagnosis.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        handoffs, "validate_diagnosis_handoff", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        handoffs, "validate_verification_handoff", lambda *args, **kwargs: None
    )

    result = handoffs.commit_verification_handoff(
        tmp_path,
        "robot-1",
        regression_report={"passed": 3},
        evidence_package={"artifacts": ["log.txt"]},
        run_id="verify-1",
    )

    assert result.source_diagnosis_handoff_ref == "artifact://diagnose/robot-1/latest/handoff.json"
    assert (tmp_path / result.regression_report_ref.removeprefix("artifact://")).is_file()
    assert (tmp_path / result.evidence_package_ref.removeprefix("artifact://")).is_file()
    assert (tmp_path / "verify/robot-1/latest/handoff.json").is_file()


def test_native_tool_provenance_is_bound_to_adapter_run(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    run_id = "run-native"
    robot_id = "robot-1"
    catalog_sha = native_catalog_sha256(reduced_agent_native_catalog())
    rollout = NativeToolRolloutDecision(
        robot_id=robot_id,
        run_id=run_id,
        mode="shadow",
        selected=True,
        catalog_sha256=catalog_sha,
        tool_count=22,
    )
    summary = NativeToolRunSummary(
        robot_id=robot_id,
        run_id=run_id,
        session_id="native-run-native",
        mode="shadow",
        selected=True,
        catalog_sha256=catalog_sha,
        call_count=0,
        unavailable_count=0,
        timeout_count=0,
        failed_count=0,
        rejected_count=0,
        truncated_count=0,
    )
    rollout_path = store.write_json(
        "adapt/robot-1/runs/run-native/native-tool-rollout.json",
        rollout.model_dump(mode="json"),
    )
    summary_path = store.write_json(
        "adapt/robot-1/runs/run-native/native-tool-summary.json",
        summary.model_dump(mode="json"),
    )
    gate_path = store.write_json(
        "adapt/robot-1/runs/run-native/native-tool-gate.json",
        {
            "schema_version": "rolo-native-tool-canary-gate/v1",
            "robot_id": robot_id,
            "run_id": run_id,
            "mode": "shadow",
            "selected": True,
            "status": "PASS",
            "blocking_reasons": [],
            "influences_release": False,
        },
    )
    run = AdapterAgentRun(
        run_id=run_id,
        robot_id=robot_id,
        source_discovery_id="discovery-1",
        provider="codex",
        status=AdapterAgentRunStatus.SUCCEEDED,
        workspace=str(tmp_path / "workspace"),
        command=["codex", "exec"],
        prompt_ref="artifact://prompt",
        event_log_ref="artifact://events",
        stderr_ref="artifact://stderr",
        final_message_ref="artifact://result",
        native_tool_rollout_ref=f"artifact://{rollout_path.relative_to(tmp_path).as_posix()}",
        native_tool_summary_ref=f"artifact://{summary_path.relative_to(tmp_path).as_posix()}",
        native_tool_gate_ref=f"artifact://{gate_path.relative_to(tmp_path).as_posix()}",
        native_tool_session_id="native-run-native",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        duration_s=0,
    )
    store.write_json(
        "adapt/robot-1/runs/run-native/run.json", run.model_dump(mode="json")
    )
    handoff = AdapterHandoff(
        robot_id=robot_id,
        source_discovery_id="discovery-1",
        source_agent_run_id=run_id,
        discovery_manifest_ref="artifact://manifest",
        discovery_manifest_sha256="0" * 64,
        tool_catalog_ref="artifact://catalog",
        tool_catalog_sha256="0" * 64,
        state_graph_ref="artifact://graph",
        state_graph_sha256="0" * 64,
        conformance_report_ref="artifact://conformance",
        conformance_report_sha256="0" * 64,
        gate_report_ref="artifact://gate",
        gate_report_sha256="0" * 64,
        native_tool_rollout_ref=run.native_tool_rollout_ref,
        native_tool_rollout_sha256=sha256_file(rollout_path),
        native_tool_summary_ref=run.native_tool_summary_ref,
        native_tool_summary_sha256=sha256_file(summary_path),
        native_tool_gate_ref=run.native_tool_gate_ref,
        native_tool_gate_sha256=sha256_file(gate_path),
        native_tool_session_id=run.native_tool_session_id,
        release_ref="output://release/manifest.json",
        release_manifest_sha256="0" * 64,
    )

    _validate_native_tool_bindings(tmp_path, handoff)

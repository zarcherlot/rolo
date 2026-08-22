from __future__ import annotations

from pathlib import Path

from rolo.adapt_observability_read_models import (
    build_adapt_baseline_status,
    build_fleet_slice_stability,
    build_slice_review_packet,
    build_slice_run_detail,
    build_slice_stability_comparison,
)
from rolo.core.artifacts import ArtifactStore
from rolo.stages.adapt.baseline import PINNED_ADAPT_BASELINE
from rolo.stages.adapt.shadow_observation import build_slice_shadow_report
from rolo.stages.adapt.slice_activation import decide_slice_activation
from rolo.stages.adapt.workset import TargetOperationSlice


def _target_slice() -> TargetOperationSlice:
    return TargetOperationSlice(
        robot_id="robot-observe",
        discovery_id="discovery-1",
        registry_sha256="1" * 64,
        slice_sha256="2" * 64,
        primary_operations=["app.target"],
        target_adapter_operations=["app.target"],
    )


def _write_slice_run(artifact_root: Path, run_id: str) -> None:
    target_slice = _target_slice()
    eligible = ["app.agent-native", "app.target"]
    activation = decide_slice_activation(
        target_slice,
        eligible,
        mode="canary",
        run_id=run_id,
        run_selectors=[run_id],
    )
    shadow = build_slice_shadow_report(target_slice, eligible)
    store = ArtifactStore(artifact_root)
    prefix = f"adapt/robot-observe/runs/{run_id}"
    store.write_json(
        f"{prefix}/slice-activation-decision.json",
        activation.model_dump(mode="json"),
    )
    store.write_json(
        f"{prefix}/target-operation-slice-shadow.json",
        shadow.model_dump(mode="json"),
    )
    store.write_json(f"{prefix}/run.json", {"status": "SUCCEEDED"})
    store.write_json(f"{prefix}/gate.json", {"status": "PASSED"})
    store.write_json(
        f"{prefix}/context_metrics.json",
        {
            "prompt_token_estimate": 500,
            "boot_context_token_estimate": 100,
            "boot_context_budget_tokens": 2_000,
        },
    )


def test_product_adapt_baseline_reports_a_release_neutral_match() -> None:
    status = build_adapt_baseline_status()

    assert status.status == "MATCHED"
    assert status.pinned == PINNED_ADAPT_BASELINE
    assert status.current == PINNED_ADAPT_BASELINE
    assert status.changed_fields == []
    assert status.influences_release is False
    assert "runtime health" in status.limitations[0]


def test_product_adapt_baseline_names_drifted_fields(monkeypatch) -> None:
    changed = PINNED_ADAPT_BASELINE.model_copy(
        update={"operation_count": PINNED_ADAPT_BASELINE.operation_count + 1}
    )
    monkeypatch.setattr(
        "rolo.adapt_observability_read_models.capture_adapt_baseline",
        lambda: changed,
    )

    status = build_adapt_baseline_status()

    assert status.status == "DRIFTED"
    assert status.changed_fields == ["operation_count"]


def test_slice_run_detail_joins_activation_shadow_and_metrics(tmp_path: Path) -> None:
    _write_slice_run(tmp_path, "run-1")

    detail = build_slice_run_detail(tmp_path, "robot-observe", "run-1")

    assert detail.run_id == "run-1"
    assert detail.observation.outcome == "ACTIVATED"
    assert detail.activation.selected_by == ["run_id"]
    assert detail.activation.release_authority_operations == [
        "app.agent-native",
        "app.target",
    ]
    assert detail.shadow is not None
    assert detail.shadow.eligible_not_in_shadow == ["app.agent-native"]
    assert detail.shadow.shadow_not_in_eligible == []
    assert detail.influences_release is False


def test_slice_run_detail_supports_legacy_decisions_without_shadow(tmp_path: Path) -> None:
    _write_slice_run(tmp_path, "run-legacy")
    (tmp_path / "adapt/robot-observe/runs/run-legacy/target-operation-slice-shadow.json").unlink()

    detail = build_slice_run_detail(tmp_path, "robot-observe", "run-legacy")

    assert detail.shadow is None
    assert detail.integrity_status == "validated"


def test_slice_windows_are_non_overlapping_and_descriptive(tmp_path: Path) -> None:
    for run_id in ("run-4", "run-3", "run-2", "run-1"):
        _write_slice_run(tmp_path, run_id)

    comparison = build_slice_stability_comparison(
        tmp_path,
        "robot-observe",
        recent_observations=2,
        previous_observations=2,
    )

    assert comparison.status == "COMPARABLE"
    assert (comparison.recent.newest_run_id, comparison.recent.oldest_run_id) == (
        "run-4",
        "run-3",
    )
    assert (comparison.previous.newest_run_id, comparison.previous.oldest_run_id) == (
        "run-2",
        "run-1",
    )
    assert comparison.delta.successful_canary_count == 0
    assert comparison.regression_signals == []
    assert comparison.influences_release is False


def test_fleet_summary_and_review_packet_remain_manual_and_secret_free(
    tmp_path: Path,
) -> None:
    _write_slice_run(tmp_path, "run-1")

    fleet = build_fleet_slice_stability(
        tmp_path,
        ["robot-observe", "robot-empty"],
        min_successful_canary_runs=2,
    )
    packet = build_slice_review_packet(
        tmp_path,
        "robot-observe",
        min_successful_canary_runs=2,
    )

    assert fleet.robot_count == 2
    assert fleet.observed_robot_count == 1
    assert fleet.recommendation_counts == {"INSUFFICIENT_DATA": 2}
    assert packet.status == "INCOMPLETE"
    assert packet.evidence_run_ids == ["run-1"]
    assert packet.evidence_refs == [
        "artifact://adapt/robot-observe/runs/run-1/slice-activation-decision.json"
    ]
    assert packet.contains_secret_payloads is False
    assert packet.checks[-1].status == "HUMAN_REQUIRED"

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from rolo.cli import app
from rolo.core.artifacts import ArtifactStore
from rolo.core.config import get_settings
from rolo.stages.adapt.slice_activation import decide_slice_activation
from rolo.stages.adapt.slice_observability import (
    SliceStabilityRecommendation,
    build_slice_stability_report,
)
from rolo.stages.adapt.workset import TargetOperationSlice


def target_slice(*operations: str) -> TargetOperationSlice:
    return TargetOperationSlice(
        robot_id="robot-observe",
        discovery_id="discovery-1",
        registry_sha256="1" * 64,
        slice_sha256="2" * 64,
        primary_operations=list(operations),
        target_adapter_operations=list(operations),
    )


def write_run(
    artifact_root: Path,
    run_id: str,
    *,
    slice_operations: tuple[str, ...] = ("app.target",),
    eligible_operations: tuple[str, ...] = ("app.agent-native", "app.target"),
    agent_status: str = "SUCCEEDED",
    gate_status: str | None = "PASSED",
    boot_tokens: int = 100,
    boot_budget: int = 2_000,
) -> None:
    decision = decide_slice_activation(
        target_slice(*slice_operations),
        eligible_operations,
        mode="canary",
        run_id=run_id,
        run_selectors=[run_id],
    )
    store = ArtifactStore(artifact_root)
    prefix = f"adapt/robot-observe/runs/{run_id}"
    store.write_json(
        f"{prefix}/slice-activation-decision.json",
        decision.model_dump(mode="json"),
    )
    store.write_json(f"{prefix}/run.json", {"status": agent_status})
    if gate_status is not None:
        store.write_json(f"{prefix}/gate.json", {"status": gate_status})
    store.write_json(
        f"{prefix}/context_metrics.json",
        {
            "prompt_token_estimate": 500,
            "boot_context_token_estimate": boot_tokens,
            "boot_context_budget_tokens": boot_budget,
        },
    )


def test_empty_or_legacy_history_requires_more_data(tmp_path: Path) -> None:
    (tmp_path / "adapt/robot-observe/runs/legacy-run").mkdir(parents=True)

    report = build_slice_stability_report(
        tmp_path,
        "robot-observe",
        min_successful_canary_runs=1,
    )

    assert report.observation_count == 0
    assert report.recommendation == SliceStabilityRecommendation.INSUFFICIENT_DATA
    assert report.recommendation_reasons == ["MINIMUM_SUCCESSFUL_CANARY_RUNS_NOT_MET"]
    assert report.influences_release is False


def test_successful_canary_window_becomes_ready_only_for_manual_review(tmp_path: Path) -> None:
    for suffix in ("01", "02", "03"):
        write_run(tmp_path, f"20260821T0000{suffix}Z-run")

    report = build_slice_stability_report(
        tmp_path,
        "robot-observe",
        min_successful_canary_runs=3,
    )

    assert report.selected_canary_count == 3
    assert report.activated_count == 3
    assert report.successful_canary_count == 3
    assert report.fallback_count == 0
    assert report.average_potential_context_reduction_ratio == 0.5
    assert report.average_effective_context_reduction_ratio == 0.5
    assert report.recommendation == SliceStabilityRecommendation.READY_FOR_REVIEW
    assert report.recommendation_reasons == ["MANUAL_REVIEW_REQUIRED"]
    assert [item.run_id for item in report.observations] == sorted(
        [item.run_id for item in report.observations], reverse=True
    )


def test_fallback_agent_failure_gate_failure_or_budget_violation_holds_canary(
    tmp_path: Path,
) -> None:
    write_run(
        tmp_path,
        "20260821T000001Z-fallback",
        slice_operations=("app.target", "app.outside"),
        eligible_operations=("app.target",),
    )
    write_run(
        tmp_path,
        "20260821T000002Z-failed",
        agent_status="FAILED",
        gate_status="FAILED",
        boot_tokens=2_001,
        boot_budget=2_000,
    )

    report = build_slice_stability_report(
        tmp_path,
        "robot-observe",
        min_successful_canary_runs=1,
    )

    assert report.recommendation == SliceStabilityRecommendation.HOLD
    assert report.fallback_count == 1
    assert report.agent_failed_count == 1
    assert report.gate_failed_count == 1
    assert report.context_budget_exceeded_count == 1
    assert report.recommendation_reasons == [
        "AGENT_RUN_FAILURE_OBSERVED",
        "CANARY_FALLBACK_OBSERVED",
        "CONTEXT_BUDGET_EXCEEDED",
        "INDEPENDENT_GATE_FAILURE_OBSERVED",
    ]


def test_report_window_limits_only_observed_slice_runs(tmp_path: Path) -> None:
    for suffix in ("01", "02", "03"):
        write_run(tmp_path, f"20260821T0000{suffix}Z-run")
    (tmp_path / "adapt/robot-observe/runs/zz-legacy").mkdir(parents=True)

    report = build_slice_stability_report(
        tmp_path,
        "robot-observe",
        max_runs=2,
        min_successful_canary_runs=2,
    )

    assert report.observation_count == 2
    assert report.successful_canary_count == 2
    assert report.recommendation == SliceStabilityRecommendation.READY_FOR_REVIEW


def test_slice_observability_cli_is_read_only_and_reports_thresholds(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_run(tmp_path, "20260821T000001Z-run")
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    monkeypatch.setenv("ROLO_ARTIFACT_DIR", str(tmp_path))
    get_settings.cache_clear()

    result = CliRunner().invoke(
        app,
        [
            "adapt",
            "slice-observability",
            "--robot",
            "robot-observe",
            "--min-successful-canary-runs",
            "1",
        ],
    )

    get_settings.cache_clear()
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["recommendation"] == "READY_FOR_REVIEW"
    assert payload["influences_release"] is False
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")) == before

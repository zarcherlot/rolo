from __future__ import annotations

import json
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.stages.adapt.slice_activation import (
    SliceActivationDecision,
    SliceActivationOutcome,
)
from rolo.stages.artifact_paths import ArtifactLayout


class SliceStabilityRecommendation(str, Enum):
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    HOLD = "HOLD"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"


class SliceRunObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    decision_ref: str
    mode: str
    outcome: SliceActivationOutcome
    selected: bool
    affects_agent_context: bool
    agent_run_status: str | None = None
    gate_status: str | None = None
    authoritative_operation_count: int = Field(ge=0)
    requested_operation_count: int = Field(ge=0)
    effective_operation_count: int = Field(ge=0)
    potential_context_reduction_ratio: float = Field(ge=0.0, le=1.0)
    effective_context_reduction_ratio: float = Field(ge=0.0, le=1.0)
    prompt_token_estimate: int | None = Field(default=None, ge=0)
    boot_context_token_estimate: int | None = Field(default=None, ge=0)
    boot_context_budget_tokens: int | None = Field(default=None, gt=0)
    context_budget_exceeded: bool = False
    alert_codes: list[str] = Field(default_factory=list)
    fallback_reason: str | None = None

    @model_validator(mode="after")
    def require_sorted_alert_codes(self) -> SliceRunObservation:
        if self.alert_codes != sorted(set(self.alert_codes)):
            raise ValueError("Slice observation alert codes must be unique and sorted")
        return self


class SliceStabilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-operation-slice-stability/v1"] = (
        "robot-target-operation-slice-stability/v1"
    )
    robot_id: str
    max_runs: int = Field(gt=0)
    min_successful_canary_runs: int = Field(gt=0)
    observation_count: int = Field(ge=0)
    selected_canary_count: int = Field(ge=0)
    activated_count: int = Field(ge=0)
    fallback_count: int = Field(ge=0)
    successful_canary_count: int = Field(ge=0)
    agent_failed_count: int = Field(ge=0)
    gate_failed_count: int = Field(ge=0)
    context_budget_exceeded_count: int = Field(ge=0)
    average_potential_context_reduction_ratio: float = Field(ge=0.0, le=1.0)
    average_effective_context_reduction_ratio: float = Field(ge=0.0, le=1.0)
    outcome_counts: dict[str, int] = Field(default_factory=dict)
    alert_counts: dict[str, int] = Field(default_factory=dict)
    recommendation: SliceStabilityRecommendation
    recommendation_reasons: list[str] = Field(default_factory=list)
    observations: list[SliceRunObservation] = Field(default_factory=list)
    influences_release: Literal[False] = False

    @model_validator(mode="after")
    def require_consistent_summary(self) -> SliceStabilityReport:
        if self.observation_count != len(self.observations):
            raise ValueError("Slice stability observation count is inconsistent")
        run_ids = [item.run_id for item in self.observations]
        if run_ids != sorted(run_ids, reverse=True) or len(run_ids) != len(set(run_ids)):
            raise ValueError("Slice stability observations must use unique newest-first run IDs")
        if self.recommendation_reasons != sorted(set(self.recommendation_reasons)):
            raise ValueError("Slice stability recommendation reasons must be unique and sorted")
        if list(self.outcome_counts) != sorted(self.outcome_counts):
            raise ValueError("Slice stability outcome counts must be sorted")
        if list(self.alert_counts) != sorted(self.alert_counts):
            raise ValueError("Slice stability alert counts must be sorted")
        return self


def build_slice_stability_report(
    artifact_root: Path,
    robot_id: str,
    *,
    max_runs: int = 50,
    min_successful_canary_runs: int = 10,
) -> SliceStabilityReport:
    if max_runs < 1:
        raise ValueError("max_runs must be positive")
    if min_successful_canary_runs < 1:
        raise ValueError("min_successful_canary_runs must be positive")
    layout = ArtifactLayout(artifact_root)
    runs_root = layout.stage_latest("adapt", robot_id).parent / "runs"
    run_paths = (
        sorted(
            (path for path in runs_root.iterdir() if path.is_dir()),
            key=lambda path: path.name,
            reverse=True,
        )
        if runs_root.is_dir()
        else []
    )
    observations: list[SliceRunObservation] = []
    for run_path in run_paths:
        decision_path = run_path / "slice-activation-decision.json"
        if not decision_path.is_file():
            continue
        decision = SliceActivationDecision.model_validate_json(
            decision_path.read_text(encoding="utf-8")
        )
        if decision.robot_id != robot_id:
            raise ValueError(
                f"Slice activation decision robot mismatch in run {run_path.name}"
            )
        if decision.run_id is not None and decision.run_id != run_path.name:
            raise ValueError(
                f"Slice activation decision run mismatch in run {run_path.name}"
            )
        observations.append(
            _observe_run(layout, run_path, decision_path, decision)
        )
        if len(observations) >= max_runs:
            break
    return _summarize(
        robot_id,
        max_runs,
        min_successful_canary_runs,
        observations,
    )


def _observe_run(
    layout: ArtifactLayout,
    run_path: Path,
    decision_path: Path,
    decision: SliceActivationDecision,
) -> SliceRunObservation:
    run = _read_json(run_path / "run.json")
    gate = _read_json(run_path / "gate.json")
    metrics = _read_json(run_path / "context_metrics.json")
    authoritative_count = len(decision.authoritative_eligible_operations)
    requested_count = len(decision.requested_context_operations)
    effective_count = len(decision.effective_context_operations)
    potential_ratio = _reduction_ratio(authoritative_count, requested_count)
    effective_ratio = _reduction_ratio(authoritative_count, effective_count)
    boot_estimate = _integer(metrics.get("boot_context_token_estimate"))
    boot_budget = _integer(metrics.get("boot_context_budget_tokens"))
    return SliceRunObservation(
        run_id=run_path.name,
        decision_ref=layout.ref(decision_path),
        mode=decision.mode.value,
        outcome=decision.outcome,
        selected=decision.selected,
        affects_agent_context=decision.affects_agent_context,
        agent_run_status=_string(run.get("status")),
        gate_status=_string(gate.get("status")),
        authoritative_operation_count=authoritative_count,
        requested_operation_count=requested_count,
        effective_operation_count=effective_count,
        potential_context_reduction_ratio=potential_ratio,
        effective_context_reduction_ratio=effective_ratio,
        prompt_token_estimate=_integer(metrics.get("prompt_token_estimate")),
        boot_context_token_estimate=boot_estimate,
        boot_context_budget_tokens=boot_budget,
        context_budget_exceeded=bool(
            boot_estimate is not None
            and boot_budget is not None
            and boot_estimate > boot_budget
        ),
        alert_codes=sorted({item.code for item in decision.alerts}),
        fallback_reason=decision.fallback_reason,
    )


def _summarize(
    robot_id: str,
    max_runs: int,
    min_successful_canary_runs: int,
    observations: list[SliceRunObservation],
) -> SliceStabilityReport:
    selected = [item for item in observations if item.selected]
    activated = [
        item for item in observations if item.outcome == SliceActivationOutcome.ACTIVATED
    ]
    fallbacks = [
        item for item in observations if item.outcome == SliceActivationOutcome.FALLBACK
    ]
    successful = [
        item
        for item in activated
        if item.agent_run_status == "SUCCEEDED" and item.gate_status == "PASSED"
    ]
    gate_failed = [item for item in selected if item.gate_status == "FAILED"]
    agent_failed = [
        item
        for item in selected
        if item.agent_run_status in {"FAILED", "TIMED_OUT"}
    ]
    budget_exceeded = [item for item in selected if item.context_budget_exceeded]
    outcome_counts = Counter(item.outcome.value for item in observations)
    alert_counts = Counter(code for item in observations for code in item.alert_codes)
    reasons: list[str] = []
    if fallbacks:
        reasons.append("CANARY_FALLBACK_OBSERVED")
    if gate_failed:
        reasons.append("INDEPENDENT_GATE_FAILURE_OBSERVED")
    if agent_failed:
        reasons.append("AGENT_RUN_FAILURE_OBSERVED")
    if budget_exceeded:
        reasons.append("CONTEXT_BUDGET_EXCEEDED")
    if reasons:
        recommendation = SliceStabilityRecommendation.HOLD
    elif len(successful) < min_successful_canary_runs:
        recommendation = SliceStabilityRecommendation.INSUFFICIENT_DATA
        reasons.append("MINIMUM_SUCCESSFUL_CANARY_RUNS_NOT_MET")
    else:
        recommendation = SliceStabilityRecommendation.READY_FOR_REVIEW
        reasons.append("MANUAL_REVIEW_REQUIRED")
    return SliceStabilityReport(
        robot_id=robot_id,
        max_runs=max_runs,
        min_successful_canary_runs=min_successful_canary_runs,
        observation_count=len(observations),
        selected_canary_count=len(selected),
        activated_count=len(activated),
        fallback_count=len(fallbacks),
        successful_canary_count=len(successful),
        agent_failed_count=len(agent_failed),
        gate_failed_count=len(gate_failed),
        context_budget_exceeded_count=len(budget_exceeded),
        average_potential_context_reduction_ratio=_average(
            [item.potential_context_reduction_ratio for item in observations]
        ),
        average_effective_context_reduction_ratio=_average(
            [item.effective_context_reduction_ratio for item in observations]
        ),
        outcome_counts=dict(sorted(outcome_counts.items())),
        alert_counts=dict(sorted(alert_counts.items())),
        recommendation=recommendation,
        recommendation_reasons=sorted(reasons),
        observations=observations,
        influences_release=False,
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _reduction_ratio(authoritative_count: int, focused_count: int) -> float:
    if authoritative_count == 0:
        return 0.0
    return round(max(authoritative_count - focused_count, 0) / authoritative_count, 6)


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None

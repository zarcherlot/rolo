from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.stages.adapt.baseline import (
    PINNED_ADAPT_BASELINE,
    AdaptBaselineSnapshot,
    capture_adapt_baseline,
)
from rolo.stages.adapt.shadow_observation import TargetOperationSliceShadowReport
from rolo.stages.adapt.slice_activation import SliceActivationDecision
from rolo.stages.adapt.slice_observability import (
    SliceRunObservation,
    SliceStabilityRecommendation,
    build_slice_run_observation,
    build_slice_stability_report,
)
from rolo.stages.artifact_paths import ArtifactLayout


class AdaptBaselineStatus(BaseModel):
    """Product-level Registry and contract fingerprint comparison."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapt-baseline-status/v1"] = (
        "rolo-adapt-baseline-status/v1"
    )
    status: Literal["MATCHED", "DRIFTED"]
    pinned: AdaptBaselineSnapshot
    current: AdaptBaselineSnapshot
    changed_fields: list[str] = Field(default_factory=list)
    source_kind: Literal["protected_product_baseline"] = "protected_product_baseline"
    influences_release: Literal[False] = False
    limitations: list[str] = Field(
        default_factory=lambda: [
            "This fingerprint covers the in-process product Registry, governance ledger, "
            "and contract catalog; it does not report robot runtime health."
        ]
    )

    @model_validator(mode="after")
    def require_consistent_status(self) -> AdaptBaselineStatus:
        expected = sorted(
            name
            for name in AdaptBaselineSnapshot.model_fields
            if getattr(self.current, name) != getattr(self.pinned, name)
        )
        if self.changed_fields != expected:
            raise ValueError("Adapt baseline changed fields are inconsistent")
        if self.status != ("DRIFTED" if expected else "MATCHED"):
            raise ValueError("Adapt baseline status is inconsistent")
        return self


class SliceRunDetail(BaseModel):
    """Bounded explanation of one immutable Slice activation decision."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapt-slice-run-detail/v1"] = (
        "rolo-adapt-slice-run-detail/v1"
    )
    robot_id: str
    run_id: str
    observation: SliceRunObservation
    activation: SliceActivationDecision
    shadow: TargetOperationSliceShadowReport | None = None
    source_kind: Literal["immutable_adapt_run_artifacts"] = (
        "immutable_adapt_run_artifacts"
    )
    integrity_status: Literal["validated"] = "validated"
    influences_release: Literal[False] = False
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Slice activation can change Adapter Agent context only; release authority "
            "continues to use the authoritative eligible operation set."
        ]
    )

    @model_validator(mode="after")
    def require_consistent_identity_and_authority(self) -> SliceRunDetail:
        if self.observation.run_id != self.run_id:
            raise ValueError("Slice observation run identity is inconsistent")
        if self.activation.robot_id != self.robot_id:
            raise ValueError("Slice activation robot identity is inconsistent")
        if self.activation.run_id is not None and self.activation.run_id != self.run_id:
            raise ValueError("Slice activation run identity is inconsistent")
        if self.shadow is not None:
            if self.shadow.robot_id != self.robot_id:
                raise ValueError("Slice shadow robot identity is inconsistent")
            if self.shadow.slice_sha256 != self.activation.slice_sha256:
                raise ValueError("Slice shadow digest is inconsistent")
        return self


class SliceObservationWindow(BaseModel):
    """Bounded metrics for one non-overlapping Slice decision window."""

    model_config = ConfigDict(extra="forbid")

    label: Literal["RECENT", "PREVIOUS"]
    requested_observations: int = Field(gt=0)
    observation_count: int = Field(ge=0)
    newest_run_id: str | None = None
    oldest_run_id: str | None = None
    successful_canary_count: int = Field(ge=0)
    fallback_count: int = Field(ge=0)
    agent_failed_count: int = Field(ge=0)
    gate_failed_count: int = Field(ge=0)
    context_budget_exceeded_count: int = Field(ge=0)
    average_effective_context_reduction_ratio: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def require_consistent_bounds(self) -> SliceObservationWindow:
        if self.observation_count > self.requested_observations:
            raise ValueError("Slice observation window exceeds its requested bound")
        empty_identity = self.newest_run_id is None and self.oldest_run_id is None
        if empty_identity != (self.observation_count == 0):
            raise ValueError("Slice observation window identity is inconsistent")
        return self


class SliceStabilityDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    successful_canary_count: int
    fallback_count: int
    agent_failed_count: int
    gate_failed_count: int
    context_budget_exceeded_count: int
    average_effective_context_reduction_ratio: float = Field(ge=-1.0, le=1.0)


class SliceStabilityComparison(BaseModel):
    """Descriptive comparison of two non-overlapping immutable Run windows."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapt-slice-stability-comparison/v1"] = (
        "rolo-adapt-slice-stability-comparison/v1"
    )
    robot_id: str
    status: Literal["NO_PREVIOUS_WINDOW", "PARTIAL", "COMPARABLE"]
    recent: SliceObservationWindow
    previous: SliceObservationWindow
    delta: SliceStabilityDelta
    regression_signals: list[str] = Field(default_factory=list)
    source_kind: Literal["immutable_adapt_run_artifacts"] = (
        "immutable_adapt_run_artifacts"
    )
    influences_release: Literal[False] = False
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Window deltas are descriptive observations, not causal diagnoses or "
            "rollout authority.",
            "Legacy Runs without a Slice activation decision are excluded from both windows.",
        ]
    )

    @model_validator(mode="after")
    def require_consistent_comparison(self) -> SliceStabilityComparison:
        if self.recent.label != "RECENT" or self.previous.label != "PREVIOUS":
            raise ValueError("Slice comparison window labels are inconsistent")
        if self.regression_signals != sorted(set(self.regression_signals)):
            raise ValueError("Slice comparison regression signals must be unique and sorted")
        expected = (
            "NO_PREVIOUS_WINDOW"
            if self.previous.observation_count == 0
            else "COMPARABLE"
            if self.recent.observation_count == self.recent.requested_observations
            and self.previous.observation_count == self.previous.requested_observations
            else "PARTIAL"
        )
        if self.status != expected:
            raise ValueError("Slice comparison status is inconsistent")
        return self


class FleetSliceRobotSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    robot_id: str
    recommendation: SliceStabilityRecommendation
    observation_count: int = Field(ge=0)
    successful_canary_count: int = Field(ge=0)
    fallback_count: int = Field(ge=0)
    diagnostic_count: int = Field(ge=0)


class FleetSliceStability(BaseModel):
    """Fleet-level Canary readiness without changing any robot configuration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapt-fleet-slice-stability/v1"] = (
        "rolo-adapt-fleet-slice-stability/v1"
    )
    max_runs_per_robot: int = Field(gt=0)
    min_successful_canary_runs: int = Field(gt=0)
    robot_count: int = Field(ge=0)
    observed_robot_count: int = Field(ge=0)
    recommendation_counts: dict[str, int] = Field(default_factory=dict)
    items: list[FleetSliceRobotSummary] = Field(default_factory=list)
    source_kind: Literal["immutable_adapt_run_artifacts"] = (
        "immutable_adapt_run_artifacts"
    )
    influences_release: Literal[False] = False
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Fleet readiness is a read-only aggregation; each robot still requires "
            "an independent human review."
        ]
    )

    @model_validator(mode="after")
    def require_consistent_fleet_summary(self) -> FleetSliceStability:
        if self.robot_count != len(self.items):
            raise ValueError("Fleet Slice robot count is inconsistent")
        if self.items != sorted(self.items, key=lambda item: item.robot_id):
            raise ValueError("Fleet Slice items must be sorted by robot ID")
        if len({item.robot_id for item in self.items}) != len(self.items):
            raise ValueError("Fleet Slice robot IDs must be unique")
        if self.observed_robot_count != sum(item.observation_count > 0 for item in self.items):
            raise ValueError("Fleet Slice observed robot count is inconsistent")
        expected = dict(sorted(Counter(item.recommendation.value for item in self.items).items()))
        if self.recommendation_counts != expected:
            raise ValueError("Fleet Slice recommendation counts are inconsistent")
        return self


class SliceReviewCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    label: str
    status: Literal["PASS", "PENDING", "BLOCKING", "HUMAN_REQUIRED"]
    summary: str


class SliceReviewPacket(BaseModel):
    """Secret-free summary for a human Canary-scope review."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-adapt-slice-review-packet/v1"] = (
        "rolo-adapt-slice-review-packet/v1"
    )
    robot_id: str
    status: Literal["BLOCKED", "INCOMPLETE", "READY_FOR_HUMAN_REVIEW"]
    baseline_status: Literal["MATCHED", "DRIFTED"]
    stability_recommendation: SliceStabilityRecommendation
    checks: list[SliceReviewCheck]
    evidence_run_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    contains_secret_payloads: Literal[False] = False
    influences_release: Literal[False] = False
    limitations: list[str] = Field(
        default_factory=lambda: [
            "This packet is a bounded review summary, not an authorization, "
            "configuration change, or physical outcome verification.",
            "Artifact bodies, logs, policy inputs, credentials, and SECRET-classified "
            "payloads are not included.",
        ]
    )

    @model_validator(mode="after")
    def require_safe_consistent_packet(self) -> SliceReviewPacket:
        check_ids = [item.check_id for item in self.checks]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("Slice review check IDs must be unique")
        if len(self.evidence_run_ids) != len(set(self.evidence_run_ids)):
            raise ValueError("Slice review Run IDs must be unique")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("Slice review evidence refs must be unique")
        if len(self.evidence_run_ids) != len(self.evidence_refs):
            raise ValueError("Slice review evidence identity is inconsistent")
        expected = (
            "BLOCKED"
            if self.baseline_status == "DRIFTED"
            or self.stability_recommendation == SliceStabilityRecommendation.HOLD
            else "READY_FOR_HUMAN_REVIEW"
            if self.stability_recommendation
            == SliceStabilityRecommendation.READY_FOR_REVIEW
            else "INCOMPLETE"
        )
        if self.status != expected:
            raise ValueError("Slice review packet status is inconsistent")
        return self


def build_adapt_baseline_status() -> AdaptBaselineStatus:
    current = capture_adapt_baseline()
    changed_fields = sorted(
        name
        for name in AdaptBaselineSnapshot.model_fields
        if getattr(current, name) != getattr(PINNED_ADAPT_BASELINE, name)
    )
    return AdaptBaselineStatus(
        status="DRIFTED" if changed_fields else "MATCHED",
        pinned=PINNED_ADAPT_BASELINE,
        current=current,
        changed_fields=changed_fields,
    )


def build_slice_run_detail(
    artifact_root: Path,
    robot_id: str,
    run_id: str,
) -> SliceRunDetail:
    layout = ArtifactLayout(artifact_root)
    run_path = layout.stage_run("adapt", robot_id, run_id)
    decision_path = run_path / "slice-activation-decision.json"
    if not decision_path.is_file():
        raise FileNotFoundError(decision_path)
    activation = SliceActivationDecision.model_validate_json(
        decision_path.read_text(encoding="utf-8")
    )
    observation = build_slice_run_observation(artifact_root, robot_id, run_id)
    shadow_path = run_path / "target-operation-slice-shadow.json"
    shadow = (
        TargetOperationSliceShadowReport.model_validate_json(
            shadow_path.read_text(encoding="utf-8")
        )
        if shadow_path.is_file()
        else None
    )
    return SliceRunDetail(
        robot_id=robot_id,
        run_id=run_id,
        observation=observation,
        activation=activation,
        shadow=shadow,
    )


def _window_summary(
    label: Literal["RECENT", "PREVIOUS"],
    requested: int,
    observations: list[SliceRunObservation],
) -> SliceObservationWindow:
    activated = [item for item in observations if item.outcome.value == "ACTIVATED"]
    successful = [
        item
        for item in activated
        if item.agent_run_status == "SUCCEEDED" and item.gate_status == "PASSED"
    ]
    selected = [item for item in observations if item.selected]
    values = [item.effective_context_reduction_ratio for item in observations]
    return SliceObservationWindow(
        label=label,
        requested_observations=requested,
        observation_count=len(observations),
        newest_run_id=observations[0].run_id if observations else None,
        oldest_run_id=observations[-1].run_id if observations else None,
        successful_canary_count=len(successful),
        fallback_count=sum(item.outcome.value == "FALLBACK" for item in observations),
        agent_failed_count=sum(
            item.agent_run_status in {"FAILED", "TIMED_OUT"} for item in selected
        ),
        gate_failed_count=sum(item.gate_status == "FAILED" for item in selected),
        context_budget_exceeded_count=sum(
            item.context_budget_exceeded for item in selected
        ),
        average_effective_context_reduction_ratio=(
            round(sum(values) / len(values), 6) if values else 0.0
        ),
    )


def build_slice_stability_comparison(
    artifact_root: Path,
    robot_id: str,
    *,
    recent_observations: int = 10,
    previous_observations: int = 10,
) -> SliceStabilityComparison:
    report = build_slice_stability_report(
        artifact_root,
        robot_id,
        max_runs=recent_observations + previous_observations,
    )
    recent = _window_summary(
        "RECENT", recent_observations, report.observations[:recent_observations]
    )
    previous = _window_summary(
        "PREVIOUS",
        previous_observations,
        report.observations[
            recent_observations : recent_observations + previous_observations
        ],
    )
    delta = SliceStabilityDelta(
        successful_canary_count=(
            recent.successful_canary_count - previous.successful_canary_count
        ),
        fallback_count=recent.fallback_count - previous.fallback_count,
        agent_failed_count=recent.agent_failed_count - previous.agent_failed_count,
        gate_failed_count=recent.gate_failed_count - previous.gate_failed_count,
        context_budget_exceeded_count=(
            recent.context_budget_exceeded_count
            - previous.context_budget_exceeded_count
        ),
        average_effective_context_reduction_ratio=round(
            recent.average_effective_context_reduction_ratio
            - previous.average_effective_context_reduction_ratio,
            6,
        ),
    )
    signals: list[str] = []
    if previous.observation_count:
        for field, signal in (
            ("fallback_count", "FALLBACK_COUNT_INCREASED"),
            ("agent_failed_count", "AGENT_FAILURE_COUNT_INCREASED"),
            ("gate_failed_count", "GATE_FAILURE_COUNT_INCREASED"),
            ("context_budget_exceeded_count", "CONTEXT_BUDGET_EXCEEDANCE_INCREASED"),
        ):
            if getattr(delta, field) > 0:
                signals.append(signal)
        if delta.average_effective_context_reduction_ratio < 0:
            signals.append("EFFECTIVE_CONTEXT_REDUCTION_DECREASED")
    status = (
        "NO_PREVIOUS_WINDOW"
        if previous.observation_count == 0
        else "COMPARABLE"
        if recent.observation_count == recent_observations
        and previous.observation_count == previous_observations
        else "PARTIAL"
    )
    return SliceStabilityComparison(
        robot_id=robot_id,
        status=status,
        recent=recent,
        previous=previous,
        delta=delta,
        regression_signals=sorted(signals),
    )


def build_fleet_slice_stability(
    artifact_root: Path,
    robot_ids: list[str],
    *,
    max_runs_per_robot: int = 20,
    min_successful_canary_runs: int = 10,
) -> FleetSliceStability:
    items: list[FleetSliceRobotSummary] = []
    for robot_id in sorted(set(robot_ids)):
        report = build_slice_stability_report(
            artifact_root,
            robot_id,
            max_runs=max_runs_per_robot,
            min_successful_canary_runs=min_successful_canary_runs,
        )
        items.append(
            FleetSliceRobotSummary(
                robot_id=robot_id,
                recommendation=report.recommendation,
                observation_count=report.observation_count,
                successful_canary_count=report.successful_canary_count,
                fallback_count=report.fallback_count,
                diagnostic_count=(
                    report.agent_failed_count
                    + report.gate_failed_count
                    + report.context_budget_exceeded_count
                ),
            )
        )
    return FleetSliceStability(
        max_runs_per_robot=max_runs_per_robot,
        min_successful_canary_runs=min_successful_canary_runs,
        robot_count=len(items),
        observed_robot_count=sum(item.observation_count > 0 for item in items),
        recommendation_counts=dict(
            sorted(Counter(item.recommendation.value for item in items).items())
        ),
        items=items,
    )


def build_slice_review_packet(
    artifact_root: Path,
    robot_id: str,
    *,
    max_runs: int = 50,
    min_successful_canary_runs: int = 10,
    max_evidence_runs: int = 20,
) -> SliceReviewPacket:
    baseline = build_adapt_baseline_status()
    report = build_slice_stability_report(
        artifact_root,
        robot_id,
        max_runs=max_runs,
        min_successful_canary_runs=min_successful_canary_runs,
    )
    no_data = report.observation_count == 0
    checks = [
        SliceReviewCheck(
            check_id="protected_product_baseline",
            label="Protected product baseline",
            status="PASS" if baseline.status == "MATCHED" else "BLOCKING",
            summary=(
                "Registry, governance ledger, and Contract Catalog match the pinned baseline."
                if baseline.status == "MATCHED"
                else f"Protected baseline drift: {', '.join(baseline.changed_fields)}."
            ),
        ),
        SliceReviewCheck(
            check_id="successful_canary_sample",
            label="Successful Canary sample",
            status=(
                "PASS"
                if report.successful_canary_count >= min_successful_canary_runs
                else "PENDING"
            ),
            summary=(
                f"{report.successful_canary_count} of {min_successful_canary_runs} "
                "required successful Canary Runs observed."
            ),
        ),
        SliceReviewCheck(
            check_id="automatic_fallbacks",
            label="Automatic context fallbacks",
            status="PENDING" if no_data else "PASS" if report.fallback_count == 0 else "BLOCKING",
            summary=f"{report.fallback_count} fallback Runs observed in the bounded window.",
        ),
        SliceReviewCheck(
            check_id="independent_failures",
            label="Agent and independent gate failures",
            status=(
                "PENDING"
                if no_data
                else "PASS"
                if report.agent_failed_count + report.gate_failed_count == 0
                else "BLOCKING"
            ),
            summary=(
                f"{report.agent_failed_count} Agent failures and "
                f"{report.gate_failed_count} gate failures observed."
            ),
        ),
        SliceReviewCheck(
            check_id="context_budget",
            label="Context budget",
            status=(
                "PENDING"
                if no_data
                else "PASS"
                if report.context_budget_exceeded_count == 0
                else "BLOCKING"
            ),
            summary=f"{report.context_budget_exceeded_count} budget exceedances observed.",
        ),
        SliceReviewCheck(
            check_id="human_rollout_decision",
            label="Human rollout decision",
            status="HUMAN_REQUIRED",
            summary="A qualified reviewer must inspect evidence before changing Canary scope.",
        ),
    ]
    evidence = report.observations[:max_evidence_runs]
    status = (
        "BLOCKED"
        if baseline.status == "DRIFTED"
        or report.recommendation == SliceStabilityRecommendation.HOLD
        else "READY_FOR_HUMAN_REVIEW"
        if report.recommendation == SliceStabilityRecommendation.READY_FOR_REVIEW
        else "INCOMPLETE"
    )
    return SliceReviewPacket(
        robot_id=robot_id,
        status=status,
        baseline_status=baseline.status,
        stability_recommendation=report.recommendation,
        checks=checks,
        evidence_run_ids=[item.run_id for item in evidence],
        evidence_refs=[item.decision_ref for item in evidence],
    )

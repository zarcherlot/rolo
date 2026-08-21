from __future__ import annotations

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
    build_slice_run_observation,
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

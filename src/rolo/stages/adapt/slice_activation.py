from __future__ import annotations

from collections.abc import Iterable, Sequence
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolo.stages.adapt.workset import TargetOperationSlice


class SliceActivationMode(str, Enum):
    SHADOW = "SHADOW"
    CANARY = "CANARY"


class SliceActivationOutcome(str, Enum):
    SHADOW_ONLY = "SHADOW_ONLY"
    NOT_SELECTED = "NOT_SELECTED"
    ACTIVATED = "ACTIVATED"
    FALLBACK = "FALLBACK"


class SliceActivationSeverity(str, Enum):
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


class SliceActivationAlert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    severity: SliceActivationSeverity
    message: str = Field(min_length=1)
    operations: list[str] = Field(default_factory=list)


class SliceActivationDecision(BaseModel):
    """Canary decision for Agent context only; release authority never changes here."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-target-operation-slice-activation/v1"] = (
        "robot-target-operation-slice-activation/v1"
    )
    robot_id: str
    run_id: str | None = None
    slice_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mode: SliceActivationMode
    selected: bool
    selected_by: list[str] = Field(default_factory=list)
    outcome: SliceActivationOutcome
    authoritative_eligible_operations: list[str] = Field(default_factory=list)
    requested_context_operations: list[str] = Field(default_factory=list)
    effective_context_operations: list[str] = Field(default_factory=list)
    release_authority_operations: list[str] = Field(default_factory=list)
    max_context_operations: int = Field(gt=0)
    alerts: list[SliceActivationAlert] = Field(default_factory=list)
    fallback_reason: str | None = None
    affects_agent_context: bool = False
    influences_release: Literal[False] = False

    @model_validator(mode="after")
    def validate_authority_and_outcome(self) -> SliceActivationDecision:
        operation_fields = (
            "authoritative_eligible_operations",
            "requested_context_operations",
            "effective_context_operations",
            "release_authority_operations",
        )
        for name in operation_fields:
            values = getattr(self, name)
            if values != sorted(set(values)):
                raise ValueError(f"{name} must contain unique sorted operations")
        if self.release_authority_operations != self.authoritative_eligible_operations:
            raise ValueError("Slice activation cannot change release authority")
        alert_codes = [item.code for item in self.alerts]
        if alert_codes != sorted(alert_codes) or len(alert_codes) != len(set(alert_codes)):
            raise ValueError("Slice activation alerts must use unique sorted codes")
        if self.selected_by != sorted(set(self.selected_by)):
            raise ValueError("selected_by must contain unique sorted selectors")
        if self.outcome == SliceActivationOutcome.ACTIVATED:
            if not self.selected or not self.affects_agent_context:
                raise ValueError("activated Slice must be selected and affect Agent context")
            if self.effective_context_operations != self.requested_context_operations:
                raise ValueError("activated Slice must use the requested context operations")
            if any(item.severity == SliceActivationSeverity.BLOCKING for item in self.alerts):
                raise ValueError("activated Slice cannot contain blocking alerts")
        else:
            if self.affects_agent_context:
                raise ValueError("non-activated Slice cannot affect Agent context")
            if self.effective_context_operations != self.authoritative_eligible_operations:
                raise ValueError("non-activated Slice must fall back to current eligibility")
        if self.outcome == SliceActivationOutcome.FALLBACK and not self.fallback_reason:
            raise ValueError("fallback outcome requires a reason")
        return self


def decide_slice_activation(
    target_slice: TargetOperationSlice,
    authoritative_eligible_operations: Sequence[str],
    *,
    mode: SliceActivationMode | str = SliceActivationMode.SHADOW,
    run_id: str | None = None,
    robot_selectors: Iterable[str] = (),
    run_selectors: Iterable[str] = (),
    max_context_operations: int = 20,
) -> SliceActivationDecision:
    if max_context_operations < 1:
        raise ValueError("Slice context operation budget must be positive")
    mode = SliceActivationMode(mode.upper() if isinstance(mode, str) else mode)
    eligible = sorted(set(authoritative_eligible_operations))
    requested = sorted(set(target_slice.target_adapter_operations))
    selected_by: list[str] = []
    if target_slice.robot_id in _selectors(robot_selectors):
        selected_by.append("robot_id")
    if run_id is not None and run_id in _selectors(run_selectors):
        selected_by.append("run_id")
    selected = mode == SliceActivationMode.CANARY and bool(selected_by)

    alerts: list[SliceActivationAlert] = []
    eligible_not_requested = sorted(set(eligible) - set(requested))
    if eligible_not_requested:
        alerts.append(
            SliceActivationAlert(
                code="ELIGIBLE_NOT_IN_SLICE",
                severity=SliceActivationSeverity.WARNING,
                message=(
                    "Slice narrows the Agent coding focus; current eligibility remains the "
                    "Bundle and release authority"
                ),
                operations=eligible_not_requested,
            )
        )
    requested_not_eligible = sorted(set(requested) - set(eligible))
    if requested_not_eligible:
        alerts.append(
            SliceActivationAlert(
                code="SLICE_OUTSIDE_ELIGIBILITY",
                severity=SliceActivationSeverity.BLOCKING,
                message="Slice cannot expand beyond authoritative eligibility",
                operations=requested_not_eligible,
            )
        )
    if eligible and not requested:
        alerts.append(
            SliceActivationAlert(
                code="SLICE_EMPTY",
                severity=SliceActivationSeverity.BLOCKING,
                message="Slice cannot replace a non-empty eligible context with an empty focus",
            )
        )
    if len(requested) > max_context_operations:
        alerts.append(
            SliceActivationAlert(
                code="SLICE_OPERATION_BUDGET_EXCEEDED",
                severity=SliceActivationSeverity.BLOCKING,
                message="Slice exceeds the configured Agent context operation budget",
                operations=requested[max_context_operations:],
            )
        )
    alerts.sort(key=lambda item: item.code)
    blocking = [item.code for item in alerts if item.severity == SliceActivationSeverity.BLOCKING]

    if mode == SliceActivationMode.SHADOW:
        outcome = SliceActivationOutcome.SHADOW_ONLY
        fallback_reason = None
    elif not selected:
        outcome = SliceActivationOutcome.NOT_SELECTED
        fallback_reason = None
    elif blocking:
        outcome = SliceActivationOutcome.FALLBACK
        fallback_reason = ",".join(blocking)
    else:
        outcome = SliceActivationOutcome.ACTIVATED
        fallback_reason = None
    activated = outcome == SliceActivationOutcome.ACTIVATED
    return SliceActivationDecision(
        robot_id=target_slice.robot_id,
        run_id=run_id,
        slice_sha256=target_slice.slice_sha256,
        mode=mode,
        selected=selected,
        selected_by=sorted(selected_by),
        outcome=outcome,
        authoritative_eligible_operations=eligible,
        requested_context_operations=requested,
        effective_context_operations=requested if activated else eligible,
        release_authority_operations=eligible,
        max_context_operations=max_context_operations,
        alerts=alerts,
        fallback_reason=fallback_reason,
        affects_agent_context=activated,
        influences_release=False,
    )


def parse_slice_selectors(value: str | Iterable[str]) -> tuple[str, ...]:
    if isinstance(value, str):
        values = value.split(",")
    else:
        values = value
    return tuple(sorted({item.strip() for item in values if item.strip()}))


def _selectors(values: Iterable[str]) -> set[str]:
    return set(parse_slice_selectors(values))

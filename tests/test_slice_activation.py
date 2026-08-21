from __future__ import annotations

import pytest
from pydantic import ValidationError

from rolo.stages.adapt.slice_activation import (
    SliceActivationDecision,
    SliceActivationMode,
    SliceActivationOutcome,
    decide_slice_activation,
    parse_slice_selectors,
)
from rolo.stages.adapt.workset import TargetOperationSlice


def target_slice(*operations: str) -> TargetOperationSlice:
    return TargetOperationSlice(
        robot_id="robot-canary",
        discovery_id="discovery-1",
        registry_sha256="1" * 64,
        slice_sha256="2" * 64,
        primary_operations=list(operations),
        target_adapter_operations=list(operations),
    )


def test_default_mode_is_shadow_only_and_preserves_current_eligibility() -> None:
    decision = decide_slice_activation(
        target_slice("app.target"),
        ["app.agent-native", "app.target"],
    )

    assert decision.mode == SliceActivationMode.SHADOW
    assert decision.outcome == SliceActivationOutcome.SHADOW_ONLY
    assert decision.effective_context_operations == ["app.agent-native", "app.target"]
    assert decision.release_authority_operations == ["app.agent-native", "app.target"]
    assert decision.affects_agent_context is False
    assert decision.influences_release is False
    assert [item.code for item in decision.alerts] == ["ELIGIBLE_NOT_IN_SLICE"]


def test_canary_requires_an_exact_robot_or_run_selector() -> None:
    not_selected = decide_slice_activation(
        target_slice("app.target"),
        ["app.target"],
        mode="canary",
        robot_selectors=["different-robot"],
        run_selectors=["different-run"],
        run_id="run-1",
    )
    selected_by_robot = decide_slice_activation(
        target_slice("app.target"),
        ["app.target"],
        mode="canary",
        robot_selectors=["robot-canary"],
        run_id="run-1",
    )
    selected_by_run = decide_slice_activation(
        target_slice("app.target"),
        ["app.target"],
        mode="canary",
        run_selectors=["run-1"],
        run_id="run-1",
    )

    assert not_selected.outcome == SliceActivationOutcome.NOT_SELECTED
    assert selected_by_robot.outcome == SliceActivationOutcome.ACTIVATED
    assert selected_by_robot.selected_by == ["robot_id"]
    assert selected_by_run.outcome == SliceActivationOutcome.ACTIVATED
    assert selected_by_run.selected_by == ["run_id"]


def test_canary_can_narrow_agent_focus_without_changing_release_authority() -> None:
    decision = decide_slice_activation(
        target_slice("app.target"),
        ["app.agent-native", "app.target"],
        mode="canary",
        robot_selectors=["robot-canary"],
    )

    assert decision.outcome == SliceActivationOutcome.ACTIVATED
    assert decision.effective_context_operations == ["app.target"]
    assert decision.release_authority_operations == ["app.agent-native", "app.target"]
    assert decision.affects_agent_context is True


@pytest.mark.parametrize(
    ("slice_operations", "eligible", "budget", "expected_code"),
    [
        (("app.target", "app.outside"), ["app.target"], 20, "SLICE_OUTSIDE_ELIGIBILITY"),
        ((), ["app.target"], 20, "SLICE_EMPTY"),
        (("app.one", "app.two"), ["app.one", "app.two"], 1, "SLICE_OPERATION_BUDGET_EXCEEDED"),
    ],
)
def test_blocking_alerts_automatically_fall_back_to_current_eligibility(
    slice_operations: tuple[str, ...],
    eligible: list[str],
    budget: int,
    expected_code: str,
) -> None:
    decision = decide_slice_activation(
        target_slice(*slice_operations),
        eligible,
        mode="canary",
        robot_selectors=["robot-canary"],
        max_context_operations=budget,
    )

    assert decision.outcome == SliceActivationOutcome.FALLBACK
    assert decision.effective_context_operations == sorted(eligible)
    assert decision.affects_agent_context is False
    assert expected_code in (decision.fallback_reason or "")


def test_selector_parser_is_exact_trimmed_and_deterministic() -> None:
    assert parse_slice_selectors(" robot-b,robot-a,robot-b, ") == (
        "robot-a",
        "robot-b",
    )


def test_decision_model_rejects_release_authority_changes() -> None:
    valid = decide_slice_activation(target_slice("app.target"), ["app.target"])
    payload = valid.model_dump(mode="json")
    payload["release_authority_operations"] = []

    with pytest.raises(ValidationError, match="cannot change release authority"):
        SliceActivationDecision.model_validate(payload)

import pytest

from rolo.agent_tools import (
    ToolPlan,
    ToolPlanStep,
    build_tool_plan,
    native_catalog_sha256,
    reduced_agent_native_catalog,
    validate_tool_plan,
)


def test_current_agent_can_build_and_validate_readonly_plan() -> None:
    catalog = reduced_agent_native_catalog()
    surface_digest = native_catalog_sha256(catalog)
    step = ToolPlanStep(
        tool_id="native.middleware.graph.inspect",
        arguments={"mode": "nodes"},
        expected_observation="当前 ROS 节点列表",
    )
    plan = build_tool_plan(
        goal="确认机器人 ROS graph 是否在线",
        target_id="raspberrypi-192-168-10-167",
        session_id="smoke-session",
        session_nonce="smoke_nonce_123456",
        surface_digest=surface_digest,
        steps=[step],
    )

    validate_tool_plan(
        plan,
        allowed_tool_ids=[item.tool_id for item in catalog],
        catalog=catalog,
    )
    assert plan.plan_sha256


def test_plan_digest_and_allowlist_are_authoritative() -> None:
    catalog = reduced_agent_native_catalog()
    plan = build_tool_plan(
        goal="inspect host",
        target_id="robot",
        session_id="session",
        session_nonce="session_nonce_123456",
        surface_digest=native_catalog_sha256(catalog),
        steps=[
            ToolPlanStep(
                tool_id="native.os.host.inspect",
                arguments={"mode": "status"},
                expected_observation="host status",
            )
        ],
    )
    with pytest.raises(ValueError, match="outside the session allowlist"):
        validate_tool_plan(plan, allowed_tool_ids=[], catalog=catalog)
    with pytest.raises(ValueError, match="digest mismatch"):
        ToolPlan.model_validate({**plan.model_dump(mode="json"), "plan_sha256": "0" * 64})


def test_mutating_step_requires_approval() -> None:
    catalog = reduced_agent_native_catalog()
    plan = build_tool_plan(
        goal="test",
        target_id="robot",
        session_id="session",
        session_nonce="session_nonce_123456",
        surface_digest=native_catalog_sha256(catalog),
        steps=[
            ToolPlanStep(
                tool_id="native.os.host.inspect",
                expected_observation="test",
                mode="mutating",
            )
        ],
    )
    with pytest.raises(ValueError, match="explicit approval"):
        validate_tool_plan(plan, allowed_tool_ids=[plan.steps[0].tool_id], catalog=catalog)

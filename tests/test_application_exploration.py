from rolo.stages.probe.application_exploration import build_l1_micro_explore_plan


def test_l1_plan_is_fixed_low_speed_and_zero_delimited() -> None:
    plan = build_l1_micro_explore_plan(cycles=2)
    assert plan.level == "L1"
    assert plan.no_motion_until_explicit_execution is True
    assert plan.total_duration_s == 7.0
    assert len(plan.segments) == 8
    for index, segment in enumerate(plan.segments):
        assert abs(segment.linear_x_mps) <= 0.05
        assert abs(segment.angular_z_rps) <= 0.20
        if index % 4 in {1, 3}:
            assert segment.kind == "stop"
            assert segment.linear_x_mps == 0.0
            assert segment.angular_z_rps == 0.0


def test_l1_plan_rejects_unbounded_cycles() -> None:
    import pytest

    with pytest.raises(ValueError):
        build_l1_micro_explore_plan(cycles=4)

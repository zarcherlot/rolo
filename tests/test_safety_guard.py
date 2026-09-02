import math

from rolo.stages.probe.safety_guard import SafetyGuardConfig, guard_velocity


def _scan(*, front: float = 2.0, stamp: float = 9.8) -> tuple[float, float, list[float], float]:
    ranges = [2.0] * 361
    ranges[180] = front
    return stamp, -math.pi, ranges, math.pi / 180


def test_stale_command_fails_closed() -> None:
    stamp, angle_min, ranges, increment = _scan()
    result = guard_velocity(
        linear_x_mps=0.1,
        angular_z_rps=0.2,
        now_s=10.0,
        command_timestamp_s=9.0,
        scan_timestamp_s=stamp,
        ranges=ranges,
        angle_min=angle_min,
        angle_increment=increment,
    )
    assert (result.linear_x_mps, result.angular_z_rps, result.reason) == (0.0, 0.0, "COMMAND_STALE")


def test_stale_scan_fails_closed() -> None:
    result = guard_velocity(
        linear_x_mps=0.1,
        angular_z_rps=0.2,
        now_s=10.0,
        command_timestamp_s=9.9,
        scan_timestamp_s=9.0,
        ranges=[2.0],
    )
    assert (result.linear_x_mps, result.angular_z_rps, result.reason) == (0.0, 0.0, "SCAN_STALE")


def test_emergency_stop_wins_over_all_other_inputs() -> None:
    result = guard_velocity(
        linear_x_mps=1.0,
        angular_z_rps=1.0,
        now_s=10.0,
        command_timestamp_s=None,
        scan_timestamp_s=None,
        ranges=None,
        emergency_stop=True,
    )
    assert (result.linear_x_mps, result.angular_z_rps, result.reason) == (
        0.0,
        0.0,
        "EMERGENCY_STOP",
    )


def test_config_rejects_unbounded_speed() -> None:
    try:
        SafetyGuardConfig(max_linear_mps=1.1)
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe speed limit must be rejected")


def test_front_obstacle_stops_forward_motion() -> None:
    stamp, angle_min, ranges, increment = _scan(front=0.2)
    result = guard_velocity(
        linear_x_mps=0.1,
        angular_z_rps=0.0,
        now_s=10.0,
        command_timestamp_s=9.9,
        scan_timestamp_s=stamp,
        ranges=ranges,
        angle_min=angle_min,
        angle_increment=increment,
    )
    assert (result.linear_x_mps, result.angular_z_rps, result.reason) == (0.0, 0.0, "OBSTACLE")


def test_clear_command_is_clamped_to_configured_limits() -> None:
    stamp, angle_min, ranges, increment = _scan()
    result = guard_velocity(
        linear_x_mps=0.5,
        angular_z_rps=-1.0,
        now_s=10.0,
        command_timestamp_s=9.9,
        scan_timestamp_s=stamp,
        ranges=ranges,
        angle_min=angle_min,
        angle_increment=increment,
    )
    assert (result.linear_x_mps, result.angular_z_rps, result.reason, result.clamped) == (
        0.1,
        -0.4,
        "CLEAR",
        True,
    )


def test_invalid_scan_fails_closed() -> None:
    result = guard_velocity(
        linear_x_mps=0.1,
        angular_z_rps=0.0,
        now_s=10.0,
        command_timestamp_s=9.9,
        scan_timestamp_s=9.9,
        ranges=[float("nan"), float("inf")],
    )
    assert (result.linear_x_mps, result.angular_z_rps, result.reason) == (0.0, 0.0, "INVALID_SCAN")

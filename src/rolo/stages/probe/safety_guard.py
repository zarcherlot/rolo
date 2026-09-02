"""Deterministic velocity guard core for a future target safety runtime.

The core is ROS-independent so a provider adapter can wrap it without making
the Rolo control plane depend on one Middleware client library.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

GuardReason = Literal[
    "CLEAR",
    "OBSTACLE",
    "SCAN_STALE",
    "COMMAND_STALE",
    "EMERGENCY_STOP",
    "INVALID_SCAN",
]


@dataclass(frozen=True)
class SafetyGuardConfig:
    max_linear_mps: float = 0.10
    max_angular_rps: float = 0.40
    obstacle_stop_m: float = 0.35
    scan_timeout_s: float = 0.50
    command_timeout_s: float = 0.25

    def __post_init__(self) -> None:
        if not 0.0 < self.max_linear_mps <= 1.0:
            raise ValueError("max_linear_mps must be in (0, 1]")
        if not 0.0 < self.max_angular_rps <= 3.0:
            raise ValueError("max_angular_rps must be in (0, 3]")
        if not 0.05 <= self.obstacle_stop_m <= 2.0:
            raise ValueError("obstacle_stop_m must be in [0.05, 2]")
        if not 0.05 <= self.scan_timeout_s <= 5.0:
            raise ValueError("scan_timeout_s must be in [0.05, 5]")
        if not 0.05 <= self.command_timeout_s <= 5.0:
            raise ValueError("command_timeout_s must be in [0.05, 5]")


@dataclass(frozen=True)
class GuardedVelocity:
    linear_x_mps: float
    angular_z_rps: float
    reason: GuardReason
    clamped: bool


def _front_min_distance(
    ranges: list[float], angle_min: float, angle_increment: float
) -> float | None:
    """Return the nearest finite range in the forward ±30° sector."""
    if not ranges or not math.isfinite(angle_increment) or angle_increment <= 0:
        return None
    values: list[float] = []
    for index, value in enumerate(ranges):
        angle = angle_min + index * angle_increment
        if abs(angle) > math.pi / 6:
            continue
        if math.isfinite(value) and value > 0:
            values.append(value)
    return min(values) if values else None


def guard_velocity(
    *,
    linear_x_mps: float,
    angular_z_rps: float,
    now_s: float,
    command_timestamp_s: float | None,
    scan_timestamp_s: float | None,
    ranges: list[float] | None,
    angle_min: float = -math.pi,
    angle_increment: float = math.pi / 180,
    emergency_stop: bool = False,
    config: SafetyGuardConfig | None = None,
) -> GuardedVelocity:
    """Clamp or zero one command according to deterministic fail-closed rules."""
    cfg = config or SafetyGuardConfig()
    if emergency_stop:
        return GuardedVelocity(0.0, 0.0, "EMERGENCY_STOP", False)
    if (
        command_timestamp_s is None
        or now_s < command_timestamp_s
        or now_s - command_timestamp_s > cfg.command_timeout_s
    ):
        return GuardedVelocity(0.0, 0.0, "COMMAND_STALE", False)
    if (
        scan_timestamp_s is None
        or now_s < scan_timestamp_s
        or now_s - scan_timestamp_s > cfg.scan_timeout_s
    ):
        return GuardedVelocity(0.0, 0.0, "SCAN_STALE", False)
    if ranges is None:
        return GuardedVelocity(0.0, 0.0, "INVALID_SCAN", False)
    front = _front_min_distance(ranges, angle_min, angle_increment)
    if front is None:
        return GuardedVelocity(0.0, 0.0, "INVALID_SCAN", False)
    if front <= cfg.obstacle_stop_m and linear_x_mps > 0:
        return GuardedVelocity(0.0, 0.0, "OBSTACLE", False)
    linear = max(-cfg.max_linear_mps, min(cfg.max_linear_mps, linear_x_mps))
    angular = max(-cfg.max_angular_rps, min(cfg.max_angular_rps, angular_z_rps))
    return GuardedVelocity(
        linear,
        angular,
        "CLEAR",
        linear != linear_x_mps or angular != angular_z_rps,
    )


__all__ = ["GuardedVelocity", "SafetyGuardConfig", "guard_velocity"]

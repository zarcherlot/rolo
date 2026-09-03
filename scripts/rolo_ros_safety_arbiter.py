#!/usr/bin/env python3
"""Small ROS 2 velocity safety arbiter for a target-side adapter.

This adapter intentionally has one job: turn the existing command fan-in into
one bounded, fail-closed ``cmd_vel_safe`` output.  It does not implement an
emergency-stop or reset protocol; that is a separate hardware/control-plane
concern.  The target controller must be remapped to consume the output topic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import rclpy
from geometry_msgs.msg import Twist
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


@dataclass
class _State:
    command: Twist | None = None
    command_at: float | None = None
    scan_front_m: float | None = None
    scan_at: float | None = None


class RoloSafetyArbiter(Node):
    """Fail-closed command arbiter with bounded speed and two watchdogs."""

    def __init__(self) -> None:
        super().__init__("rolo_safety_arbiter")
        self.declare_parameter("input_topic", "/controller/cmd_vel")
        self.declare_parameter("output_topic", "/controller/cmd_vel_safe")
        self.declare_parameter("scan_topic", "/scan")
        self.declare_parameter("max_linear_mps", 0.10)
        self.declare_parameter("max_angular_rps", 0.40)
        self.declare_parameter("obstacle_stop_m", 0.35)
        self.declare_parameter("command_timeout_s", 0.25)
        self.declare_parameter("scan_timeout_s", 0.50)

        self._max_linear = float(self.get_parameter("max_linear_mps").value)
        self._max_angular = float(self.get_parameter("max_angular_rps").value)
        self._obstacle_stop = float(self.get_parameter("obstacle_stop_m").value)
        self._command_timeout = float(self.get_parameter("command_timeout_s").value)
        self._scan_timeout = float(self.get_parameter("scan_timeout_s").value)
        if not 0.0 < self._max_linear <= 1.0:
            raise ValueError("max_linear_mps must be in (0, 1]")
        if not 0.0 < self._max_angular <= 3.0:
            raise ValueError("max_angular_rps must be in (0, 3]")
        if not 0.05 <= self._obstacle_stop <= 2.0:
            raise ValueError("obstacle_stop_m must be in [0.05, 2]")
        if not 0.05 <= self._command_timeout <= 5.0:
            raise ValueError("command_timeout_s must be in [0.05, 5]")
        if not 0.05 <= self._scan_timeout <= 5.0:
            raise ValueError("scan_timeout_s must be in [0.05, 5]")

        self._state = _State()
        input_topic = str(self.get_parameter("input_topic").value)
        output_topic = str(self.get_parameter("output_topic").value)
        scan_topic = str(self.get_parameter("scan_topic").value)
        self._publisher = self.create_publisher(Twist, output_topic, 10)
        self.create_subscription(Twist, input_topic, self._on_command, 10)
        self.create_subscription(LaserScan, scan_topic, self._on_scan, 10)
        self.create_timer(0.05, self._tick)
        self.get_logger().info(
            f"guarding {input_topic} -> {output_topic} using {scan_topic}; "
            "fail-closed watchdog active"
        )

    def _now(self) -> float:
        return self.get_clock().now().nanoseconds / 1_000_000_000.0

    def _on_command(self, message: Twist) -> None:
        self._state.command = message
        self._state.command_at = self._now()

    def _on_scan(self, message: LaserScan) -> None:
        values: list[float] = []
        if message.angle_increment > 0 and math.isfinite(message.angle_increment):
            for index, value in enumerate(message.ranges):
                angle = message.angle_min + index * message.angle_increment
                if abs(angle) <= math.pi / 6 and math.isfinite(value) and value > 0:
                    values.append(float(value))
        self._state.scan_front_m = min(values) if values else None
        self._state.scan_at = self._now()

    def _tick(self) -> None:
        now = self._now()
        state = self._state
        output = Twist()
        if state.command is None or state.command_at is None:
            self._publisher.publish(output)
            return
        if now - state.command_at > self._command_timeout or now < state.command_at:
            self._publisher.publish(output)
            return
        if state.scan_at is None or now - state.scan_at > self._scan_timeout or now < state.scan_at:
            self._publisher.publish(output)
            return
        if state.scan_front_m is None:
            self._publisher.publish(output)
            return
        if state.scan_front_m <= self._obstacle_stop and state.command.linear.x > 0:
            self._publisher.publish(output)
            return
        output.linear.x = max(-self._max_linear, min(self._max_linear, state.command.linear.x))
        output.linear.y = max(-self._max_linear, min(self._max_linear, state.command.linear.y))
        output.angular.z = max(-self._max_angular, min(self._max_angular, state.command.angular.z))
        self._publisher.publish(output)


def main() -> None:
    rclpy.init()
    node = RoloSafetyArbiter()
    try:
        rclpy.spin(node)
    except ExternalShutdownException:
        # A launch/system shutdown may already have torn down the context.
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

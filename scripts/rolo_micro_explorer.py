#!/usr/bin/env python3
"""Execute one bounded L1 exploration plan through the safety arbiter.

The script is intentionally target-side and narrow: it accepts only the plan
shape emitted by Rolo, publishes to the arbiter input, and publishes zero
between every segment and on shutdown.  It does not bypass ``cmd_vel_safe``.
"""

from __future__ import annotations

import json
import sys
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


class MicroExplorer(Node):
    def __init__(self, plan: dict) -> None:
        super().__init__("rolo_micro_explorer")
        self._publisher = self.create_publisher(Twist, "/controller/cmd_vel", 10)
        self._segments = plan["segments"]

    def zero(self) -> None:
        self._publisher.publish(Twist())
        rclpy.spin_once(self, timeout_sec=0.05)

    def run(self) -> None:
        self.zero()
        for segment in self._segments:
            end = time.monotonic() + float(segment["duration_s"])
            while time.monotonic() < end:
                message = Twist()
                message.linear.x = float(segment["linear_x_mps"])
                message.angular.z = float(segment["angular_z_rps"])
                self._publisher.publish(message)
                rclpy.spin_once(self, timeout_sec=0.05)
            self.zero()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: rolo_micro_explorer.py PLAN.json", file=sys.stderr)
        return 2
    plan = json.loads(open(sys.argv[1], encoding="utf-8").read())
    if plan.get("schema_version") != "rolo-micro-explore-plan/v1":
        print("unsupported exploration plan", file=sys.stderr)
        return 2
    rclpy.init()
    node = MicroExplorer(plan)
    try:
        node.run()
    finally:
        node.zero()
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

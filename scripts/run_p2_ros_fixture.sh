#!/usr/bin/env bash
set -euo pipefail

if ! command -v ros2 >/dev/null 2>&1; then
  echo "ros2 is unavailable; source the target ROS setup before starting the fixture" >&2
  exit 2
fi

: "${ROS_DOMAIN_ID:=50}"
: "${ROS_LOCALHOST_ONLY:=1}"
export ROS_DOMAIN_ID ROS_LOCALHOST_ONLY

exec ros2 run tf2_ros static_transform_publisher \
  --x 1 --y 2 --z 3 \
  --roll 0 --pitch 0 --yaw 0 \
  --frame-id map --child-frame-id base_link \
  --ros-args \
  -r __node:=rolo_p2_validation_fixture \
  -r /tf_static:=/tf

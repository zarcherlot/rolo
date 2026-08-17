from pathlib import Path

from robot_loop.registry import RobotRegistry


def test_loads_two_heterogeneous_robots() -> None:
    registry = RobotRegistry(Path("configs/robots"))
    registry.load()

    assert len(registry) == 2
    assert registry.get("robot_a").platform["drive_model"] == "differential"
    assert registry.get("robot_b").platform["drive_model"] == "ackermann"
    assert registry.get("robot_a").features["robot_use"]["local_visual_detection"] is False
    assert registry.get("robot_b").features["robot_use"]["local_visual_detection"] is False

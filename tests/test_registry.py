from pathlib import Path

from robot_loop.registry import RobotRegistry


def test_loads_two_heterogeneous_robots() -> None:
    registry = RobotRegistry(Path("configs/local/robots"))
    registry.load()

    assert len(registry) == 2
    assert registry.get("demo_diff").platform["drive_model"] == "differential"
    assert registry.get("demo_ackermann").platform["drive_model"] == "ackermann"
    assert registry.get("demo_diff").features["robot_use"]["local_visual_detection"] is False
    assert registry.get("demo_ackermann").features["robot_use"]["local_visual_detection"] is False

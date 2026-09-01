from pathlib import Path

import yaml


def test_nav2_bindings_are_in_target_profile_not_core_runtime() -> None:
    path = Path(__file__).parents[1] / "config" / "integrations" / "nav2.yaml"
    profile = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert profile["provider"] == "ros2_navigation"
    assert profile["map_import"] == {
        "accepted_legacy_formats": ["nav2"],
        "canonical_format": "ros_yaml",
    }
    assert profile["bindings"]["navigate_to_pose"]["operation"] == "app.navigation.start"
    assert set(profile["lifecycle_roles"]) == {
        "localization",
        "map",
        "controller",
        "planner",
        "local_costmap",
        "global_costmap",
    }

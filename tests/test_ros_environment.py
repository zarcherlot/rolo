from __future__ import annotations

import os
from pathlib import Path

import pytest

from rolo.stages.adapt.ros_environment import (
    resolve_ros_environment,
    select_ros_setup_files,
    verify_pinned_setup_files,
)


def _setup(path: Path, content: str = "# setup\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_auto_selection_orders_unique_base_before_project_overlay(tmp_path: Path) -> None:
    ros_root = tmp_path / "opt/ros"
    base = _setup(ros_root / "humble/setup.bash")
    project = tmp_path / "robot_ws"
    overlay = _setup(project / "install/local_setup.bash")

    mode, records = select_ros_setup_files(
        auto_source=True,
        configured=[],
        project_root=project,
        install_roots=[project / "install"],
        environment={"ROS_DISTRO": "humble"},
        ros_root=ros_root,
    )

    assert mode == "AUTO"
    assert [record.path for record in records] == [str(base.resolve()), str(overlay.resolve())]
    assert [record.kind for record in records] == ["BASE", "OVERLAY"]


def test_auto_selection_fails_closed_when_ros_distribution_is_ambiguous(
    tmp_path: Path,
) -> None:
    ros_root = tmp_path / "opt/ros"
    _setup(ros_root / "humble/setup.bash")
    _setup(ros_root / "jazzy/setup.bash")

    with pytest.raises(ValueError, match="multiple ROS distributions"):
        select_ros_setup_files(
            auto_source=True,
            configured=[],
            project_root=None,
            environment={},
            ros_root=ros_root,
        )


def test_resolver_applies_only_operator_runtime_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    setup = _setup(tmp_path / "setup.bash")

    def source(records, environment):
        assert records[0].path == str(setup.resolve())
        return {
            **environment,
            "ROS_DISTRO": "humble",
            "ROS_DOMAIN_ID": "1",
            "RMW_IMPLEMENTATION": "rmw_fastrtps_cpp",
        }

    monkeypatch.setattr("rolo.stages.adapt.ros_environment._source_setup_files", source)
    result = resolve_ros_environment(
        auto_source=True,
        configured=[setup],
        project_root=None,
        environment={"PATH": str(tmp_path)},
        domain_id="7",
        rmw_implementation="rmw_cyclonedds_cpp",
    )

    assert result.mode == "EXPLICIT"
    assert result.environment["ROS_DISTRO"] == "humble"
    assert result.environment["ROS_DOMAIN_ID"] == "7"
    assert result.environment["RMW_IMPLEMENTATION"] == "rmw_cyclonedds_cpp"


def test_pinned_setup_digest_change_is_rejected(tmp_path: Path) -> None:
    setup = _setup(tmp_path / "setup.bash", "first\n")
    _, records = select_ros_setup_files(
        auto_source=True,
        configured=[setup],
        project_root=None,
        environment={},
    )
    setup.write_text("changed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="digest changed"):
        verify_pinned_setup_files(records)


@pytest.mark.skipif(os.name != "posix", reason="requires the target Linux shell")
def test_posix_setup_is_sourced_without_shell_startup_files(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    ros2 = fake_bin / "ros2"
    ros2.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    ros2.chmod(0o700)
    prefix = tmp_path / "install"
    prefix.mkdir()
    setup = _setup(
        tmp_path / "setup.bash",
        "export ROS_DISTRO=humble\n"
        f"export AMENT_PREFIX_PATH='{prefix}'\n"
        f"export PATH='{fake_bin}:'\"$PATH\"\n",
    )

    result = resolve_ros_environment(
        auto_source=True,
        configured=[setup],
        project_root=None,
        environment={"PATH": os.environ["PATH"]},
    )

    assert result.environment["ROS_DISTRO"] == "humble"
    assert result.environment["AMENT_PREFIX_PATH"] == str(prefix)
    assert result.warnings == []

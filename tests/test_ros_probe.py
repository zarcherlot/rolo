from pathlib import Path

from rolo.stages.adapt.discovery import RosProbe


def test_ros_probe_distinguishes_environment_defaults_and_installed_candidates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ros_root = tmp_path / "opt" / "ros"
    humble = ros_root / "humble"
    (humble / "lib").mkdir(parents=True)
    (humble / "setup.bash").write_text("# fixture", encoding="utf-8")
    (humble / "lib" / "librmw_fastrtps_cpp.so").write_bytes(b"")
    (humble / "lib" / "librmw_cyclonedds_cpp.so.1").write_bytes(b"")
    probe = RosProbe(
        ros_root=ros_root,
        environment={
            "ROS_DISTRO": "humble",
            "ROS_DOMAIN_ID": "23",
            "PYTHONPATH": str(humble),
            "OPENAI_API_KEY": "must-not-be-recorded",
        },
    )
    monkeypatch.setattr(
        probe,
        "_run_ros",
        lambda _args: {"available": False, "error": "fixture has no ROS graph"},
    )

    result = probe.run()

    assert result.data["ros_distro"] == "humble"
    assert result.data["ros_distro_source"] == "ENVIRONMENT"
    assert result.data["domain_id"] == "23"
    assert result.data["domain_id_source"] == "ENVIRONMENT"
    assert result.data["rmw"] is None
    assert result.data["rmw_source"] == "NOT_SELECTED"
    assert result.data["rmw_candidates"] == ["rmw_cyclonedds_cpp", "rmw_fastrtps_cpp"]
    assert result.data["runtime_environment"] == {
        "ROS_DISTRO": "humble",
        "ROS_DOMAIN_ID": "23",
        "PYTHONPATH": str(humble.resolve()),
    }
    assert "must-not-be-recorded" not in str(result.data)

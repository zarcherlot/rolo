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
    probe = RosProbe(ros_root=ros_root, environment={"ROS_DISTRO": "humble"})
    monkeypatch.setattr(
        probe,
        "_run_ros",
        lambda _args: {"available": False, "error": "fixture has no ROS graph"},
    )

    result = probe.run()

    assert result.data["ros_distro"] == "humble"
    assert result.data["ros_distro_source"] == "ENVIRONMENT"
    assert result.data["domain_id"] == "0"
    assert result.data["domain_id_source"] == "ROS_DEFAULT"
    assert result.data["rmw"] is None
    assert result.data["rmw_source"] == "NOT_SELECTED"
    assert result.data["rmw_candidates"] == ["rmw_cyclonedds_cpp", "rmw_fastrtps_cpp"]


def test_ros_probe_uses_humble_compatible_action_arguments(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []
    probe = RosProbe(ros_root=tmp_path / "missing", environment={"ROS_DISTRO": "humble"})

    def succeeded(args):
        calls.append(list(args))
        return {
            "available": True,
            "argv": ["ros2", *args],
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        }

    monkeypatch.setattr(probe, "_run_ros", succeeded)

    result = probe.run()

    assert result.status == "SUCCEEDED"
    assert calls[-1] == ["action", "list", "-t"]
    assert all("--no-daemon" in args for args in calls[:-1])


def test_ros_probe_does_not_misclassify_argument_error_as_sandbox(
    tmp_path: Path, monkeypatch
) -> None:
    probe = RosProbe(
        ros_root=tmp_path / "missing",
        environment={"ROS_DISTRO": "humble", "CODEX_SANDBOX_NETWORK_DISABLED": "1"},
    )

    def run(args):
        if args[0] == "action":
            return {
                "available": True,
                "argv": ["ros2", *args, "--no-daemon"],
                "returncode": 2,
                "stdout": "",
                "stderr": "ros2: error: unrecognized arguments: --no-daemon",
            }
        return {
            "available": True,
            "argv": ["ros2", *args],
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        }

    monkeypatch.setattr(probe, "_run_ros", run)

    result = probe.run()

    assert result.status == "PARTIAL"
    assert result.data["command_diagnostics"]["actions"]["failure_class"] == (
        "CLI_ARGUMENT_UNSUPPORTED"
    )
    assert not any("outside the coding sandbox" in warning for warning in result.warnings)


def test_ros_probe_reports_only_evidenced_sandbox_failure(tmp_path: Path, monkeypatch) -> None:
    probe = RosProbe(
        ros_root=tmp_path / "missing",
        environment={"ROS_DISTRO": "humble", "CODEX_SANDBOX_NETWORK_DISABLED": "1"},
    )

    monkeypatch.setattr(
        probe,
        "_run_ros",
        lambda args: {
            "available": True,
            "argv": ["ros2", *args],
            "returncode": 1,
            "stderr": "PermissionError: sandbox blocked localhost socket",
        },
    )

    result = probe.run()

    assert result.status == "UNAVAILABLE"
    assert result.data["command_diagnostics"]["nodes"]["failure_class"] == (
        "EXECUTION_SANDBOX_RESTRICTED"
    )
    assert any("outside the coding sandbox" in warning for warning in result.warnings)

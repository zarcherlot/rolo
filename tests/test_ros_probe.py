from pathlib import Path

from rolo.stages.adapt.discovery import LinuxProbe, RosProbe
from rolo.stages.adapt.routes import legacy_probe_routes


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
    assert result.status == "UNAVAILABLE"
    assert result.data["command_diagnostics"]["nodes"]["succeeded"] is False
    assert any("fixture has no ROS graph" in warning for warning in result.warnings)


def test_ros_probe_retries_a_failed_inherited_cli_in_a_clean_base_setup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ros_root = tmp_path / "opt" / "ros"
    setup = ros_root / "humble" / "setup.bash"
    setup.parent.mkdir(parents=True)
    setup.write_text("# fixture", encoding="utf-8")
    monkeypatch.setattr(
        "rolo.stages.adapt.discovery.shutil.which",
        lambda name: f"/usr/bin/{name}" if name in {"ros2", "bash"} else None,
    )

    def fake_run(argv, **_kwargs):
        if argv[0] == "ros2":
            return {
                "available": True,
                "argv": list(argv),
                "returncode": 1,
                "stderr": "Traceback: inherited Python environment is incompatible",
            }
        return {
            "available": True,
            "argv": list(argv),
            "returncode": 0,
            "stdout": "/controller\n",
            "stderr": "",
        }

    monkeypatch.setattr("rolo.stages.adapt.discovery._run", fake_run)
    result = RosProbe(ros_root=ros_root, environment={"ROS_DISTRO": "humble"}).run()

    assert result.status == "SUCCEEDED"
    assert result.data["nodes"] == ["/controller"]
    diagnostics = result.data["command_diagnostics"]["nodes"]
    assert diagnostics["attempts"][0]["succeeded"] is False
    assert "Traceback" in diagnostics["attempts"][0]["stderr_excerpt"]
    assert diagnostics["attempts"][1]["succeeded"] is True


def test_ros_probe_classifies_codex_sandbox_failure_and_disables_daemon_use(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[list[str]] = []
    probe = RosProbe(
        ros_root=tmp_path / "missing",
        environment={"ROS_DISTRO": "humble", "CODEX_SANDBOX_NETWORK_DISABLED": "1"},
    )

    def blocked(args):
        calls.append(list(args))
        return {
            "available": True,
            "argv": ["ros2", *args],
            "returncode": 1,
            "stderr": "PermissionError: sandbox blocked localhost socket",
        }

    monkeypatch.setattr(probe, "_run_ros", blocked)
    result = probe.run()

    assert result.status == "UNAVAILABLE"
    assert result.data["execution_environment"]["codex_sandbox_network_disabled"] is True
    assert result.data["command_diagnostics"]["nodes"]["failure_class"] == (
        "EXECUTION_SANDBOX_RESTRICTED"
    )
    assert all("--no-daemon" in args for args in calls)
    assert any("outside the coding sandbox" in warning for warning in result.warnings)


def test_ros_probe_does_not_retry_an_environment_change_inside_known_network_sandbox(
    tmp_path: Path,
    monkeypatch,
) -> None:
    setup = tmp_path / "opt" / "ros" / "humble" / "setup.bash"
    setup.parent.mkdir(parents=True)
    setup.write_text("# fixture", encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "rolo.stages.adapt.discovery.shutil.which", lambda name: f"/usr/bin/{name}"
    )

    def blocked(argv, **_kwargs):
        calls.append(list(argv))
        return {"available": True, "argv": list(argv), "returncode": 1, "stderr": "blocked"}

    monkeypatch.setattr("rolo.stages.adapt.discovery._run", blocked)
    probe = RosProbe(
        ros_root=tmp_path / "opt" / "ros",
        environment={"ROS_DISTRO": "humble", "CODEX_SANDBOX_NETWORK_DISABLED": "1"},
    )

    probe._run_ros(["node", "list", "--no-daemon"])

    assert calls == [["ros2", "node", "list", "--no-daemon"]]


def test_linux_probe_does_not_publish_a_cli_route_when_self_description_fails(
    monkeypatch,
) -> None:
    monkeypatch.setattr("rolo.stages.adapt.discovery.platform.system", lambda: "Linux")
    monkeypatch.setattr("rolo.stages.adapt.discovery.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(
        "rolo.stages.adapt.discovery._run",
        lambda argv, **_kwargs: {
            "available": True,
            "argv": list(argv),
            "returncode": 1 if argv[0] == "ros2" else 0,
            "stdout": "" if argv[0] == "ros2" else "1.0",
            "stderr": "Traceback: broken ROS CLI" if argv[0] == "ros2" else "",
        },
    )

    result = LinuxProbe().run()

    assert result.status == "PARTIAL"
    assert result.data["executables"]["ros2"]["installed"] is True
    assert result.data["executables"]["ros2"]["available"] is False
    assert not any(item.endpoint == "ros2" for item in legacy_probe_routes(result))

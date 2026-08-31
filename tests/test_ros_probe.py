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
    assert calls[-1] == ["action", "list", "-t"]
    assert all("--no-daemon" in args for args in calls[:-1])
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


def test_ros_probe_uses_humble_compatible_action_arguments(
    tmp_path: Path,
    monkeypatch,
) -> None:
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


def test_ros_probe_stability_ignores_dds_enumeration_order(
    tmp_path: Path, monkeypatch
) -> None:
    probe = RosProbe(
        ros_root=tmp_path / "missing",
        environment={"ROS_DISTRO": "humble"},
        stabilize=True,
    )
    samples = {
        "node": ["/b\n/a\n", "/a\n/b\n"],
        "topic": [
            "/topic_b [std_msgs/msg/String]\n/topic_a [std_msgs/msg/String]\n",
            "/topic_a [std_msgs/msg/String]\n/topic_b [std_msgs/msg/String]\n",
        ],
        "service": [
            ("/svc_b [example_interfaces/srv/AddTwoInts]\n"
             "/svc_a [example_interfaces/srv/AddTwoInts]\n"),
            ("/svc_a [example_interfaces/srv/AddTwoInts]\n"
             "/svc_b [example_interfaces/srv/AddTwoInts]\n"),
        ],
        "action": [
            ("/act_b [example_interfaces/action/Fibonacci]\n"
             "/act_a [example_interfaces/action/Fibonacci]\n"),
            ("/act_a [example_interfaces/action/Fibonacci]\n"
             "/act_b [example_interfaces/action/Fibonacci]\n"),
        ],
    }
    seen = {key: 0 for key in samples}

    def succeeded(args):
        key = args[0]
        index = seen[key]
        seen[key] += 1
        return {
            "available": True,
            "argv": ["ros2", *args],
            "returncode": 0,
            "stdout": samples[key][min(index, 1)],
            "stderr": "",
        }

    monkeypatch.setattr(probe, "_run_ros", succeeded)
    result = probe.run()

    assert result.data["stability"] == {
        "attempts": 2,
        "stable": True,
        "sampled_fields": ["actions", "nodes", "services", "topics"],
    }


def test_ros_probe_filters_topics_owned_only_by_its_ros2cli_daemon(
    tmp_path: Path, monkeypatch
) -> None:
    probe = RosProbe(
        ros_root=tmp_path / "missing",
        environment={"ROS_DISTRO": "humble"},
        enrich_routes=True,
    )

    def succeeded(args):
        if args[:2] == ["topic", "list"]:
            stdout = (
                "/parameter_events [rcl_interfaces/msg/ParameterEvent]\n"
                "/rosout [rcl_interfaces/msg/Log]\n"
            )
        elif args[:3] == ["topic", "info", "-v"]:
            stdout = "Node name: _ros2cli_daemon_0_fixture\nEndpoint type: PUBLISHER\n"
        elif args[:2] == ["interface", "show"]:
            stdout = "string fixture\n"
        elif args[:2] == ["node", "list"]:
            stdout = "/_ros2cli_daemon_0_fixture\n"
        else:
            stdout = ""
        return {
            "available": True,
            "argv": ["ros2", *args],
            "returncode": 0,
            "stdout": stdout,
            "stderr": "",
        }

    monkeypatch.setattr(probe, "_run_ros", succeeded)

    result = probe.run()

    assert result.data["topics"] == []
    assert result.data["nodes"] == []
    assert result.data["route_enrichment"]["provider_ids"] == {}
    assert result.data["route_enrichment"]["filtered_probe_owned_endpoints"] == [
        "/parameter_events",
        "/rosout",
    ]


def test_ros_probe_keeps_multi_publisher_topic_without_claiming_one_provider(
    tmp_path: Path, monkeypatch
) -> None:
    probe = RosProbe(
        ros_root=tmp_path / "missing",
        environment={"ROS_DISTRO": "humble"},
        enrich_routes=True,
    )

    def succeeded(args):
        if args[:2] == ["topic", "list"]:
            stdout = (
                "/global_costmap/global_costmap/transition_event "
                "[lifecycle_msgs/msg/TransitionEvent]\n"
            )
        elif args[:3] == ["topic", "info", "-v"]:
            stdout = (
                "Node name: global_costmap\n"
                "Endpoint type: PUBLISHER\n"
                "Node name: rolo_validation_fixture\n"
                "Endpoint type: PUBLISHER\n"
            )
        elif args[:2] == ["interface", "show"]:
            stdout = "uint64 timestamp\n"
        else:
            stdout = ""
        return {
            "available": True,
            "argv": ["ros2", *args],
            "returncode": 0,
            "stdout": stdout,
            "stderr": "",
        }

    monkeypatch.setattr(probe, "_run_ros", succeeded)

    result = probe.run()

    assert result.data["topics"] == [
        "/global_costmap/global_costmap/transition_event "
        "[lifecycle_msgs/msg/TransitionEvent]"
    ]
    assert "/global_costmap/global_costmap/transition_event" not in result.data[
        "route_enrichment"
    ]["provider_ids"]


def test_ros_probe_ignores_subscribers_when_identifying_topic_provider(
    tmp_path: Path, monkeypatch
) -> None:
    probe = RosProbe(
        ros_root=tmp_path / "missing",
        environment={"ROS_DISTRO": "humble"},
        enrich_routes=True,
    )

    def succeeded(args):
        if args[:2] == ["topic", "list"]:
            stdout = "/scan [sensor_msgs/msg/LaserScan]\n"
        elif args[:3] == ["topic", "info", "-v"]:
            stdout = (
                "Node name: rolo_validation_fixture\n"
                "Endpoint type: PUBLISHER\n"
                "Node name: local_costmap\n"
                "Endpoint type: SUBSCRIPTION\n"
                "Node name: global_costmap\n"
                "Endpoint type: SUBSCRIPTION\n"
            )
        elif args[:2] == ["interface", "show"]:
            stdout = "float32[] ranges\n"
        else:
            stdout = ""
        return {
            "available": True,
            "argv": ["ros2", *args],
            "returncode": 0,
            "stdout": stdout,
            "stderr": "",
        }

    monkeypatch.setattr(probe, "_run_ros", succeeded)

    result = probe.run()

    assert result.data["route_enrichment"]["provider_ids"]["/scan"] == (
        "ros_node:rolo_validation_fixture"
    )


def test_ros_probe_route_enrichment_is_bounded_by_topic_budget(
    tmp_path: Path, monkeypatch
) -> None:
    probe = RosProbe(
        ros_root=tmp_path / "missing",
        environment={"ROS_DISTRO": "humble"},
        enrich_routes=True,
    )
    monkeypatch.setattr(
        "rolo.stages.adapt.discovery.MAX_ROUTE_ENRICHMENT_TOPICS", 1
    )

    def succeeded(args):
        if args[:2] == ["topic", "list"]:
            stdout = "/first [std_msgs/msg/String]\n/second [std_msgs/msg/String]\n"
        elif args[:3] == ["topic", "info", "-v"]:
            stdout = "Node name: first_node\nEndpoint type: PUBLISHER\n"
        elif args[:2] == ["interface", "show"]:
            stdout = "string data\n"
        else:
            stdout = ""
        return {
            "available": True,
            "argv": ["ros2", *args],
            "returncode": 0,
            "stdout": stdout,
            "stderr": "",
        }

    monkeypatch.setattr(probe, "_run_ros", succeeded)

    result = probe.run()

    enrichment = result.data["route_enrichment"]
    assert result.status == "PARTIAL"
    assert enrichment["topic_limit"] == 1
    assert enrichment["truncated"] is True
    assert enrichment["provider_ids"] == {"/first": "ros_node:first_node"}
    assert enrichment["interface_schema_sha256"]
    assert any(item.startswith("/second ") for item in result.data["topics"])


def test_ros_probe_does_not_misclassify_argument_error_as_sandbox(
    tmp_path: Path,
    monkeypatch,
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


def test_ros_probe_reports_only_evidenced_sandbox_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
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


def test_linux_probe_uses_offline_colcon_help(monkeypatch) -> None:
    monkeypatch.setattr("rolo.stages.adapt.discovery.platform.system", lambda: "Linux")
    monkeypatch.setattr("rolo.stages.adapt.discovery.shutil.which", lambda name: f"/bin/{name}")
    calls: list[list[str]] = []

    def succeeded(argv, **_kwargs):
        calls.append(list(argv))
        return {
            "available": True,
            "argv": list(argv),
            "returncode": 0,
            "stdout": "colcon help\n",
            "stderr": "",
        }

    monkeypatch.setattr("rolo.stages.adapt.discovery._run", succeeded)

    result = LinuxProbe().run()

    assert result.status == "SUCCEEDED"
    assert ["colcon", "--help"] in calls
    assert ["colcon", "version-check"] not in calls

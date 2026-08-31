import hashlib
import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rolo import host_introspection
from rolo.cli import app


def test_host_inventory_exposes_bootstrap_control_planes() -> None:
    result = host_introspection.host_inventory()

    assert result["operation"] == "linux.host.inventory"
    assert result["status"] == "SUCCEEDED"
    assert result["data"]["host"]["system"]
    assert set(result["data"]["control_planes"]) == {
        "service_managers",
        "container_runtimes",
        "schedulers",
        "container_markers",
    }


def test_retired_host_inspect_cli_is_removed() -> None:
    runner = CliRunner()

    inspect_result = runner.invoke(app, ["linux", "host", "inspect"])

    assert inspect_result.exit_code != 0
    assert "No such command" in inspect_result.output


def test_generic_host_resource_and_time_operations_are_callable(tmp_path: Path) -> None:
    target = tmp_path / "payload.bin"
    target.write_bytes(b"rolo")

    results = [
        host_introspection.host_status(),
        host_introspection.host_uptime(),
        host_introspection.file_hash(target),
        host_introspection.resource_cpu(),
        host_introspection.resource_memory(),
        host_introspection.resource_disk(tmp_path),
        host_introspection.resource_snapshot(tmp_path),
        host_introspection.time_status(),
    ]

    assert all(result["operation"].startswith("linux.") for result in results)
    assert all(result["status"] in {"SUCCEEDED", "PARTIAL", "UNAVAILABLE"} for result in results)
    assert results[2]["data"]["sha256"] == (
        "b5beb35d79007f63bf1029e61b635d309eca02ac0c5459ee691c53a35e0089fa"
    )
    assert results[5]["data"]["total_bytes"] > 0
    assert results[7]["data"]["monotonic_ns"] > 0


def test_network_routes_degrades_when_platform_has_no_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_introspection.platform, "system", lambda: "UnknownOS")

    result = host_introspection.network_routes()

    assert result["operation"] == "linux.network.routes"
    assert result["status"] == "UNAVAILABLE"
    assert result["data"] == {"routes": []}
    assert host_introspection.network_connections()["status"] == "UNAVAILABLE"
    assert host_introspection.network_dns()["status"] == "UNAVAILABLE"


def test_second_linux_metadata_batch_is_bounded_and_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = tmp_path / "payload.txt"
    payload.write_text("content is not returned", encoding="utf-8")
    (tmp_path / "second.txt").write_text("two", encoding="utf-8")

    inspected = host_introspection.file_inspect(payload)
    listed = host_introspection.file_list(tmp_path, limit=1)
    verified = host_introspection.binary_verify(
        payload,
        hashlib.sha256(payload.read_bytes()).hexdigest(),
    )

    assert inspected["data"]["kind"] == "file"
    assert "content" not in inspected["data"]
    assert len(listed["data"]["entries"]) == 1
    assert verified["data"]["verified"] is True
    with pytest.raises(ValueError, match="64 hexadecimal"):
        host_introspection.binary_verify(payload, "not-a-digest")
    with pytest.raises(ValueError, match="limit must be between"):
        host_introspection.file_list(tmp_path, limit=1_001)

    calls: list[list[str]] = []
    monkeypatch.setattr(host_introspection.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        host_introspection.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"docker", "dpkg-query", "dpkg"} else None,
    )

    def fake_command(argv: list[str], **kwargs: object) -> dict[str, object]:
        del kwargs
        calls.append(argv)
        if argv[0] == "docker":
            return {
                "status": "SUCCEEDED",
                "returncode": 0,
                "stdout": '{"Name":"drive","CPUPerc":"1.0%"}\n',
            }
        if argv[0] == "dpkg-query":
            return {
                "status": "SUCCEEDED",
                "returncode": 0,
                "stdout": "drive\t1.2.3\tamd64\tinstall ok installed\n",
            }
        return {"status": "SUCCEEDED", "returncode": 0, "stdout": ""}

    monkeypatch.setattr(host_introspection, "_command", fake_command)

    stats = host_introspection.container_stats("drive")
    package = host_introspection.package_inspect("drive")
    integrity = host_introspection.package_verify("drive")

    assert stats["data"]["containers"] == [{"Name": "drive", "CPUPerc": "1.0%"}]
    assert package["data"]["manager"] == "dpkg"
    assert integrity["data"]["verified"] is True
    assert calls[0] == [
        "docker",
        "stats",
        "--no-stream",
        "--format",
        "{{json .}}",
        "drive",
    ]


def test_network_metadata_uses_structured_linux_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_introspection.platform, "system", lambda: "Linux")

    def fake_command(argv: list[str], **kwargs: object) -> dict[str, object]:
        del kwargs
        return {
            "status": "SUCCEEDED",
            "stdout": '[{"ifindex":1,"ifname":"lo"}]',
            "argv": argv,
        }

    monkeypatch.setattr(host_introspection, "_command", fake_command)

    interfaces = host_introspection.network_interfaces()
    statistics = host_introspection.network_statistics()

    assert interfaces["data"]["interfaces"][0]["ifname"] == "lo"
    assert statistics["data"]["interfaces"][0]["ifindex"] == 1


def test_process_resource_parser_normalizes_proc_byte_values() -> None:
    values = host_introspection._proc_key_values(
        "Name:\tdriver\nVmRSS:\t12 kB\nThreads:\t4\n", byte_values=True
    )

    assert values == {"Name": "driver", "VmRSS_bytes": 12 * 1024, "Threads": 4}


def test_middleware_status_and_graph_are_derived_from_bounded_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inspection = {
        "status": "SUCCEEDED",
        "data": {
            "installed_interfaces": {"ros2": "/usr/bin/ros2", "mqtt": None},
            "process_candidates": [
                {
                    "process": {"pid": 42, "name": "robot_bridge"},
                    "protocol_tokens": ["ros", "dds"],
                }
            ],
            "listeners": [{"local_port": 7400}],
        },
        "warnings": [],
    }
    monkeypatch.setattr(host_introspection, "middleware_inspect", lambda: inspection)

    status = host_introspection.middleware_status()
    graph = host_introspection.middleware_graph_snapshot()

    assert status["data"] == {
        "installed_interfaces": {"ros2": "/usr/bin/ros2"},
        "process_candidate_count": 1,
        "listener_count": 1,
    }
    node_ids = {node["id"] for node in graph["data"]["nodes"]}
    assert {"interface:ros2", "interface:ros", "interface:dds", "process:42"} <= node_ids
    assert len(graph["data"]["edges"]) == 2


def test_ros_read_only_discovery_uses_ros2_cli_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        host_introspection.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name == "ros2" else None,
    )

    def fake_command(argv: list[str], **kwargs: object) -> dict[str, object]:
        del kwargs
        calls.append(argv)
        return {"status": "SUCCEEDED", "stdout": "/alpha\n/beta\n"}

    monkeypatch.setattr(host_introspection, "_command", fake_command)

    nodes = host_introspection.ros_node_list()
    topic = host_introspection.ros_topic_describe("/camera/image")
    actions = host_introspection.ros_action_list()

    assert nodes["data"] == {"ros_version": 2, "nodes": ["/alpha", "/beta"]}
    assert topic["operation"] == "ros.topic.describe"
    assert actions["data"]["ros_version"] == 2
    assert calls == [
        ["ros2", "node", "list"],
        ["ros2", "topic", "info", "/camera/image", "--verbose"],
        ["ros2", "action", "list", "-t"],
    ]


def test_ros_node_status_is_compact_visibility_not_interface_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        host_introspection.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name == "ros2" else None,
    )

    def fake_command(argv: list[str], **kwargs: object) -> dict[str, object]:
        del kwargs
        calls.append(argv)
        return {"status": "SUCCEEDED", "stdout": "/alpha\n/beta\n"}

    monkeypatch.setattr(host_introspection, "_command", fake_command)

    result = host_introspection.ros_node_status("/alpha")

    assert result["data"] == {"name": "/alpha", "visible": True, "ros_version": 2}
    assert "details" not in result["data"]
    assert calls == [["ros2", "node", "list"]]


def test_ros_action_discovery_degrades_without_ros2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_introspection.shutil, "which", lambda name: None)

    result = host_introspection.ros_action_list()

    assert result["status"] == "UNAVAILABLE"
    assert result["data"] == {"ros_version": None, "actions": []}


def test_ros_parameter_reads_require_explicit_node_and_remain_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        host_introspection.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name == "ros2" else None,
    )

    def fake_command(argv: list[str], **kwargs: object) -> dict[str, object]:
        del kwargs
        calls.append(argv)
        return {"status": "SUCCEEDED", "stdout": "Integer value is: 7\n"}

    monkeypatch.setattr(host_introspection, "_command", fake_command)

    value = host_introspection.ros_parameter_get("/controller", "rate")
    descriptor = host_introspection.ros_parameter_describe("/controller", "rate")

    assert value["data"]["value"] == "Integer value is: 7"
    assert descriptor["data"]["ros_version"] == 2
    assert calls == [
        ["ros2", "param", "get", "/controller", "rate"],
        ["ros2", "param", "describe", "/controller", "rate"],
    ]


def test_service_list_normalizes_linux_systemd_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_introspection.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        host_introspection,
        "_command",
        lambda *args, **kwargs: {
            "status": "SUCCEEDED",
            "stdout": "robot.service loaded active running Robot controller\n",
        },
    )

    result = host_introspection.service_list()

    assert result["data"]["services"] == [
        {
            "name": "robot.service",
            "load": "loaded",
            "active": "active",
            "sub": "running",
            "description": "Robot controller",
        }
    ]


def test_cli_probe_rejects_operational_arguments(tmp_path: Path) -> None:
    executable = tmp_path / "robot-driver"
    executable.write_text("placeholder", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported self-description"):
        host_introspection.cli_probe(executable, ["move", "--speed"])


def test_config_locate_searches_only_adjacent_bounded_locations(tmp_path: Path) -> None:
    binary_dir = tmp_path / "bin"
    config_dir = binary_dir / "config"
    config_dir.mkdir(parents=True)
    binary = binary_dir / "controller"
    binary.write_text("", encoding="utf-8")
    config = config_dir / "controller.yaml"
    config.write_text("enabled: true\n", encoding="utf-8")

    result = host_introspection.config_locate(binary=binary)

    assert result["data"]["candidates"] == [
        {"path": str(config.resolve()), "source": "binary adjacency"}
    ]


def test_secret_assignment_redaction_preserves_key_but_not_value() -> None:
    redacted = host_introspection._redact(
        "--token=abc password: hunter2 --api-key third safe=value"
    )

    assert "abc" not in redacted
    assert "hunter2" not in redacted
    assert "third" not in redacted
    assert redacted == ("--token=<redacted> password: <redacted> --api-key <redacted> safe=value")


def test_structured_redaction_hides_nested_secret_fields() -> None:
    value = {"Config": {"Env": ["SAFE=yes", "TOKEN=abc"], "ApiKey": "secret"}}

    assert host_introspection._redact_data(value) == {
        "Config": {"Env": ["SAFE=yes", "TOKEN=<redacted>"], "ApiKey": "<redacted>"}
    }


def test_command_reports_missing_timeout_failure_and_bounded_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_introspection.shutil, "which", lambda _: None)
    assert host_introspection._command(["missing-tool"])["status"] == "UNAVAILABLE"

    monkeypatch.setattr(host_introspection.shutil, "which", lambda _: "/usr/bin/tool")

    def timeout_run(*args, **kwargs):
        del args, kwargs
        raise host_introspection.subprocess.TimeoutExpired(
            "tool", 1, output="secret=abc", stderr="bad"
        )

    monkeypatch.setattr(host_introspection.subprocess, "run", timeout_run)
    timed_out = host_introspection._command(["tool"])
    assert timed_out["status"] == "TIMEOUT"
    assert "abc" not in timed_out["stdout"]

    def failed_run(*args, **kwargs):
        del args, kwargs
        raise OSError("permission denied")

    monkeypatch.setattr(host_introspection.subprocess, "run", failed_run)
    assert host_introspection._command(["tool"])["status"] == "PROBE_FAILED"


def test_platform_specific_adapters_cover_windows_and_unavailable_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_introspection.platform, "system", lambda: "Other")
    for operation in (
        host_introspection.service_list,
        host_introspection.schedule_list,
        host_introspection.process_list,
    ):
        assert operation()["status"] == "UNAVAILABLE"
    with pytest.raises(ValueError, match="invalid service name"):
        host_introspection.service_inspect("-bad")
    with pytest.raises(ValueError, match="invalid container name"):
        host_introspection.container_inspect("bad\nname")

    monkeypatch.setattr(host_introspection.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        host_introspection,
        "_command",
        lambda argv, **kwargs: {
            "status": "SUCCEEDED",
            "stdout": ("SERVICE_NAME: robot\n        STATE              : 4  RUNNING\n")
            if argv[0] == "sc.exe"
            else '"Image Name","PID"\n"robot.exe","42"\n',
        },
    )
    assert host_introspection.service_list()["data"]["services"][0]["name"] == "robot"
    assert host_introspection.process_list()["data"]["processes"][0]["pid"] == 42


def test_container_schedule_process_and_file_edge_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(host_introspection.shutil, "which", lambda _: None)
    assert host_introspection.container_list()["status"] == "UNAVAILABLE"
    with pytest.raises(ValueError, match="runtime must be"):
        host_introspection.container_list("containerd")

    missing = tmp_path / "missing"
    assert host_introspection.file_hash(missing)["status"] == "UNAVAILABLE"
    assert host_introspection.file_list(missing)["status"] == "UNAVAILABLE"
    assert host_introspection.binary_describe(missing)["status"] == "UNAVAILABLE"
    with pytest.raises(ValueError, match="pid must be positive"):
        host_introspection.process_inspect(0)
    with pytest.raises(ValueError, match="pid must be positive"):
        host_introspection.process_resources(-1)

    monkeypatch.setattr(host_introspection.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        host_introspection.shutil,
        "which",
        lambda name: "/usr/bin/docker" if name == "docker" else None,
    )
    monkeypatch.setattr(
        host_introspection,
        "_command",
        lambda argv, **kwargs: {"status": "SUCCEEDED", "stdout": "bad-json\n"},
    )
    assert host_introspection.container_list("docker")["data"]["containers"] == [
        {"raw": "bad-json"}
    ]
    assert host_introspection.container_stats()["data"]["containers"] == [{"raw": "bad-json"}]


def test_binary_cli_package_and_config_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "script"
    script.write_bytes(b"#!/usr/bin/env python\nprint('ok')\n")
    monkeypatch.setattr(
        host_introspection,
        "_command",
        lambda argv, **kwargs: {"status": "SUCCEEDED", "stdout": "ok"},
    )
    described = host_introspection.binary_describe(script)
    assert described["data"]["format"] == "script"
    assert host_introspection.cli_probe(script, ["--help"])["data"]["probe_status"] == "SUCCEEDED"
    monkeypatch.setattr(host_introspection.platform, "system", lambda: "Linux")
    monkeypatch.setattr(host_introspection.shutil, "which", lambda _: None)
    assert host_introspection.package_inspect("unknown")["status"] == "UNAVAILABLE"
    with pytest.raises(ValueError, match="invalid package name"):
        host_introspection.package_inspect("-bad")
    assert host_introspection.config_locate(binary=script)["data"]["candidates"] == []


def test_linux_service_schedule_process_and_resource_failure_shapes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_introspection.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        host_introspection,
        "_command",
        lambda argv, **kwargs: {"status": "PROBE_FAILED", "stdout": "", "stderr": "failed"},
    )
    assert host_introspection.service_list()["status"] == "PARTIAL"
    assert host_introspection.schedule_list()["status"] == "PARTIAL"
    assert host_introspection.process_list()["status"] == "PARTIAL"
    assert host_introspection.resource_gpu()["status"] in {"UNAVAILABLE", "PARTIAL", "SUCCEEDED"}
    assert host_introspection.middleware_status()["operation"] == "middleware.status"


def test_cli_exposes_introspection_command_tree() -> None:
    runner = CliRunner()

    linux_help = runner.invoke(app, ["linux", "--help"])
    middleware = runner.invoke(app, ["middleware", "inspect"])
    runtime_version = runner.invoke(app, ["runtime", "version"])
    binary = runner.invoke(app, ["linux", "binary", "describe", sys.executable])

    assert linux_help.exit_code == 0, linux_help.output
    for command in (
        "host",
        "service",
        "container",
        "schedule",
        "process",
        "binary",
        "package",
        "cli",
        "config",
        "file",
        "network",
        "resource",
        "time",
    ):
        assert command in linux_help.output
    assert middleware.exit_code == 0, middleware.output
    assert json.loads(middleware.output)["operation"] == "middleware.inspect"
    assert binary.exit_code == 0, binary.output
    assert json.loads(binary.output)["operation"] == "linux.binary.describe"
    assert runtime_version.exit_code == 0, runtime_version.output
    assert json.loads(runtime_version.output)["version"]

from __future__ import annotations

from pathlib import Path

import pytest

from rolo.commands import canonical


@pytest.mark.parametrize(
    ("command", "backend"),
    [
        ("linux_host_inventory", "host_inventory"),
        ("linux_host_status", "host_status"),
        ("linux_host_uptime", "host_uptime"),
        ("linux_service_list", "service_list"),
        ("linux_schedule_list", "schedule_list"),
        ("linux_process_list", "process_list"),
        ("linux_network_listeners", "network_listeners"),
        ("linux_network_routes", "network_routes"),
        ("linux_network_interfaces", "network_interfaces"),
        ("linux_network_statistics", "network_statistics"),
        ("linux_network_connections", "network_connections"),
        ("linux_network_dns", "network_dns"),
        ("linux_resource_cpu", "resource_cpu"),
        ("linux_resource_memory", "resource_memory"),
        ("linux_resource_snapshot", "resource_snapshot"),
        ("linux_resource_gpu", "resource_gpu"),
        ("linux_time_status", "time_status"),
        ("middleware_inspect", "middleware_inspect"),
        ("middleware_status", "middleware_status"),
        ("middleware_graph_snapshot", "middleware_graph_snapshot"),
        ("ros_graph_snapshot", "ros_graph_snapshot"),
        ("ros_node_list", "ros_node_list"),
        ("ros_topic_list", "ros_topic_list"),
        ("ros_service_list", "ros_service_list"),
        ("ros_action_list", "ros_action_list"),
        ("ros_parameter_list", "ros_parameter_list"),
        ("ros_clock_status", "ros_clock_status"),
    ],
)
def test_canonical_read_only_wrappers_emit_backend_result(
    command: str, backend: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[object] = []
    monkeypatch.setattr(canonical, "emit", captured.append)
    if command == "ros_graph_snapshot":
        monkeypatch.setattr(
            canonical,
            "RosProbe",
            lambda: type("Probe", (), {"run": lambda self: {"backend": backend}})(),
        )
    else:
        monkeypatch.setattr(
            canonical.host_introspection,
            backend,
            lambda *args, **kwargs: {"backend": backend, "args": args, "kwargs": kwargs},
        )
    getattr(canonical, command)()
    assert captured[0]["backend"] == backend


def test_canonical_argument_wrappers_forward_arguments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: list[object] = []
    monkeypatch.setattr(canonical, "emit", captured.append)
    monkeypatch.setattr(canonical, "authorize_data_access", lambda *args, **kwargs: None)

    def fake(name):
        return lambda *args, **kwargs: {"name": name, "args": args, "kwargs": kwargs}

    for name in (
        "service_inspect",
        "container_inspect",
        "container_stats",
        "schedule_inspect",
        "process_inspect",
        "process_resources",
        "binary_describe",
        "package_inspect",
        "package_verify",
        "file_hash",
        "file_inspect",
        "file_list",
        "network_listeners",
        "network_routes",
        "ros_node_status",
        "ros_node_inspect",
        "ros_node_lifecycle",
        "ros_topic_describe",
        "ros_service_describe",
        "ros_action_describe",
        "ros_parameter_get",
        "ros_parameter_describe",
        "ros_bag_inspect",
    ):
        monkeypatch.setattr(canonical.host_introspection, name, fake(name))

    canonical.linux_service_inspect("svc")
    canonical.linux_container_inspect("ctr", runtime="docker")
    canonical.linux_container_stats(name="ctr", runtime="podman")
    canonical.linux_schedule_inspect("timer")
    canonical.linux_process_inspect(42)
    canonical.linux_process_resources(42)
    canonical.linux_binary_describe(tmp_path / "bin")
    canonical.linux_package_inspect("pkg")
    canonical.linux_package_verify("pkg")
    canonical.linux_file_hash(tmp_path / "x")
    canonical.linux_file_inspect(tmp_path / "x")
    canonical.linux_file_list(tmp_path, limit=2)
    canonical.ros_node_status("/node")
    canonical.ros_node_inspect("/node")
    canonical.ros_node_lifecycle("/node")
    canonical.ros_topic_describe("/topic")
    canonical.ros_service_describe("/service")
    canonical.ros_action_describe("/action")
    canonical.ros_parameter_get("param", "/node")
    canonical.ros_parameter_describe("param", "/node")
    canonical.ros_bag_inspect(tmp_path / "bag")

    assert len(captured) == 21

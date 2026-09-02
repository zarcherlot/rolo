import os
import subprocess
import sys
from pathlib import Path

import pytest

from rolo.agent_tools.native_tools import (
    AgentNativeRunner,
    AgentNativeToolDescriptor,
    NativeToolInvocation,
    NativeToolStatus,
    RemoteAgentNativeRunner,
    reduced_agent_native_catalog,
)


def _descriptor(*args: str, **kwargs: object) -> AgentNativeToolDescriptor:
    return AgentNativeToolDescriptor(
        tool_id=kwargs.pop("tool_id", "test.echo"),
        family="test",
        execution_path="DIRECT_RUNNER",
        executable=sys.executable,
        argv_template=[sys.executable, *args],
        access="read",
        risk="R0",
        max_duration_s=2,
        max_output_bytes=64,
        evidence_kind="TEST",
        **kwargs,
    )


def test_runner_executes_fixed_argv_and_bounds_output() -> None:
    descriptor = _descriptor("-c", "print('password=secret-value')")
    result = AgentNativeRunner([descriptor]).run("test.echo")

    assert result.status == NativeToolStatus.SUCCEEDED
    assert "secret-value" not in result.stdout
    assert "<redacted>" in result.stdout
    assert result.argv[0] == sys.executable


def test_runner_rejects_unknown_tool_and_reports_nonzero_exit() -> None:
    descriptor = _descriptor("-c", "raise SystemExit(3)")
    runner = AgentNativeRunner([descriptor])

    with pytest.raises(ValueError, match="unknown agent-native tool"):
        runner.run("test.unknown")
    assert runner.run("test.echo").status == NativeToolStatus.FAILED


def test_runner_classifies_empty_usb_inventory_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_executor(command: list[str], **kwargs: object):
        return type("Completed", (), {"returncode": 1, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(
        "rolo.agent_tools.native_tools.shutil.which", lambda value, path=None: value
    )
    runner = AgentNativeRunner(reduced_agent_native_catalog(), executor=fake_executor)

    result = runner.run("native.hardware.inventory", {"mode": "usb"})

    assert result.status == NativeToolStatus.UNAVAILABLE
    assert result.limitations == [
        "command exited with return code 1; environment resource is unavailable"
    ]


def test_runner_timeout_is_fail_closed() -> None:
    descriptor = _descriptor("-c", "import time; time.sleep(10)")
    result = AgentNativeRunner([descriptor]).run("test.echo")

    assert result.status == NativeToolStatus.TIMEOUT
    assert result.limitations == ["tool execution timed out"]


def test_network_timeout_is_explicitly_marked_as_environment_limited() -> None:
    descriptor = AgentNativeToolDescriptor(
        tool_id="test.network",
        family="middleware",
        execution_path="DIRECT_RUNNER",
        executable=sys.executable,
        argv_template=[sys.executable, "-c", "pass"],
        access="read",
        risk="R0",
        max_duration_s=2,
        max_output_bytes=64,
        evidence_kind="TEST",
        variants={
            "status": NativeToolInvocation(
                executable=sys.executable,
                argv_template=[sys.executable, "-c", "pass"],
                environment_dependency="NETWORK",
            )
        },
    )

    def timeout_executor(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(kwargs.get("timeout", 0), 0)

    runner = AgentNativeRunner([descriptor], executor=timeout_executor)
    result = runner.run("test.network", {"mode": "status"})

    assert result.status == NativeToolStatus.TIMEOUT
    assert result.environment_limited is True
    assert "network-dependent check" in result.limitations[-1]


def test_middleware_snapshot_declares_network_dependency() -> None:
    middleware = next(
        item
        for item in reduced_agent_native_catalog()
        if item.tool_id == "native.middleware.snapshot"
    )
    assert middleware.variants["status"].environment_dependency == "NETWORK"


def test_descriptor_rejects_interpolation_and_unsafe_environment() -> None:
    with pytest.raises(ValueError, match="does not accept interpolation"):
        _descriptor("{user}")
    with pytest.raises(ValueError, match="approved environment"):
        _descriptor("-c", "print('ok')", allowed_env_keys=["PATH"])


def test_runner_forwards_validated_ros_runtime_paths_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    python_root = tmp_path / "ros-python"
    python_root.mkdir()
    (python_root / "ros2cli_fixture.py").write_text(
        "VALUE = 'available'\n", encoding="utf-8"
    )
    library_root = tmp_path / "ros-lib"
    library_root.mkdir()
    missing_root = tmp_path / "missing"
    monkeypatch.setenv(
        "PYTHONPATH", os.pathsep.join((str(python_root), str(missing_root)))
    )
    monkeypatch.setenv("LD_LIBRARY_PATH", str(library_root))
    descriptor = _descriptor(
        "-c",
        "import ros2cli_fixture; print(ros2cli_fixture.VALUE)",
        allowed_env_keys=["PYTHONPATH", "LD_LIBRARY_PATH"],
    )

    result = AgentNativeRunner([descriptor]).run("test.echo")

    assert result.status == NativeToolStatus.SUCCEEDED
    assert result.stdout.strip() == "available"


def test_non_ros_family_does_not_inherit_ros_runtime_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def fake_executor(command: list[str], **kwargs: object):
        captured["env"] = kwargs["env"]
        return type("Completed", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    python_root = tmp_path / "ros-python"
    python_root.mkdir()
    monkeypatch.setenv("PYTHONPATH", str(python_root))
    monkeypatch.setattr(
        "rolo.agent_tools.native_tools.shutil.which", lambda value, path=None: value
    )
    runner = AgentNativeRunner(reduced_agent_native_catalog(), executor=fake_executor)

    runner.run("native.os.host.inspect", {"mode": "status"})

    captured_env = captured["env"]
    assert isinstance(captured_env, dict)
    assert "PYTHONPATH" not in captured_env


def test_runner_accepts_explicit_target_runtime_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def fake_executor(command: list[str], **kwargs: object):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return type("Completed", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    target_bin = tmp_path / "bin"
    target_bin.mkdir()
    monkeypatch.setattr(
        "rolo.agent_tools.native_tools.shutil.which",
        lambda value, path=None: value if path and str(target_bin) in path else None,
    )
    runner = AgentNativeRunner([_descriptor("-c", "print('ok')")], executor=fake_executor)

    result = runner.run(
        "test.echo",
        environment={"PATH": str(target_bin), "PYTHONPATH": "/opt/ros/target/python"},
    )

    assert result.status.value == "SUCCEEDED"
    assert captured["command"] == [sys.executable, "-c", "print('ok')"]
    assert captured["env"] == {
        "PATH": str(target_bin),
    }


def test_remote_runner_does_not_require_controller_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def remote_executor(command: list[str], **kwargs: object):
        captured["command"] = command
        captured["environment"] = kwargs["environment"]
        return type("Completed", (), {"returncode": 0, "stdout": "Linux target\n", "stderr": ""})()

    monkeypatch.setattr("rolo.agent_tools.native_tools.shutil.which", lambda *_: None)
    runner = RemoteAgentNativeRunner(
        reduced_agent_native_catalog(),
        executor=remote_executor,
    )

    result = runner.run("native.os.host.inspect", {"mode": "status"})

    assert result.status == NativeToolStatus.SUCCEEDED
    assert captured["command"] == ["uname", "-a"]
    assert captured["environment"] == {}


def test_ros_runner_uses_an_ephemeral_log_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_log_dir: Path | None = None

    def fake_executor(command: list[str], **kwargs: object):
        nonlocal captured_log_dir
        environment = kwargs["env"]
        assert isinstance(environment, dict)
        captured_log_dir = Path(environment["ROS_LOG_DIR"])
        assert captured_log_dir.is_dir()
        return type("Completed", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(
        "rolo.agent_tools.native_tools.shutil.which", lambda value, path=None: value
    )
    runner = AgentNativeRunner(reduced_agent_native_catalog(), executor=fake_executor)

    runner.run("native.middleware.graph.inspect", {"mode": "nodes"})

    assert captured_log_dir is not None
    assert not captured_log_dir.exists()


def test_reduced_catalog_uses_family_tools_with_structured_modes() -> None:
    catalog = reduced_agent_native_catalog()

    assert len(catalog) == 22
    assert len({item.tool_id for item in catalog}) == len(catalog)
    assert "native.os.host.status" not in {item.tool_id for item in catalog}
    host = next(item for item in catalog if item.tool_id == "native.os.host.inspect")
    middleware = next(
        item for item in catalog if item.tool_id == "native.middleware.graph.inspect"
    )
    assert set(host.variants) == {"inventory", "status", "time", "uptime"}
    assert host.variants["status"].argv_template == ["uname", "-a"]
    assert {"PYTHONPATH", "LD_LIBRARY_PATH"}.issubset(middleware.allowed_env_keys)


def test_family_runner_resolves_only_allowlisted_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_executor(command: list[str], **kwargs: object):
        captured["command"] = command
        return type("Completed", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(
        "rolo.agent_tools.native_tools.shutil.which", lambda value, path=None: value
    )
    runner = AgentNativeRunner(reduced_agent_native_catalog(), executor=fake_executor)
    result = runner.run("native.os.process.inspect", {"mode": "inspect", "pid": "42"})

    assert captured["command"] == ["ps", "-p", "42", "-o", "pid,ppid,stat,comm,args"]
    assert result.arguments == {"mode": "inspect", "pid": "42"}
    with pytest.raises(ValueError, match="positive integer"):
        runner.run("native.os.process.inspect", {"mode": "inspect", "pid": "4;2"})
    with pytest.raises(ValueError, match="bounded relative path"):
        runner.run("native.os.file.inspect", {"mode": "read", "path": "../secret"})


def test_reduced_catalog_exposes_only_the_curated_native_surface() -> None:
    catalog = reduced_agent_native_catalog()
    assert len(catalog) == 22
    assert {item.family for item in catalog} == {"hardware", "OS", "Middleware"}
    assert all("native.linux." not in item.tool_id for item in catalog)
    assert all("native.ros." not in item.tool_id for item in catalog)
    assert all(item.access == "read" for item in catalog)

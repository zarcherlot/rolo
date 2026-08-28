import sys

import pytest

from rolo.agent_tools.native_tools import (
    AgentNativeRunner,
    AgentNativeToolDescriptor,
    NativeToolStatus,
    default_agent_native_catalog,
    native_operation_family_map,
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


def test_default_catalog_is_fixed_and_read_only() -> None:
    catalog = default_agent_native_catalog()

    assert [item.tool_id for item in catalog] == [
        "native.hw.inventory.scan",
        "native.linux.host.status",
        "native.linux.process.list",
        "native.ros.node.list",
    ]
    assert all(item.access == "read" for item in catalog)
    assert all(item.argv_template[0] == item.executable for item in catalog)


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


def test_runner_timeout_is_fail_closed() -> None:
    descriptor = _descriptor("-c", "import time; time.sleep(10)")
    result = AgentNativeRunner([descriptor]).run("test.echo")

    assert result.status == NativeToolStatus.TIMEOUT
    assert result.limitations == ["tool execution timed out"]


def test_descriptor_rejects_interpolation_and_unsafe_environment() -> None:
    with pytest.raises(ValueError, match="does not accept interpolation"):
        _descriptor("{user}")
    with pytest.raises(ValueError, match="approved environment"):
        _descriptor("-c", "print('ok')", allowed_env_keys=["PATH"])


def test_reduced_catalog_uses_family_tools_with_structured_modes() -> None:
    catalog = reduced_agent_native_catalog()

    assert len(catalog) == 22
    assert len({item.tool_id for item in catalog}) == len(catalog)
    assert "native.linux.host.status" not in {item.tool_id for item in catalog}
    host = next(item for item in catalog if item.tool_id == "native.linux.host.inspect")
    assert set(host.variants) == {"inventory", "status", "time", "uptime"}
    assert host.variants["status"].argv_template == ["uname", "-a"]


def test_family_runner_resolves_only_allowlisted_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_executor(command: list[str], **kwargs: object):
        captured["command"] = command
        return type("Completed", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    monkeypatch.setattr("rolo.agent_tools.native_tools.shutil.which", lambda value: value)
    runner = AgentNativeRunner(reduced_agent_native_catalog(), executor=fake_executor)
    result = runner.run("native.linux.process.inspect", {"mode": "inspect", "pid": "42"})

    assert captured["command"] == ["ps", "-p", "42", "-o", "pid,ppid,stat,comm,args"]
    assert result.arguments == {"mode": "inspect", "pid": "42"}
    with pytest.raises(ValueError, match="positive integer"):
        runner.run("native.linux.process.inspect", {"mode": "inspect", "pid": "4;2"})
    with pytest.raises(ValueError, match="bounded relative path"):
        runner.run("native.linux.file.inspect", {"mode": "read", "path": "../secret"})


def test_governance_native_operations_have_family_replacements() -> None:
    from rolo.stages.adapt.operation_registry_v2 import RegistryView, build_registry_projection

    operations = build_registry_projection().operations(RegistryView.AGENT_NATIVE)
    mapping = native_operation_family_map(operations)
    family_ids = {item.tool_id for item in reduced_agent_native_catalog()}

    assert len(mapping) == 73
    assert set(mapping.values()).issubset(family_ids)

import sys

import pytest

from rolo.agent_tools.native_tools import (
    AgentNativeRunner,
    AgentNativeToolDescriptor,
    NativeToolStatus,
    default_agent_native_catalog,
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

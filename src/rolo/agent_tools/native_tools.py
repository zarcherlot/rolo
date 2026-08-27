from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NativeToolStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    UNAVAILABLE = "UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


_SAFE_TOOL_ID = re.compile(r"^[a-z][a-z0-9_.-]{1,127}$")
_SECRET = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|credential|cookie|authorization)"
    r"(\s*[=:]\s*|\s+)([^\s,;]+)"
)
_SAFE_ENV_KEYS = {
    "AMENT_PREFIX_PATH",
    "COLCON_PREFIX_PATH",
    "ROS_DISTRO",
    "ROS_DOMAIN_ID",
    "ROS_LOCALHOST_ONLY",
    "RMW_IMPLEMENTATION",
}
_PROCESS_ENV_KEYS = {"COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _redact(value: str) -> str:
    return _SECRET.sub(lambda match: f"{match.group(1)}{match.group(2)}<redacted>", value)


class AgentNativeToolDescriptor(BaseModel):
    """Allowlisted command metadata; this is not a Canonical Operation contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "rolo-agent-native-tool/v1"
    tool_id: str = Field(pattern=_SAFE_TOOL_ID.pattern)
    family: str = Field(min_length=1, max_length=32)
    execution_path: str = Field(pattern=r"^(DIRECT_RUNNER|ROS_CLI)$")
    executable: str = Field(min_length=1, max_length=256)
    argv_template: list[str] = Field(min_length=1, max_length=16)
    access: str = Field(pattern=r"^read$")
    risk: str = Field(pattern=r"^(R0|R1)$")
    max_duration_s: float = Field(gt=0, le=120)
    max_output_bytes: int = Field(gt=0, le=1_000_000)
    evidence_kind: str = Field(min_length=1, max_length=64)
    sensitive: bool = False
    allowed_env_keys: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("argv_template")
    @classmethod
    def require_fixed_argv(cls, value: list[str]) -> list[str]:
        if not value or not value[0] or any("\x00" in item for item in value):
            raise ValueError("argv_template must contain non-empty, NUL-free arguments")
        if any("{" in item or "}" in item for item in value):
            raise ValueError("argv_template does not accept interpolation")
        return value

    @field_validator("allowed_env_keys")
    @classmethod
    def restrict_environment(cls, value: list[str]) -> list[str]:
        if any(item not in _SAFE_ENV_KEYS for item in value):
            raise ValueError("agent-native tools may only forward approved environment keys")
        if len(value) != len(set(value)):
            raise ValueError("allowed_env_keys must be unique")
        return value


class AgentNativeToolResult(BaseModel):
    """Bounded, auditable result returned to the Agent."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "rolo-agent-native-tool-result/v1"
    tool_id: str
    status: NativeToolStatus
    argv: list[str]
    observed_at: datetime
    duration_ms: float = Field(ge=0)
    stdout: str = ""
    stderr: str = ""
    stdout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stderr_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    truncated: bool = False
    evidence_kind: str
    sensitive: bool
    limitations: list[str] = Field(default_factory=list, max_length=32)
    evidence_refs: list[str] = Field(default_factory=list, max_length=64)


CommandExecutor = Callable[..., subprocess.CompletedProcess[str]]


class AgentNativeRunner:
    """Execute only registered, fixed argv read tools with bounded output."""

    def __init__(
        self,
        descriptors: Sequence[AgentNativeToolDescriptor],
        *,
        executor: CommandExecutor | None = None,
    ) -> None:
        by_id = {item.tool_id: item for item in descriptors}
        if len(by_id) != len(descriptors):
            raise ValueError("agent-native tool IDs must be unique")
        self._descriptors = by_id
        self._executor = executor or subprocess.run

    def list_tools(self) -> list[AgentNativeToolDescriptor]:
        return [self._descriptors[key] for key in sorted(self._descriptors)]

    def run(self, tool_id: str) -> AgentNativeToolResult:
        descriptor = self._descriptors.get(tool_id)
        if descriptor is None:
            raise ValueError(f"unknown agent-native tool: {tool_id}")
        argv = list(descriptor.argv_template)
        resolved = shutil.which(descriptor.executable)
        if resolved is None:
            return self._result(
                descriptor,
                argv,
                NativeToolStatus.UNAVAILABLE,
                "",
                "executable not found",
                0,
                ["executable not found"],
            )
        env = {
            key: os.environ[key]
            for key in _PROCESS_ENV_KEYS | set(descriptor.allowed_env_keys)
            if key in os.environ
        }
        started = time.monotonic()
        try:
            completed = self._executor(
                [resolved, *argv[1:]],
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=descriptor.max_duration_s,
                env=env,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return self._result(
                descriptor,
                argv,
                NativeToolStatus.TIMEOUT,
                stdout,
                stderr,
                (time.monotonic() - started) * 1000,
                ["tool execution timed out"],
            )
        except OSError as exc:
            return self._result(
                descriptor,
                argv,
                NativeToolStatus.FAILED,
                "",
                str(exc),
                (time.monotonic() - started) * 1000,
                ["tool execution failed"],
            )
        status = (
            NativeToolStatus.SUCCEEDED
            if completed.returncode == 0
            else NativeToolStatus.FAILED
        )
        limitations = [] if status == NativeToolStatus.SUCCEEDED else [
            f"command exited with return code {completed.returncode}"
        ]
        return self._result(
            descriptor,
            argv,
            status,
            completed.stdout or "",
            completed.stderr or "",
            (time.monotonic() - started) * 1000,
            limitations,
        )

    @staticmethod
    def _result(
        descriptor: AgentNativeToolDescriptor,
        argv: list[str],
        status: NativeToolStatus,
        stdout: str,
        stderr: str,
        duration_ms: float,
        limitations: list[str],
    ) -> AgentNativeToolResult:
        stdout = _redact(stdout)
        stderr = _redact(stderr)
        output_bytes = len(stdout.encode("utf-8")) + len(stderr.encode("utf-8"))
        truncated = output_bytes > descriptor.max_output_bytes
        if truncated:
            stdout_budget = descriptor.max_output_bytes // 2
            stderr_budget = descriptor.max_output_bytes - stdout_budget
            stdout = stdout.encode("utf-8")[:stdout_budget].decode("utf-8", errors="ignore")
            stderr = stderr.encode("utf-8")[:stderr_budget].decode("utf-8", errors="ignore")
            limitations = [*limitations, "tool output exceeded the configured byte limit"]
        return AgentNativeToolResult(
            tool_id=descriptor.tool_id,
            status=status,
            argv=argv,
            observed_at=_utc_now(),
            duration_ms=round(max(duration_ms, 0), 3),
            stdout=stdout,
            stderr=stderr,
            stdout_sha256=hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
            stderr_sha256=hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
            truncated=truncated,
            evidence_kind=descriptor.evidence_kind,
            sensitive=descriptor.sensitive,
            limitations=limitations,
        )


def default_agent_native_catalog() -> list[AgentNativeToolDescriptor]:
    """Return the first read-only Linux/ROS/HW slice; unavailable tools degrade explicitly."""
    descriptors = [
        AgentNativeToolDescriptor(
            tool_id="native.linux.host.status",
            family="linux",
            execution_path="DIRECT_RUNNER",
            executable="uname",
            argv_template=["uname", "-a"],
            access="read",
            risk="R0",
            max_duration_s=8,
            max_output_bytes=64_000,
            evidence_kind="HOST_STATUS",
        ),
        AgentNativeToolDescriptor(
            tool_id="native.linux.process.list",
            family="linux",
            execution_path="DIRECT_RUNNER",
            executable="ps",
            argv_template=["ps", "-eo", "pid,comm,args"],
            access="read",
            risk="R0",
            max_duration_s=8,
            max_output_bytes=200_000,
            evidence_kind="PROCESS_LIST",
        ),
        AgentNativeToolDescriptor(
            tool_id="native.ros.node.list",
            family="ros",
            execution_path="ROS_CLI",
            executable="ros2",
            argv_template=["ros2", "node", "list"],
            access="read",
            risk="R0",
            max_duration_s=8,
            max_output_bytes=200_000,
            evidence_kind="ROS_GRAPH",
            allowed_env_keys=sorted(_SAFE_ENV_KEYS),
        ),
        AgentNativeToolDescriptor(
            tool_id="native.hw.inventory.scan",
            family="hw",
            execution_path="DIRECT_RUNNER",
            executable="lsusb",
            argv_template=["lsusb"],
            access="read",
            risk="R0",
            max_duration_s=8,
            max_output_bytes=100_000,
            evidence_kind="HARDWARE_INVENTORY",
        ),
    ]
    return sorted(descriptors, key=lambda item: item.tool_id)

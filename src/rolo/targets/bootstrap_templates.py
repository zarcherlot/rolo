from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.targets.host_launchers import (
    BOOTSTRAP_DISPATCHER_PATH,
    RUNTIME_LAUNCHER_PATH,
    render_bootstrap_dispatcher,
    render_runtime_launcher,
)

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
_RUNTIME_USER_PATTERN = r"^[a-z_][a-z0-9_-]{0,31}$"
_IDENTIFIER_RE = re.compile(_IDENTIFIER_PATTERN)
_RUNTIME_USER_RE = re.compile(_RUNTIME_USER_PATTERN)
_ABSOLUTE_EXECUTABLE_PATTERN = re.compile(r"^/[A-Za-z0-9._/-]{1,4095}$")
_SHA256_PATTERN = r"^[0-9a-f]{64}$"


def _content_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class TargetHostTemplateBundle(BaseModel):
    """Reviewable host-integration templates; rendering does not install them."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rolo-target-host-template-bundle/v2"] = (
        "rolo-target-host-template-bundle/v2"
    )
    target_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    runtime_user: str = Field(pattern=_RUNTIME_USER_PATTERN)
    robotctl_path: str = Field(min_length=2, max_length=4096)
    agent_port: int = Field(ge=1, le=65535)
    systemd_unit_name: str = Field(pattern=r"^rolo-bootstrap-agentd@[A-Za-z0-9._-]+\.service$")
    systemd_unit: str = Field(min_length=1, max_length=32_768)
    systemd_unit_sha256: str = Field(pattern=_SHA256_PATTERN)
    authorized_keys_options: str = Field(min_length=1, max_length=8192)
    authorized_keys_options_sha256: str = Field(pattern=_SHA256_PATTERN)
    bootstrap_dispatcher_path: Literal[
        "/opt/rolo/libexec/rolo-bootstrap-dispatch"
    ] = BOOTSTRAP_DISPATCHER_PATH
    bootstrap_dispatcher: str = Field(min_length=1, max_length=256_000)
    bootstrap_dispatcher_sha256: str = Field(pattern=_SHA256_PATTERN)
    runtime_launcher_path: Literal["/opt/rolo/bin/robotctl"] = RUNTIME_LAUNCHER_PATH
    runtime_launcher: str = Field(min_length=1, max_length=128_000)
    runtime_launcher_sha256: str = Field(pattern=_SHA256_PATTERN)
    bootstrap_authorized_keys_options: str = Field(min_length=1, max_length=8192)
    bootstrap_authorized_keys_options_sha256: str = Field(pattern=_SHA256_PATTERN)

    @field_validator("robotctl_path")
    @classmethod
    def validate_robotctl_path(cls, value: str) -> str:
        return _validate_robotctl_path(value)

    @model_validator(mode="after")
    def verify_content_binding(self) -> TargetHostTemplateBundle:
        if self.robotctl_path != RUNTIME_LAUNCHER_PATH:
            raise ValueError("target runtime launcher path is not canonical")
        if self.systemd_unit_name != f"rolo-bootstrap-agentd@{self.target_id}.service":
            raise ValueError("target systemd template identity mismatch")
        if _content_sha256(self.systemd_unit) != self.systemd_unit_sha256:
            raise ValueError("target systemd template digest mismatch")
        if (
            _content_sha256(self.authorized_keys_options)
            != self.authorized_keys_options_sha256
        ):
            raise ValueError("target authorized_keys template digest mismatch")
        if _content_sha256(self.bootstrap_dispatcher) != self.bootstrap_dispatcher_sha256:
            raise ValueError("target bootstrap dispatcher digest mismatch")
        if _content_sha256(self.runtime_launcher) != self.runtime_launcher_sha256:
            raise ValueError("target runtime launcher digest mismatch")
        if (
            _content_sha256(self.bootstrap_authorized_keys_options)
            != self.bootstrap_authorized_keys_options_sha256
        ):
            raise ValueError("target bootstrap authorized_keys digest mismatch")
        expected_unit = _render_systemd_unit(
            target_id=self.target_id,
            runtime_user=self.runtime_user,
            robotctl_path=self.robotctl_path,
            agent_port=self.agent_port,
        )
        if self.systemd_unit != expected_unit:
            raise ValueError("target systemd template content is not canonical")
        expected_options = _render_authorized_keys_options(self.robotctl_path)
        if self.authorized_keys_options != expected_options:
            raise ValueError("target authorized_keys template content is not canonical")
        if self.bootstrap_dispatcher != render_bootstrap_dispatcher():
            raise ValueError("target bootstrap dispatcher is not canonical")
        if self.runtime_launcher != render_runtime_launcher():
            raise ValueError("target runtime launcher is not canonical")
        expected_bootstrap_options = _render_bootstrap_authorized_keys_options()
        if self.bootstrap_authorized_keys_options != expected_bootstrap_options:
            raise ValueError("target bootstrap authorized_keys content is not canonical")
        return self


def _validate_robotctl_path(value: str) -> str:
    if not _ABSOLUTE_EXECUTABLE_PATTERN.fullmatch(value):
        raise ValueError("robotctl path must be a simple absolute POSIX path")
    path = PurePosixPath(value)
    if str(path) != value or any(part in {"", ".", ".."} for part in path.parts[1:]):
        raise ValueError("robotctl path must be normalized")
    return value


def _render_systemd_unit(
    *,
    target_id: str,
    runtime_user: str,
    robotctl_path: str,
    agent_port: int,
) -> str:
    return (
        "[Unit]\n"
        f"Description=Rolo bootstrap agent for {target_id}\n"
        "After=network.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"User={runtime_user}\n"
        f"Group={runtime_user}\n"
        "Environment=HOME=/var/lib/rolo\n"
        "StateDirectory=rolo\n"
        "WorkingDirectory=/var/lib/rolo\n"
        f"ExecStart={robotctl_path} bootstrap-agentd --robot {target_id} "
        f"--host 127.0.0.1 --port {agent_port}\n"
        "Restart=on-failure\n"
        "RestartSec=2\n"
        "NoNewPrivileges=true\n"
        "PrivateTmp=true\n"
        "ProtectSystem=strict\n"
        "ProtectHome=true\n"
        "ReadWritePaths=/var/lib/rolo\n"
        "IPAddressDeny=any\n"
        "IPAddressAllow=localhost\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


def _render_authorized_keys_options(robotctl_path: str) -> str:
    return f'restrict,command="{robotctl_path} target-executor dispatch"'


def _render_bootstrap_authorized_keys_options() -> str:
    return f'restrict,command="{BOOTSTRAP_DISPATCHER_PATH}"'


def render_target_host_templates(
    *,
    target_id: str,
    runtime_user: str = "rolo",
    robotctl_path: str = "/opt/rolo/bin/robotctl",
    agent_port: int = 8100,
) -> TargetHostTemplateBundle:
    """Render deterministic least-privilege systemd and OpenSSH fragments."""

    if not _IDENTIFIER_RE.fullmatch(target_id):
        raise ValueError("target id is invalid")
    if not _RUNTIME_USER_RE.fullmatch(runtime_user):
        raise ValueError("target runtime user is invalid")
    robotctl_path = _validate_robotctl_path(robotctl_path)
    if robotctl_path != RUNTIME_LAUNCHER_PATH:
        raise ValueError("target runtime launcher path is fixed")
    if not 1 <= agent_port <= 65535:
        raise ValueError("target agent port must be between 1 and 65535")
    unit_name = f"rolo-bootstrap-agentd@{target_id}.service"
    unit = _render_systemd_unit(
        target_id=target_id,
        runtime_user=runtime_user,
        robotctl_path=robotctl_path,
        agent_port=agent_port,
    )
    authorized_keys_options = _render_authorized_keys_options(robotctl_path)
    bootstrap_dispatcher = render_bootstrap_dispatcher()
    runtime_launcher = render_runtime_launcher()
    bootstrap_authorized_keys_options = _render_bootstrap_authorized_keys_options()
    return TargetHostTemplateBundle(
        target_id=target_id,
        runtime_user=runtime_user,
        robotctl_path=robotctl_path,
        agent_port=agent_port,
        systemd_unit_name=unit_name,
        systemd_unit=unit,
        systemd_unit_sha256=_content_sha256(unit),
        authorized_keys_options=authorized_keys_options,
        authorized_keys_options_sha256=_content_sha256(authorized_keys_options),
        bootstrap_dispatcher=bootstrap_dispatcher,
        bootstrap_dispatcher_sha256=_content_sha256(bootstrap_dispatcher),
        runtime_launcher=runtime_launcher,
        runtime_launcher_sha256=_content_sha256(runtime_launcher),
        bootstrap_authorized_keys_options=bootstrap_authorized_keys_options,
        bootstrap_authorized_keys_options_sha256=_content_sha256(
            bootstrap_authorized_keys_options
        ),
    )

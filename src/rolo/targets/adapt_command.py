from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.targets.command_bus import CommandEnvelope
from rolo.targets.credentials import file_credential_path
from rolo.targets.models import (
    DeploymentCommand,
    DeploymentCommandKind,
    InteractionSurface,
)


def _absolute_path(value: str, *, field_name: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{field_name} must be an absolute controller path")
    return str(path.resolve())


def _target_absolute_path(value: str, *, field_name: str) -> str:
    if any(character in value for character in ("\x00", "\r", "\n")):
        raise ValueError(f"{field_name} contains control characters")
    path = PurePosixPath(value)
    if not path.is_absolute() or "." in path.parts or ".." in path.parts:
        raise ValueError(f"{field_name} must be a normalized absolute target path")
    return str(path)


class AdaptStartParameters(BaseModel):
    """Typed execution parameters with an explicit controller/target path location."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "rolo-adapt-start-parameters/v1", "rolo-adapt-start-parameters/v2"
    ] = (
        "rolo-adapt-start-parameters/v2"
    )
    project_root_location: Literal["CONTROLLER", "TARGET"] = "CONTROLLER"
    project_root: str = Field(min_length=1, max_length=4096)
    urdf_path: str | None = Field(default=None, min_length=1, max_length=4096)
    scratch_root: str | None = Field(default=None, min_length=1, max_length=4096)
    timeout_s: int = Field(ge=1, le=86_400)
    evidence_mode: Literal["local", "remote"] = "local"
    allowed_executables: list[str] = Field(default_factory=list, max_length=64)
    collector_descriptor_path: str | None = Field(default=None, min_length=1, max_length=4096)
    verification_secret_ref: str | None = Field(default=None, min_length=1, max_length=4096)
    ssh_target: str | None = Field(
        default=None,
        min_length=1,
        max_length=253,
        pattern=r"^(?:[A-Za-z0-9_.-]+@)?[A-Za-z0-9_.-]+$",
    )
    known_hosts_path: str | None = Field(default=None, min_length=1, max_length=4096)
    collector_config: str = Field(
        default=".rolo/config/target-evidence-collector.json",
        min_length=1,
        max_length=4096,
        pattern=r"^[/A-Za-z0-9_.-]+$",
    )
    evidence_timeout_s: float = Field(default=45.0, ge=1.0, le=300.0)

    @field_validator("project_root")
    @classmethod
    def validate_project_root(cls, value: str, info: Any) -> str:
        if info.data.get("project_root_location", "CONTROLLER") == "TARGET":
            return _target_absolute_path(value, field_name="project_root")
        return _absolute_path(value, field_name="project_root")

    @field_validator(
        "urdf_path",
        "scratch_root",
        "collector_descriptor_path",
        "known_hosts_path",
    )
    @classmethod
    def validate_controller_paths(cls, value: str | None, info: Any) -> str | None:
        return _absolute_path(value, field_name=info.field_name) if value is not None else None

    @field_validator("allowed_executables")
    @classmethod
    def validate_allowed_executables(cls, values: list[str]) -> list[str]:
        normalized = sorted(
            {_absolute_path(value, field_name="allowed_executables") for value in values}
        )
        if len(normalized) != len(values):
            raise ValueError("allowed_executables must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_remote_inputs(self) -> AdaptStartParameters:
        remote_values = (
            self.collector_descriptor_path,
            self.verification_secret_ref,
            self.ssh_target,
            self.known_hosts_path,
        )
        if self.evidence_mode == "local" and any(value is not None for value in remote_values):
            raise ValueError("local evidence mode does not accept remote collector options")
        if self.evidence_mode == "remote" and self.allowed_executables:
            raise ValueError(
                "remote executable allowlists must be established on the target collector"
            )
        return self

    def canonical_sha256(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def validate_command(self, command: DeploymentCommand) -> None:
        if command.command != DeploymentCommandKind.ADAPT:
            raise ValueError("AdaptStartParameters require an ADAPT command")
        if self.project_root_location == "TARGET":
            matches = command.workspace_root == self.project_root
        else:
            normalized_workspace = (
                command.workspace_root.replace("/", "\\")
                if command.workspace_root
                else ""
            )
            normalized_project = self.project_root.replace("/", "\\")
            matches = normalized_workspace.casefold() == normalized_project.casefold()
        if not matches:
            raise ValueError("ADAPT command workspace does not match bound parameters")


def build_adapt_start_envelope(
    *,
    target_id: str,
    parameters: AdaptStartParameters,
    active_probe: Literal["none", "help", "runtime-readonly"] = "runtime-readonly",
    run_adapter_agent: bool = True,
    requested_by: str = "local-user",
    interaction_surface: InteractionSurface = InteractionSurface.CLI,
) -> CommandEnvelope:
    semantic_seed = json.dumps(
        {
            "active_probe": active_probe,
            "parameters_sha256": parameters.canonical_sha256(),
            "run_adapter_agent": run_adapter_agent,
            "target_id": target_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    idempotency_key = f"adapt-{hashlib.sha256(semantic_seed).hexdigest()[:32]}"
    command = DeploymentCommand(
        command=DeploymentCommandKind.ADAPT,
        target_id=target_id,
        workspace_root=parameters.project_root,
        active_probe=active_probe,
        run_adapter_agent=run_adapter_agent,
        requested_by=requested_by,
        interaction_surface=interaction_surface,
        idempotency_key=idempotency_key,
        parameters_sha256=parameters.canonical_sha256(),
    )
    parameters.validate_command(command)
    return CommandEnvelope(command=command, parameters=parameters)


def render_adapt_start_cli(envelope: CommandEnvelope) -> list[str]:
    envelope.validate()
    if not isinstance(envelope.parameters, AdaptStartParameters):
        raise ValueError("ADAPT canonical CLI requires AdaptStartParameters")
    command = envelope.command
    parameters = envelope.parameters
    parameters.validate_command(command)
    argv = [
        "robotctl",
        "adapt",
        "start",
        "--robot-id",
        command.target_id,
        "--project-root",
        parameters.project_root,
        "--active-probe",
        command.active_probe,
        "--timeout",
        str(parameters.timeout_s),
        "--evidence-mode",
        parameters.evidence_mode,
        "--collector-config",
        parameters.collector_config,
        "--evidence-timeout",
        str(parameters.evidence_timeout_s),
    ]
    if not command.run_adapter_agent:
        argv.append("--discover-only")
    if parameters.urdf_path is not None:
        argv.extend(("--urdf", parameters.urdf_path))
    if parameters.scratch_root is not None:
        argv.extend(("--scratch-root", parameters.scratch_root))
    for executable in parameters.allowed_executables:
        argv.extend(("--allow-executable", executable))
    if parameters.collector_descriptor_path is not None:
        argv.extend(("--collector-descriptor", parameters.collector_descriptor_path))
    if parameters.verification_secret_ref is not None:
        argv.extend(
            ("--verification-secret", str(file_credential_path(parameters.verification_secret_ref)))
        )
    if parameters.ssh_target is not None:
        argv.extend(("--ssh-target", parameters.ssh_target))
    if parameters.known_hosts_path is not None:
        argv.extend(("--known-hosts", parameters.known_hosts_path))
    return argv

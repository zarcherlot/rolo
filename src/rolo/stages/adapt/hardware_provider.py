from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo.adapter_runner import BoundedAdapterRunner


class HardwareEvidenceComponent(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=256)
    source: Literal["hardware_provider"] = "hardware_provider"
    provider_id: str = Field(min_length=1, max_length=256)


class HardwareEvidenceDevice(BaseModel):
    model_config = ConfigDict(extra="allow")

    path: str = Field(min_length=1, max_length=4096)
    category: str | None = Field(default=None, max_length=128)


class HardwareEvidenceProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-hardware-evidence/v1"] = "robot-hardware-evidence/v1"
    robot_id: str
    components: list[HardwareEvidenceComponent] = Field(default_factory=list, max_length=1024)
    devices: list[HardwareEvidenceDevice] = Field(default_factory=list, max_length=1024)
    warnings: list[str] = Field(default_factory=list, max_length=256)


class HardwareEvidenceProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-hardware-evidence-request/v1"] = (
        "robot-hardware-evidence-request/v1"
    )
    robot_id: str
    mode: Literal["READ_ONLY"] = "READ_ONLY"


def collect_hardware_provider_evidence(
    provider_path: Path,
    *,
    robot_id: str,
    timeout_s: float = 15,
) -> HardwareEvidenceProviderResult:
    path = provider_path.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"hardware evidence provider is not a regular file: {path}")
    command = [sys.executable, str(path)] if path.suffix.lower() == ".py" else [str(path)]
    completed = BoundedAdapterRunner().run(
        command,
        stdin=HardwareEvidenceProviderRequest(robot_id=robot_id).model_dump_json(),
        cwd=path.parent,
        timeout_s=timeout_s,
        max_stdout_bytes=1_000_000,
        max_stderr_bytes=200_000,
    )
    if completed.timed_out:
        raise ValueError("hardware evidence provider timed out")
    if completed.output_limited:
        raise ValueError("hardware evidence provider exceeded its output limit")
    if completed.returncode != 0:
        raise ValueError(
            "hardware evidence provider failed with code "
            f"{completed.returncode}: {completed.stderr.strip()[:1000]}"
        )
    try:
        result = HardwareEvidenceProviderResult.model_validate_json(completed.stdout)
    except ValueError as exc:
        raise ValueError(f"hardware evidence provider returned invalid evidence: {exc}") from exc
    if result.robot_id != robot_id:
        raise ValueError("hardware evidence provider robot identity mismatch")
    return result

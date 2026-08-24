from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rolo import __version__
from rolo.core.artifacts import ArtifactStore
from rolo.core.hashing import sha256_file
from rolo.core.models import DiscoveryReport
from rolo.stages.adapt.conformance import (
    latest_adapter_handoff_path,
    validate_adapter_handoff,
)
from rolo.stages.adapt.discovery import load_latest_report
from rolo.stages.adapt.operation_registry import (
    adapter_operation_eligibility,
    canonical_operation_registry,
)
from rolo.stages.adapt.proposal_orchestration import RegistrySnapshot
from rolo.stages.adapt.service import assess_adapt
from rolo.stages.artifact_paths import ArtifactLayout


class AcceptanceRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    contract_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation_count: int = Field(gt=0)


class AcceptanceTargetEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    robot_id: str
    deployment_mode: Literal["local", "remote"]
    collector_id: str
    target_host_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    access: Literal["READ_ONLY"]


class AcceptanceRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    gate_status: Literal["PASSED"]
    gate_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    handoff_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    release_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AdaptAcceptancePack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-adapt-acceptance-pack/v1"] = (
        "robot-adapt-acceptance-pack/v1"
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    robot_id: str
    rolo_version: str
    source_revision: str | None
    status: Literal["COMPLETE", "INCOMPLETE"]
    adapt_status: str
    discovery_id: str
    discovery_status: str
    discovery_mode: str
    registry: AcceptanceRegistry
    target_evidence: AcceptanceTargetEvidence | None
    eligible_operations: list[str]
    deferred_operations: dict[str, str]
    release: AcceptanceRelease | None
    blockers: list[str]


def _source_revision() -> str | None:
    configured = os.environ.get("ROLO_SOURCE_REVISION", "").strip()
    if configured:
        return configured
    root = Path(__file__).resolve().parents[4]
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    revision = completed.stdout.strip()
    return revision if completed.returncode == 0 and len(revision) == 40 else None


def _target_evidence(report: DiscoveryReport) -> AcceptanceTargetEvidence | None:
    probes = report.probes
    for layer in ("linux", "hw", "ros"):
        probe = probes.get(layer)
        binding = probe.data.get("target_evidence") if probe is not None else None
        if isinstance(binding, dict):
            return AcceptanceTargetEvidence(
                robot_id=str(binding.get("robot_id", "")),
                deployment_mode=str(binding.get("deployment_mode", "")),
                collector_id=str(binding.get("collector_id", "")),
                target_host_fingerprint=str(binding.get("target_host_fingerprint", "")),
                bundle_payload_sha256=str(binding.get("bundle_payload_sha256", "")),
                access=str(binding.get("access", "")),
            )
    return None


def build_adapt_acceptance_pack(
    artifact_root: Path,
    output_root: Path,
    robot_id: str,
) -> AdaptAcceptancePack:
    report = load_latest_report(artifact_root, robot_id)
    assessment = assess_adapt(artifact_root, robot_id)
    registry = RegistrySnapshot(canonical_operation_registry())
    eligible, deferred = adapter_operation_eligibility(report)
    blockers = list(assessment.blockers)
    release = None
    handoff_path = ArtifactLayout(artifact_root).stage_latest_index("adapt", robot_id)
    if handoff_path.is_file():
        try:
            handoff = validate_adapter_handoff(
                artifact_root,
                robot_id,
                output_root=output_root,
            )
            latest_handoff = latest_adapter_handoff_path(artifact_root, robot_id)
            release = AcceptanceRelease(
                run_id=handoff.source_agent_run_id,
                gate_status="PASSED",
                gate_report_sha256=handoff.gate_report_sha256,
                handoff_sha256=sha256_file(latest_handoff),
                release_manifest_sha256=handoff.release_manifest_sha256,
            )
        except (OSError, ValueError) as exc:
            blockers.append(f"Latest Adapt release validation failed: {exc}")
    complete = assessment.status.value == "COMPLETE" and release is not None and not blockers
    return AdaptAcceptancePack(
        robot_id=robot_id,
        rolo_version=__version__,
        source_revision=_source_revision(),
        status="COMPLETE" if complete else "INCOMPLETE",
        adapt_status=assessment.status.value,
        discovery_id=report.discovery_id,
        discovery_status=report.status.value,
        discovery_mode=report.discovery_mode,
        registry=AcceptanceRegistry(
            version=registry.registry_version,
            sha256=registry.registry_sha256,
            contract_catalog_sha256=registry.contract_catalog_sha256,
            operation_count=registry.operation_count,
        ),
        target_evidence=_target_evidence(report),
        eligible_operations=sorted(eligible),
        deferred_operations=dict(sorted(deferred.items())),
        release=release,
        blockers=blockers,
    )


def write_adapt_acceptance_pack(
    artifact_root: Path,
    output_root: Path,
    robot_id: str,
    destination: Path | None = None,
) -> tuple[AdaptAcceptancePack, Path, str]:
    pack = build_adapt_acceptance_pack(artifact_root, output_root, robot_id)
    if destination is None:
        relative = f"acceptance/{robot_id}/{pack.discovery_id}.json"
        path = ArtifactStore(artifact_root).write_json(relative, pack.model_dump(mode="json"))
    else:
        path = destination.expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(pack.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return pack, path, sha256_file(path)

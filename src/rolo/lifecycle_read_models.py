from __future__ import annotations

from datetime import datetime
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from rolo.core.hashing import sha256_file
from rolo.core.models import utc_now
from rolo.stages.adapt.conformance import validate_adapter_handoff
from rolo.stages.adapt.models import (
    AdapterAgentRun,
    AdapterHandoff,
    AdaptGateReport,
    AdaptGateStatus,
)
from rolo.stages.artifact_paths import ArtifactLayout
from rolo.stages.contracts import PipelineAssessment, StageName


class LifecycleRunStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    GATED = "GATED"
    UNKNOWN = "UNKNOWN"


class LifecycleGateStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class LifecycleHandoffStatus(str, Enum):
    VERIFIED = "VERIFIED"
    INVALID = "INVALID"
    MISSING = "MISSING"


class LifecycleGateCheck(BaseModel):
    schema_version: Literal["rolo-lifecycle-gate-check/v1"] = (
        "rolo-lifecycle-gate-check/v1"
    )
    check_id: str
    label: str
    status: Literal["PASSED", "FAILED", "UNKNOWN"]
    authority: Literal["OBSERVED", "GATED"]
    evidence_id: str | None = None


class LifecycleArtifactSummary(BaseModel):
    schema_version: Literal["rolo-lifecycle-artifact-summary/v1"] = (
        "rolo-lifecycle-artifact-summary/v1"
    )
    name: str
    kind: Literal["agent_run", "gate", "handoff", "summary"]
    integrity_status: Literal["validated", "verified", "unresolved"]
    evidence_id: str | None = None
    reference_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class LifecycleHandoffSummary(BaseModel):
    schema_version: Literal["rolo-lifecycle-handoff-summary/v1"] = (
        "rolo-lifecycle-handoff-summary/v1"
    )
    status: LifecycleHandoffStatus
    authority: Literal["GATED", "OBSERVED", "NONE"]
    promoted_at: datetime | None = None
    artifact_count: int = Field(ge=0)
    digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    evidence_id: str | None = None
    limitations: list[str] = Field(default_factory=list)


class LifecycleRunSummary(BaseModel):
    schema_version: Literal["rolo-lifecycle-run-summary/v1"] = (
        "rolo-lifecycle-run-summary/v1"
    )
    robot_id: str
    run_id: str
    stage: StageName
    status: LifecycleRunStatus
    gate_status: LifecycleGateStatus
    handoff_status: LifecycleHandoffStatus
    provider: str | None = None
    model: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_s: float | None = Field(default=None, ge=0.0)
    gate_check_count: int = Field(ge=0)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    integrity_status: Literal["validated", "verified", "unresolved"]
    limitations: list[str] = Field(default_factory=list)


class LifecycleRunCollection(BaseModel):
    schema_version: Literal["rolo-lifecycle-run-collection/v1"] = (
        "rolo-lifecycle-run-collection/v1"
    )
    robot_id: str
    items: list[LifecycleRunSummary]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)
    observed_at: datetime
    freshness: Literal["fresh", "unknown"] = "unknown"
    source_kind: Literal["lifecycle_artifacts"] = "lifecycle_artifacts"
    limitations: list[str] = Field(default_factory=list)


class LifecycleRunDetail(BaseModel):
    schema_version: Literal["rolo-lifecycle-run-detail/v1"] = (
        "rolo-lifecycle-run-detail/v1"
    )
    run: LifecycleRunSummary
    gate_checks: list[LifecycleGateCheck]
    handoff: LifecycleHandoffSummary
    artifacts: list[LifecycleArtifactSummary]
    observed_at: datetime
    freshness: Literal["fresh", "unknown"] = "unknown"


class LifecycleEvidenceSpec(BaseModel):
    evidence_id: str
    reference: str
    title: str
    summary: str
    authority: Literal["OBSERVED", "GATED"]
    source_kind: Literal["lifecycle_run", "lifecycle_gate", "lifecycle_handoff"]
    integrity_status: Literal["validated", "verified"]
    observed_at: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    limitations: list[str] = Field(default_factory=list)


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _evidence_id(robot_id: str, reference: str) -> str:
    return f"ev_{_digest(robot_id + chr(0) + reference)[:18]}"


def _artifact_ref(layout: ArtifactLayout, path: Path) -> str:
    return layout.ref(path)


def _read_optional(path: Path, model: type[BaseModel]) -> BaseModel | None:
    if not path.is_file():
        return None
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def _safe_run_roots(
    artifact_root: Path, robot_id: str
) -> tuple[list[tuple[StageName, Path]], list[str]]:
    layout = ArtifactLayout(artifact_root)
    roots: list[tuple[StageName, Path]] = []
    limitations: list[str] = []
    for stage in StageName:
        runs_root = artifact_root / stage.value / robot_id / "runs"
        if not runs_root.is_dir():
            continue
        for candidate in runs_root.iterdir():
            if not candidate.is_dir():
                continue
            try:
                expected = layout.stage_run(stage.value, robot_id, candidate.name)
            except ValueError:
                limitations.append(
                    f"One {stage.value} run has an unsafe identifier and was omitted."
                )
                continue
            if candidate.resolve() != expected.resolve():
                limitations.append(
                    f"One {stage.value} run did not resolve to its canonical location."
                )
                continue
            roots.append((stage, candidate))
    return roots, limitations


def _adapt_detail(
    artifact_root: Path,
    output_root: Path,
    robot_id: str,
    run_root: Path,
    *,
    observed_at: datetime,
) -> LifecycleRunDetail:
    layout = ArtifactLayout(artifact_root)
    run_id = run_root.name
    run_path = run_root / "run.json"
    gate_path = run_root / "gate.json"
    handoff_path = run_root / "handoff.json"
    summary_path = run_root / "summary.json"

    run_model = _read_optional(run_path, AdapterAgentRun)
    gate_model = _read_optional(gate_path, AdaptGateReport)
    handoff_model = _read_optional(handoff_path, AdapterHandoff)
    run = run_model if isinstance(run_model, AdapterAgentRun) else None
    gate = gate_model if isinstance(gate_model, AdaptGateReport) else None
    handoff = handoff_model if isinstance(handoff_model, AdapterHandoff) else None

    if run is not None and (run.robot_id != robot_id or run.run_id != run_id):
        raise ValueError("lifecycle agent run identity mismatch")
    if gate is not None and (gate.robot_id != robot_id or gate.run_id != run_id):
        raise ValueError("lifecycle gate identity mismatch")
    if handoff is not None and (
        handoff.robot_id != robot_id or handoff.source_agent_run_id != run_id
    ):
        raise ValueError("lifecycle handoff identity mismatch")

    handoff_verified = False
    handoff_limitation: list[str] = []
    if handoff is not None:
        try:
            validate_adapter_handoff(
                artifact_root,
                robot_id,
                handoff_path=handoff_path,
                output_root=output_root,
            )
            handoff_verified = True
        except (FileNotFoundError, OSError, ValueError):
            handoff_limitation.append(
                "The handoff is present but its complete hash chain could not be verified."
            )

    run_ref = _artifact_ref(layout, run_path)
    gate_ref = _artifact_ref(layout, gate_path)
    handoff_ref = _artifact_ref(layout, handoff_path)
    run_evidence = _evidence_id(robot_id, run_ref) if run is not None else None
    gate_evidence = _evidence_id(robot_id, gate_ref) if gate is not None else None
    handoff_evidence = _evidence_id(robot_id, handoff_ref) if handoff is not None else None

    if handoff_verified:
        status = LifecycleRunStatus.GATED
    elif gate is not None and gate.status is AdaptGateStatus.FAILED:
        status = LifecycleRunStatus.FAILED
    elif run is not None and run.status.value == "RUNNING":
        status = LifecycleRunStatus.RUNNING
    elif run is not None and run.status.value == "SUCCEEDED":
        status = LifecycleRunStatus.SUCCEEDED
    elif run is not None and run.status.value in {"FAILED", "TIMED_OUT", "CANCELLED"}:
        status = LifecycleRunStatus.FAILED
    else:
        status = LifecycleRunStatus.UNKNOWN

    gate_status = (
        LifecycleGateStatus.PASSED
        if gate is not None and gate.status is AdaptGateStatus.PASSED
        else LifecycleGateStatus.FAILED
        if gate is not None
        else LifecycleGateStatus.NOT_AVAILABLE
    )
    handoff_status = (
        LifecycleHandoffStatus.VERIFIED
        if handoff_verified
        else LifecycleHandoffStatus.INVALID
        if handoff is not None
        else LifecycleHandoffStatus.MISSING
    )
    gate_authority: Literal["OBSERVED", "GATED"] = (
        "GATED" if handoff_verified else "OBSERVED"
    )
    gate_checks = [
        LifecycleGateCheck(
            check_id=f"check_{_digest(run_id + chr(0) + label)[:16]}",
            label=label,
            status="PASSED",
            authority=gate_authority,
            evidence_id=gate_evidence,
        )
        for label in (gate.checks if gate else [])
    ]
    if gate is not None and gate.status is AdaptGateStatus.FAILED:
        gate_checks.append(
            LifecycleGateCheck(
                check_id=f"check_{_digest(run_id + chr(0) + 'gate-result')[:16]}",
                label="Independent Adapt gate result",
                status="FAILED",
                authority="OBSERVED",
                evidence_id=gate_evidence,
            )
        )

    artifacts: list[LifecycleArtifactSummary] = []
    for name, kind, path, evidence_id, integrity in (
        ("Agent run metadata", "agent_run", run_path, run_evidence, "validated"),
        (
            "Independent gate report",
            "gate",
            gate_path,
            gate_evidence,
            "verified" if handoff_verified else "validated",
        ),
        (
            "Adapter handoff",
            "handoff",
            handoff_path,
            handoff_evidence,
            "verified" if handoff_verified else "validated",
        ),
        ("Run summary", "summary", summary_path, None, "validated"),
    ):
        if path.is_file():
            artifacts.append(
                LifecycleArtifactSummary(
                    name=name,
                    kind=kind,
                    integrity_status=integrity,
                    evidence_id=evidence_id,
                    reference_digest=sha256_file(path),
                )
            )

    evidence_ids = [
        value for value in (run_evidence, gate_evidence, handoff_evidence) if value
    ]
    limitations = []
    if run is None:
        limitations.append("Agent execution metadata is unavailable for this run.")
    if gate is None:
        limitations.append("No independent gate report is available.")
    if handoff_status is LifecycleHandoffStatus.MISSING:
        limitations.append("No lifecycle handoff was published.")
    limitations.extend(handoff_limitation)

    summary = LifecycleRunSummary(
        robot_id=robot_id,
        run_id=run_id,
        stage=StageName.PROBE,
        status=status,
        gate_status=gate_status,
        handoff_status=handoff_status,
        provider=run.provider if run else None,
        model=run.model if run else None,
        started_at=run.started_at if run else None,
        completed_at=run.completed_at if run else None,
        duration_s=run.duration_s if run else None,
        gate_check_count=len(gate_checks),
        evidence_ids=evidence_ids,
        confidence=1.0 if handoff_verified else 0.8 if run or gate else 0.3,
        integrity_status=(
            "verified" if handoff_verified else "validated" if run or gate else "unresolved"
        ),
        limitations=limitations,
    )
    return LifecycleRunDetail(
        run=summary,
        gate_checks=gate_checks,
        handoff=LifecycleHandoffSummary(
            status=handoff_status,
            authority="GATED" if handoff_verified else "OBSERVED" if handoff else "NONE",
            promoted_at=handoff.promoted_at if handoff else None,
            artifact_count=len(artifacts),
            digest=sha256_file(handoff_path) if handoff else None,
            evidence_id=handoff_evidence,
            limitations=handoff_limitation,
        ),
        artifacts=artifacts,
        observed_at=observed_at,
    )


def _placeholder_detail(
    robot_id: str,
    stage: StageName,
    run_root: Path,
    *,
    observed_at: datetime,
) -> LifecycleRunDetail:
    summary = LifecycleRunSummary(
        robot_id=robot_id,
        run_id=run_root.name,
        stage=stage,
        status=LifecycleRunStatus.UNKNOWN,
        gate_status=LifecycleGateStatus.NOT_AVAILABLE,
        handoff_status=LifecycleHandoffStatus.MISSING,
        gate_check_count=0,
        confidence=0.2,
        integrity_status="unresolved",
        limitations=[
            f"{stage.value.title()} run artifacts do not yet have a supported read model."
        ],
    )
    return LifecycleRunDetail(
        run=summary,
        gate_checks=[],
        handoff=LifecycleHandoffSummary(
            status=LifecycleHandoffStatus.MISSING,
            authority="NONE",
            artifact_count=0,
            limitations=["No supported handoff model is available for this run."],
        ),
        artifacts=[],
        observed_at=observed_at,
    )


def _detail_for_root(
    artifact_root: Path,
    output_root: Path,
    robot_id: str,
    stage: StageName,
    run_root: Path,
    *,
    observed_at: datetime,
) -> LifecycleRunDetail:
    if stage is StageName.PROBE:
        return _adapt_detail(
            artifact_root,
            output_root,
            robot_id,
            run_root,
            observed_at=observed_at,
        )
    return _placeholder_detail(robot_id, stage, run_root, observed_at=observed_at)


def build_lifecycle_run_collection(
    artifact_root: Path,
    output_root: Path,
    robot_id: str,
    *,
    stage: StageName | None = None,
    status: LifecycleRunStatus | None = None,
    limit: int = 50,
    offset: int = 0,
    pipeline: PipelineAssessment | None = None,
    observed_at: datetime | None = None,
) -> LifecycleRunCollection:
    observed_at = observed_at or utc_now()
    roots, limitations = _safe_run_roots(artifact_root, robot_id)
    items: list[LifecycleRunSummary] = []
    for item_stage, run_root in roots:
        if stage is not None and item_stage is not stage:
            continue
        try:
            detail = _detail_for_root(
                artifact_root,
                output_root,
                robot_id,
                item_stage,
                run_root,
                observed_at=observed_at,
            )
        except (OSError, ValueError):
            limitations.append(
                f"Run {run_root.name} has invalid lifecycle metadata and was omitted."
            )
            continue
        if status is not None and detail.run.status is not status:
            continue
        items.append(detail.run)
    items.sort(
        key=lambda item: (
            item.completed_at or item.started_at or datetime.min.replace(tzinfo=observed_at.tzinfo),
            item.run_id,
        ),
        reverse=True,
    )
    if pipeline is not None and not items:
        limitations.append(
            "Stage assessments are available, but no supported immutable run artifact exists."
        )
    total = len(items)
    return LifecycleRunCollection(
        robot_id=robot_id,
        items=items[offset : offset + limit],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=offset + limit if offset + limit < total else None,
        observed_at=observed_at,
        limitations=limitations,
    )


def get_lifecycle_run_detail(
    artifact_root: Path,
    output_root: Path,
    robot_id: str,
    run_id: str,
    *,
    observed_at: datetime | None = None,
) -> LifecycleRunDetail | None:
    observed_at = observed_at or utc_now()
    matches: list[tuple[StageName, Path]] = []
    for stage in StageName:
        try:
            run_root = ArtifactLayout(artifact_root).stage_run(stage.value, robot_id, run_id)
        except ValueError:
            return None
        if run_root.is_dir():
            matches.append((stage, run_root))
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError("lifecycle run identity is ambiguous across stages")
    stage, run_root = matches[0]
    return _detail_for_root(
        artifact_root,
        output_root,
        robot_id,
        stage,
        run_root,
        observed_at=observed_at,
    )


def lifecycle_evidence_specs(
    artifact_root: Path,
    output_root: Path,
    robot_id: str,
) -> dict[str, LifecycleEvidenceSpec]:
    observed_at = utc_now()
    roots, _ = _safe_run_roots(artifact_root, robot_id)
    specs: dict[str, LifecycleEvidenceSpec] = {}
    layout = ArtifactLayout(artifact_root)
    for stage, run_root in roots:
        if stage is not StageName.PROBE:
            continue
        try:
            detail = _adapt_detail(
                artifact_root,
                output_root,
                robot_id,
                run_root,
                observed_at=observed_at,
            )
        except (OSError, ValueError):
            continue
        verified = detail.run.handoff_status is LifecycleHandoffStatus.VERIFIED
        for name, path, source_kind, authority, summary in (
            (
                "Adapter Agent run metadata",
                run_root / "run.json",
                "lifecycle_run",
                "OBSERVED",
                "Bounded execution metadata for one Adapter Agent run.",
            ),
            (
                "Independent Adapt gate report",
                run_root / "gate.json",
                "lifecycle_gate",
                "GATED" if verified else "OBSERVED",
                "Independent contract, route, and publication gate checks for this run.",
            ),
            (
                "Lifecycle handoff",
                run_root / "handoff.json",
                "lifecycle_handoff",
                "GATED" if verified else "OBSERVED",
                "The immutable handoff that binds discovery, catalog, graph, gate, and release.",
            ),
        ):
            if not path.is_file():
                continue
            reference = layout.ref(path)
            evidence_id = _evidence_id(robot_id, reference)
            is_verified = verified and source_kind in {"lifecycle_gate", "lifecycle_handoff"}
            specs[evidence_id] = LifecycleEvidenceSpec(
                evidence_id=evidence_id,
                reference=reference,
                title=name,
                summary=summary,
                authority=authority,
                source_kind=source_kind,
                integrity_status="verified" if is_verified else "validated",
                observed_at=(
                    detail.run.completed_at or detail.run.started_at or observed_at
                ),
                confidence=1.0 if is_verified else 0.8,
                limitations=(
                    ["This evidence describes lifecycle processing, not physical outcome success."]
                    if is_verified
                    else ["This artifact is not backed by a completely verified handoff chain."]
                ),
            )
    return specs

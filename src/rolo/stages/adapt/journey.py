"""One-command Adapt onboarding built from the existing lifecycle services."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, model_validator

from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings
from rolo.core.models import ProbeResult
from rolo.doctor import build_doctor_report
from rolo.runtime import create_runtime
from rolo.stages.adapt.active_discovery import ActiveDiscoveryInputs, ActiveProbeMode
from rolo.stages.adapt.discovery import DiscoveryService
from rolo.stages.adapt.enrollment import EnrollmentService
from rolo.stages.adapt.models import AdaptPlanStatus
from rolo.stages.adapt.service import AdaptRunService, assess_adapt
from rolo.stages.adapt.target_evidence import (
    EvidenceDeploymentConfig,
    EvidenceDeploymentMode,
    collect_over_ssh,
    collect_target_evidence,
    load_collector_state,
    new_request,
    verify_evidence_bundle,
)
from rolo.stages.artifact_paths import resolve_artifact_ref
from rolo.targets import (
    CollectorEnrollmentPinV4,
    TargetEvidenceCollectionRequestV4,
    TargetExecutionStatus,
    TargetExecutor,
    verify_target_evidence_v4,
)

MAX_PROJECT_DIRECTORIES = 2_000
MAX_PROJECT_DEPTH = 4
MAX_ROOTS_PER_KIND = 32
SKIP_DIRECTORY_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "artifacts",
    "dist",
    "log",
    "node_modules",
    "output",
    "third-party",
    "third_party",
    "vendor",
    "vendors",
    "venv",
}


class ProjectEvidence(BaseModel):
    project_root: Path
    source_roots: list[Path] = Field(default_factory=list)
    build_roots: list[Path] = Field(default_factory=list)
    install_roots: list[Path] = Field(default_factory=list)
    document_roots: list[Path] = Field(default_factory=list)
    launch_roots: list[Path] = Field(default_factory=list)
    truncated: bool = False
    observation_mode: Literal["LOCAL_FILESYSTEM", "TARGET_METADATA"] = (
        "LOCAL_FILESYSTEM"
    )
    target_workspace_manifest_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    target_observed_paths: list[str] = Field(default_factory=list, max_length=256)
    target_project_root: str | None = Field(default=None, min_length=1, max_length=4096)

    @field_serializer("project_root")
    def serialize_project_root(self, value: Path) -> str:
        return self.target_project_root or str(value)

    @model_validator(mode="after")
    def bind_observation_mode(self) -> ProjectEvidence:
        if self.observation_mode == "TARGET_METADATA":
            if self.target_workspace_manifest_sha256 is None:
                raise ValueError("target project evidence requires a manifest digest")
            if self.target_project_root is None:
                raise ValueError("target project evidence requires its target root")
            target_root = PurePosixPath(self.target_project_root)
            if (
                not target_root.is_absolute()
                or "." in target_root.parts
                or ".." in target_root.parts
                or self.project_root.as_posix() != str(target_root)
            ):
                raise ValueError("target project evidence root is not canonical")
            if any(
                (
                    self.source_roots,
                    self.build_roots,
                    self.install_roots,
                    self.document_roots,
                    self.launch_roots,
                )
            ):
                raise ValueError(
                    "target metadata evidence cannot expose target paths as controller roots"
                )
            if self.target_observed_paths != sorted(set(self.target_observed_paths)):
                raise ValueError("target observed paths must be unique and sorted")
            if any(
                PurePosixPath(path).is_absolute()
                or "." in PurePosixPath(path).parts
                or ".." in PurePosixPath(path).parts
                or "\\" in path
                or ":" in path
                for path in self.target_observed_paths
            ):
                raise ValueError("target observed paths must be normalized and relative")
        elif (
            self.target_workspace_manifest_sha256 is not None
            or self.target_observed_paths
            or self.target_project_root is not None
        ):
            raise ValueError("local project evidence cannot contain target metadata binding")
        return self

    def active_inputs(self, active_probe: ActiveProbeMode) -> ActiveDiscoveryInputs:
        return ActiveDiscoveryInputs(
            source_roots=self.source_roots,
            build_roots=self.build_roots,
            install_roots=self.install_roots,
            document_roots=self.document_roots,
            launch_roots=self.launch_roots,
            target_workspace_manifest_sha256=(
                self.target_workspace_manifest_sha256
            ),
            active_probe=active_probe,
        )


class TargetEvidenceJourneySummary(BaseModel):
    schema_version: Literal["robot-adapt-target-evidence/v1"] = (
        "robot-adapt-target-evidence/v1"
    )
    mode: EvidenceDeploymentMode
    collector_id: str
    target_host_fingerprint: str
    bundle_payload_sha256: str
    bundle_path: str
    collected_at: str
    signature_version: Literal["HMAC_V1_V3", "ED25519_V4"] = "HMAC_V1_V3"
    target_id: str | None = None
    descriptor_sha256: str | None = None
    key_id: str | None = None


@dataclass(frozen=True)
class TargetEvidenceV4Deployment:
    mode: EvidenceDeploymentMode
    pin: CollectorEnrollmentPinV4
    executor: TargetExecutor


class AdaptJourneyResult(BaseModel):
    schema_version: Literal["robot-adapt-journey/v2"] = "robot-adapt-journey/v2"
    status: Literal["COMPLETE", "DISCOVERY_COMPLETE", "BLOCKED"]
    robot_id: str
    enrollment: str
    doctor_status: str
    discovery_id: str | None = None
    discovery_status: str | None = None
    adapt_status: str | None = None
    evidence: ProjectEvidence
    wiki: str | None = None
    discovery_artifact: str | None = None
    adapt_artifact: str | None = None
    release_id: str | None = None
    gate: str | None = None
    handoff: str | None = None
    blockers: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    workbench_url: str
    target_evidence: TargetEvidenceJourneySummary | None = None


def _has_root_document(path: Path) -> bool:
    try:
        return any(
            candidate.is_file()
            for pattern in ("README*", "CHANGELOG*", "LICENSE*", "*.md", "*.rst")
            for candidate in path.glob(pattern)
        )
    except OSError:
        return False


def detect_project_evidence(project_root: Path) -> ProjectEvidence:
    """Find conventional primary evidence roots without choosing a URDF for the user."""
    root = project_root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"project root must be an existing directory: {root}")

    build_roots: list[Path] = []
    install_roots: list[Path] = []
    document_roots: list[Path] = [root] if _has_root_document(root) else []
    launch_roots: list[Path] = []
    queue: deque[tuple[Path, int]] = deque([(root, 0)])
    visited = 0
    truncated = False

    while queue:
        current, depth = queue.popleft()
        if depth >= MAX_PROJECT_DEPTH:
            continue
        try:
            children = sorted(
                (
                    path
                    for path in current.iterdir()
                    if path.is_dir() and not path.is_symlink()
                ),
                key=lambda path: path.name.casefold(),
            )
        except OSError:
            continue
        for child in children:
            visited += 1
            if visited > MAX_PROJECT_DIRECTORIES:
                truncated = True
                queue.clear()
                break
            name = child.name.casefold()
            if name in SKIP_DIRECTORY_NAMES or name.startswith("."):
                continue
            if name == "build" and len(build_roots) < MAX_ROOTS_PER_KIND:
                build_roots.append(child.resolve())
                continue
            if name == "install" and len(install_roots) < MAX_ROOTS_PER_KIND:
                install_roots.append(child.resolve())
                continue
            if name in {"doc", "docs", "documentation"}:
                if len(document_roots) < MAX_ROOTS_PER_KIND:
                    document_roots.append(child.resolve())
                continue
            if name == "launch":
                if len(launch_roots) < MAX_ROOTS_PER_KIND:
                    launch_roots.append(child.resolve())
                continue
            queue.append((child, depth + 1))

    return ProjectEvidence(
        project_root=root,
        source_roots=[root],
        build_roots=list(dict.fromkeys(build_roots)),
        install_roots=list(dict.fromkeys(install_roots)),
        document_roots=list(dict.fromkeys(document_roots)),
        launch_roots=list(dict.fromkeys(launch_roots)),
        truncated=truncated,
    )


class AdaptJourneyService:
    """Compose enrollment, readiness, discovery, Wiki, Agent, gate, and release."""

    def __init__(self, settings: Settings, discovery: DiscoveryService) -> None:
        self.settings = settings
        self.discovery = discovery

    def start(
        self,
        *,
        robot_id: str,
        evidence: ProjectEvidence,
        urdf_path: Path | None,
        active_probe: ActiveProbeMode,
        run_agent: bool,
        scratch_root: Path | None,
        timeout_s: int,
        evidence_deployment: EvidenceDeploymentConfig | None = None,
        evidence_v4_deployment: TargetEvidenceV4Deployment | None = None,
        evidence_timeout_s: float = 45.0,
        target_application_probe: ProbeResult | None = None,
        preverified_target_probes: dict[str, ProbeResult] | None = None,
        preverified_target_evidence: TargetEvidenceJourneySummary | None = None,
    ) -> AdaptJourneyResult:
        enrollment = EnrollmentService(config_root=self.settings.rolo_config_dir).enroll(
            robot_id=robot_id
        )
        doctor = build_doctor_report(
            self.settings,
            require_adapter_sandbox=run_agent,
        )
        display_host = (
            "127.0.0.1" if self.settings.rolo_host in {"0.0.0.0", "::"} else self.settings.rolo_host
        )
        workbench_url = f"http://{display_host}:{self.settings.rolo_port}"
        if doctor["status"] != "READY":
            return AdaptJourneyResult(
                status="BLOCKED",
                robot_id=robot_id,
                enrollment=enrollment.status,
                doctor_status=str(doctor["status"]),
                evidence=evidence,
                blockers=[str(item) for item in doctor.get("errors", [])],
                next_steps=["robotctl doctor"],
                workbench_url=workbench_url,
            )

        target_probes = None
        target_evidence = None
        if active_probe == ActiveProbeMode.RUNTIME_READONLY:
            has_preverified = (
                preverified_target_probes is not None
                or preverified_target_evidence is not None
            )
            if has_preverified:
                if (
                    preverified_target_probes is None
                    or preverified_target_evidence is None
                ):
                    raise ValueError(
                        "preverified target evidence requires probes and summary together"
                    )
                if evidence_deployment is not None or evidence_v4_deployment is not None:
                    raise ValueError(
                        "preverified target evidence cannot be combined with collection"
                    )
                target_probes = preverified_target_probes
                target_evidence = preverified_target_evidence
            elif evidence_deployment is None and evidence_v4_deployment is None:
                raise ValueError(
                    "runtime-readonly Adapt journey requires a pinned target "
                    "evidence deployment"
                )
            if evidence_deployment is not None and evidence_v4_deployment is not None:
                raise ValueError(
                    "Adapt journey cannot select legacy and v4 evidence deployments together"
                )
            try:
                if evidence_v4_deployment is not None:
                    request = new_request(
                        robot_id,
                        executable_help_ids=[
                            item.executable_id
                            for item in evidence_v4_deployment.pin.configuration.help_executables
                        ],
                    )
                    collection = evidence_v4_deployment.executor.collect_evidence_v4(
                        TargetEvidenceCollectionRequestV4(
                            request_id=f"evidence-{request.nonce}",
                            target_id=evidence_v4_deployment.pin.descriptor.target_id,
                            evidence_request=request,
                            timeout_s=evidence_timeout_s,
                        )
                    )
                    if (
                        collection.execution_status != TargetExecutionStatus.SUCCEEDED
                        or collection.bundle is None
                    ):
                        code = collection.error_code.value if collection.error_code else "UNKNOWN"
                        raise ValueError(f"v4 target evidence executor failed: {code}")
                    bundle_v4 = collection.bundle
                    target_probes = verify_target_evidence_v4(
                        bundle_v4,
                        pin=evidence_v4_deployment.pin,
                        request=request,
                        deployment_mode=evidence_v4_deployment.mode,
                    )
                    bundle_path = ArtifactStore(self.settings.rolo_artifact_dir).write_text(
                        f"target-evidence/{robot_id}/{request.nonce}.json",
                        bundle_v4.model_dump_json(indent=2) + "\n",
                    )
                    target_evidence = TargetEvidenceJourneySummary(
                        mode=evidence_v4_deployment.mode,
                        collector_id=bundle_v4.collector_id,
                        target_host_fingerprint=bundle_v4.target_host_fingerprint,
                        bundle_payload_sha256=bundle_v4.payload_sha256,
                        bundle_path=str(bundle_path),
                        collected_at=bundle_v4.collected_at.isoformat(),
                        signature_version="ED25519_V4",
                        target_id=bundle_v4.target_id,
                        descriptor_sha256=bundle_v4.descriptor_sha256,
                        key_id=bundle_v4.key_id,
                    )
                elif evidence_deployment is not None:
                    assert evidence_deployment is not None
                    request = new_request(
                        robot_id,
                        executable_help_ids=[
                            item.executable_id
                            for item in evidence_deployment.collector.help_executables
                        ],
                    )
                    if evidence_deployment.mode == EvidenceDeploymentMode.LOCAL:
                        state_path = Path(
                            evidence_deployment.local_collector_state_path or ""
                        )
                        bundle = collect_target_evidence(
                            request,
                            load_collector_state(state_path),
                        )
                    else:
                        bundle = collect_over_ssh(
                            evidence_deployment,
                            request,
                            timeout_s=evidence_timeout_s,
                        )
                    target_probes = verify_evidence_bundle(
                        bundle,
                        deployment=evidence_deployment,
                        request=request,
                    )
                    bundle_path = ArtifactStore(self.settings.rolo_artifact_dir).write_text(
                        f"target-evidence/{robot_id}/{request.nonce}.json",
                        bundle.model_dump_json(indent=2) + "\n",
                    )
                    target_evidence = TargetEvidenceJourneySummary(
                        mode=evidence_deployment.mode,
                        collector_id=bundle.collector_id,
                        target_host_fingerprint=bundle.target_host_fingerprint,
                        bundle_payload_sha256=bundle.payload_sha256,
                        bundle_path=str(bundle_path),
                        collected_at=bundle.collected_at.isoformat(),
                    )
            except (OSError, ValueError) as exc:
                return AdaptJourneyResult(
                    status="BLOCKED",
                    robot_id=robot_id,
                    enrollment=enrollment.status,
                    doctor_status=str(doctor["status"]),
                    evidence=evidence,
                    blockers=[f"Target evidence collection or verification failed: {exc}"],
                    next_steps=[
                        f"robotctl target-evidence collect --robot {robot_id}",
                    ],
                    workbench_url=workbench_url,
                )
        elif (
            preverified_target_probes is not None
            or preverified_target_evidence is not None
        ):
            raise ValueError(
                "preverified target evidence requires active_probe=runtime-readonly"
            )

        runtime = create_runtime(self.settings)
        try:
            robot = runtime.registry.get(robot_id)
        except KeyError as exc:
            raise ValueError(str(exc)) from exc
        report, discovery_artifact = self.discovery.run(
            robot=robot,
            urdf_path=urdf_path,
            active_inputs=evidence.active_inputs(active_probe),
            target_probes=target_probes,
            target_application_probe=target_application_probe,
        )
        wiki = resolve_artifact_ref(self.settings.rolo_artifact_dir, report.review_ref)
        assessment = assess_adapt(self.settings.rolo_artifact_dir, robot_id)
        base = {
            "robot_id": robot_id,
            "enrollment": enrollment.status,
            "doctor_status": str(doctor["status"]),
            "discovery_id": report.discovery_id,
            "discovery_status": report.status.value,
            "adapt_status": assessment.status.value,
            "evidence": evidence,
            "wiki": str(wiki),
            "discovery_artifact": str(discovery_artifact),
            "workbench_url": workbench_url,
            "target_evidence": target_evidence,
        }
        if report.status.value == "FAILED":
            return AdaptJourneyResult(
                status="BLOCKED",
                blockers=["Discovery failed; inspect the persisted report and probe diagnostics."],
                next_steps=[f"robotctl adapt status --robot {robot_id}"],
                **base,
            )
        if not run_agent:
            return AdaptJourneyResult(
                status="DISCOVERY_COMPLETE",
                next_steps=[f"robotctl adapt run --robot {robot_id}", "robotctl serve"],
                **base,
            )

        adapt_service = AdaptRunService(runtime.artifacts, self.settings)
        plan = adapt_service.dry_run(robot_id)
        if plan.status != AdaptPlanStatus.REQUIRES_CODING:
            return AdaptJourneyResult(
                status="BLOCKED",
                blockers=[
                    "No target-observed, gateable operation route is available for Adapter Agent "
                    "promotion."
                ],
                next_steps=[
                    f"robotctl adapt status --robot {robot_id}",
                    f"robotctl adapt operations summary --robot {robot_id}",
                ],
                **base,
            )
        try:
            summary, adapt_artifact = adapt_service.run(
                robot_id=robot_id,
                scratch_root=scratch_root,
                timeout_s=timeout_s,
            )
        except ValueError as exc:
            return AdaptJourneyResult(
                status="BLOCKED",
                blockers=[str(exc)],
                next_steps=[
                    "robotctl adapt agent-config",
                    f"robotctl adapt status --robot {robot_id}",
                ],
                **base,
            )
        return AdaptJourneyResult(
            status="COMPLETE",
            adapt_status="COMPLETE",
            adapt_artifact=str(adapt_artifact),
            release_id=summary.run_id,
            gate=summary.gate_ref,
            handoff=summary.handoff_ref,
            next_steps=["robotctl serve", f"robotctl pipeline-status --robot {robot_id}"],
            **{key: value for key, value in base.items() if key != "adapt_status"},
        )

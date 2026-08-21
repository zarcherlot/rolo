"""One-command Adapt onboarding built from the existing lifecycle services."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from rolo.core.config import Settings
from rolo.doctor import build_doctor_report
from rolo.runtime import create_runtime
from rolo.stages.adapt.active_discovery import ActiveDiscoveryInputs, ActiveProbeMode
from rolo.stages.adapt.discovery import DiscoveryService
from rolo.stages.adapt.enrollment import EnrollmentService
from rolo.stages.adapt.models import AdaptPlanStatus
from rolo.stages.adapt.service import AdaptRunService, assess_adapt
from rolo.stages.artifact_paths import resolve_artifact_ref

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

    def active_inputs(self, active_probe: ActiveProbeMode) -> ActiveDiscoveryInputs:
        return ActiveDiscoveryInputs(
            source_roots=self.source_roots,
            build_roots=self.build_roots,
            install_roots=self.install_roots,
            document_roots=self.document_roots,
            launch_roots=self.launch_roots,
            active_probe=active_probe,
        )


class AdaptJourneyResult(BaseModel):
    schema_version: Literal["robot-adapt-journey/v1"] = "robot-adapt-journey/v1"
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
    ) -> AdaptJourneyResult:
        enrollment = EnrollmentService(config_root=self.settings.rolo_config_dir).enroll(
            robot_id=robot_id
        )
        doctor = build_doctor_report(self.settings)
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

        runtime = create_runtime(self.settings)
        try:
            robot = runtime.registry.get(robot_id)
        except KeyError as exc:
            raise ValueError(str(exc)) from exc
        report, discovery_artifact = self.discovery.run(
            robot=robot,
            urdf_path=urdf_path,
            active_inputs=evidence.active_inputs(active_probe),
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

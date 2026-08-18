"""Read-only direct dependency resolution for discovered standard CLI candidates."""

from __future__ import annotations

import hashlib
import importlib.metadata as importlib_metadata
import os
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field

from rolo.stages.build.active_discovery import ActiveDiscoveryReport


class ResolutionStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"


class CandidateResolutionStatus(str, Enum):
    INSTALLED = "INSTALLED"
    MISSING = "MISSING"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    UNKNOWN = "UNKNOWN"


class SoftwareDiscoveryPolicy(BaseModel):
    """Small, direct-candidate bound; no host package inventory is collected."""

    model_config = ConfigDict(extra="forbid")

    max_candidates: int = Field(default=1_000, gt=0)


class DirectDependencyCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    name: str
    ecosystem: Literal["python", "ros"]
    required: bool = True
    specifiers: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    executable_ids: list[str] = Field(default_factory=list)
    status: CandidateResolutionStatus = CandidateResolutionStatus.UNKNOWN
    resolved_package_id: str | None = None
    resolved_package_name: str | None = None
    installed_version: str | None = None
    reason: str | None = None


class DirectDependencyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-direct-dependency-report/v1"] = (
        "robot-direct-dependency-report/v1"
    )
    discovery_id: str
    status: ResolutionStatus
    omitted_candidate_count: int = Field(default=0, ge=0)
    unresolved_executables: list[str] = Field(default_factory=list)
    counts_by_ecosystem: dict[str, int] = Field(default_factory=dict)
    counts_by_status: dict[str, int] = Field(default_factory=dict)
    candidates: list[DirectDependencyCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime


class SoftwareSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-software-summary/v1"] = "robot-software-summary/v1"
    discovery_id: str
    status: ResolutionStatus
    dependency_report_ref: str = ""
    direct_dependency_count: int = Field(default=0, ge=0)
    installed_dependency_count: int = Field(default=0, ge=0)
    missing_dependency_count: int = Field(default=0, ge=0)
    conflicting_dependency_count: int = Field(default=0, ge=0)
    unknown_dependency_count: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)


def _normalized_candidate_name(ecosystem: str, name: str) -> str:
    if ecosystem == "python":
        return canonicalize_name(name)
    return name.casefold()


def _candidate_id(ecosystem: str, name: str) -> str:
    identity = f"{ecosystem}\0{_normalized_candidate_name(ecosystem, name)}".encode()
    return f"depcand-{hashlib.sha256(identity).hexdigest()[:16]}"


def _version_checked_candidate(
    candidate: DirectDependencyCandidate,
    *,
    package_id: str,
    package_name: str,
    version: str | None,
) -> DirectDependencyCandidate:
    installed = candidate.model_copy(
        update={
            "status": CandidateResolutionStatus.INSTALLED,
            "resolved_package_id": package_id,
            "resolved_package_name": package_name,
            "installed_version": version,
            "reason": None,
        }
    )
    if not candidate.specifiers:
        return installed
    requested = ",".join(candidate.specifiers)
    if not version:
        return installed.model_copy(
            update={
                "status": CandidateResolutionStatus.UNKNOWN,
                "reason": (
                    "installed package version is unavailable; cannot evaluate "
                    f"constraint {requested}"
                ),
            }
        )
    try:
        specifiers = SpecifierSet(requested)
        parsed_version = Version(version)
    except (InvalidSpecifier, InvalidVersion) as exc:
        return installed.model_copy(
            update={
                "status": CandidateResolutionStatus.UNKNOWN,
                "reason": f"cannot compare version {version!r} with {requested!r}: {exc}",
            }
        )
    if not specifiers.contains(parsed_version, prereleases=None):
        return installed.model_copy(
            update={
                "status": CandidateResolutionStatus.VERSION_CONFLICT,
                "reason": (
                    f"installed version {version!r} does not satisfy "
                    f"constraint {requested!r}"
                ),
            }
        )
    return installed


def _python_candidate(
    candidate: DirectDependencyCandidate,
) -> DirectDependencyCandidate:
    try:
        distribution = importlib_metadata.distribution(candidate.name)
    except importlib_metadata.PackageNotFoundError:
        return candidate.model_copy(
            update={
                "status": CandidateResolutionStatus.MISSING,
                "reason": "distribution is absent from the current Python environment",
            }
        )
    except (OSError, ValueError) as exc:
        return candidate.model_copy(
            update={"status": CandidateResolutionStatus.UNKNOWN, "reason": str(exc)}
        )
    package_name = distribution.metadata.get("Name") or candidate.name
    return _version_checked_candidate(
        candidate,
        package_id=f"python:{canonicalize_name(package_name)}",
        package_name=package_name,
        version=distribution.version,
    )


def _ament_prefixes(environment: Mapping[str, str]) -> list[Path]:
    roots: list[Path] = []
    for raw in environment.get("AMENT_PREFIX_PATH", "").split(os.pathsep):
        if not raw:
            continue
        path = Path(raw).expanduser().resolve()
        if path.is_dir() and path not in roots:
            roots.append(path)
        if len(roots) >= 50:
            break
    return roots


def _ros_candidate(
    candidate: DirectDependencyCandidate,
    *,
    prefixes: Sequence[Path],
) -> DirectDependencyCandidate:
    if not prefixes:
        return candidate.model_copy(
            update={
                "status": CandidateResolutionStatus.UNKNOWN,
                "reason": "no readable ament prefixes are available",
            }
        )
    for prefix in prefixes:
        resource = prefix / "share/ament_index/resource_index/packages" / candidate.name
        manifest = prefix / "share" / candidate.name / "package.xml"
        if not resource.is_file() and not manifest.is_file():
            continue
        version: str | None = None
        if manifest.is_file():
            try:
                version = ET.parse(manifest).getroot().findtext("version")
            except (OSError, ET.ParseError):
                version = None
        prefix_id = hashlib.sha256(str(prefix).encode()).hexdigest()[:12]
        return _version_checked_candidate(
            candidate,
            package_id=f"ros:{prefix_id}:{candidate.name}",
            package_name=candidate.name,
            version=version,
        )
    return candidate.model_copy(
        update={
            "status": CandidateResolutionStatus.MISSING,
            "reason": "package is absent from all readable ament prefixes",
        }
    )


class DirectDependencyResolver:
    def __init__(
        self,
        policy: SoftwareDiscoveryPolicy | None = None,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.policy = policy or SoftwareDiscoveryPolicy()
        self.environment = environment if environment is not None else os.environ

    def _candidates(
        self,
        *,
        projects: Sequence[dict[str, Any]],
        active_report: ActiveDiscoveryReport,
    ) -> tuple[list[DirectDependencyCandidate], int]:
        merged: dict[tuple[str, str], dict[str, Any]] = {}

        def add(
            *,
            ecosystem: str,
            name: str,
            required: bool,
            specifier: str | None = None,
            scope: str | None = None,
            evidence_ref: str | None = None,
            executable_id: str | None = None,
        ) -> None:
            normalized_name = name.strip()
            if not normalized_name or ecosystem not in {"python", "ros"}:
                return
            if ecosystem == "python":
                normalized_name = canonicalize_name(normalized_name)
            key = (ecosystem, _normalized_candidate_name(ecosystem, normalized_name))
            item = merged.setdefault(
                key,
                {
                    "name": normalized_name,
                    "ecosystem": ecosystem,
                    "required": False,
                    "specifiers": set(),
                    "scopes": set(),
                    "evidence_refs": set(),
                    "executable_ids": set(),
                },
            )
            item["required"] = item["required"] or required
            if specifier:
                item["specifiers"].add(specifier)
            if scope:
                item["scopes"].add(scope)
            if evidence_ref:
                item["evidence_refs"].add(evidence_ref)
            if executable_id:
                item["executable_ids"].add(executable_id)

        for project in projects:
            for declaration in project.get("dependency_declarations", []):
                if not declaration.get("applicable", True):
                    continue
                add(
                    ecosystem=str(declaration.get("ecosystem", "")),
                    name=str(declaration.get("name", "")),
                    required=bool(declaration.get("required", True)),
                    specifier=declaration.get("specifier"),
                    scope=declaration.get("scope"),
                    evidence_ref=declaration.get("source"),
                )
        for executable in active_report.executables:
            for package in executable.launch_analysis.packages:
                add(
                    ecosystem="ros",
                    name=package,
                    required=True,
                    scope="launch",
                    evidence_ref=(
                        executable.launch_analysis.references[0]
                        if executable.launch_analysis.references
                        else executable.path
                    ),
                    executable_id=executable.executable_id,
                )
        candidates = [
            DirectDependencyCandidate(
                candidate_id=_candidate_id(item["ecosystem"], item["name"]),
                name=item["name"],
                ecosystem=item["ecosystem"],
                required=item["required"],
                specifiers=sorted(item["specifiers"]),
                scopes=sorted(item["scopes"]),
                evidence_refs=sorted(item["evidence_refs"]),
                executable_ids=sorted(item["executable_ids"]),
            )
            for item in merged.values()
        ]
        candidates.sort(key=lambda item: (item.ecosystem, item.name.casefold()))
        omitted = max(0, len(candidates) - self.policy.max_candidates)
        return candidates[: self.policy.max_candidates], omitted

    def resolve(
        self,
        *,
        discovery_id: str,
        projects: Sequence[dict[str, Any]],
        active_report: ActiveDiscoveryReport,
        collected_at: datetime,
    ) -> DirectDependencyReport:
        candidates, omitted = self._candidates(projects=projects, active_report=active_report)
        unresolved_executables = [
            executable.executable_id
            for executable in active_report.executables
            if not any(
                declaration.get("ecosystem") in {"python", "ros"}
                for declaration in executable.source_analysis.dependency_declarations
            )
            and not executable.launch_analysis.packages
        ]
        prefixes = _ament_prefixes(self.environment)
        resolved: list[DirectDependencyCandidate] = []
        for candidate in candidates:
            if candidate.ecosystem == "python":
                resolved.append(_python_candidate(candidate))
            else:
                resolved.append(_ros_candidate(candidate, prefixes=prefixes))
        return self._report(
            discovery_id=discovery_id,
            candidates=resolved,
            omitted=omitted,
            unresolved_executables=unresolved_executables,
            created_at=collected_at,
        )

    @staticmethod
    def _report(
        *,
        discovery_id: str,
        candidates: list[DirectDependencyCandidate],
        omitted: int,
        unresolved_executables: list[str],
        created_at: datetime,
    ) -> DirectDependencyReport:
        counts = Counter(candidate.status.value for candidate in candidates)
        ecosystem_counts = Counter(candidate.ecosystem for candidate in candidates)
        incomplete = bool(unresolved_executables) or omitted > 0 or any(
            candidate.status == CandidateResolutionStatus.UNKNOWN
            for candidate in candidates
        )
        status = ResolutionStatus.PARTIAL if incomplete else ResolutionStatus.SUCCEEDED
        warnings: list[str] = []
        if omitted:
            warnings.append(f"{omitted} relevance candidates exceeded the configured limit")
        if unresolved_executables:
            warnings.append(
                "dependency declarations are unavailable for executables: "
                + ", ".join(unresolved_executables)
            )
        warnings.extend(
            f"{candidate.ecosystem}:{candidate.name}: {candidate.reason or candidate.status.value}"
            for candidate in candidates
            if candidate.status == CandidateResolutionStatus.UNKNOWN
        )
        return DirectDependencyReport(
            discovery_id=discovery_id,
            status=status,
            omitted_candidate_count=omitted,
            unresolved_executables=unresolved_executables,
            counts_by_ecosystem=dict(sorted(ecosystem_counts.items())),
            counts_by_status=dict(sorted(counts.items())),
            candidates=candidates,
            warnings=warnings,
            created_at=created_at,
        )


def build_software_summary(
    *,
    discovery_id: str,
    report: DirectDependencyReport,
    dependency_report_ref: str,
) -> SoftwareSummary:
    required = [candidate for candidate in report.candidates if candidate.required]
    counts = Counter(candidate.status.value for candidate in report.candidates)
    return SoftwareSummary(
        discovery_id=discovery_id,
        status=report.status,
        dependency_report_ref=dependency_report_ref,
        direct_dependency_count=len(report.candidates),
        installed_dependency_count=counts[CandidateResolutionStatus.INSTALLED.value],
        missing_dependency_count=sum(
            candidate.status == CandidateResolutionStatus.MISSING for candidate in required
        ),
        conflicting_dependency_count=sum(
            candidate.status == CandidateResolutionStatus.VERSION_CONFLICT
            for candidate in required
        ),
        unknown_dependency_count=len(report.unresolved_executables)
        + sum(
            candidate.status == CandidateResolutionStatus.UNKNOWN
            for candidate in required
        ),
        warnings=report.warnings,
    )


def enrich_active_report(
    active_report: ActiveDiscoveryReport,
    resolution: DirectDependencyReport,
    *,
    dependency_report_ref: str,
) -> None:
    candidates = resolution.candidates
    declared = list(active_report.dependency_summary.get("declared", []))
    compact_candidates = [
        {
            "candidate_id": candidate.candidate_id,
            "name": candidate.name,
            "ecosystem": candidate.ecosystem,
            "required": candidate.required,
            "status": candidate.status.value,
        }
        for candidate in candidates
    ]

    def ids_with_status(*statuses: CandidateResolutionStatus) -> list[str]:
        accepted = set(statuses)
        return [
            candidate.candidate_id
            for candidate in candidates
            if candidate.required and candidate.status in accepted
        ]

    active_report.dependency_summary = {
        "report_ref": dependency_report_ref,
        "declared": declared,
        "candidates": compact_candidates,
        "required": [candidate.candidate_id for candidate in candidates if candidate.required],
        "installed": ids_with_status(CandidateResolutionStatus.INSTALLED),
        "missing": ids_with_status(CandidateResolutionStatus.MISSING),
        "unknown": ids_with_status(CandidateResolutionStatus.UNKNOWN),
        "conflicting": ids_with_status(CandidateResolutionStatus.VERSION_CONFLICT),
        "unresolved_executables": resolution.unresolved_executables,
    }
    by_key = {
        (
            candidate.ecosystem,
            _normalized_candidate_name(candidate.ecosystem, candidate.name),
        ): candidate
        for candidate in candidates
    }
    for executable in active_report.executables:
        applicable_keys = {
            (
                str(declaration.get("ecosystem", "")),
                _normalized_candidate_name(
                    str(declaration.get("ecosystem", "")),
                    str(declaration.get("name", "")),
                ),
            )
            for declaration in executable.source_analysis.dependency_declarations
        }
        applicable_keys.update(
            ("ros", _normalized_candidate_name("ros", package))
            for package in executable.launch_analysis.packages
        )
        applicable = [by_key[key] for key in sorted(applicable_keys) if key in by_key]
        executable.dependencies["installed"] = [
            candidate.candidate_id
            for candidate in applicable
            if candidate.status == CandidateResolutionStatus.INSTALLED
        ]
        executable.dependencies["missing"] = [
            candidate.candidate_id
            for candidate in applicable
            if candidate.required and candidate.status == CandidateResolutionStatus.MISSING
        ]
        executable.dependencies["unknown"] = [
            candidate.candidate_id
            for candidate in applicable
            if candidate.required
            and candidate.status == CandidateResolutionStatus.UNKNOWN
        ]
        executable.dependencies["version_conflicts"] = [
            candidate.candidate_id
            for candidate in applicable
            if candidate.required
            and candidate.status == CandidateResolutionStatus.VERSION_CONFLICT
        ]
    active_report.global_conflicts = sorted(
        set(active_report.global_conflicts)
        | {
            f"dependency version conflict: {candidate.ecosystem}:{candidate.name}: "
            f"{candidate.reason}"
            for candidate in candidates
            if candidate.required
            and candidate.status == CandidateResolutionStatus.VERSION_CONFLICT
        }
    )
    active_report.unknowns = sorted(
        set(active_report.unknowns)
        | {
            f"dependency resolution unknown: {candidate.ecosystem}:{candidate.name}"
            for candidate in candidates
            if candidate.required and candidate.status == CandidateResolutionStatus.UNKNOWN
        }
        | {
            f"dependency declarations unavailable: {executable_id}"
            for executable_id in resolution.unresolved_executables
        }
    )
    active_report.warnings = sorted(set(active_report.warnings) | set(resolution.warnings))

"""Deterministic, targeted package relevance and dependency resolution."""

from __future__ import annotations

import hashlib
import importlib.metadata as importlib_metadata
import os
import platform
import queue
import re
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field

from rolo.stages.build.active_discovery import ActiveDiscoveryReport
from rolo.stages.build.software_inventory import (
    CollectorStatus,
    DpkgPackageCollector,
    PackageRecord,
    SoftwareInventoryPolicy,
)


class CandidateResolutionStatus(str, Enum):
    INSTALLED = "INSTALLED"
    MISSING = "MISSING"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    UNMANAGED = "UNMANAGED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"


class PackageRelevanceCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    name: str
    ecosystem: Literal["python", "ros", "dpkg", "executable"]
    relevance: Literal["DIRECT"] = "DIRECT"
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


class PackageRelevanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-package-relevance/v1"] = "robot-package-relevance/v1"
    discovery_id: str
    status: CollectorStatus
    complete: bool
    candidate_count: int = Field(ge=0)
    omitted_candidate_count: int = Field(default=0, ge=0)
    installed_count: int = Field(default=0, ge=0)
    missing_count: int = Field(default=0, ge=0)
    conflict_count: int = Field(default=0, ge=0)
    unknown_count: int = Field(default=0, ge=0)
    unmanaged_count: int = Field(default=0, ge=0)
    counts_by_ecosystem: dict[str, int] = Field(default_factory=dict)
    counts_by_status: dict[str, int] = Field(default_factory=dict)
    candidates: list[PackageRelevanceCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime


@dataclass(frozen=True)
class RelevantSoftwareResolution:
    report: PackageRelevanceReport
    records: tuple[PackageRecord, ...]
    ownership_by_executable: dict[str, PackageRelevanceCandidate]


def _normalized_candidate_name(ecosystem: str, name: str) -> str:
    if ecosystem == "python":
        return canonicalize_name(name)
    if ecosystem == "executable":
        return os.path.normcase(name)
    return name.casefold()


def _candidate_id(ecosystem: str, name: str) -> str:
    identity = f"{ecosystem}\0{_normalized_candidate_name(ecosystem, name)}".encode()
    return f"pkgcand-{hashlib.sha256(identity).hexdigest()[:16]}"


def _safe_environment() -> dict[str, str]:
    environment = {"LANG": "C", "LC_ALL": "C"}
    if os.name == "nt":
        for name in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
            if name in os.environ:
                environment[name] = os.environ[name]
    else:
        environment["PATH"] = "/usr/bin:/bin"
    return environment


def _version_checked_candidate(
    candidate: PackageRelevanceCandidate,
    *,
    record: PackageRecord,
) -> PackageRelevanceCandidate:
    """Apply declared Python/ROS version constraints to an installed record."""
    installed = candidate.model_copy(
        update={
            "status": CandidateResolutionStatus.INSTALLED,
            "resolved_package_id": record.package_id,
            "resolved_package_name": record.name,
            "installed_version": record.version,
            "reason": None,
        }
    )
    if not candidate.specifiers:
        return installed
    requested = ",".join(candidate.specifiers)
    if not record.version:
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
    except InvalidSpecifier as exc:
        return installed.model_copy(
            update={
                "status": CandidateResolutionStatus.UNKNOWN,
                "reason": f"invalid version constraint {requested!r}: {exc}",
            }
        )
    try:
        version = Version(record.version)
    except InvalidVersion as exc:
        return installed.model_copy(
            update={
                "status": CandidateResolutionStatus.UNKNOWN,
                "reason": (
                    f"installed version {record.version!r} cannot be compared with "
                    f"constraint {requested!r}: {exc}"
                ),
            }
        )
    if not specifiers.contains(version, prereleases=None):
        return installed.model_copy(
            update={
                "status": CandidateResolutionStatus.VERSION_CONFLICT,
                "reason": (
                    f"installed version {record.version!r} does not satisfy "
                    f"constraint {requested!r}"
                ),
            }
        )
    return installed


def _bounded_command(
    command: Sequence[str],
    *,
    policy: SoftwareInventoryPolicy,
) -> tuple[int | None, bytes, str | None]:
    try:
        process = subprocess.Popen(
            list(command),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_safe_environment(),
            start_new_session=os.name == "posix",
            shell=False,
        )
    except OSError as exc:
        return None, b"", str(exc)
    assert process.stdout is not None
    assert process.stderr is not None
    output_queue: queue.Queue[tuple[str, bytes | OSError | None]] = queue.Queue(
        maxsize=8
    )

    def read_stream(name: str, stream: Any) -> None:
        try:
            for block in iter(lambda: stream.read(8192), b""):
                output_queue.put((name, block))
        except OSError as exc:
            output_queue.put((name, exc))
        finally:
            output_queue.put((name, None))

    for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
        threading.Thread(
            target=read_stream,
            args=(name, stream),
            daemon=True,
        ).start()

    limit = policy.max_targeted_query_output_bytes
    retained_stdout = bytearray()
    retained_stderr = bytearray()
    total = 0
    completed_streams = 0
    deadline = time.monotonic() + policy.targeted_query_timeout_s
    while completed_streams < 2:
        remaining_s = deadline - time.monotonic()
        if remaining_s <= 0:
            DpkgPackageCollector._terminate(process)
            return None, bytes(retained_stdout), (
                f"targeted package query exceeded {policy.targeted_query_timeout_s:g} seconds"
            )
        try:
            stream_name, item = output_queue.get(timeout=min(remaining_s, 0.1))
        except queue.Empty:
            continue
        if item is None:
            completed_streams += 1
            continue
        if isinstance(item, OSError):
            DpkgPackageCollector._terminate(process)
            return None, bytes(retained_stdout), str(item)
        total += len(item)
        retained = retained_stdout if stream_name == "stdout" else retained_stderr
        remaining_bytes = max(
            0,
            limit - len(retained_stdout) - len(retained_stderr),
        )
        retained.extend(item[:remaining_bytes])
        if total > limit:
            DpkgPackageCollector._terminate(process)
            return None, bytes(retained_stdout), (
                f"targeted package query output exceeded {limit} bytes"
            )
    try:
        returncode = process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired) as exc:
        DpkgPackageCollector._terminate(process)
        return None, bytes(retained_stdout), str(exc)
    diagnostic = retained_stderr.decode("utf-8", errors="replace").strip() or None
    return returncode, bytes(retained_stdout), diagnostic


def _python_record(
    candidate: PackageRelevanceCandidate,
    *,
    collected_at: datetime,
) -> tuple[PackageRelevanceCandidate, PackageRecord | None]:
    try:
        distribution = importlib_metadata.distribution(candidate.name)
    except importlib_metadata.PackageNotFoundError:
        return (
            candidate.model_copy(
                update={
                    "status": CandidateResolutionStatus.MISSING,
                    "reason": "distribution is absent from the current Python environment",
                }
            ),
            None,
        )
    except (OSError, ValueError) as exc:
        return (
            candidate.model_copy(
                update={"status": CandidateResolutionStatus.UNKNOWN, "reason": str(exc)}
            ),
            None,
        )
    canonical_name = distribution.metadata.get("Name") or candidate.name
    try:
        install_root = str(Path(distribution.locate_file("")).resolve())
    except (OSError, TypeError):
        install_root = None
    record = PackageRecord(
        package_id=f"python:{canonicalize_name(canonical_name)}",
        name=canonical_name,
        version=distribution.version,
        architecture=platform.machine().lower() or None,
        status="installed",
        manager="python",
        install_root=install_root,
        collector="python.metadata",
        collector_provenance="importlib.metadata",
        collected_at=collected_at,
    )
    return _version_checked_candidate(candidate, record=record), record


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


def _ros_record(
    candidate: PackageRelevanceCandidate,
    *,
    prefixes: Sequence[Path],
    collected_at: datetime,
) -> tuple[PackageRelevanceCandidate, PackageRecord | None]:
    if not prefixes:
        return (
            candidate.model_copy(
                update={
                    "status": CandidateResolutionStatus.UNKNOWN,
                    "reason": "no readable ament prefixes are available",
                }
            ),
            None,
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
        record = PackageRecord(
            package_id=(
                f"ros:{hashlib.sha256(str(prefix).encode()).hexdigest()[:12]}:"
                f"{candidate.name}"
            ),
            name=candidate.name,
            version=version,
            architecture=platform.machine().lower() or None,
            status="installed",
            manager="ros",
            install_root=str(prefix),
            collector="ros.ament",
            collector_provenance="ament-index-static",
            collected_at=collected_at,
        )
        return _version_checked_candidate(candidate, record=record), record
    return (
        candidate.model_copy(
            update={
                "status": CandidateResolutionStatus.MISSING,
                "reason": "package is absent from all readable ament prefixes",
            }
        ),
        None,
    )


def _dpkg_metadata(
    package_name: str,
    *,
    executable: Path,
    policy: SoftwareInventoryPolicy,
    collected_at: datetime,
) -> tuple[PackageRecord | None, str | None, bool]:
    command = [
        str(executable),
        "-W",
        "-f=${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n",
        "--",
        package_name,
    ]
    returncode, stdout, error = _bounded_command(command, policy=policy)
    if returncode != 0 or not stdout:
        return (
            None,
            error or f"dpkg-query metadata lookup exited with {returncode}",
            returncode == 1,
        )
    try:
        record = DpkgPackageCollector._parse_line(
            stdout.splitlines(keepends=True)[0], collected_at
        )
        return record, None, False
    except ValueError as exc:
        return None, str(exc), False


def _executable_owner(
    candidate: PackageRelevanceCandidate,
    *,
    executable: Path | None,
    policy: SoftwareInventoryPolicy,
    collected_at: datetime,
) -> tuple[PackageRelevanceCandidate, PackageRecord | None]:
    if platform.system() != "Linux":
        return (
            candidate.model_copy(
                update={
                    "status": CandidateResolutionStatus.NOT_APPLICABLE,
                    "reason": "dpkg ownership is not applicable on this host",
                }
            ),
            None,
        )
    if executable is None:
        return (
            candidate.model_copy(
                update={
                    "status": CandidateResolutionStatus.UNKNOWN,
                    "reason": "trusted /usr/bin/dpkg-query was not found",
                }
            ),
            None,
        )
    returncode, stdout, error = _bounded_command(
        [str(executable), "-S", "--", candidate.name],
        policy=policy,
    )
    if returncode == 1 and not stdout:
        return (
            candidate.model_copy(
                update={
                    "status": CandidateResolutionStatus.UNMANAGED,
                    "reason": "no dpkg package owns this executable path",
                }
            ),
            None,
        )
    if returncode != 0:
        return (
            candidate.model_copy(
                update={
                    "status": CandidateResolutionStatus.UNKNOWN,
                    "reason": error or f"dpkg-query ownership lookup exited with {returncode}",
                }
            ),
            None,
        )
    owners: set[str] = set()
    for line in stdout.decode("utf-8", errors="replace").splitlines():
        prefix, separator, _ = line.partition(": ")
        if not separator:
            continue
        owners.update(
            owner
            for owner in (part.strip() for part in prefix.split(","))
            if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9+_.:-]*", owner)
        )
    if not owners:
        return (
            candidate.model_copy(
                update={
                    "status": CandidateResolutionStatus.UNKNOWN,
                    "reason": "dpkg-query returned no parseable package owner",
                }
            ),
            None,
        )
    owner = sorted(owners)[0]
    record, metadata_error, _ = _dpkg_metadata(
        owner,
        executable=executable,
        policy=policy,
        collected_at=collected_at,
    )
    if record is None:
        return (
            candidate.model_copy(
                update={
                    "status": CandidateResolutionStatus.UNKNOWN,
                    "reason": metadata_error,
                }
            ),
            None,
        )
    reason = f"multiple owners found; selected {owner}" if len(owners) > 1 else None
    return (
        candidate.model_copy(
            update={
                "status": CandidateResolutionStatus.INSTALLED,
                "resolved_package_id": record.package_id,
                "resolved_package_name": record.name,
                "installed_version": record.version,
                "reason": reason,
            }
        ),
        record,
    )


class RelevantSoftwareResolver:
    def __init__(
        self,
        policy: SoftwareInventoryPolicy,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.policy = policy
        self.environment = environment if environment is not None else os.environ

    def _candidates(
        self,
        *,
        projects: Sequence[dict[str, Any]],
        active_report: ActiveDiscoveryReport,
    ) -> tuple[list[PackageRelevanceCandidate], int]:
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
            if not normalized_name:
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
                ecosystem = declaration.get("ecosystem")
                if ecosystem not in {"python", "ros", "dpkg"}:
                    continue
                add(
                    ecosystem=ecosystem,
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
            if executable.path:
                add(
                    ecosystem="executable",
                    name=executable.path,
                    required=False,
                    scope="ownership",
                    evidence_ref=executable.path,
                    executable_id=executable.executable_id,
                )
        candidates = [
            PackageRelevanceCandidate(
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
        omitted = max(0, len(candidates) - self.policy.max_relevant_candidates)
        return candidates[: self.policy.max_relevant_candidates], omitted

    def resolve(
        self,
        *,
        discovery_id: str,
        projects: Sequence[dict[str, Any]],
        active_report: ActiveDiscoveryReport,
        collected_at: datetime,
        enabled: bool,
    ) -> RelevantSoftwareResolution:
        candidates, omitted = self._candidates(projects=projects, active_report=active_report)
        if not enabled:
            blocked = [
                candidate.model_copy(
                    update={
                        "status": CandidateResolutionStatus.BLOCKED_BY_POLICY,
                        "reason": "software relevance queries were disabled by policy",
                    }
                )
                for candidate in candidates
            ]
            report = self._report(
                discovery_id=discovery_id,
                candidates=blocked,
                omitted=omitted,
                created_at=collected_at,
                forced_status=CollectorStatus.BLOCKED_BY_POLICY,
            )
            return RelevantSoftwareResolution(report, (), {})

        prefixes = _ament_prefixes(self.environment)
        dpkg_executable = DpkgPackageCollector._trusted_executable()
        resolved: list[PackageRelevanceCandidate] = []
        records: dict[str, PackageRecord] = {}
        ownership: dict[str, PackageRelevanceCandidate] = {}
        ownership_queries = 0
        for candidate in candidates:
            record: PackageRecord | None
            if candidate.ecosystem == "python":
                result, record = _python_record(candidate, collected_at=collected_at)
            elif candidate.ecosystem == "ros":
                result, record = _ros_record(
                    candidate,
                    prefixes=prefixes,
                    collected_at=collected_at,
                )
            elif candidate.ecosystem == "executable":
                if ownership_queries >= self.policy.max_ownership_queries:
                    result = candidate.model_copy(
                        update={
                            "status": CandidateResolutionStatus.BLOCKED_BY_POLICY,
                            "reason": (
                                "per-run executable ownership query limit reached: "
                                f"{self.policy.max_ownership_queries}"
                            ),
                        }
                    )
                    record = None
                else:
                    ownership_queries += 1
                    result, record = _executable_owner(
                        candidate,
                        executable=dpkg_executable,
                        policy=self.policy,
                        collected_at=collected_at,
                    )
                for executable_id in candidate.executable_ids:
                    ownership[executable_id] = result
            else:
                if dpkg_executable is None or platform.system() != "Linux":
                    result = candidate.model_copy(
                        update={
                            "status": CandidateResolutionStatus.UNKNOWN,
                            "reason": "trusted dpkg-query is unavailable",
                        }
                    )
                    record = None
                else:
                    record, error, not_found = _dpkg_metadata(
                        candidate.name,
                        executable=dpkg_executable,
                        policy=self.policy,
                        collected_at=collected_at,
                    )
                    result = candidate.model_copy(
                        update={
                            "status": (
                                CandidateResolutionStatus.INSTALLED
                                if record
                                else CandidateResolutionStatus.MISSING
                                if not_found
                                else CandidateResolutionStatus.UNKNOWN
                            ),
                            "resolved_package_id": record.package_id if record else None,
                            "resolved_package_name": record.name if record else None,
                            "installed_version": record.version if record else None,
                            "reason": error,
                        }
                    )
            resolved.append(result)
            if record is not None:
                records[record.package_id] = record
        report = self._report(
            discovery_id=discovery_id,
            candidates=resolved,
            omitted=omitted,
            created_at=collected_at,
        )
        return RelevantSoftwareResolution(
            report=report,
            records=tuple(records[key] for key in sorted(records)),
            ownership_by_executable=ownership,
        )

    @staticmethod
    def _report(
        *,
        discovery_id: str,
        candidates: list[PackageRelevanceCandidate],
        omitted: int,
        created_at: datetime,
        forced_status: CollectorStatus | None = None,
    ) -> PackageRelevanceReport:
        counts = Counter(candidate.status.value for candidate in candidates)
        ecosystem_counts = Counter(candidate.ecosystem for candidate in candidates)
        incomplete = omitted > 0 or any(
            candidate.status
            in {
                CandidateResolutionStatus.UNKNOWN,
                CandidateResolutionStatus.BLOCKED_BY_POLICY,
            }
            for candidate in candidates
        )
        status = forced_status or (
            CollectorStatus.PARTIAL if incomplete else CollectorStatus.SUCCEEDED
        )
        warnings: list[str] = []
        if omitted:
            warnings.append(f"{omitted} relevance candidates exceeded the configured limit")
        warnings.extend(
            f"{candidate.ecosystem}:{candidate.name}: {candidate.reason or candidate.status.value}"
            for candidate in candidates
            if candidate.status
            in {
                CandidateResolutionStatus.UNKNOWN,
                CandidateResolutionStatus.BLOCKED_BY_POLICY,
            }
        )
        return PackageRelevanceReport(
            discovery_id=discovery_id,
            status=status,
            complete=status == CollectorStatus.SUCCEEDED,
            candidate_count=len(candidates),
            omitted_candidate_count=omitted,
            installed_count=counts[CandidateResolutionStatus.INSTALLED.value],
            missing_count=counts[CandidateResolutionStatus.MISSING.value],
            conflict_count=counts[CandidateResolutionStatus.VERSION_CONFLICT.value],
            unknown_count=counts[CandidateResolutionStatus.UNKNOWN.value],
            unmanaged_count=counts[CandidateResolutionStatus.UNMANAGED.value],
            counts_by_ecosystem=dict(sorted(ecosystem_counts.items())),
            counts_by_status=dict(sorted(counts.items())),
            candidates=candidates,
            warnings=warnings,
            created_at=created_at,
        )


def enrich_active_report(
    active_report: ActiveDiscoveryReport,
    resolution: RelevantSoftwareResolution,
) -> None:
    candidates = resolution.report.candidates
    dependency_candidates = [
        candidate for candidate in candidates if candidate.ecosystem != "executable"
    ]
    active_report.dependency_summary = {
        "required": [
            candidate.model_dump(mode="json")
            for candidate in dependency_candidates
            if candidate.required
        ],
        "resolved": [
            candidate.model_dump(mode="json")
            for candidate in dependency_candidates
            if candidate.status == CandidateResolutionStatus.INSTALLED
        ],
        "missing": [
            candidate.model_dump(mode="json")
            for candidate in dependency_candidates
            if candidate.required and candidate.status == CandidateResolutionStatus.MISSING
        ],
        "unknown": [
            candidate.model_dump(mode="json")
            for candidate in dependency_candidates
            if candidate.required
            and candidate.status
            in {
                CandidateResolutionStatus.UNKNOWN,
                CandidateResolutionStatus.BLOCKED_BY_POLICY,
            }
        ],
        "conflicting": [],
        "installation_plan_ref": None,
    }
    active_report.dependency_summary["conflicting"] = [
        candidate.model_dump(mode="json")
        for candidate in dependency_candidates
        if candidate.required
        and candidate.status == CandidateResolutionStatus.VERSION_CONFLICT
    ]
    by_key = {
        (
            candidate.ecosystem,
            _normalized_candidate_name(candidate.ecosystem, candidate.name),
        ): candidate
        for candidate in candidates
    }
    for executable in active_report.executables:
        owner = resolution.ownership_by_executable.get(executable.executable_id)
        if owner is not None:
            executable.package_ownership = {
                "manager": "dpkg" if owner.status == CandidateResolutionStatus.INSTALLED else None,
                "package": owner.resolved_package_name,
                "package_id": owner.resolved_package_id,
                "version": owner.installed_version,
                "status": owner.status.value,
                "reason": owner.reason,
            }
        applicable_keys = {
            (
                declaration.get("ecosystem"),
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
        applicable = [
            by_key[key]
            for key in sorted(applicable_keys)
            if key in by_key
        ]
        executable.dependencies["resolved"] = [
            candidate.model_dump(mode="json")
            for candidate in applicable
            if candidate.status == CandidateResolutionStatus.INSTALLED
        ]
        executable.dependencies["missing"] = [
            candidate.model_dump(mode="json")
            for candidate in applicable
            if candidate.required and candidate.status == CandidateResolutionStatus.MISSING
        ]
        executable.dependencies["unknown"] = [
            candidate.model_dump(mode="json")
            for candidate in applicable
            if candidate.required
            and candidate.status
            in {
                CandidateResolutionStatus.UNKNOWN,
                CandidateResolutionStatus.BLOCKED_BY_POLICY,
            }
        ]
        executable.dependencies["version_conflicts"] = [
            candidate.model_dump(mode="json")
            for candidate in applicable
            if candidate.required
            and candidate.status == CandidateResolutionStatus.VERSION_CONFLICT
        ]
    active_report.global_conflicts = sorted(
        set(active_report.global_conflicts)
        | {
            f"dependency version conflict: {candidate.ecosystem}:{candidate.name}: "
            f"{candidate.reason}"
            for candidate in dependency_candidates
            if candidate.required
            and candidate.status == CandidateResolutionStatus.VERSION_CONFLICT
        }
    )
    active_report.unknowns = sorted(
        set(active_report.unknowns)
        | {
            f"dependency resolution unknown: {candidate.ecosystem}:{candidate.name}"
            for candidate in dependency_candidates
            if candidate.required
            and candidate.status
            in {
                CandidateResolutionStatus.UNKNOWN,
                CandidateResolutionStatus.BLOCKED_BY_POLICY,
            }
        }
    )
    active_report.warnings = sorted(
        set(active_report.warnings) | set(resolution.report.warnings)
    )

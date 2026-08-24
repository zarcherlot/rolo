"""Bounded, explicitly unverified insights for the engineer-facing robot Wiki."""

from __future__ import annotations

import json
import re
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rolo.core.models import DiscoveryReport
from rolo.stages.adapt.active_discovery import ActiveDiscoveryReport, ExecutableDiscovery
from rolo.stages.adapt.agent_contracts import AgentArtifactProvenance
from rolo.stages.adapt.wiki_context import ros_evidence_relevant

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SEMVER_PATTERN = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"


class WikiHeuristicFinding(BaseModel):
    """One advisory inference that can never replace discovered machine evidence."""

    model_config = ConfigDict(extra="forbid")

    category: Literal["SAFETY", "ARCHITECTURE", "HARDWARE", "OPERATIONS", "MAINTENANCE"]
    statement: str = Field(min_length=1, max_length=500)
    confidence: Literal["LOW", "MEDIUM"]
    basis: list[str] = Field(min_length=1, max_length=8)
    verification: str = Field(min_length=1, max_length=500)
    source: Literal["DETERMINISTIC_RULE", "ADAPT_AGENT_SKILL"] = "DETERMINISTIC_RULE"


class RoloDeterministicWikiFinding(WikiHeuristicFinding):
    """Built-in finding retained inside a new-writer bundle without Agent authorship."""

    source: Literal["DETERMINISTIC_RULE"] = "DETERMINISTIC_RULE"


class RoloWikiHeuristicFinding(WikiHeuristicFinding):
    """Traceable new-writer finding; legacy readers keep their original shape."""

    source: Literal["ADAPT_AGENT_SKILL"] = "ADAPT_AGENT_SKILL"
    insight_type: Literal[
        "DISCOVERY_PATH",
        "FAILURE_MODE",
        "OPERATION_MAPPING",
        "ADAPTER_CONSTRAINT",
        "KNOWN_LIMITATION",
        "REVERIFICATION_CONDITION",
        "VERSION_DIFFERENCE",
    ] | None = None
    counter_evidence_refs: list[str] = Field(default_factory=list, max_length=8)
    previous_version_difference: str | None = Field(default=None, min_length=1, max_length=500)
    author_skill_version: str = Field(pattern=_SEMVER_PATTERN)

    @field_validator("basis", "counter_evidence_refs")
    @classmethod
    def validate_unique_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Wiki evidence references must be unique")
        return value


class WikiUnknownAssessment(BaseModel):
    """Advisory review of one exact machine-reported unknown."""

    model_config = ConfigDict(extra="forbid")

    unknown: str = Field(min_length=1, max_length=500)
    classification: Literal[
        "COLLECTED_EVIDENCE_REVIEW",
        "TARGET_PROBE_REQUIRED",
        "EXTERNAL_INPUT_REQUIRED",
        "INSUFFICIENT_EVIDENCE",
    ]
    assessment: str = Field(min_length=1, max_length=500)
    confidence: Literal["LOW", "MEDIUM"]
    basis: list[str] = Field(min_length=1, max_length=8)
    next_step: str = Field(min_length=1, max_length=500)
    source: Literal["DETERMINISTIC_RULE", "ADAPT_AGENT_SKILL"] = "DETERMINISTIC_RULE"


class RoloWikiUnknownAssessment(WikiUnknownAssessment):
    """Traceable new-writer assessment of an exact deterministic unknown."""

    source: Literal["ADAPT_AGENT_SKILL"] = "ADAPT_AGENT_SKILL"
    author_skill_version: str = Field(pattern=_SEMVER_PATTERN)

    @field_validator("basis")
    @classmethod
    def validate_unique_basis(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Wiki evidence references must be unique")
        return value


class WikiInsightBundle(BaseModel):
    """Skill-shaped output contract for optional, non-authoritative Wiki enrichment."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-wiki-insights/v1"] = "robot-wiki-insights/v1"
    robot_id: str
    discovery_id: str
    findings: list[WikiHeuristicFinding] = Field(default_factory=list, max_length=40)
    unknown_assessments: list[WikiUnknownAssessment] = Field(
        default_factory=list,
        max_length=100,
    )


class RoloWikiInsightBundle(WikiInsightBundle):
    """New-writer contract; the wider base model remains the legacy read boundary."""

    schema_version: Literal["rolo-wiki-insights/v1"] = "rolo-wiki-insights/v1"
    robot_id: str = Field(min_length=1, max_length=128)
    discovery_id: str = Field(min_length=1, max_length=128)
    target_fingerprint_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    release_id: str | None = Field(default=None, min_length=1, max_length=128)
    conformance_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    previous_wiki_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    findings: list[RoloWikiHeuristicFinding | RoloDeterministicWikiFinding] = Field(
        default_factory=list,
        max_length=40,
    )
    unknown_assessments: list[RoloWikiUnknownAssessment] = Field(
        default_factory=list,
        max_length=100,
    )
    provenance: AgentArtifactProvenance

    @model_validator(mode="after")
    def validate_writer_provenance(self) -> RoloWikiInsightBundle:
        if self.provenance.skill_name != "rolo-wiki-authoring":
            raise ValueError("Wiki writer provenance must identify rolo-wiki-authoring")
        if not self.provenance.input_artifact_sha256:
            raise ValueError("Wiki writer provenance requires input artifact hashes")
        authored_versions = [
            item.author_skill_version
            for item in self.findings
            if isinstance(item, RoloWikiHeuristicFinding)
        ]
        authored_versions.extend(item.author_skill_version for item in self.unknown_assessments)
        if any(version != self.provenance.skill_version for version in authored_versions):
            raise ValueError("Wiki insight author versions must match bundle provenance")
        return self


class RoloWikiValidationContext(BaseModel):
    """Caller-owned identities and references accepted for one Wiki Agent run."""

    model_config = ConfigDict(extra="forbid")

    input_artifact_sha256: dict[str, str] = Field(min_length=1, max_length=64)
    allowed_evidence_refs: frozenset[str] = Field(min_length=1, max_length=20_000)
    target_fingerprint_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    release_id: str | None = Field(default=None, min_length=1, max_length=128)
    conformance_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)

    @field_validator("input_artifact_sha256")
    @classmethod
    def validate_input_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        for name, digest in value.items():
            if not name or len(name) > 160:
                raise ValueError("input artifact names must contain 1-160 characters")
            if not re.fullmatch(_SHA256_PATTERN, digest):
                raise ValueError("input artifact hashes must be lowercase SHA-256")
        return value


def validate_rolo_wiki_insights(
    bundle: RoloWikiInsightBundle,
    context: RoloWikiValidationContext,
) -> None:
    """Reject stale identities, fabricated provenance and unresolvable evidence references."""

    if bundle.provenance.input_artifact_sha256 != context.input_artifact_sha256:
        raise ValueError("Wiki writer input artifact identity does not match caller context")
    actual_identity = (
        bundle.target_fingerprint_sha256,
        bundle.release_id,
        bundle.conformance_sha256,
    )
    expected_identity = (
        context.target_fingerprint_sha256,
        context.release_id,
        context.conformance_sha256,
    )
    if actual_identity != expected_identity:
        raise ValueError("Wiki writer target/release/conformance identity mismatch")
    refs = {
        ref
        for finding in bundle.findings
        if isinstance(finding, RoloWikiHeuristicFinding)
        for ref in [*finding.basis, *finding.counter_evidence_refs]
    }
    refs.update(ref for item in bundle.unknown_assessments for ref in item.basis)
    unknown_refs = sorted(refs - context.allowed_evidence_refs)
    if unknown_refs:
        raise ValueError(
            "Wiki writer references evidence outside the caller allowlist: "
            + ", ".join(unknown_refs[:3])
        )


def parse_wiki_insight_bundle_json(value: str) -> WikiInsightBundle | RoloWikiInsightBundle:
    """Read either migration-cycle artifact while keeping new writers on the Rolo contract."""

    payload = json.loads(value)
    if isinstance(payload, dict) and payload.get("schema_version") == "rolo-wiki-insights/v1":
        return RoloWikiInsightBundle.model_validate_json(value)
    return WikiInsightBundle.model_validate_json(value)


class WikiInsightProvider(Protocol):
    """Optional Adapt Agent skill or other bounded heuristic provider."""

    provider: str

    def infer(
        self,
        report: DiscoveryReport,
        active: ActiveDiscoveryReport,
    ) -> WikiInsightBundle: ...

    def validation_context(
        self,
        report: DiscoveryReport,
        active: ActiveDiscoveryReport,
    ) -> RoloWikiValidationContext: ...


_MOTION_CUES = (
    "cmd_vel",
    "actuator",
    "joint",
    "servo",
    "gripper",
    "trajectory",
    "motor",
    "move",
    "teleop",
)


def _names(executable: ExecutableDiscovery) -> list[str]:
    values: list[str] = []
    ros = executable.communication.ros
    for role in ("publishers", "subscribers", "services", "actions"):
        for item in ros.get(role, []):
            value = item.get("name") if isinstance(item, dict) else item
            if value:
                values.append(str(value))
    return values


def has_motion_cue(executable: ExecutableDiscovery) -> bool:
    searchable = "\n".join(
        [
            executable.name,
            executable.path or "",
            *_names(executable),
            *executable.communication.network.get("protocols", []),
        ]
    ).casefold()
    return any(cue in searchable for cue in _MOTION_CUES)


def infer_builtin_wiki_insights(
    report: DiscoveryReport,
    active: ActiveDiscoveryReport,
) -> WikiInsightBundle:
    """Create conservative findings from already-collected evidence only."""
    findings: list[WikiHeuristicFinding] = []
    ros_probe = report.probes.get("ros")
    ros_data = ros_probe.data if ros_probe else {}
    if ros_evidence_relevant(report, active) and not ros_data.get("nodes"):
        findings.append(
            WikiHeuristicFinding(
                category="ARCHITECTURE",
                statement="本次没有观测到在线 ROS 节点，静态接口不能视为运行拓扑。",
                confidence="MEDIUM",
                basis=["ROS probe returned no online nodes"],
                verification="在正确的 ROS 环境、RMW 和 Domain ID 下启动系统后重新执行只读探测。",
            )
        )

    suspicious: list[str] = []
    for executable in active.executables:
        names = _names(executable)
        unique = set(names)
        duplicate_count = len(names) - len(unique)
        if len(names) >= 20 and (duplicate_count >= 5 or len(unique) >= 15):
            suspicious.append(executable.name)
    if suspicious:
        findings.append(
            WikiHeuristicFinding(
                category="ARCHITECTURE",
                statement=(
                    "部分程序关联了异常多或高度重复的接口，可能存在跨文件聚合或静态误归属："
                    + ", ".join(sorted(set(suspicious))[:8])
                ),
                confidence="MEDIUM",
                basis=["static interface count and duplicate ratio"],
                verification="按源文件、符号、构建 target 和运行节点重新关联接口，并与在线图核对。",
            )
        )

    unsafe_false_negatives = [
        executable.name
        for executable in active.executables
        if has_motion_cue(executable)
        and executable.safety.get("motion_possible") is False
    ]
    if unsafe_false_negatives:
        findings.append(
            WikiHeuristicFinding(
                category="SAFETY",
                statement=(
                    "发现运动相关接口或命名，但程序被标记为不可运动；在确认前按可能运动处理："
                    + ", ".join(sorted(set(unsafe_false_negatives))[:8])
                ),
                confidence="MEDIUM",
                basis=["motion-related endpoint/name", "motion_possible=false"],
                verification="审查发布方向和控制调用，在受控环境中验证实际副作用与失联行为。",
            )
        )

    hardware = report.probes.get("hw")
    devices = hardware.data.get("devices", []) if hardware else []
    internal_video = [
        item
        for item in devices
        if isinstance(item, dict)
        and any(
            token in str(item.get("driver", item.get("model", ""))).casefold()
            for token in ("pispbe", "rpivid")
        )
    ]
    if internal_video:
        findings.append(
            WikiHeuristicFinding(
                category="HARDWARE",
                statement=(
                    f"{len(internal_video)} 个 video 节点看起来属于 ISP/编解码流水线，"
                    "不能按相同数量计为物理摄像头。"
                ),
                confidence="MEDIUM",
                basis=["kernel driver names contain pispbe/rpivid"],
                verification="通过 media graph、udev、VID/PID、序列号和业务配置确认物理相机映射。",
            )
        )

    return WikiInsightBundle(
        robot_id=report.robot_id,
        discovery_id=report.discovery_id,
        findings=findings,
    )


def merge_wiki_insights(
    report: DiscoveryReport,
    active: ActiveDiscoveryReport,
    external: WikiInsightBundle | RoloWikiInsightBundle | None,
) -> WikiInsightBundle | RoloWikiInsightBundle:
    """Merge optional skill output without allowing it to target another discovery."""
    builtin = infer_builtin_wiki_insights(report, active)
    if external is None:
        return builtin
    if external.robot_id != report.robot_id or external.discovery_id != report.discovery_id:
        raise ValueError("Wiki insight bundle does not match the discovery")
    reported_unknowns = set(active.unknowns)
    invalid_unknowns = [
        item.unknown
        for item in external.unknown_assessments
        if item.unknown not in reported_unknowns
    ]
    if invalid_unknowns:
        raise ValueError(
            "Wiki insight bundle references unknowns not present in active discovery: "
            + ", ".join(invalid_unknowns[:3])
        )
    if isinstance(external, RoloWikiInsightBundle):
        unique_rolo: dict[
            tuple[str, str],
            WikiHeuristicFinding | RoloWikiHeuristicFinding | RoloDeterministicWikiFinding,
        ] = {
            (item.category, item.statement): item for item in builtin.findings
        }
        for item in external.findings:
            unique_rolo.setdefault((item.category, item.statement), item)
        unique_unknowns = {item.unknown: item for item in external.unknown_assessments}
        return RoloWikiInsightBundle.model_validate(
            external.model_dump(mode="json")
            | {
                "findings": [
                    item.model_dump(mode="json") for item in list(unique_rolo.values())[:40]
                ],
                "unknown_assessments": [
                    item.model_dump(mode="json")
                    for item in list(unique_unknowns.values())[:100]
                ],
            }
        )
    unique: dict[tuple[str, str], WikiHeuristicFinding] = {}
    for finding in [*builtin.findings, *external.findings]:
        unique[(finding.category, finding.statement)] = finding
    unknown_assessments = {
        item.unknown: item for item in external.unknown_assessments
    }
    merged_findings = list(unique.values())[:40]
    merged_unknowns = list(unknown_assessments.values())[:100]
    return builtin.model_copy(
        update={
            "findings": merged_findings,
            "unknown_assessments": merged_unknowns,
        }
    )


def collect_wiki_insights(
    report: DiscoveryReport,
    active: ActiveDiscoveryReport,
    provider: WikiInsightProvider | None,
) -> tuple[WikiInsightBundle | RoloWikiInsightBundle, str | None]:
    """Run optional skill enrichment without making discovery depend on it."""
    if provider is None:
        return infer_builtin_wiki_insights(report, active), None
    try:
        external = provider.infer(report, active)
        if isinstance(external, RoloWikiInsightBundle):
            context_factory = getattr(provider, "validation_context", None)
            if not callable(context_factory):
                raise ValueError("Rolo Wiki provider did not supply a validation context")
            validate_rolo_wiki_insights(external, context_factory(report, active))
        return merge_wiki_insights(report, active, external), None
    except Exception as exc:
        return infer_builtin_wiki_insights(report, active), str(exc)[:500]

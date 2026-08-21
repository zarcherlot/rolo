"""Bounded, explicitly unverified insights for the engineer-facing robot Wiki."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from rolo.core.models import DiscoveryReport
from rolo.stages.adapt.active_discovery import ActiveDiscoveryReport, ExecutableDiscovery


class WikiHeuristicFinding(BaseModel):
    """One advisory inference that can never replace discovered machine evidence."""

    model_config = ConfigDict(extra="forbid")

    category: Literal["SAFETY", "ARCHITECTURE", "HARDWARE", "OPERATIONS", "MAINTENANCE"]
    statement: str = Field(min_length=1, max_length=500)
    confidence: Literal["LOW", "MEDIUM"]
    basis: list[str] = Field(min_length=1, max_length=8)
    verification: str = Field(min_length=1, max_length=500)
    source: Literal["DETERMINISTIC_RULE", "ADAPT_AGENT_SKILL"] = "DETERMINISTIC_RULE"


class WikiInsightBundle(BaseModel):
    """Skill-shaped output contract for optional, non-authoritative Wiki enrichment."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["robot-wiki-insights/v1"] = "robot-wiki-insights/v1"
    robot_id: str
    discovery_id: str
    findings: list[WikiHeuristicFinding] = Field(default_factory=list, max_length=40)


class WikiInsightProvider(Protocol):
    """Optional Adapt Agent skill or other bounded heuristic provider."""

    provider: str

    def infer(
        self,
        report: DiscoveryReport,
        active: ActiveDiscoveryReport,
    ) -> WikiInsightBundle: ...


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
    if not ros_data.get("nodes"):
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
    external: WikiInsightBundle | None,
) -> WikiInsightBundle:
    """Merge optional skill output without allowing it to target another discovery."""
    builtin = infer_builtin_wiki_insights(report, active)
    if external is None:
        return builtin
    if external.robot_id != report.robot_id or external.discovery_id != report.discovery_id:
        raise ValueError("Wiki insight bundle does not match the discovery")
    unique: dict[tuple[str, str], WikiHeuristicFinding] = {}
    for finding in [*builtin.findings, *external.findings]:
        unique[(finding.category, finding.statement)] = finding
    return builtin.model_copy(update={"findings": list(unique.values())[:40]})


def collect_wiki_insights(
    report: DiscoveryReport,
    active: ActiveDiscoveryReport,
    provider: WikiInsightProvider | None,
) -> tuple[WikiInsightBundle, str | None]:
    """Run optional skill enrichment without making discovery depend on it."""
    if provider is None:
        return infer_builtin_wiki_insights(report, active), None
    try:
        external = provider.infer(report, active)
        return merge_wiki_insights(report, active, external), None
    except Exception as exc:
        return infer_builtin_wiki_insights(report, active), str(exc)[:500]

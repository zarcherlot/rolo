from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable
from typing import Any

from rolo.core.models import DiscoveryReport
from rolo.stages.adapt.active_discovery import ActiveDiscoveryReport, ExecutableDiscovery
from rolo.stages.adapt.operation_registry import canonical_operation_registry
from rolo.stages.adapt.routes import probe_routes
from rolo.stages.adapt.wiki_context import ros_evidence_relevant
from rolo.stages.adapt.wiki_diff import WikiDiscoveryDiff, build_wiki_discovery_diff
from rolo.stages.adapt.wiki_insights import (
    WikiInsightBundle,
    has_motion_cue,
    merge_wiki_insights,
)

MAX_PRIMARY_APPLICATIONS = 80
MAX_STATIC_GRAPH_EDGES = 40

_INTERNAL_DEVICE_TOKENS = ("pispbe", "rpivid", "isp", "codec", "v4l2loopback")


def _text(value: Any) -> str:
    rendered = "unknown" if value is None or value == "" else str(value)
    return rendered.replace("|", "\\|").replace("`", "'").replace("\n", " ")


def _items(values: Iterable[Any], *, limit: int = 8) -> str:
    all_values = list(values)
    rendered = [_text(value) for value in all_values[:limit]]
    if len(all_values) > limit:
        rendered.append(f"另有 {len(all_values) - limit} 项")
    return ", ".join(rendered) or "未获取"


def _unique(values: Iterable[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _names(values: Iterable[Any]) -> list[str]:
    names: list[str] = []
    for value in values:
        if isinstance(value, dict):
            value = value.get("name") or value.get("path") or value.get("endpoint")
        if value not in (None, ""):
            names.append(str(value))
    return list(dict.fromkeys(names))


def _named(values: Iterable[Any], *, limit: int = 8) -> str:
    return _items(_names(values), limit=limit)


def _compact_paths(values: Iterable[str], *, limit: int = 5) -> str:
    rendered = []
    for value in _unique(values):
        parts = str(value).replace("\\", "/").split("/")
        rendered.append("/".join(parts[-3:]))
    return _items(rendered, limit=limit)


def _number(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, list):
        return "[" + ", ".join(_number(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{key}: {_number(item)}" for key, item in value.items()) + "}"
    return _text(value)


def _meters(value: Any) -> str:
    if value is None or value == "":
        return "未获取"
    if isinstance(value, list):
        return " × ".join(f"{float(item) * 1000:g}" for item in value) + " mm"
    return f"{float(value) * 1000:g} mm"


def _device_endpoint_groups(devices: Iterable[Any]) -> list[dict[str, Any]]:
    """Group OS endpoints only when stable topology supports the grouping."""
    physical: dict[str, list[str]] = {}
    internal: list[str] = []
    unresolved: list[str] = []
    for raw in devices:
        if not isinstance(raw, dict):
            unresolved.append(str(raw))
            continue
        endpoint = str(raw.get("path") or raw.get("name") or "unidentified")
        driver_text = " ".join(
            str(raw.get(field, "")) for field in ("driver", "model", "name")
        ).casefold()
        if any(token in driver_text for token in _INTERNAL_DEVICE_TOKENS):
            internal.append(endpoint)
            continue
        serial = raw.get("serial")
        topology = raw.get("id_path") or raw.get("bus_path") or raw.get("physical_path")
        vendor = raw.get("vendor_id")
        product = raw.get("product_id")
        if serial:
            key = f"serial:{serial}"
        elif topology:
            key = f"path:{topology}"
        elif vendor and product:
            key = f"usb:{vendor}:{product}:{endpoint}"
        else:
            unresolved.append(endpoint)
            continue
        physical.setdefault(key, []).append(endpoint)
    groups = [
        {"classification": "物理设备候选", "identity": key, "endpoints": sorted(values)}
        for key, values in sorted(physical.items())
    ]
    if internal:
        groups.append(
            {
                "classification": "内部流水线端点",
                "identity": "driver/model heuristic",
                "endpoints": sorted(internal),
            }
        )
    if unresolved:
        groups.append(
            {
                "classification": "未归并端点",
                "identity": "缺少序列号或稳定拓扑",
                "endpoints": sorted(unresolved),
            }
        )
    return groups


def _append_discovery_diff(lines: list[str], diff: WikiDiscoveryDiff) -> None:
    lines.extend(["## 与上次发现的差异", ""])
    if diff.status == "NO_BASELINE":
        lines.extend(["尚无可验证的同机器人基线；本次结果将作为后续比较基线。", ""])
        return
    lines.extend(
        [
            f"- 对比基线：`{_text(diff.baseline_discovery_id)}`",
            f"- 结论：`{_text(diff.status)}`",
            "",
        ]
    )
    if not diff.changes:
        lines.extend(["工程关注字段未发现变化。", ""])
        return
    lines.extend(["| 类别 | 新增 | 移除 |", "|---|---|---|"])
    for change in diff.changes:
        lines.append(
            f"| {_text(change.category)} | {_items(change.added, limit=5)} | "
            f"{_items(change.removed, limit=5)} |"
        )
    lines.append("")


def _is_missing(value: Any) -> bool:
    return value is None or value == "" or str(value).casefold() in {
        "unknown",
        "unresolved",
        "none",
        "not_probed",
        "unavailable",
    }


def _is_support_artifact(executable: ExecutableDiscovery) -> bool:
    name = executable.name.casefold()
    path = (executable.path or "").replace("\\", "/").casefold()
    if name == "a.out" or name.startswith("cmakedeterminecompilerabi_"):
        return True
    if name.endswith(".ps1") and executable.origin == "DISCOVERED_BUILD_ARTIFACT":
        return True
    if "rosidl_" in name or "rosidl_generator" in path:
        return True
    return "/cmakefiles/" in path


def _application_score(executable: ExecutableDiscovery) -> int:
    score = 0
    if executable.origin == "EXPLICIT":
        score += 100
    if executable.launch_analysis.available:
        score += 80
    if executable.origin in {"SOURCE_DECLARED", "LAUNCH_DECLARED"}:
        score += 60
    if executable.invocation.entrypoint:
        score += 30
    if executable.communication.network.get("protocols"):
        score += 20
    if executable.communication.ipc or executable.communication.hardware_bus:
        score += 20
    if any(executable.communication.ros.get(role) for role in ("publishers", "subscribers")):
        score += 20
    if executable.communication.ros.get("services") or executable.communication.ros.get("actions"):
        score += 20
    if executable.documentation_analysis.available:
        score += 10
    return score


def _primary_applications(
    executables: Iterable[ExecutableDiscovery],
) -> tuple[list[ExecutableDiscovery], list[ExecutableDiscovery]]:
    primary: list[tuple[int, ExecutableDiscovery]] = []
    support: list[ExecutableDiscovery] = []
    for executable in executables:
        score = _application_score(executable)
        if _is_support_artifact(executable) or score == 0:
            support.append(executable)
        else:
            primary.append((score, executable))
    ordered = [
        executable
        for _, executable in sorted(
            primary,
            key=lambda item: (-item[0], item[1].name.casefold(), item[1].executable_id),
        )
    ]
    return ordered[:MAX_PRIMARY_APPLICATIONS], [*support, *ordered[MAX_PRIMARY_APPLICATIONS:]]


def _ros_interfaces(executable: ExecutableDiscovery) -> tuple[list[str], list[str]]:
    ros = executable.communication.ros
    outgoing = _names([*ros.get("publishers", []), *ros.get("services", [])])
    incoming = _names([*ros.get("subscribers", []), *ros.get("actions", [])])
    return outgoing, incoming


def _application_risk(executable: ExecutableDiscovery) -> str:
    declared = str(executable.safety.get("risk", "未评估"))
    motion = executable.safety.get("motion_possible")
    if has_motion_cue(executable) and motion is not True:
        return "需安全复核（发现运动线索）"
    if motion is True:
        return f"{declared}；可能运动"
    return declared


def _interface_quality(executable: ExecutableDiscovery) -> str:
    ros = executable.communication.ros
    roles = ("publishers", "subscribers", "services", "actions")
    values = [name for role in roles for name in _names(ros.get(role, []))]
    raw_count = sum(len(ros.get(role, [])) for role in roles)
    if raw_count >= 20 and (raw_count - len(set(values)) >= 5 or len(values) >= 15):
        return "疑似聚合，需复核"
    if any(
        isinstance(item, dict) and item.get("name_source") == "SYMBOLIC_EXPRESSION"
        for role in roles
        for item in ros.get(role, [])
    ):
        return f"静态/{executable.communication.confidence.value}（含符号候选）"
    return f"静态/{executable.communication.confidence.value}"


def _compatibility_text(
    compatibility: dict[str, Any],
    critical_unknowns: list[str],
) -> str:
    status = compatibility.get("status")
    if str(status).upper() == "MATCH" and critical_unknowns:
        return "未发现明确冲突；关键项未获取，不能确认完全兼容"
    if _is_missing(status):
        return "未评估"
    return str(status)


def _critical_unknowns(
    expected: dict[str, Any],
    geometry: dict[str, Any],
    ros_data: dict[str, Any],
    *,
    ros_relevant: bool,
) -> list[str]:
    values = {
        "底盘驱动模型": expected.get("platform", {}).get("drive_model"),
        "最大线速度": geometry.get("hard_max_linear_velocity_mps"),
        "最大角速度": geometry.get("hard_max_angular_velocity_radps"),
    }
    if ros_relevant:
        values.update(
            {
                "ROS 发行版": ros_data.get("ros_distro"),
                "RMW": ros_data.get("rmw"),
                "ROS Domain ID": ros_data.get("domain_id"),
            }
        )
    return [name for name, value in values.items() if _is_missing(value)]


def _unknown_category(value: str) -> str:
    lowered = value.casefold()
    if "dependency declaration" in lowered or "executable" in lowered:
        return "可通过构建/源码补采"
    if any(token in lowered for token in ("runtime", "online", "topic", "node", "ros graph")):
        return "需启动后观测"
    if any(token in lowered for token in ("geometry", "drive_model", "semantic")):
        return "可启发式推断，需确认"
    return "需人工或外部资料"


def _summarize_warning(value: str) -> str:
    executable_ids = re.findall(r"exe-\d+", value)
    if executable_ids:
        prefix = value.split(":", 1)[0]
        return f"{prefix}：{len(set(executable_ids))} 个程序（完整列表见机器报告）"
    return value if len(value) <= 300 else value[:297] + "..."


def _mermaid_label(value: Any) -> str:
    return _text(value).replace('"', "'").replace("[", "(").replace("]", ")")


def _append_operation_catalog(lines: list[str], report: DiscoveryReport) -> None:
    lines.extend(
        [
            "## 工程操作候选",
            "",
            "> 这里只展示本机发现到的 canonical operation 候选，不展示完整产品 registry。",
            "> 候选表示“可能适用”，不表示已绑定、可调用或已验证；运动类操作在验证前按高风险处理。",
            "",
        ]
    )
    if not report.operation_candidates:
        lines.extend(["本次没有发现工程操作候选。", ""])
        return
    definitions = {item.operation: item for item in canonical_operation_registry().operations}
    lines.extend(
        [
            "| 操作 | 工程含义 | 访问/风险 | 发现依据 | 状态 |",
            "|---|---|---|---|---|",
        ]
    )
    for candidate in sorted(report.operation_candidates, key=lambda item: item.operation):
        definition = definitions.get(candidate.operation)
        access = definition.access if definition else "未定义"
        risk = definition.risk if definition else "未评估"
        description = definition.description if definition else "未在产品 registry 中定义"
        endpoints = _names(item.endpoint for item in candidate.route_evidence)
        basis = endpoints or candidate.semantic_bindings or candidate.evidence
        lines.append(
            f"| `{_text(candidate.operation)}` | {_text(description)} | "
            f"{_text(access)}/{_text(risk)} | {_items(basis, limit=4)} | "
            "发现但未验证 |"
        )
    lines.append("")


def _append_hardware_details(
    lines: list[str],
    expected: dict[str, Any],
    geometry: dict[str, Any],
    urdf_structure: dict[str, Any],
    urdf_hardware: dict[str, Any],
    reconciliation: dict[str, Any],
    hardware_data: dict[str, Any],
    *,
    ros_relevant: bool,
) -> None:
    unresolved_semantics = (
        expected.get("features", {})
        .get("enrollment", {})
        .get("unresolved_semantics", [])
    )
    lines.extend(
        [
            "## 硬件与机器人规格",
            "",
            "| 项目 | 期望/声明 | 实际发现 |",
            "|---|---|---|",
            f"| 计算平台 | {_text(expected.get('platform', {}).get('compute'))} | "
            f"{_text(hardware_data.get('compute_platform'))} |",
            f"| CPU 架构 | {_text(expected.get('platform', {}).get('architecture'))} | "
            f"{_text(hardware_data.get('architecture'))} |",
            f"| 驱动模型 | {_text(expected.get('platform', {}).get('drive_model'))} | "
            "未从确定性证据提升 |",
            f"| 最大线速度 | {_text(geometry.get('hard_max_linear_velocity_mps'))} m/s | "
            "未从确定性证据提升 |",
            f"| 最大角速度 | {_text(geometry.get('hard_max_angular_velocity_radps'))} rad/s | "
            "未从确定性证据提升 |",
            "",
            "### URDF 结构与语义",
            "",
            f"- Base link：`{_text(expected.get('platform', {}).get('base_link'))}`",
            f"- Footprint：{_text(geometry.get('footprint_m'))}",
            f"- 车体尺寸：{_meters(geometry.get('body_dimensions_m'))}",
            f"- 整车包络：{_meters(geometry.get('envelope_m'))}",
            f"- 车轮：{_text(geometry.get('wheel_count'))} 个；半径="
            f"{_meters(geometry.get('wheel_radii_m'))}；宽度="
            f"{_meters(geometry.get('wheel_widths_m'))}",
            f"- 轮距：{_meters(geometry.get('track_width_m'))}；轴距："
            f"{_meters(geometry.get('wheelbase_m'))}；离地间隙："
            f"{_meters(geometry.get('ground_clearance_m'))}",
            f"- 已声明质量：{_number(geometry.get('declared_mass_kg'))} kg；覆盖 link："
            f"{_text(geometry.get('mass_link_count'))}/{len(urdf_structure.get('links', []))}",
            f"- Links（{len(urdf_structure.get('links', []))}）："
            f"{_items(urdf_structure.get('links', []), limit=20)}",
            f"- 未解析语义：{_items(unresolved_semantics, limit=20)}",
            "",
            "<details>",
            f"<summary>URDF 关节明细（{len(urdf_structure.get('joints', []))} 项）</summary>",
            "",
            "#### Joints",
            "",
            "| Joint | 类型 | Parent → Child | Axis | Limits |",
            "|---|---|---|---|---|",
        ]
    )
    joints = urdf_structure.get("joints", [])
    if joints:
        for joint in joints[:100]:
            lines.append(
                f"| {_text(joint.get('name'))} | {_text(joint.get('type'))} | "
                f"{_text(joint.get('parent'))} → {_text(joint.get('child'))} | "
                f"{_number(joint.get('axis'))} | {_number(joint.get('limits'))} |"
            )
    else:
        lines.append("| 未获取 | 未获取 | 未获取 | 未获取 | 未获取 |")
    lines.extend(["", "</details>", ""])

    inertial_links = [link for link in urdf_hardware.get("links", []) if link.get("inertial")]
    if inertial_links:
        lines.extend(
            [
                "<details>",
                f"<summary>质量、质心与惯量（{len(inertial_links)} 个 link）</summary>",
                "",
                "#### 质量、质心与惯量",
                "",
                "| Link | 质量 | 质心 xyz | 惯量张量 |",
                "|---|---:|---|---|",
            ]
        )
        for link in inertial_links[:100]:
            inertial = link["inertial"]
            lines.append(
                f"| {_text(link.get('name'))} | {_number(inertial.get('mass_kg'))} kg | "
                f"{_number(inertial.get('origin', {}).get('xyz'))} | "
                f"{_number(inertial.get('tensor_kg_m2'))} |"
            )
        lines.extend(["", "</details>", ""])

    lines.extend(
        [
            "### 硬件组件",
            "",
            "> `/dev/video*`、input 和 ISP 节点是操作系统接口，不自动等同于物理传感器。",
            "",
            "| 组件 | 类型 | 型号/驱动 | 接口或位置 | 采用信息 |",
            "|---|---|---|---|---|",
        ]
    )
    components = reconciliation.get("effective", [])
    if components:
        for component in components[:50]:
            model_or_driver = component.get("model") or component.get("driver")
            interface_or_location = (
                component.get("path") or component.get("urdf_link") or component.get("transmission")
            )
            lines.append(
                f"| {_text(component.get('name'))} | {_text(component.get('kind'))}/"
                f"{_text(component.get('modality'))} | {_text(model_or_driver)} | "
                f"{_text(interface_or_location)} | {_text(component.get('effective_source'))} |"
            )
    else:
        lines.append("| 未获取 | 未获取 | 未获取 | 未获取 | 未获取 |")
    endpoint_groups = _device_endpoint_groups(hardware_data.get("devices", []))
    lines.extend(
        [
            "",
            "### 设备接口归并",
            "",
            "> 仅凭稳定序列号/拓扑归并物理设备；驱动启发式只会降级内部端点，不会提升物理身份。",
            "",
            "| 分类 | 归并依据 | 操作系统端点 |",
            "|---|---|---|",
        ]
    )
    if endpoint_groups:
        for group in endpoint_groups:
            lines.append(
                f"| {_text(group['classification'])} | {_text(group['identity'])} | "
                f"{_items(group['endpoints'], limit=8)} |"
            )
    else:
        lines.append("| 未获取设备端点 | 无 | 无 |")
    lines.extend(
        [
            "",
            "### 控制与仿真声明",
            "",
            f"- Transmissions：{_named(urdf_hardware.get('transmissions', []), limit=20)}",
        ]
    )
    if ros_relevant or urdf_hardware.get("ros2_control"):
        lines.append(
            f"- ros2_control：{_named(urdf_hardware.get('ros2_control', []), limit=20)}"
        )
    lines.extend(
        [
            f"- Gazebo：{_named(urdf_hardware.get('gazebo', []), limit=20)}",
            f"- 主机设备节点：{len(hardware_data.get('devices', []))} 个（原始清单见机器报告）",
            f"- 硬件总线：{_items(hardware_data.get('buses', {}), limit=20)}",
            "",
        ]
    )


def _append_target_software_stack(
    lines: list[str],
    report: DiscoveryReport,
    applications: list[ExecutableDiscovery],
    *,
    ros_relevant: bool,
) -> None:
    """Describe the observed target and application stack without assuming middleware."""
    linux = report.probes.get("linux")
    application = report.probes.get("application")
    linux_data = linux.data if linux else {}
    host = linux_data.get("host", {})
    os_release = host.get("os_release", {})
    software = linux_data.get("executables", {})
    projects = application.data.get("projects", []) if application else []
    processes = linux_data.get("processes", [])
    environment = linux_data.get("environment", {})
    os_name = (
        os_release.get("PRETTY_NAME")
        or os_release.get("NAME")
        or " ".join(
            str(value)
            for value in (host.get("system"), host.get("release"))
            if value
        )
    )
    lines.extend(
        [
            "## 目标主机与软件栈",
            "",
            "> 本节按目标主机 probe 与源码/制品声明分别陈述，不预设操作系统或中间件。",
            "",
            "### 目标主机",
            "",
            "| 项目 | 发现值 | 证据状态 |",
            "|---|---|---|",
            f"| 主机名 | {_text(host.get('hostname'))} | "
            f"{_text(linux.status.value if linux else 'NOT_PROBED')} |",
            f"| 操作系统 | {_text(os_name)} | 目标主机观测 |",
            f"| 内核 | {_text(host.get('version') or host.get('release'))} | 目标主机观测 |",
            f"| CPU 架构 | {_text(host.get('architecture'))} | 目标主机观测 |",
            f"| 已准入运行环境键 | {_items(sorted(environment), limit=20)} | "
            "仅列键名，不披露值 |",
            f"| 进程快照 | {len(processes)} 项 | 只读、时点观测 |",
            f"| 进程样本 | {_items(processes, limit=8)} | 仅进程名，不含命令参数 |",
            "",
            "### 工程与应用软件",
            "",
            "| 工程根目录 | 包 | 语言 | 构建系统 | 入口 | 源码版本 |",
            "|---|---|---|---|---|---|",
        ]
    )
    if projects:
        for project in projects[:20]:
            if not isinstance(project, dict):
                continue
            entrypoints = [
                item.get("name") or item.get("target")
                for item in project.get("entrypoints", [])
                if isinstance(item, dict)
            ]
            lines.append(
                f"| {_text(project.get('root'))} | "
                f"{_items(project.get('packages', []), limit=8)} | "
                f"{_items(project.get('languages', []), limit=8)} | "
                f"{_items(project.get('build_systems', []), limit=8)} | "
                f"{_items(entrypoints, limit=8)} | "
                f"{_text(project.get('source_revision'))} |"
            )
    else:
        lines.append("| 未提供源码工程 | 未获取 | 未获取 | 未获取 | 未获取 | 未获取 |")
    dependency_names = sorted(
        {
            str(name)
            for project in projects
            if isinstance(project, dict)
            for name in project.get("declared_dependencies", [])
        }
    )
    project_protocols = sorted(
        {
            str(protocol)
            for project in projects
            if isinstance(project, dict)
            for protocol in project.get("protocols", [])
        }
    )
    lines.extend(
        [
            "",
            f"- 声明依赖：{_items(dependency_names, limit=20)}",
            f"- 源码声明协议：{_items(project_protocols, limit=20)}",
            "",
            "### 程序与入口证据",
            "",
            "| 程序 | 来源 | 入口/路径 | Help 探测 | 哈希 |",
            "|---|---|---|---|---|",
        ]
    )
    if applications:
        for executable in applications[:30]:
            help_probe = executable.invocation.help_probe
            lines.append(
                f"| `{_text(executable.name)}` | {_text(executable.origin)} | "
                f"{_text(executable.invocation.entrypoint or executable.path)} | "
                f"{_text(help_probe.status.value)} | {_text(executable.sha256)} |"
            )
    else:
        lines.append("| 未识别到程序入口 | 未获取 | 未获取 | 未执行 | 未获取 |")
    lines.extend(
        [
            "",
            "### 主机工具证据",
            "",
            "| 工具 | 状态 | 路径 | 版本证据 |",
            "|---|---:|---|---|",
        ]
    )
    visible_tools = [
        (name, metadata)
        for name, metadata in sorted(software.items())
        if metadata.get("available") or (ros_relevant and name in {"ros2", "colcon"})
    ]
    if visible_tools:
        for name, metadata in visible_tools:
            lines.append(
                f"| {_text(name)} | "
                f"{'available' if metadata.get('available') else 'unavailable'} | "
                f"{_text(metadata.get('path'))} | "
                f"{_items(metadata.get('version_output', []), limit=2)} |"
            )
    else:
        lines.append("| 未获取可用工具证据 | unknown | 未获取 | 未获取 |")
    lines.append("")


def render_discovery_review_markdown(
    report: DiscoveryReport,
    active: ActiveDiscoveryReport,
    *,
    insight_bundle: WikiInsightBundle | None = None,
    previous_report: DiscoveryReport | None = None,
    previous_active: ActiveDiscoveryReport | None = None,
) -> str:
    """Render a concise engineer-facing Wiki; machine reports retain exhaustive evidence."""
    hardware = report.probes.get("hw")
    ros = report.probes.get("ros")
    hardware_data = hardware.data if hardware else {}
    ros_data = ros.data if ros else {}
    expected = report.capability_manifest.get("expected_profile", {})
    compatibility = report.capability_manifest.get("compatibility", {})
    geometry = expected.get("geometry", {})
    features = expected.get("features", {})
    urdf_structure = features.get("urdf_structure", {})
    urdf_hardware = features.get("urdf_hardware", {})
    reconciliation = report.capability_manifest.get("hardware_reconciliation", {})
    ros_relevant = ros_evidence_relevant(report, active)
    critical_unknowns = _critical_unknowns(
        expected,
        geometry,
        ros_data,
        ros_relevant=ros_relevant,
    )
    insights = merge_wiki_insights(report, active, insight_bundle)
    applications, support_artifacts = _primary_applications(active.executables)
    discovery_diff = build_wiki_discovery_diff(
        report,
        active,
        previous_report,
        previous_active,
    )

    lines = [
        f"# 机器人 Wiki：{_text(report.robot_id)}",
        "",
        "> 面向接手、启动和排障的工程视图。完整原始观测保留在同次发现的机器 JSON 中。",
        "> “静态发现”和“启发式推断”均不等于运行或物理验证。本文可由总工持续修正。",
        "",
        "## 全栈摘要",
        "",
        "| 项目 | 结论 |",
        "|---|---|",
        f"| 发现编号 | `{_text(report.discovery_id)}` |",
        f"| 技术状态 | `{_text(report.status.value)}` |",
        f"| 发现模式/置信度 | `{_text(active.discovery_mode.level.value)}` / "
        f"`{_text(active.discovery_mode.confidence.value)}` |",
        f"| 兼容性判断 | {_text(_compatibility_text(compatibility, critical_unknowns))} |",
        f"| 工程应用/辅助产物 | {len(applications)} / {len(support_artifacts)} |",
        f"| 目标软件形态 | "
        f"{'ROS 相关软件栈' if ros_relevant else 'Application/CLI 软件栈（无中间件证据）'} |",
        f"| 待确认/警告 | {len(active.unknowns)} / {len(active.warnings)} |",
        "",
        "### 当前证据边界",
        "",
        "- 证据优先级：构建/部署产物 → 文档/launch → 只读 probe。",
        "- 源码只补充主证据缺口；静态字符串不能证明接口一定在运行。",
        f"- 未归属静态接口：{len(active.unattributed_source_interfaces)} 项；"
        "不会静默分配给无源文件证据的程序。",
        f"- 尚未确定的关键项：{_items(critical_unknowns, limit=10)}。",
        "- operation candidate 仅表示可能适用，不表示 adapter 已生成或操作已验证。",
        "",
    ]
    if insights.findings:
        lines.extend(
            [
                "### 需要优先复核的启发式发现",
                "",
                "> 以下内容是带依据的推断，不是事实提升；完成“验证方式”后才能转为工程结论。",
                "",
                "| 类别 | 推断 | 置信度/来源 | 依据 | 验证方式 |",
                "|---|---|---:|---|---|",
            ]
        )
        for finding in insights.findings:
            lines.append(
                f"| {_text(finding.category)} | {_text(finding.statement)} | "
                f"{_text(finding.confidence)}/{_text(finding.source)} | "
                f"{_items(finding.basis, limit=3)} | "
                f"{_text(finding.verification)} |"
            )
        lines.append("")

    _append_discovery_diff(lines, discovery_diff)

    _append_target_software_stack(
        lines,
        report,
        applications,
        ros_relevant=ros_relevant,
    )

    startup_entries = [
        item.name for item in applications if item.launch_analysis.available
    ]
    startup_steps = [
        step for item in applications for step in item.invocation.startup_sequence
    ]
    shutdown_methods = [
        item.invocation.shutdown_method
        for item in applications
        if item.invocation.shutdown_method
    ]
    health_checks = [
        item.invocation.health_check
        for item in applications
        if item.invocation.health_check
    ]
    lines.extend(
        [
            "## 启动与健康检查",
            "",
            "> 自动发现尚不能保证启动顺序、关机步骤和健康阈值；空白项需要总工补充。",
            "",
            "| 项目 | 当前发现 | 验证状态 |",
            "|---|---|---|",
            f"| 启动入口 | {_items(startup_entries, limit=12)} | 静态未验证 |",
            f"| 启动顺序 | {_items(startup_steps, limit=8)} | 待确认 |",
            f"| 停止方式 | {_items(shutdown_methods, limit=8)} | 待确认 |",
            f"| 健康检查 | {_items(health_checks, limit=8)} | 待确认 |",
            (
                f"| 在线 ROS 节点 | {_items(ros_data.get('nodes', []), limit=12)} | "
                "运行时观测 |"
                if ros_relevant
                else f"| 已识别程序入口 | "
                f"{_items([item.name for item in applications], limit=12)} | "
                "声明/静态证据；运行实例待目标主机确认 |"
            ),
            "",
        ]
    )

    _append_hardware_details(
        lines,
        expected,
        geometry,
        urdf_structure,
        urdf_hardware,
        reconciliation,
        hardware_data,
        ros_relevant=ros_relevant,
    )

    lines.extend(
        [
            "",
            "## 应用程序与启动关系",
            "",
            "> 只在正文列出有 launch、显式入口、源码入口或通信证据的工程应用。",
            "> 构建 hook、CMake 探测文件和中间件生成库已从正文降级为统计，不视为机器人应用。",
            "",
        ]
    )
    if not applications:
        lines.extend(["未识别到有足够证据的工程应用入口。", ""])
    else:
        lines.extend(
            [
                "| 应用/入口 | 包或启动证据 | 主要接口（已去重） | 风险提示 | 证据状态 |",
                "|---|---|---|---|---|",
            ]
        )
        for executable in applications:
            launch = executable.launch_analysis
            outgoing, incoming = _ros_interfaces(executable)
            defaults = [
                f"{name}={value if value is not None else 'dynamic'}"
                for name, value in launch.argument_defaults.items()
            ]
            launch_evidence = (
                f"包={_items(launch.packages, limit=3)}；节点={_items(launch.nodes, limit=3)}；"
                f"条件={_items(launch.conditions, limit=2)}；"
                f"默认参数={_items(defaults, limit=2)}；"
                f"包含={_items(launch.included_launch_files, limit=2)}；"
                f"证据={_compact_paths(launch.references, limit=2)}；"
                f"状态=`{launch.verification}`"
                if launch.available
                else f"入口={_text(executable.invocation.entrypoint or executable.path)}"
            )
            protocols = executable.communication.network.get("protocols", [])
            endpoints = [
                *executable.communication.network.get("listen_endpoints", []),
                *executable.communication.network.get("remote_endpoints", []),
            ]
            interface_parts = []
            if outgoing or incoming:
                interface_parts.append(
                    f"ROS 出={_items(outgoing, limit=4)}；入={_items(incoming, limit=4)}"
                )
            if protocols or endpoints:
                interface_parts.append(
                    f"网络={_items(protocols, limit=4)}；端点={_items(endpoints, limit=4)}"
                )
            if executable.communication.ipc:
                interface_parts.append(f"IPC={_items(executable.communication.ipc, limit=4)}")
            if executable.communication.hardware_bus:
                interface_parts.append(
                    f"硬件总线={_items(executable.communication.hardware_bus, limit=4)}"
                )
            interface = "；".join(interface_parts) or "未发现可归属的运行时通信接口"
            lines.append(
                f"| `{_text(executable.name)}` | {launch_evidence} | {interface} | "
                f"{_text(_application_risk(executable))} | "
                f"{_text(_interface_quality(executable))} |"
            )
        lines.append("")
    if active.unattributed_source_interfaces:
        lines.extend(
            [
                "### 未归属的静态接口",
                "",
                "> 已发现接口调用，但入口、构建 target 或安装声明不足以确认所属程序。"
                "这些候选不会进入程序拓扑，需通过构建声明或在线图核对。",
                "",
                "| 角色 | 名称/表达式 | 类型 | 源文件 |",
                "|---|---|---|---|",
            ]
        )
        for interface in active.unattributed_source_interfaces[:30]:
            lines.append(
                f"| {_text(interface.get('role'))} | {_text(interface.get('name'))} | "
                f"{_text(interface.get('type'))} | "
                f"{_compact_paths([str(interface.get('source', ''))], limit=1)} |"
            )
        if len(active.unattributed_source_interfaces) > 30:
            lines.append(
                f"| — | 另有 {len(active.unattributed_source_interfaces) - 30} 项 | — | "
                "见 `active_discovery_report.json` |"
            )
        lines.append("")
    if support_artifacts:
        counts = Counter(
            "环境/构建脚本"
            if item.name.casefold().endswith(".ps1")
            else "编译探测文件"
            if item.name.casefold() == "a.out"
            or item.name.casefold().startswith("cmakedeterminecompilerabi_")
            else "ROSIDL 生成库"
            if "rosidl_" in item.name.casefold()
            else "其他未归类产物"
            for item in support_artifacts
        )
        lines.extend(
            [
                "### 已降级的辅助产物",
                "",
                "、".join(f"{name} {count} 个" for name, count in sorted(counts.items()))
                + "。完整路径和哈希见 `active_discovery_report.json`。",
                "",
            ]
        )

    cli_routes = _unique(
        [
            route
            for layer in ("application", "linux")
            if (probe := report.probes.get(layer)) is not None
            for route in probe_routes(probe)
            if route.kind == "cli"
        ]
        + [
            route
            for candidate in report.operation_candidates
            for route in candidate.route_evidence
            if route.kind == "cli"
        ]
    )
    network_protocols = sorted(
        {
            str(protocol)
            for executable in applications
            for protocol in executable.communication.network.get("protocols", [])
        }
    )
    ipc_kinds = sorted(
        {
            str(kind)
            for executable in applications
            for kind, value in executable.communication.ipc.items()
            if value
        }
    )
    hardware_buses = sorted(
        {
            str(kind)
            for executable in applications
            for kind, value in executable.communication.hardware_bus.items()
            if value
        }
    )
    lines.extend(
        [
            "## 运行时与通信接口",
            "",
            f"- CLI 路由：{_items([route.endpoint for route in cli_routes], limit=20)}",
            f"- 网络协议：{_items(network_protocols, limit=20)}",
            f"- IPC 机制：{_items(ipc_kinds, limit=20)}",
            f"- 硬件通信：{_items(hardware_buses, limit=20)}",
            "",
        ]
    )
    if ros_relevant:
        lines.extend(
            [
                "### ROS 运行时与拓扑",
                "",
                f"- 发行版：{_text(ros_data.get('ros_distro'))}",
                f"- RMW：{_text(ros_data.get('rmw'))}",
                f"- Domain ID：{_text(ros_data.get('domain_id'))}",
                f"- 在线节点：{_items(ros_data.get('nodes', []), limit=20)}",
                f"- Topics：{_items(ros_data.get('topics', []), limit=20)}",
                f"- Services：{_items(ros_data.get('services', []), limit=20)}",
                f"- Actions：{_items(ros_data.get('actions', []), limit=20)}",
                "",
            ]
        )
        if not ros_data.get("nodes"):
            lines.extend(
                [
                    "> 本次没有在线节点证据；以下关系若存在，仅为静态候选，不代表真实运行拓扑。",
                    "",
                ]
            )
        graph_lines: list[str] = ["```mermaid", "flowchart LR"]
        edge_count = 0
        topic_ids: dict[str, str] = {}
        declared_topics: set[str] = set()
        for index, executable in enumerate(applications):
            outgoing, incoming = _ros_interfaces(executable)
            if not outgoing and not incoming:
                continue
            source = f"exe{index}"
            graph_lines.append(f'  {source}["{_mermaid_label(executable.name)}"]')
            for role, names in (("publishers", outgoing), ("subscribers", incoming)):
                for name in names:
                    if edge_count >= MAX_STATIC_GRAPH_EDGES:
                        break
                    target = topic_ids.setdefault(name, f"topic{len(topic_ids)}")
                    if name not in declared_topics:
                        graph_lines.append(f'  {target}(("{_mermaid_label(name)}"))')
                        declared_topics.add(name)
                    graph_lines.append(
                        f"  {source} --> {target}"
                        if role == "publishers"
                        else f"  {target} -.-> {source}"
                    )
                    edge_count += 1
        if edge_count:
            lines.extend([*graph_lines, "```", ""])
            if edge_count >= MAX_STATIC_GRAPH_EDGES:
                lines.extend(
                    [
                        f"> 静态图已限制为 {MAX_STATIC_GRAPH_EDGES} 条去重边；完整候选见机器报告。",
                        "",
                    ]
                )
        else:
            lines.extend(["没有足够证据生成有意义的程序—接口关系图。", ""])
    else:
        lines.extend(
            [
                "> 本次没有观测到可归属的中间件运行时；按目标主机的 Application/CLI、"
                "网络、IPC 和设备接口组织。",
                "",
            ]
        )

    _append_operation_catalog(lines, report)

    grouped_unknowns: dict[str, list[str]] = {}
    for unknown in active.unknowns:
        grouped_unknowns.setdefault(_unknown_category(unknown), []).append(unknown)
    lines.extend(
        [
            "## 依赖、差异与未知项",
            "",
            "| 获取方式 | 数量 | 示例 |",
            "|---|---:|---|",
        ]
    )
    if grouped_unknowns:
        for category, values in grouped_unknowns.items():
            lines.append(f"| {category} | {len(values)} | {_items(values, limit=3)} |")
    else:
        lines.append("| 无已记录缺口 | 0 | — |")
    lines.extend(
        [
            "",
            f"- 缺失依赖：{_items(active.dependency_summary.get('missing', []), limit=10)}",
            f"- 冲突依赖：{_items(active.dependency_summary.get('conflicting', []), limit=10)}",
            f"- 兼容性差异：{_named(compatibility.get('mismatches', []), limit=10)}",
            "",
        ]
    )
    if insights.unknown_assessments:
        lines.extend(
            [
                "### 启发式 Unknown 检视",
                "",
                "> Agent 仅给出证据复核路径；原 Unknown 仍保留，且不会因此提升探测或门禁状态。",
                "",
                "| Unknown | 初步分类 | Agent 判断 | 置信度/来源 | 下一步 |",
                "|---|---|---|---:|---|",
            ]
        )
        for assessment in insights.unknown_assessments:
            lines.append(
                f"| {_text(assessment.unknown)} | {_text(assessment.classification)} | "
                f"{_text(assessment.assessment)}（依据：{_items(assessment.basis, limit=3)}） | "
                f"{_text(assessment.confidence)}/{_text(assessment.source)} | "
                f"{_text(assessment.next_step)} |"
            )
        lines.append("")
    if active.warnings:
        lines.extend(["### 警告", ""])
        lines.extend(f"- {_text(_summarize_warning(warning))}" for warning in active.warnings[:20])
        if len(active.warnings) > 20:
            lines.append(f"- 另有 {len(active.warnings) - 20} 条，见机器报告。")
        lines.append("")
    lines.extend(
        [
            "## 总工维护建议",
            "",
            "1. 启动、停止、健康检查、急停和失联行为。",
            (
                "2. ROS 发行版/RMW/Domain、启动顺序和在线节点基线。"
                if ros_relevant
                else "2. 目标主机软件版本、CLI/API/协议、启动顺序和运行实例基线。"
            ),
            "3. 物理设备与 `/dev/*`、驱动、固件和标定文件的映射。",
            "4. 速度/负载/关节安全限制及其来源和验证日期。",
            "5. 版本基线、日志位置、已知故障、负责人和恢复步骤。",
            "",
            "## 自动发现附录说明",
            "",
            "- 本 Wiki 保留工程结论、关键证据和可行动缺口，不复制完整 registry。",
            "- 完整 executable、文件哈希、原始设备节点、重复接口候选和依赖 ID "
            "保留在同次发现的 JSON/active discovery 报告中。",
            "- 启发式洞察可由确定性规则或 Adapt Agent skill 生成，但必须携带依据、"
            "置信度和验证方式，且不得提升为已验证事实。",
            "",
            "维护方式：直接编辑本 Markdown；机器证据不会因 Wiki 编辑而改变。"
            "下一次发现会生成新版本，旧版本可用于追溯。",
            "",
        ]
    )
    return "\n".join(lines)

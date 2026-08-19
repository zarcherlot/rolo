from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from rolo.core.models import DiscoveryReport
from rolo.stages.adapt.active_discovery import ActiveDiscoveryReport


def _text(value: Any) -> str:
    rendered = "unknown" if value is None or value == "" else str(value)
    return rendered.replace("|", "\\|").replace("`", "'").replace("\n", " ")


def _items(values: Iterable[Any], *, limit: int = 30) -> str:
    rendered = [_text(value) for value in list(values)[:limit]]
    return ", ".join(rendered) or "none"


def _named(values: Iterable[Any], *, limit: int = 30) -> str:
    names = []
    for value in list(values)[:limit]:
        if isinstance(value, dict):
            names.append(value.get("name") or value.get("path") or value)
        else:
            names.append(value)
    return _items(names, limit=limit)


def _remappings(values: Iterable[dict[str, str]], *, limit: int = 30) -> str:
    rendered = [
        f"{_text(value.get('from'))} → {_text(value.get('to'))}" for value in list(values)[:limit]
    ]
    return ", ".join(rendered) or "none"


def _compact_paths(values: Iterable[str], *, limit: int = 10) -> str:
    rendered = []
    for value in list(values)[:limit]:
        parts = str(value).replace("\\", "/").split("/")
        rendered.append("/".join(parts[-2:]))
    return ", ".join(rendered) or "none"


def _meters(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, list):
        return " × ".join(f"{float(item) * 1000:g}" for item in value) + " mm"
    return f"{float(value) * 1000:g} mm"


def render_discovery_review_markdown(
    report: DiscoveryReport,
    active: ActiveDiscoveryReport,
) -> str:
    """Render the editable whole-stack robot Wiki maintained by the chief engineer."""
    hardware = report.probes.get("hw")
    linux = report.probes.get("linux")
    ros = report.probes.get("ros")
    hardware_data = hardware.data if hardware else {}
    linux_data = linux.data if linux else {}
    ros_data = ros.data if ros else {}
    host = linux_data.get("host", {})
    expected = report.capability_manifest.get("expected_profile", {})
    compatibility = report.capability_manifest.get("compatibility", {})
    software = linux_data.get("executables", {})
    geometry = expected.get("geometry", {})
    features = expected.get("features", {})
    enrollment = features.get("enrollment", {})
    urdf_structure = features.get("urdf_structure", {})
    urdf_hardware = features.get("urdf_hardware", {})
    reconciliation = report.capability_manifest.get("hardware_reconciliation", {})

    lines = [
        f"# 机器人 Wiki：{_text(report.robot_id)}",
        "",
        "> 这是机器人的工程 Wiki，由发现结果生成，并由软硬件总工持续维护。",
        "> 可以直接修正、补充和重写本文档；它不参与证据文件哈希。机器 JSON 保留原始观测。",
        "",
        "## 全栈摘要",
        "",
        f"- 发现编号：`{_text(report.discovery_id)}`",
        f"- 技术状态：`{_text(report.status.value)}`",
        f"- 发现模式：`{_text(active.discovery_mode.level.value)}`",
        f"- 置信度：`{_text(active.discovery_mode.confidence.value)}`",
        "- 证据优先级：`构建/部署产物 → 文档/launch → 只读 probe`",
        "- 源码角色：`仅用于主证据缺口补充，不作为主要溯源依据`",
        f"- 软硬件兼容性：`{_text(compatibility.get('status'))}`",
        f"- 待确认未知项：{len(active.unknowns)}",
        f"- 警告：{len(active.warnings)}",
        "",
        "## 硬件与机器人规格",
        "",
        "| 项目 | 期望/声明 | 实际发现 |",
        "|---|---|---|",
        f"| 计算平台 | {_text(expected.get('platform', {}).get('compute'))} | "
        f"{_text(hardware_data.get('compute_platform'))} |",
        f"| CPU 架构 | {_text(expected.get('platform', {}).get('architecture'))} | "
        f"{_text(hardware_data.get('architecture'))} |",
        f"| 驱动模型 | {_text(expected.get('platform', {}).get('drive_model'))} | "
        "由 URDF/配置声明 |",
        f"| 最大线速度 | {_text(geometry.get('hard_max_linear_velocity_mps'))} m/s | "
        "未作为发现值提升 |",
        f"| 最大角速度 | {_text(geometry.get('hard_max_angular_velocity_radps'))} rad/s | "
        "未作为发现值提升 |",
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
        f"- 已声明质量：{_text(geometry.get('declared_mass_kg'))} kg；覆盖 link："
        f"{_text(geometry.get('mass_link_count'))}/{len(urdf_structure.get('links', []))}",
        f"- Links（{len(urdf_structure.get('links', []))}）："
        f"{_items(urdf_structure.get('links', []), limit=100)}",
        f"- 未解析语义：{_items(enrollment.get('unresolved_semantics', []), limit=100)}",
        "",
        "#### Joints",
        "",
        "| Joint | 类型 | Parent → Child | Axis | Limits |",
        "|---|---|---|---|---|",
    ]
    joints = urdf_structure.get("joints", [])
    if joints:
        for joint in joints[:100]:
            lines.append(
                f"| {_text(joint.get('name'))} | {_text(joint.get('type'))} | "
                f"{_text(joint.get('parent'))} → {_text(joint.get('child'))} | "
                f"{_text(joint.get('axis'))} | {_text(joint.get('limits'))} |"
            )
    else:
        lines.append("| none | unknown | unknown | unknown | none |")
    inertial_links = [link for link in urdf_hardware.get("links", []) if link.get("inertial")]
    if inertial_links:
        lines.extend(
            [
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
                f"| {_text(link.get('name'))} | {_text(inertial.get('mass_kg'))} kg | "
                f"{_text(inertial.get('origin', {}).get('xyz'))} | "
                f"{_text(inertial.get('tensor_kg_m2'))} |"
            )
    lines.extend(
        [
            "",
            "#### 硬件组件",
            "",
            "| 组件 | 类型 | 型号/驱动 | 接口或位置 | 采用信息 |",
            "|---|---|---|---|---|",
        ]
    )
    components = reconciliation.get("effective", [])
    if components:
        for component in components[:100]:
            model_or_driver = component.get("model") or component.get("driver")
            interface_or_location = (
                component.get("path") or component.get("urdf_link") or component.get("transmission")
            )
            lines.append(
                f"| {_text(component.get('name'))} | {_text(component.get('kind'))}/"
                f"{_text(component.get('modality'))} | {_text(model_or_driver)} | "
                f"{_text(interface_or_location)} | "
                f"{_text(component.get('effective_source'))} |"
            )
    else:
        lines.append("| none | unknown | unknown | unknown | unknown |")
    differences = reconciliation.get("differences", [])
    if differences:
        lines.extend(
            [
                "",
                "#### 硬件描述差异",
                "",
                "| 组件/字段 | URDF | 实机读取 | 采用值 |",
                "|---|---|---|---|",
            ]
        )
        for difference in differences[:100]:
            lines.append(
                f"| {_text(difference.get('component'))}.{_text(difference.get('field'))} | "
                f"{_text(difference.get('urdf'))} | {_text(difference.get('observed'))} | "
                f"{_text(difference.get('effective'))} |"
            )
    lines.extend(
        [
            "",
            "#### 控制与仿真声明",
            "",
            f"- Transmissions：{_named(urdf_hardware.get('transmissions', []), limit=100)}",
            f"- ros2_control：{_named(urdf_hardware.get('ros2_control', []), limit=100)}",
            f"- Gazebo：{_named(urdf_hardware.get('gazebo', []), limit=100)}",
            "",
            f"- 主机设备：{_named(hardware_data.get('devices', []))}",
            f"- 硬件总线：{_items(hardware_data.get('buses', {}))}",
            "",
            "## 主机与软件栈",
            "",
            "| 项目 | 发现值 |",
            "|---|---|",
            f"| 主机名 | {_text(host.get('hostname'))} |",
            f"| 操作系统 | {_text(host.get('system'))} {_text(host.get('release'))} |",
            f"| ROS 发行版 | {_text(ros_data.get('ros_distro'))} |",
            f"| RMW | {_text(ros_data.get('rmw'))} |",
            f"| ROS Domain ID | {_text(ros_data.get('domain_id'))} |",
            "",
            "### 可用工具",
            "",
            "| 工具 | 状态 | 版本证据 |",
            "|---|---:|---|",
        ]
    )
    for name, metadata in sorted(software.items()):
        lines.append(
            f"| {_text(name)} | {'available' if metadata.get('available') else 'unavailable'} | "
            f"{_items(metadata.get('version_output', []), limit=3)} |"
        )

    lines.extend(["", "## 应用程序与启动拓扑", ""])
    lines.extend(
        [
            "> launch 信息来自 Python AST/XML 静态解析，不会执行 launch；动态表达式仍可能未解析。",
            "",
        ]
    )
    if not active.executables:
        lines.append("未识别到可执行入口。")
    for executable in active.executables:
        ros_communication = executable.communication.ros
        launch = executable.launch_analysis
        lines.extend(
            [
                f"### {_text(executable.name)}",
                "",
                f"- 身份：`{_text(executable.origin)}`；位置/入口："
                f"`{_text(executable.path or executable.invocation.entrypoint or '未解析')}`；"
                f"格式/架构：`{_text(executable.file_format)}/{_text(executable.architecture)}`",
                "- 功能与接口：以 DiscoveryReport 的 operation candidates 为准；"
                f"发布={_named(ros_communication.get('publishers', []))}；"
                f"订阅={_named(ros_communication.get('subscribers', []))}；"
                f"服务/动作={_named(ros_communication.get('services', []))}/"
                f"{_named(ros_communication.get('actions', []))}；"
                f"协议={_items(executable.communication.network.get('protocols', []))}",
                (
                    f"- 启动声明：包={_items(launch.packages)}；节点={_items(launch.nodes)}；"
                    f"条件={_items(launch.conditions)}；参数={_items(launch.arguments)}；"
                    f"Remapping={_remappings(launch.remappings)}；"
                    f"URDF={_items(launch.urdf_references)}；"
                    f"证据={_compact_paths(launch.references)}；状态=`{launch.verification}`"
                    if launch.available
                    else "- 启动声明：未从受支持的 launch 文件识别"
                ),
                f"- 依赖与风险：依赖={_items(executable.source_analysis.declared_dependencies)}；"
                f"风险=`{_text(executable.safety.get('risk'))}`；可能运动="
                f"`{_text(executable.safety.get('motion_possible'))}`",
                "",
            ]
        )

    lines.extend(
        [
            "## ROS 与通信拓扑",
            "",
            "> 在线列表以只读 probe 为准；程序与接口的静态边优先来自文档/launch。",
            "> 源码扫描结果只补充主证据未覆盖的缺口，不能覆盖构建产物、文档或 probe。",
            "",
            f"- 在线节点：{_items(ros_data.get('nodes', []), limit=100)}",
            f"- Topics：{_items(ros_data.get('topics', []), limit=100)}",
            f"- Services：{_items(ros_data.get('services', []), limit=100)}",
            f"- Actions：{_items(ros_data.get('actions', []), limit=100)}",
            "",
            "```mermaid",
            "flowchart LR",
        ]
    )
    edge_count = 0
    for index, executable in enumerate(active.executables):
        source = f"exe{index}"
        lines.append(f'  {source}["{_text(executable.name)}"]')
        ros_communication = executable.communication.ros
        for role in ("publishers", "subscribers"):
            for item_index, item in enumerate(ros_communication.get(role, [])[:30]):
                name = item.get("name") if isinstance(item, dict) else item
                target = f"topic{index}_{role}_{item_index}"
                lines.append(f'  {target}(("{_text(name)}"))')
                lines.append(
                    f"  {source} --> {target}"
                    if role == "publishers"
                    else f"  {target} -.-> {source}"
                )
                edge_count += 1
    if not edge_count:
        lines.append('  no_edges["没有足够证据生成程序—Topic 关系"]')
    lines.extend(["```", "", "## 依赖、差异与未知项", ""])
    lines.extend(
        [
            f"- 缺失依赖：{_items(active.dependency_summary.get('missing', []), limit=100)}",
            f"- 冲突依赖：{_items(active.dependency_summary.get('conflicting', []), limit=100)}",
            f"- 未知项：{_items(active.unknowns, limit=100)}",
            f"- 兼容性差异：{_named(compatibility.get('mismatches', []), limit=100)}",
            "",
        ]
    )
    if active.warnings:
        lines.extend(["### 警告", ""])
        lines.extend(f"- {_text(warning)}" for warning in active.warnings)
        lines.append("")
    lines.extend(
        [
            "## 总工维护建议",
            "",
            "- 补充程序、节点、板卡和外围设备的工程用途与负责人",
            "- 修正自动发现无法判断的通信方向、部署关系和启动顺序",
            "- 记录版本基线、已知风险、维护窗口和现场约束",
            "- 保留静态推断的不确定性，直到受控验证得到证据",
            "",
            "维护方式：直接编辑本 Markdown 文档；无需额外确认命令。下一次发现会生成新的",
            "运行版本，旧版本仍可用于历史追溯。",
            "",
        ]
    )
    return "\n".join(lines)

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
    sensors = expected.get("sensors", {})
    geometry = expected.get("geometry", {})

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
        f"- 传感器：{_items(sensors)}",
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
    for name, metadata in sorted(software.items()):
        lines.append(
            f"| {_text(name)} | {'available' if metadata.get('available') else 'unavailable'} | "
            f"{_items(metadata.get('version_output', []), limit=3)} |"
        )

    lines.extend(["", "## 应用程序与功能概览", ""])
    if not active.executables:
        lines.append("未识别到可执行入口。")
    for executable in active.executables:
        ros_communication = executable.communication.ros
        lines.extend(
            [
                f"### {_text(executable.name)}",
                "",
                f"- 位置：`{_text(executable.path or '未解析')}`",
                f"- 来源：`{_text(executable.origin)}`；格式/架构："
                f"`{_text(executable.file_format)}/{_text(executable.architecture)}`",
                f"- 启动入口：`{_text(executable.invocation.entrypoint)}`",
                f"- 功能候选：{_named(executable.capability_candidates)}",
                f"- ROS 节点：{_named(ros_communication.get('nodes', []))}",
                f"- 发布：{_named(ros_communication.get('publishers', []))}",
                f"- 订阅：{_named(ros_communication.get('subscribers', []))}",
                f"- 服务：{_named(ros_communication.get('services', []))}",
                f"- 动作：{_named(ros_communication.get('actions', []))}",
                f"- 网络协议：{_items(executable.communication.network.get('protocols', []))}",
                f"- 依赖声明：{_items(executable.source_analysis.declared_dependencies)}",
                f"- 风险：`{_text(executable.safety.get('risk'))}`；可能运动："
                f"`{_text(executable.safety.get('motion_possible'))}`",
                "",
            ]
        )

    lines.extend(
        [
            "## ROS 与通信拓扑",
            "",
            "> 在线列表是运行时证据；程序与接口的边来自源码和 launch 静态证据。",
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

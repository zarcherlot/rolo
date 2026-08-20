# Robot Wiki 真机验证清单

本清单只验证发现和 Wiki，不执行任何 canonical operation。测试前按设备原有安全流程准备，
机器人启动/停止仍由现场工程师使用已经批准的方式完成。

## 1. 部署与环境

- 部署 `main` 的固定 commit，记录 commit SHA；不要直接部署未提交工作区。
- 使用机器人应用实际运行用户，并 source 正常使用的 ROS setup 和 workspace overlay。
- 确认 `ROS_DISTRO`、`RMW_IMPLEMENTATION`、`ROS_DOMAIN_ID` 是否显式配置；未配置也要记录。
- `ROLO_ARTIFACT_DIR` 和 `ROLO_OUTPUT_DIR` 放在源码目录之外。
- 启发式 skill 默认开启；验证前先完成 `codex login`，并可显式设置：

```bash
export WIKI_INSIGHTS_AGENT_ENABLED=true
export WIKI_INSIGHTS_AGENT_TIMEOUT_S=180
export WIKI_INSIGHTS_SKILL_PATH=skills/robot-wiki-heuristics/SKILL.md
```

## 2. 第一次发现：静态基线

保持机器人应用未启动，但不要关闭发现硬件所需的正常系统服务。路径按真机实际部署修改：

```bash
uv run robotctl adapt discover run \
  --robot "$ROBOT_ID" \
  --urdf /path/to/robot.urdf \
  --build-root /path/to/build \
  --install-root /path/to/install \
  --doc-root /path/to/docs \
  --launch-root /path/to/launch \
  --source-root /path/to/source \
  --active-probe none

uv run robotctl adapt discover review --robot "$ROBOT_ID"
```

检查：

- setuptools `console_scripts`、CMake target 和 `install(PROGRAMS ...)` 入口是否出现；
- C++ 字面量接口显示真实名称，参数变量显示为 `<symbol:...>`，不得伪装成确定 Topic；
- 注释代码、测试程序和未安装脚本没有被当作运行入口；
- “未归属的静态接口”有源文件证据，且没有被强行分配给不相关程序；
- 完整 registry 没有进入 Wiki，正文只出现本机有证据的 operation candidates。

## 3. 第二次发现：在线只读观测

由现场工程师按设备现有批准流程启动应用，确认机器人处于不会意外运动的受控状态，然后运行：

```bash
uv run robotctl adapt discover run \
  --robot "$ROBOT_ID" \
  --urdf /path/to/robot.urdf \
  --build-root /path/to/build \
  --install-root /path/to/install \
  --doc-root /path/to/docs \
  --launch-root /path/to/launch \
  --source-root /path/to/source \
  --active-probe runtime-readonly

uv run robotctl adapt discover review --robot "$ROBOT_ID"
```

检查：

- ROS distro、RMW、Domain ID 的值及来源与实际环境一致；安装候选没有被写成运行事实；
- 在线 Node/Topic/Service/Action 与 `ros2 ... list` 的同一时刻结果一致；
- 静态接口与在线图不一致时仍保留“静态未验证”，没有自动提升为已验证；
- `wiki_diff.json` 以第一次 discovery 为基线，主要变化集中在 ROS 在线图；
- `wiki_insights.json` 中 Agent 结论均为 `ADAPT_AGENT_SKILL`、LOW/MEDIUM，并包含依据和验证方式；
- Agent 不可用或输出无效时 discovery 仍成功，`wiki_generation.json` 记录回退原因。

## 4. 设备归并检查

用系统工具和业务配置人工核对 Wiki 的设备接口归并：

- USB：VID/PID、序列号、物理端口路径；
- 摄像头：`udev` 属性与 media graph，区分传感器、ISP、codec 和虚拟 video 节点；
- 串口/CAN：稳定别名、USB 拓扑、驱动和连接的控制器；
- input 设备：物理设备与多个 event 节点的关系。

没有稳定序列号或拓扑时应保留“未归并端点”，不得仅按 `/dev/*` 数量推断物理设备数量。

## 5. 回传制品

请回传两个 discovery ID 及各自以下文件，不要包含凭据、私有源码或操作 payload：

```text
robot_wiki.md
report.json
active_discovery_report.json
hw.json
ros.json
wiki_diff.json
wiki_insights.json
wiki_generation.json
```

同时提供：正常启动方式的文字说明、预期核心节点/Topic 清单，以及你认为 Wiki 中错误、重复或缺失的
条目。收到制品后再校准启发式规则、设备归并和未来质量门禁阈值。

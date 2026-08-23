<p align="center">
  <img src="rolo-logo.svg" width="720" alt="rolo Loop Exit — robot only loop once">
</p>

<p align="center">
  <strong>在每一次执行中自我进化</strong><br>
</p>

<p align="center">
  中文 · <a href="docs/README.en.md">English</a>
</p>

## rolo 是什么

rolo (robot only loop once) 是一种具身机器人开发原则：每一次用例的执行，构建输入、过程、结果和外部观测的切片，让机器人自主解释并修正问题。

> [!NOTE]
> 当前版本是开发中的 MVP。模拟后端适合本地验证，但不替代真实机器人上的安全控制、急停、碰撞检测或人工授权。

## rolo 特性

### 一次运行，一个完整证据闭环

rolo 不把“命令成功返回”视为任务完成。每次执行都应留下可以回放、解释和复现的 episode，包括：

- 下发命令与机器人实际执行状态；
- 传感器、系统遥测和相机画面；
- 参数、软件和能力配置版本；
- 测试判定、异常区间与诊断结论。

### 标准 CLI

异构机器人的自由度、执行器、传感器和计算平台统一通过标准 CLI 暴露。上层 Agent 面对一致的命令格式、单位、坐标系、时间戳、错误码和回滚语义。软件栈分为四层：

- **Hardware**：传感器、执行器、总线、固件、电源与硬件状态；
- **Linux**：进程、服务、网络、资源、文件与系统性能；
- **Middleware**：节点、Topic、Service、Action、TF、参数与诊断信息；
- **Application**：建图、定位、导航、操作、测试、调优与任务状态。

当前产品共定义 **294 个操作**：
[`docs/CANONICAL_OPERATIONS.md`](docs/CANONICAL_OPERATIONS.md)。

### 主动发现

首次配置时，rolo 为唯一 `robot_id` 建立一份可持续维护的**机器人 Wiki**。它把计算平台、
系统版本、传感器、执行器、总线、Linux 服务、ROS 图、本地源码、启动入口、通信协议、
依赖和风险放进同一张全栈地图。团队不再需要从某位资深工程师的记忆、零散 README、
厂商手册和现场脚本中拼凑“这台机器人到底如何工作”。

### `robot_use`

`robot_use` 可组合机器人本体或第三视角相机（如 VICON）、带时间戳的关键帧、任务状态、控制命令、里程计和遥测，用于多模态分析：

- 低频周期监督与状态变化触发；
- 测试步骤结束后的强制验证；
- 异常遥测触发的高频监督；
- 重叠时间窗与多帧时序理解；
- 未知错误时刻的粗到细录像回溯。

### 自主测试

用户可以结构化描述速度、加速度、目标误差、障碍物距离、禁入区、最长任务时间、传感器限制和故障条件。rolo 的目标是验证约束是否明确、可执行和可观测，并据此生成覆盖矩阵、正常/边界/异常测试、状态转换与组合测试、变形与故障注入测试、测试 Oracle、风险等级和执行顺序。

### 自主调优

算法参数通过统一注册表表达，包括标准名称、单位、当前值、默认值、范围、依赖关系、重启或标定要求、风险等级与回滚方法。调优遵循“建立基线 → 生成候选 → 受控试运行 → 评估 → 回归 → 固化或回滚”的生命周期。

### 自治与可审计

rolo 使用状态图管理发现、标定、操作、建图、定位、导航、测试、诊断、调优和回归。长时间任务可以生成 checkpoint，记录当前配置、活动任务、测试进度和证据索引。多台机器人可以运行相同的 Agent 和测试 DSL，同时保持独立身份、参数、状态与证据。

## 快速开始

开发和评审首先遵循 [ROLO 最高开发准则](docs/DEVELOPMENT_PRINCIPLES.md)。新环境的第一条
验收路径是 [10 分钟安装与 Demo](docs/QUICKSTART_10_MIN.md)：它使用离线 mock 夹具验证
安装、Discovery、Wiki、阶段状态和完整 Adapt 测试链路，不冒充真实机器人验收。

### 安装与配置

```bash
git clone https://github.com/zarcherlot/rolo.git
cd rolo
uv sync --frozen

# 在目标机器人上 source 日常运行使用的 ROS 和 workspace overlay 后执行：
uv run robotctl adapt start \
  --robot-id your_robot_id \
  --project-root /path/to/robot-workspace \
  --urdf /path/to/robot.urdf  # 可省略
```

不需要下载或安装 wheel。`uv sync --frozen` 从 Git checkout 创建锁定环境；此后的正式产品
入口只有一条 `robotctl adapt start`。它自动注册或复用机器人身份、检查环境、识别工程证据、
幂等建立本地 collector、采集并验证新鲜签名证据、执行只读发现、生成 Wiki，并在存在目标机
观测路由时继续完成 Adapter Agent、独立门禁、State Graph、Tool Catalog、handoff 和
release。Codex 首次认证是独立的人工安全门；尚未认证
时，以运行 Rolo 的同一操作系统用户执行一次 `codex login --device-auth`。

上述一条命令适用于 Rolo 与机器人工程运行在同一目标机的模式。控制器与目标机分离时，
descriptor、secret 和 SSH host-key 必须独立置备，按
[`TARGET_EVIDENCE_DEPLOYMENT.md`](docs/TARGET_EVIDENCE_DEPLOYMENT.md) 使用签名证据流程，不能为
追求“一条命令”而取消信任绑定。远程 pin 完成后，同样由
`robotctl adapt start --evidence-mode remote` 在一次 Journey 中采集、验签并完成 Adapt。

### 访问管理 API

API 默认仅监听机器人本机回环地址。需要远程访问时，建立 SSH 端口转发：

```bash
ssh -L 8080:127.0.0.1:8080 robot@ROBOT_IP
```

端口转发建立后，访问 `http://127.0.0.1:8080/docs`。API 与所有探针仍运行在目标机器人上。

### 三阶段工作流

| 阶段 | 主要产物 | Agent 要求 |
|---|---|---|
| `adapt` | 可编辑机器人 Wiki、机器证据、canonical CLI、State Graph、conformance、adapt handoff | Adapter Agent；缺省配置 Codex |
| `diagnose` | 约束内闭环诊断、调参证据、冻结配置、diagnosis handoff | Diagnosis Agent；`robot_use` 可选 |
| `verify` | 可选正式用例、全量回归、报告、证据包、verification handoff | Verification Agent |

状态查看：

```bash
uv run robotctl pipeline-status --robot "$ROBOT_ID"
```

#### 第一阶段：适配

Adapt 的目标是交付两样核心资产：

1. 一份研发团队读得懂、可维护的机器人 Wiki；
2. 一套由证据支撑并通过独立门禁的 canonical CLI、State Graph 和下游 handoff。

它让一个具身研发团队快速回答：机器人由哪些板卡和外设组成、运行哪些程序、如何启动、
节点和协议怎样连接、哪些依赖缺失、哪些能力只是推断、哪些接口已经完成门禁注册并可交给
Agent。新成员、算法、嵌入式、运维和测试看到的是同一份系统全貌。

正式产品流程是一条命令：

```bash
uv run robotctl adapt start \
  --robot-id "$ROBOT_ID" \
  --project-root /path/to/robot-application \
  --urdf /path/to/your_robot.urdf
```

`--urdf` 可省略；缺失硬件规格会作为未知项保留。`adapt start` 会在工程根目录四层以内有界
识别常规 `build`、`install`、`docs` 和 `launch`，并把工程根目录作为源码补充。若只需要
Discovery 与 Wiki，可增加 `--discover-only`。默认 `--evidence-mode local`，签名 bundle 的
collector ID、目标指纹、payload digest 和路径会写入 Journey v2 输出。

Rolo 开发者和现场排障仍可使用同一套底层服务的细粒度命令：

```bash
uv run robotctl adapt discover run --robot "$ROBOT_ID" \
  --urdf /path/to/your_robot.urdf \
  --build-root /path/to/robot-application/build \
  --install-root /path/to/robot-application/install \
  --doc-root /path/to/robot-application/docs \
  --launch-root /path/to/robot-application/launch \
  --source-root /path/to/robot-application \
  --active-probe runtime-readonly
uv run robotctl adapt discover review --robot "$ROBOT_ID"
uv run robotctl adapt operations summary --robot "$ROBOT_ID"
uv run robotctl adapt run --robot "$ROBOT_ID"
```

细粒度命令是调试接口，不是产品用户的必经启动步骤。完整边界见
[`ADAPT_SHORT_JOURNEY.md`](docs/ADAPT_SHORT_JOURNEY.md)。

Wiki 启发式 Agent skill 默认开启并在只读 sandbox 中运行；不可用或输出不合规时自动回退到
确定性规则，可通过 `WIKI_INSIGHTS_AGENT_ENABLED=false` 关闭。

```text
robot_wiki.md
├── 全栈摘要
│   ├── 发现状态、模式、兼容性与关键证据边界
│   └── 有依据、低/中置信度且待验证的启发式发现
├── 与上次发现的差异
│   └── 平台、ROS、应用、设备、操作候选和未知项变化
├── 启动与健康检查
│   └── launch 入口、参数默认值、include、启动顺序、停止与健康检查缺口
├── 硬件与机器人规格
│   ├── 计算平台、CPU 架构与驱动模型
│   ├── URDF 结构、几何与关键安全规格
│   └── 物理设备候选、内部流水线端点、未归并端点与硬件总线
├── 主机与软件栈
│   ├── 操作系统及 ROS/RMW/Domain 的配置来源与候选值
│   └── 工具可用性和版本证据
├── 应用程序与启动拓扑
│   ├── pyproject/setuptools/CMake 入口、launch 证据与风险
│   └── 按源文件/target 归属的 Python/C++ ROS 接口及未归属候选
├── ROS 与通信拓扑
│   └── 在线图与有边数上限的静态候选关系图
├── 工程操作候选
│   └── 只显示本次发现有适用证据的候选，不复制完整 registry
├── 依赖、差异与未知项
│   └── 按获取方式归类的缺口、依赖与兼容性差异
└── 总工维护建议与自动发现附录
```

主机透视 CLI 见 [`docs/AUTODISCOVERY.md`](docs/AUTODISCOVERY.md)，Adapter Agent 配置见 [`.env.example`](.env.example)。

#### 第二阶段：诊断

Diagnosis Agent 读取 adapt handoff 和用户约束，执行闭环诊断与调参。需要图像模型监督时，在源码仓库之外安全设置后端，再提交带时间戳的画面和结构化遥测：

```bash
export ROBOT_USE_BACKEND=openai
export OPENAI_API_KEY="..."
export OPENAI_MODEL="an-image-capable-model-available-to-your-project"

uv run robotctl diagnose status --robot "$ROBOT_ID"
uv run robotctl diagnose robot-use poll --robot "$ROBOT_ID" --image /tmp/frame.jpg
```

`robot_use` 只提供语义监督，不在本地执行视觉检测，也不拥有机器人的安全决策权。调参必须受用户约束和硬安全边界限制，每次修改后都要运行受影响的 smoke、安全与回归检查。

#### 第三阶段：验证

第三阶段用于检查正式验收准备度，并在实现相应 Verification Agent 能力后生成用例、执行全量回归和打包证据：

```bash
uv run robotctl verify status --robot "$ROBOT_ID"
```

## 工程结构

```text
src/rolo/stages/adapt/            第一阶段：发现、适配、conformance 与 handoff 发布
skills/rolo-wiki-authoring/        可选只读 Wiki 启发式 Agent skill
src/rolo/stages/diagnose/         第二阶段：Diagnosis Agent 闭环诊断、调参与 robot_use
src/rolo/stages/verify/           第三阶段：可选自主验证与正式验收
src/rolo/commands/                按命令域拆分的 robotctl 接口
src/rolo/core/                    共享配置、领域模型、制品与机器人注册表
src/rolo/integrations/robot_use/  robot_use 外部监督后端
src/rolo/                         共享 API、agentd 与 runtime
tests/                            离线单元测试、API 测试与测试夹具
schemas/                          导出的 JSON Schema
```

## 参与项目

欢迎通过 Issue 描述机器人平台、复现步骤和预期行为，并通过 Pull Request 提交小而可验证的改动。提交前请运行：

```powershell
uv run pytest
uv run ruff check .
```

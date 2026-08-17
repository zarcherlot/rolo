<p align="center">
  <img src="rolo-logo.svg" width="720" alt="rolo Loop Exit — robot only loop once">
</p>

<p align="center">
  <strong>在每一次执行中自我进化。</strong><br>
</p>

<p align="center">
  中文 · <a href="docs/README.en.md">English</a>
</p>

## rolo 是什么

**rolo** 是 **robot only loop once** 的缩写。它表达的是一种机器人开发原则：每运行一个边界清晰的任务，把输入、执行、观察和结果保留下来，让问题能够被解释、闭环和修正。

> [!NOTE]
> 当前版本是开发中的 MVP。模拟后端适合本地验证，但不替代真实机器人上的安全控制、急停、碰撞检测或人工授权。

## 产品特性

rolo 面向真实机器人的自主调试与测试，把每次运行组织成一个边界清晰的闭环：定义任务、执行动作、持续观察、判断结果、保留证据，再根据新的证据决定下一次运行。

### 1. 一次运行，一个完整证据闭环

rolo 不把“命令成功返回”视为任务完成。每次执行都应留下可以回放、解释和复现的 episode，包括：

- 下发命令与机器人实际执行状态；
- 传感器、系统遥测和相机画面；
- 参数、软件和能力配置版本；
- 测试判定、异常区间与诊断结论。

### 2. 标准 CLI

异构机器人的自由度、执行器、传感器和计算平台统一通过标准 CLI 暴露。上层 Agent 面对一致的命令格式、单位、坐标系、时间戳、错误码和回滚语义。软件栈分为四层：

- **Hardware**：传感器、执行器、总线、固件、电源与硬件状态；
- **Linux**：进程、服务、网络、资源、文件与系统性能；
- **Middleware**：节点、Topic、Service、Action、TF、参数与诊断信息；
- **Application**：建图、定位、导航、操作、测试、调优与任务状态。

### 3. 主动发现

首次部署时，rolo 为机器人分配唯一 `robot_id`，并通过主动发现生成标准化 capability manifest、语义绑定候选和 CLI tool catalog。发现范围包括计算平台、系统版本、传感器、执行器、总线、Linux 服务、ROS 图、本地源码工程以及已有的厂商和应用入口。

### 4. `robot_use`

`robot_use` 可组合机器人本体或第三视角相机（如 VICON）、带时间戳的关键帧、任务状态、控制命令、里程计和遥测，用于多模态分析：

- 低频周期监督与状态变化触发；
- 测试步骤结束后的强制验证；
- 异常遥测触发的高频监督；
- 重叠时间窗与多帧时序理解；
- 未知错误时刻的粗到细录像回溯。

### 5. 自主测试

用户可以结构化描述速度、加速度、目标误差、障碍物距离、禁入区、最长任务时间、传感器限制和故障条件。rolo 的目标是验证约束是否明确、可执行和可观测，并据此生成覆盖矩阵、正常/边界/异常测试、状态转换与组合测试、变形与故障注入测试、测试 Oracle、风险等级和执行顺序。

### 6. 自主调优

算法参数通过统一注册表表达，包括标准名称、单位、当前值、默认值、范围、依赖关系、重启或标定要求、风险等级与回滚方法。调优遵循“建立基线 → 生成候选 → 受控试运行 → 评估 → 回归 → 固化或回滚”的生命周期。

### 7. 自治与可审计

rolo 使用状态图管理发现、标定、操作、建图、定位、导航、测试、诊断、调优和回归。长时间任务可以生成 checkpoint，记录当前配置、活动任务、测试进度和证据索引。多台机器人可以运行相同的 Agent 和测试 DSL，同时保持独立身份、参数、状态与证据。

## 快速开始

### 环境要求

- Windows PowerShell 5.1+
- [`uv`](https://docs.astral.sh/uv/)
- 由 `uv` 管理的 Python 3.12

ROS 2 和 FFmpeg 对本地 mock 模式是可选项；接入真实机器人和相机后才需要它们。

### 安装与运行

```powershell
Copy-Item .env.example .env
uv sync --dev
uv run robotctl doctor
uv run robotctl robots
uv run robotctl serve
```

API 默认运行在 `http://127.0.0.1:8080`，OpenAPI 文档位于 `http://127.0.0.1:8080/docs`。

### 使用案例：三阶段机器人流程

完成本地安装后，按三阶段推进一台机器人；任意时刻可用 `uv run robotctl pipeline-status --robot demo_diff` 查看总状态。

| 阶段 | 主要产物 | Agent 要求 |
|---|---|---|
| `build` | 安装包、探针、capability manifest、候选语义绑定、工具目录、canonical CLI、State Graph、build handoff | Coding Agent |
| `debug` | 约束内闭环诊断、调参证据、冻结配置、debug handoff | Diagnosis Agent；`robot_use` 可选 |
| `test` | 可选正式用例、全量回归、报告和证据包 | Test Agent（选择该阶段时） |

#### 第一阶段：构建

Build 阶段合并安装、注册、发现、标准 CLI 构建和 State Graph 门禁。真机基线为 ARM64 + Ubuntu 22.04 + ROS 2 Humble；先构建通用归档并在目标机按物理结构注册唯一身份：

```powershell
.\scripts\build_bundles.ps1
```

归档位于 `dist/release/rolo-0.1.0-arm64.zip`。在目标机解压后执行：

```bash
sudo bash install.sh my_robot_01 differential_drive --confirm-safety-profile
```

本地开发无需安装归档；在空白配置目录中注册真机时，先核对结构、传感器和硬安全边界：

```powershell
$env:ROBOT_LOOP_CONFIG_DIR = "C:\robot-loop-config"
uv run robotctl build enroll profiles
uv run robotctl build enroll init --robot-id my_robot_01 --profile differential_drive --confirm-safety-profile
uv run robotctl build enroll show
```

每个实例只拥有一个 `robot_id`；更换身份或结构模板需要单独迁移。随后按真机相同顺序启动最小 daemon、执行只读发现，再启动完整 agentd：

```powershell
# 终端 1
uv run robotctl bootstrap-agentd --robot demo_diff --port 8100

# 终端 2
uv run robotctl build discover run --robot demo_diff --source-root C:\path\to\robot-application
uv run robotctl build discover show --robot demo_diff
uv run robotctl agentd --robot demo_diff --port 8101
```

发现流程采集硬件、主机软件栈、ROS 图和本地源码工程，保存 `hw/linux/ros/application` 探针，并将 capability manifest、候选语义绑定、工具目录和 build inputs 写入制品目录。缺少 ROS、BSP 或厂商驱动时仍保留 bootstrap agentd，完整 agentd 以 `DEGRADED` 运行；发现失败则不启动完整 agentd。新绑定与标定在验证前保持不可用。证据模型与安全边界见 [`AUTODISCOVERY.md`](docs/AUTODISCOVERY.md)。

Coding Agent 随后读取 build inputs，生成构建计划，并通过统一 CLI 实现和检查各层 adapter：

```powershell
uv run robotctl build plan --robot demo_diff
uv run robotctl tool catalog --robot demo_diff
uv run robotctl hw inventory scan
uv run robotctl linux host inspect
uv run robotctl ros graph snapshot
uv run robotctl app robot discover
uv run robotctl build status --robot demo_diff
```

只有 canonical CLI conformance 和 State Graph 基线通过后，才允许进入调试阶段。

#### 第二阶段：闭环诊断、调试与 `robot_use`

Diagnosis Agent 读取 build handoff 和用户约束，执行闭环诊断与调参。默认 `robot_use` 后端为本地 `mock`；需要图像模型监督时，在源码仓库之外安全设置后端，再提交带时间戳的画面和结构化遥测：

```powershell
$env:ROBOT_USE_BACKEND = "openai"
$env:OPENAI_API_KEY = "..."
$env:OPENAI_MODEL = "an-image-capable-model-available-to-your-project"

uv run robotctl debug status --robot demo_diff
uv run robotctl debug robot-use poll --robot demo_diff --image C:\path\to\frame.jpg
```

`robot_use` 只提供语义监督，不在本地执行视觉检测，也不拥有机器人的安全决策权。调参必须受用户约束和硬安全边界限制，每次修改后都要运行受影响的 smoke、安全与回归检查。

#### 第三阶段：可选正式测试

第三阶段用于检查正式验收准备度，并在实现相应 Test Skill 后由 Test Agent 生成用例、执行全量回归和打包证据：

```powershell
uv run robotctl test status --robot demo_diff
```

正式测试可选，但调试阶段的安全和影响范围回归不可省略。当前 MVP 尚未实现完整的自主验收执行器；ARM64 生产级离线安装也仍需补充 wheelhouse。阶段契约与实现成熟度见 [`ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

## 工程结构

```text
src/rolo/stages/build/   第一阶段：安装、注册、探针发现、CLI 构建与 State Graph 门禁
src/rolo/stages/debug/   第二阶段：Diagnosis Agent 闭环诊断、调参与 robot_use
src/rolo/stages/test/    第三阶段：可选自主测试与正式验收
src/rolo/core/           共享配置、领域模型、制品与机器人注册表
src/rolo/                共享 API、agentd、runtime 与兼容入口
configs/local/        本地 mock 示例机器人的能力清单
configs/profiles/     可注册的机器人结构与传感器模板
configs/deployment/   通用部署与服务配置
configs/platforms/    ARM64 兼容性和计算平台清单
configs/robot_use.yaml
configs/discovery.yaml
schemas/              导出的 JSON Schema
tests/                离线单元测试与 API 测试
scripts/              开发与安装包构建脚本
rolo-logo.svg         rolo 最终 SVG 标志
artifacts/            运行时产物（Git 忽略）
```

## 参与项目

欢迎通过 Issue 描述机器人平台、复现步骤和预期行为，并通过 Pull Request 提交小而可验证的改动。提交前请运行：

```powershell
uv run pytest
uv run ruff check .
```

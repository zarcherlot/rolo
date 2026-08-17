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

rolo (robot only loop once) 是一种具身机器人开发原则：每执行一次边界清晰的用例，获得输入、执行、观察和结果的切片，让机器人自主的解释、闭环和修正问题。

> [!NOTE]
> 当前版本是开发中的 MVP。模拟后端适合本地验证，但不替代真实机器人上的安全控制、急停、碰撞检测或人工授权。

## 产品特性

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

### 运行环境

rolo 安装并运行在目标机器人本体。agentd、探针和运行时制品均以机器人环境为准；可以通过本地控制台或 SSH 执行部署与后续操作。

| 项目 | 最低要求 |
|---|---|
| 处理器架构 | ARM64 |
| 操作系统 | Ubuntu LTS 20.04+；已验证 20.04、22.04、24.04 |
| Python | Python 3.10+，包含 `venv` |
| 系统环境 | systemd、Bash |
| 权限与工具 | `sudo`、`unzip`；远程部署时需 SSH/SCP |
| 依赖获取 | 安装时可访问目标环境已配置的 Python 软件包索引 |

Ubuntu 20.04 默认提供 Python 3.8，部署前需安装 Python 3.10+ 及对应的 `venv`。完全离线部署需在 ARM64 bundle 中补充 wheelhouse。

ROS 2、BSP、厂商驱动和 FFmpeg 按实际能力接入。ROS 探针优先检查当前环境，并可根据 Ubuntu 20.04、22.04、24.04 发现 Foxy、Humble、Jazzy 或 `/opt/ros` 下的其他发行版。缺少这些可选依赖不会阻止基础安装；doctor 和探针会将受影响能力标记为告警、`DEGRADED` 或 `UNAVAILABLE`。

### 构建与部署

使用已有发布归档时可直接执行复制与安装步骤。从源码生成归档还需要 PowerShell 5.1+、[`uv`](https://docs.astral.sh/uv/) 和 Python 3.10+：

```powershell
.\scripts\build_bundles.ps1
scp .\dist\release\rolo-0.1.0-arm64.zip robot@ROBOT_IP:/tmp/
ssh robot@ROBOT_IP
```

登录目标机器人后执行：

```bash
cd /tmp
unzip rolo-0.1.0-arm64.zip
cd rolo-0.1.0-arm64
sudo bash install.sh my_robot_01 differential_drive --confirm-safety-profile

sudo -i
set -a
source /etc/rolo/rolo.env
set +a
ROBOTCTL=/opt/rolo/venv/bin/robotctl
$ROBOTCTL doctor
$ROBOTCTL robots
```

安装完成后，rolo 软件包、agentd、探针和运行时制品均位于目标机器人。后续示例假设已进入上述 root shell，并已设置 `$ROBOTCTL`。

### 访问控制面

API 默认仅监听机器人本机回环地址。需要远程访问时，建立 SSH 端口转发：

```bash
ssh -L 8080:127.0.0.1:8080 robot@ROBOT_IP
```

端口转发建立后，访问 `http://127.0.0.1:8080/docs`。API 与所有探针仍运行在目标机器人上。

### 使用案例：三阶段工作流

完成机器人部署后，按三阶段推进；任意时刻可在机器人 shell 执行 `$ROBOTCTL pipeline-status --robot my_robot_01` 查看总状态。

| 阶段 | 主要产物 | Agent 要求 |
|---|---|---|
| `build` | 安装包、探针、capability manifest、候选语义绑定、工具目录、canonical CLI、State Graph、build handoff | Coding Agent；默认 Codex，可配置其他厂商 |
| `debug` | 约束内闭环诊断、调参证据、冻结配置、debug handoff | Diagnosis Agent；`robot_use` 可选 |
| `test` | 可选正式用例、全量回归、报告和证据包 | Test Agent（选择该阶段时） |

#### 第一阶段：构建

Build 阶段合并安装、注册、发现、标准 CLI 构建和 State Graph 门禁。安装器已经根据物理结构注册唯一 `robot_id`；更换身份或结构模板需要单独迁移。systemd 在机器人上严格按 `bootstrap-agentd → discovery → agentd` 启动，可检查身份和发现结果，或对机器人本地的应用源码重新运行只读发现：

```bash
$ROBOTCTL build enroll show
systemctl status rolo-bootstrap-agentd.service rolo-discovery.service rolo-agentd.service
$ROBOTCTL build discover show --robot my_robot_01
$ROBOTCTL build discover run --robot my_robot_01 --source-root /opt/robot-application
```

发现流程采集硬件、主机软件栈、ROS 图和本地源码工程，保存 `hw/linux/ros/application` 探针，并将 capability manifest、候选语义绑定、工具目录和 build inputs 写入制品目录。缺少 ROS、BSP 或厂商驱动时仍保留 bootstrap agentd，完整 agentd 以 `DEGRADED` 运行；发现失败则不启动完整 agentd。新绑定与标定在验证前保持不可用。证据模型与安全边界见 [`AUTODISCOVERY.md`](docs/AUTODISCOVERY.md)。

Coding Agent 随后读取 build inputs，生成构建计划，并通过统一 CLI 实现和检查各层 adapter。默认执行器是本机 `codex exec`。如果设备已经执行过 `codex login`，无需提供 API Key；也可通过环境变量选择模型，或连接支持 Responses API 的其他厂商/中转站。API Key 只从执行器进程环境读取，不会写入命令、Build Plan 或制品：

```bash
export CODING_AGENT_PROVIDER=codex
export CODING_AGENT_EXECUTOR=codex
export CODING_AGENT_AUTO_INSTALL=true
export CODING_AGENT_REQUIRE_AUTH=true
# 可选：留空时使用厂商官方/默认端点；中转站填写其兼容 API 地址
export CODING_AGENT_BASE_URL=""
export CODING_AGENT_API_KEY=""
# 可选：留空时由 Codex 或所选厂商采用默认模型
export CODING_AGENT_MODEL=""

$ROBOTCTL build agent-config
$ROBOTCTL build agent-prepare
$ROBOTCTL build plan --robot my_robot_01
$ROBOTCTL build execute --robot my_robot_01 --workspace /opt/robot-application
$ROBOTCTL tool catalog --robot my_robot_01
$ROBOTCTL hw inventory scan
$ROBOTCTL linux host inspect
$ROBOTCTL ros graph snapshot
$ROBOTCTL app robot discover
$ROBOTCTL build status --robot my_robot_01
```

部署 bundle 默认按 `configs/deployment/common.yaml` 的 `coding_agent` 配置，以 `rolo` 服务用户调用白名单中的官方 Codex Linux 安装器，并运行 `agent-prepare --skip-auth` 验证可执行文件和版本。安装源不能由 Base URL 替换。首次部署仍需用户以同一系统用户完成 `codex login --device-auth`；认证不会被静默自动化。

完整链路为“读取配置 → 缺失时自动安装 → 验证版本和认证 → 显式执行”。`build execute` 会再次运行依赖门禁；状态不是 `READY` 时不会启动模型。审计结果写入 `coding-agent/dependency/latest.json`。`build plan` 只生成计划，不会修改源码；执行器固定使用 `workspace-write` 沙箱、超时限制和结构化输出，保留 JSONL 事件、标准错误和无密钥运行元数据。它不会直接发布 `handoff.json`，该制品仍须由后续 conformance 门禁晋级。

例如使用其他厂商或中转站时，将 `CODING_AGENT_PROVIDER` 改为厂商标识，设置其 `CODING_AGENT_BASE_URL` 和模型名；若服务需要认证，再通过进程环境设置 `CODING_AGENT_API_KEY`。Build Plan 仅保存 provider、Base URL、模型名、Key 环境变量名以及是否已配置 Key，不保存 Key 本身。

机器人本体的自动安装、设备码登录、验证命令和落盘文件见 [`CODEX_SETUP.md`](docs/CODEX_SETUP.md)。

只有 canonical CLI conformance 和 State Graph 基线通过后，才允许进入调试阶段。

#### 第二阶段：闭环诊断、调试与 `robot_use`

Diagnosis Agent 读取 build handoff 和用户约束，执行闭环诊断与调参。默认 `robot_use` 后端为本地 `mock`；需要图像模型监督时，在源码仓库之外安全设置后端，再提交带时间戳的画面和结构化遥测：

```bash
export ROBOT_USE_BACKEND=openai
export OPENAI_API_KEY="..."
export OPENAI_MODEL="an-image-capable-model-available-to-your-project"

$ROBOTCTL debug status --robot my_robot_01
$ROBOTCTL debug robot-use poll --robot my_robot_01 --image /tmp/frame.jpg
```

`robot_use` 只提供语义监督，不在本地执行视觉检测，也不拥有机器人的安全决策权。调参必须受用户约束和硬安全边界限制，每次修改后都要运行受影响的 smoke、安全与回归检查。

#### 第三阶段：可选正式测试

第三阶段用于检查正式验收准备度，并在实现相应 Test Skill 后由 Test Agent 生成用例、执行全量回归和打包证据：

```bash
$ROBOTCTL test status --robot my_robot_01
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

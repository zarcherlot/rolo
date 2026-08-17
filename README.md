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

rolo (robot only loop once) 是一种具身机器人开发原则：每执行一次边界清晰的用例，获得输入、执行、观察和结果的切片，让机器人自主的解释、闭环和修正问题。

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

### 主动发现

首次配置时，rolo 为唯一 `robot_id`主动发现生成标准化 capability manifest、语义绑定候选和 CLI tool catalog。发现范围包括计算平台、系统版本、传感器、执行器、总线、Linux 服务、ROS 图、本地源码工程以及已有的厂商和应用入口。

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

### 安装与配置

```bash
git clone https://github.com/zarcherlot/rolo.git
cd rolo
uv sync --frozen

uv run robotctl init --robot-id your_robot_id
```

### 访问控制面

API 默认仅监听机器人本机回环地址。需要远程访问时，建立 SSH 端口转发：

```bash
ssh -L 8080:127.0.0.1:8080 robot@ROBOT_IP
```

端口转发建立后，访问 `http://127.0.0.1:8080/docs`。API 与所有探针仍运行在目标机器人上。

### 三阶段工作流

完成机器人配置后，按三阶段推进；任意时刻可在仓库目录执行 `uv run robotctl pipeline-status --robot "$ROBOT_ID"` 查看总状态。

| 阶段 | 主要产物 | Agent 要求 |
|---|---|---|
| `build` | 注册、探针、capability manifest、候选语义绑定、工具目录、canonical CLI、State Graph、build handoff | Coding Agent；缺省配置 Codex |
| `debug` | 约束内闭环诊断、调参证据、冻结配置、debug handoff | Diagnosis Agent；`robot_use` 可选 |
| `test` | 可选正式用例、全量回归、报告和证据包 | Test Agent |

#### 第一阶段：构建

Build 阶段合并注册、发现、标准 CLI 构建和 State Graph 门禁。首次配置登记用户指定的 `robot_id`，可在仓库目录检查身份和发现结果，或对机器人本地的URDF应用源码重新运行只读发现：

```bash
uv run robotctl build enroll show
uv run robotctl build discover show --robot "$ROBOT_ID"
uv run robotctl build discover run --robot "$ROBOT_ID" \
  --urdf /path/to/your_robot.urdf \
  --source-root /path/to/robot-application
```

发现流程采集硬件、主机软件栈、ROS 图和本地源码工程，保存 `hw/linux/ros/application` 四类探针，并将 capability manifest、候选语义绑定、工具目录和 build inputs 写入制品目录。

Coding Agent 随后读取 build inputs，生成构建计划，并通过统一 CLI 实现和检查各层 adapter。可通过本地 `.env` 选择模型或配置 API Key，支持中转站。

```dotenv
CODING_AGENT_PROVIDER=codex
CODING_AGENT_EXECUTOR=codex
CODING_AGENT_AUTO_INSTALL=true
CODING_AGENT_REQUIRE_AUTH=true
CODING_AGENT_EXECUTABLE=codex

CODING_AGENT_BASE_URL=
CODING_AGENT_MODEL=
CODING_AGENT_API_KEY=
```

```bash
uv run robotctl build agent-config
uv run robotctl build agent-prepare
uv run robotctl build plan --robot "$ROBOT_ID"
uv run robotctl build execute --robot "$ROBOT_ID" --workspace /path/to/robot-application
uv run robotctl tool catalog --robot "$ROBOT_ID"
uv run robotctl hw inventory scan
uv run robotctl linux host inspect
uv run robotctl ros graph snapshot
uv run robotctl app robot discover
uv run robotctl build status --robot "$ROBOT_ID"
```

只有 canonical CLI conformance 和 State Graph 基线通过后，才允许进入调试阶段。

#### 第二阶段：闭环调试与诊断

Diagnosis Agent 读取 build handoff 和用户约束，执行闭环诊断与调参。需要图像模型监督时，在源码仓库之外安全设置后端，再提交带时间戳的画面和结构化遥测：

```bash
export ROBOT_USE_BACKEND=openai
export OPENAI_API_KEY="..."
export OPENAI_MODEL="an-image-capable-model-available-to-your-project"

uv run robotctl debug status --robot "$ROBOT_ID"
uv run robotctl debug robot-use poll --robot "$ROBOT_ID" --image /tmp/frame.jpg
```

`robot_use` 只提供语义监督，不在本地执行视觉检测，也不拥有机器人的安全决策权。调参必须受用户约束和硬安全边界限制，每次修改后都要运行受影响的 smoke、安全与回归检查。

#### 第三阶段：测试

第三阶段用于检查正式验收准备度，并在实现相应 Test Skill 后由 Test Agent 生成用例、执行全量回归和打包证据：

```bash
uv run robotctl test status --robot "$ROBOT_ID"
```

## 工程结构

```text
src/rolo/stages/build/   第一阶段：注册、探针发现、CLI 构建与 State Graph 门禁
src/rolo/stages/debug/   第二阶段：Diagnosis Agent 闭环诊断、调参与 robot_use
src/rolo/stages/test/    第三阶段：可选自主测试与正式验收
src/rolo/core/           共享配置、领域模型、制品与机器人注册表
src/rolo/                共享 API、agentd、runtime 与兼容入口
configs/local/        本地 mock 示例机器人的能力清单
configs/profiles/     URDF profile 格式示例
configs/platforms/    ARM64 兼容性和计算平台清单
configs/robot_use.yaml
configs/discovery.yaml
schemas/              导出的 JSON Schema
tests/                离线单元测试与 API 测试
scripts/              开发辅助脚本
rolo-logo.svg         rolo 最终 SVG 标志
```

## 参与项目

欢迎通过 Issue 描述机器人平台、复现步骤和预期行为，并通过 Pull Request 提交小而可验证的改动。提交前请运行：

```powershell
uv run pytest
uv run ruff check .
```

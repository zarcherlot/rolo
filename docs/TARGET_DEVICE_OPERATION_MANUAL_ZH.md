# Rolo 目标机部署与 Adapt 操作手册

版本：`v0.1.0-rc.2`

适用范围：Linux 机器人或机器人应用目标机；ROS 为可选 Middleware

本手册用于在真实机器人目标机上部署 Rolo 并运行 Adapt。Adapt 负责采集签名证据、发现
机器人接口、生成 Wiki 和 Adapter、执行独立门禁，并发布 State Graph、Tool Catalog、handoff
与不可变 release。Adapt 不执行机器人写操作，也不证明行为正确性、可靠性、性能或安全性。
未经后续安全验收，不要执行 `robotctl tool invoke`。

## 0. 控制器 SSH + 自然语言执行远程 Adapt（推荐操作路径）

本节给出统一 Agent 开发预览中最短、可复现的远程操作路径。操作者先 SSH 登录
Controller，在 Controller 上启动 Rolo Session Agent；Session Agent 再通过已注册、host-key pinned、
用途分离的 SSH 身份访问目标机。Codex 只选择 broker 暴露的结构化动作，不接触目标 SSH 私钥、
Controller bearer、原始目标输出、shell 或任意 argv。

```text
操作者终端
  └─ SSH 登录 Controller
       └─ robotctl target agent run "自然语言请求"
            ├─ Codex：只选择结构化动作
            └─ authenticated broker
                 ├─ Controller Job / Approval / artifact store
                 └─ pinned SSH + forced command → 目标机 runtime
```

当前实现有三个必须先接受的边界：

1. CLI 的一次 `target agent run` 是一轮有界自然语言会话，不是持续等待输入的聊天 REPL。每轮可执行
   1–8 个动作；下一轮必须使用新的 `--idempotency-key`。同一 key 只用于原请求的安全重试，不能换消息复用。
2. Agent 不能批准自己创建的 R2/R3 Approval。结果为 `APPROVAL_REQUIRED` 时，必须由另一主体通过
   `target approval decide` 或独立 authenticated GUI 审批，然后才可让 Agent 运行 Job。
3. 当前 SSH Adapt 只完成 metadata/source/runtime evidence 绑定的 discovery Journey。成功标准是 Adapt Job
   `COMPLETE` 且 Journey 为 `DISCOVERY_COMPLETE`；SSH 模式仍拒绝 `--run-adapter-agent`，因此本流程不代表
   Adapter 已生成、stage、activate，也不代表机器人行为通过安全验证。

### 0.1 选择“远程”的含义

推荐让 Rolo、Codex 和所有 Controller 状态都运行在 Controller 主机，目标机只运行受限 runtime：

```bash
ssh rolo-operator@controller.example.internal
cd /opt/rolo-controller
```

这种方式不要求启动 HTTP API；`robotctl target agent run` 会在当前 Controller 进程中启动 Session Agent。
不要把 Codex provider key 或 Controller 状态复制到目标机，也不要让通用管理员 SSH 身份成为 runtime 身份。

如果要从本机浏览器使用 `rolo-deployment-control` GUI，则让 API 只监听 Controller loopback，并建立 SSH
端口转发：

```bash
# Controller：使用仅含 target:write 的独立操作 token。
export ROLO_API_TOKEN='<controller-operator-token>'
export ROLO_API_TOKEN_PRINCIPAL='operator@example.com'
export ROLO_API_TOKEN_PERMISSIONS='target:write'
uv run robotctl serve --host 127.0.0.1 --port 8080

# 操作者本机：保持该命令运行，再让 GUI 连接 http://127.0.0.1:8080。
ssh -N -L 8080:127.0.0.1:8080 rolo-operator@controller.example.internal
```

审批者应使用另一个 principal 和只在审批入口使用的 `approval:write` token。不要给 Session Agent 请求同时
携带 `approval:write`，也不要把 API 直接绑定公网地址。

### 0.2 Controller 首次准备

以下命令以源码 checkout 为例；如果使用已审核安装包，可去掉 `uv run`：

```bash
git fetch origin
git switch codex/unified-agent-deployment
uv sync --locked

command -v codex
uv run robotctl --help
```

如果控制器是第一次检出该开发分支，本地还没有同名分支，请把上面的 `git switch` 替换为：

```bash
git switch --track -c codex/unified-agent-deployment origin/codex/unified-agent-deployment
```

为 Controller 状态选择持久目录。运行 Rolo 的专用账号应独占这些目录：

```bash
install -d -m 0700 /var/lib/rolo-controller/config
install -d -m 0700 /var/lib/rolo-controller/artifacts
install -d -m 0700 /var/lib/rolo-controller/output

export ROLO_CONFIG_DIR=/var/lib/rolo-controller/config
export ROLO_ARTIFACT_DIR=/var/lib/rolo-controller/artifacts
export ROLO_OUTPUT_DIR=/var/lib/rolo-controller/output
```

启用 Session Agent，并使用一份只供模型 provider 使用的 credential。该 key 不能复用浏览器 token、SSH key
或目标 authorization key：

```bash
export ROLO_SESSION_AGENT_ENABLED=true
export ROLO_SESSION_AGENT_API_KEY='<dedicated-provider-key>'
export ROLO_SESSION_AGENT_MODEL='<approved-codex-model>'
export ROLO_SESSION_AGENT_BASE_URL='https://api.openai.com/v1'
export ROLO_SESSION_AGENT_EXECUTABLE='codex'
export ROLO_SESSION_AGENT_PROVIDER_TIMEOUT_S=120

export ROLO_API_TOKEN_PRINCIPAL='operator@example.com'
export ROLO_API_TOKEN_PERMISSIONS='target:write'
```

先检查静态边界和真实 provider。`production_ready=false` 是当前 W10 未完成时的预期结果，不应篡改为通过：

```bash
uv run robotctl target agent readiness

ROLO_RUN_REAL_SESSION_AGENT=1 \
  uv run pytest -q tests/test_real_session_agent.py
```

若 readiness 显示 feature flag、provider credential、Codex executable 或模型未配置，先修复 Controller；
不要降级为让 Codex 获得自由 shell。

### 0.3 注册 SSH 目标

如果 `robotctl target tui --page target --target wheeltec` 已能显示正确注册信息，可跳到 0.4。首次注册前必须
通过独立可信信道核对目标 OpenSSH Ed25519 host key，并准备只包含该 host 的 `known_hosts`。不要把未经核对的
`ssh-keyscan` 输出直接当作信任依据。

下面示例同时登记三种用途的 SSH 身份：已有管理员身份用于 host provisioning；bootstrap 身份用于受限安装；
runtime 身份只执行最终只读/授权 proof-bound forced commands。三个私钥路径必须不同：

```bash
uv run robotctl target add wheeltec \
  --ssh rolo-bootstrap@192.168.1.20 \
  --port 22 \
  --credential-ref file-credential:///home/controller/.ssh/rolo-wheeltec-bootstrap \
  --provisioning-user operator \
  --provisioning-credential-ref file-credential:///home/controller/.ssh/wheeltec-admin \
  --runtime-user rolo-runtime \
  --runtime-credential-ref file-credential:///home/controller/.ssh/rolo-wheeltec-runtime \
  --known-hosts /home/controller/.config/rolo/ssh/wheeltec_known_hosts \
  --host-key-sha256 'SHA256:<独立核验的43字符Base64指纹>' \
  --workspace /home/robot/wheeltec_ws \
  --desired-version 0.2.0 \
  --release-signing-key-id release-key-2026 \
  --release-signing-public-key /etc/rolo/trust/release-key-2026.pub.pem \
  --requested-by operator@example.com \
  --idempotency-key target-wheeltec-20260826
```

`file-credential://` 只引用 Controller 上的绝对私钥路径；结果、日志和 Agent prompt 都不应包含私钥正文。
目标机若还没有 bootstrap/runtime forced-command 用户、Controller authorization public-key pin 和 v4 Collector
identity，先完成 4.0 的 host provisioning、Bootstrap、service start 和 `robotctl target enroll`。统一 W7–W10
链不需要在目标机手工执行 legacy `robotctl target-evidence collector-init`。

### 0.4 第一轮自然语言：连接检查

在 Controller 的 SSH 会话中执行：

```bash
uv run robotctl target agent run \
  '只允许操作 wheeltec。读取注册状态，创建 runtime-readonly 连接评估 Job，并在策略允许时运行它；不要执行部署、审批或其他目标。' \
  --target wheeltec \
  --max-tool-calls 4 \
  --timeout-s 180 \
  --idempotency-key nl-wheeltec-assess-20260826-01
```

保存 JSON 返回中的 `session_id`、`receipts[].job_id`、状态和摘要。若 Agent 只创建 Job 而没有运行，使用一个新
自然语言轮次，并把真实 Job ID 明确写入消息：

```bash
uv run robotctl target agent run \
  '运行已创建的连接评估 Job deployment-<32位十六进制ID>，然后报告最终状态；不要创建新 Job。' \
  --target wheeltec \
  --max-tool-calls 3 \
  --timeout-s 180 \
  --idempotency-key nl-wheeltec-assess-20260826-02
```

连接评估必须完成且不能出现 host-key、credential purpose、forced-command 或目标身份错误。需要原始规范化状态时：

```bash
uv run robotctl target job get --job-id deployment-<连接评估Job ID>
uv run robotctl target job events --job-id deployment-<连接评估Job ID>
```

### 0.5 通过自然语言建立三段 SSH Adapt 证据链

完整的 SSH discovery 需要 project-evidence、source-discovery、runtime-evidence 三个独立 Job。每个 Job 都会创建
独立 R2 Approval，因此按“自然语言提交 → 独立审批 → 自然语言运行”重复三次。示例审批者
`reviewer@example.com` 必须与请求人不同。

第一段，冻结项目 metadata 候选：

```bash
uv run robotctl target agent run \
  '为 wheeltec 提交默认有界 project evidence 请求，审批人是 reviewer@example.com；提交后停止，不要自批或运行。' \
  --target wheeltec \
  --max-tool-calls 2 \
  --timeout-s 120 \
  --idempotency-key nl-wheeltec-project-evidence-20260826-01
```

从返回中复制真实 `approval_id` 和 `job_id`，由审批者核对 target、workspace、候选集合和 digest 后审批：

```bash
uv run robotctl target approval decide \
  --approval-id approval-<32位十六进制ID> \
  --principal reviewer@example.com \
  --idempotency-key approve-wheeltec-project-evidence-20260826-01 \
  --reason '已核对 wheeltec、workspace、默认候选范围与请求摘要' \
  --approve

uv run robotctl target agent run \
  '运行已批准的 project-evidence Job deployment-<32位十六进制ID>，不要执行其他 Job。' \
  --target wheeltec \
  --max-tool-calls 2 \
  --timeout-s 180 \
  --idempotency-key nl-wheeltec-project-evidence-20260826-02
```

第二段，冻结 workspace 根目录的有界结构化源码分析：

```bash
uv run robotctl target agent run \
  '为 wheeltec 提交 source discovery 请求，审批人是 reviewer@example.com；只使用已注册 workspace 的默认根目录，不读取源码正文。' \
  --target wheeltec \
  --max-tool-calls 2 \
  --timeout-s 120 \
  --idempotency-key nl-wheeltec-source-discovery-20260826-01

uv run robotctl target approval decide \
  --approval-id approval-<source审批ID> \
  --principal reviewer@example.com \
  --idempotency-key approve-wheeltec-source-discovery-20260826-01 \
  --reason '已核对 workspace、scan root、文件和时间预算' \
  --approve

uv run robotctl target agent run \
  '运行已批准的 source-discovery Job deployment-<source Job ID>，不要执行其他 Job。' \
  --target wheeltec \
  --max-tool-calls 2 \
  --timeout-s 240 \
  --idempotency-key nl-wheeltec-source-discovery-20260826-02
```

第三段，采集 proof-bound `hw/linux/ros` 运行时证据。该 artifact 最长只允许 300 秒 freshness，因此批准后应
立即运行，并紧接着提交 Adapt：

```bash
uv run robotctl target agent run \
  '为 wheeltec 提交 runtime evidence 请求，审批人是 reviewer@example.com；只采集固定的 hw、linux、ros 只读证据。' \
  --target wheeltec \
  --max-tool-calls 2 \
  --timeout-s 120 \
  --idempotency-key nl-wheeltec-runtime-evidence-20260826-01

uv run robotctl target approval decide \
  --approval-id approval-<runtime审批ID> \
  --principal reviewer@example.com \
  --idempotency-key approve-wheeltec-runtime-evidence-20260826-01 \
  --reason '已核对目标、固定证据层、Collector pin、proof 摘要和有效期' \
  --approve

uv run robotctl target agent run \
  '立即运行已批准的 runtime-evidence Job deployment-<runtime Job ID>，不要执行其他 Job。' \
  --target wheeltec \
  --max-tool-calls 2 \
  --timeout-s 180 \
  --idempotency-key nl-wheeltec-runtime-evidence-20260826-02
```

三份 Job 必须均为 `COMPLETE`。如果任何一份为 `BLOCKED`、`FAILED` 或已过期，不要继续拼接 Adapt；先查看
`target job events`，修复后创建新的证据 Job。

### 0.6 最终自然语言轮次：创建并运行 SSH Adapt

把前三步真实的完成态 Job ID 原样写入消息。不要让模型猜 ID，也不要省略 project Job；source Job 必须与
project Job 绑定同一 workspace。runtime Job 应在 300 秒 freshness 窗口内：

```bash
uv run robotctl target agent run \
  '为 wheeltec 创建并运行 discovery-only Adapt。绑定 project-evidence Job deployment-<project Job ID>、source-discovery Job deployment-<source Job ID>、runtime-evidence Job deployment-<runtime Job ID>；使用 runtime-readonly，不运行 adapter agent。完成后报告 Adapt Job ID 和最终状态。' \
  --target wheeltec \
  --max-tool-calls 4 \
  --timeout-s 600 \
  --idempotency-key nl-wheeltec-adapt-20260826-01
```

如果本轮只返回 `SUBMITTED`，用返回的真实 Adapt Job ID 开一个新轮次运行：

```bash
uv run robotctl target agent run \
  '运行 Adapt Job deployment-<Adapt Job ID> 并报告最终状态；不要创建或运行其他 Job。' \
  --target wheeltec \
  --max-tool-calls 2 \
  --timeout-s 600 \
  --idempotency-key nl-wheeltec-adapt-20260826-02
```

最终验收：

```bash
uv run robotctl target job get --job-id deployment-<Adapt Job ID>
uv run robotctl target job events --job-id deployment-<Adapt Job ID>
uv run robotctl target tui --page job --job-id deployment-<Adapt Job ID>
uv run robotctl target tui --page blocker
```

只有 Job 为 `COMPLETE` 且 Journey artifact 为 `DISCOVERY_COMPLETE` 才表示本次远程 discovery Adapt 完成。
`APPROVAL_REQUIRED` 表示等待人类审批，`SUBMITTED` 表示只创建未运行，`ACTION_BUDGET_EXHAUSTED` 表示应缩小
自然语言请求，`BLOCKED/REQUIRES_RECONCILIATION` 表示结果可能不确定、不得盲目重跑。

### 0.7 停止、取消与恢复

已知 Job ID 时可自然语言请求取消，也可使用确定性 CLI：

```bash
uv run robotctl target agent run \
  '取消 Job deployment-<32位十六进制ID>，不要操作其他 Job。' \
  --target wheeltec \
  --max-tool-calls 2 \
  --timeout-s 120 \
  --idempotency-key nl-wheeltec-cancel-20260826-01

uv run robotctl target job cancel --job-id deployment-<32位十六进制ID>
```

SSH 断开、Controller 重启或运行结果未知时，先读取 Job 和 Event。只有未开始的幂等提交可以安全重试；目标写操作
进入 `REQUIRES_RECONCILIATION` 时必须走对应 reconciliation 流程。不得使用 raw SSH 修改 target runtime、
`current.json`、authorization pin 或 Job artifact。

## 1. 选择证据采集模式

Rolo 支持两种显式模式，两者生成相同格式的签名目标证据。

### 模式 A：Rolo 运行在目标机上（推荐）

适合能够在机器人主机上运行 Rolo 和 Codex Agent 的部署。`adapt start` 默认使用本地模式，
不需要指定 `--evidence-mode`。这是最短的首次真机路径。

### 模式 B：控制器加目标机 Collector

适合目标机资源有限、不允许保存 Codex 凭据，或 Agent 必须运行在独立控制器上的部署。
目标机只运行受限的只读 Collector；控制器显式使用 `--evidence-mode remote`。远程采集失败
不会回退到控制器本机的 Linux、ROS 或硬件证据。

## 2. 模式 A：目标机一体化部署

### 2.1 部署前检查

目标机应准备：

- Linux，推荐 Ubuntu/Debian；
- Git 和 `uv`；
- 机器人工程所需的运行时；使用 ROS 的目标应安装对应 ROS 发行版，非 ROS 目标无需安装 ROS；
- 机器人工程源码；
- 完整 Agent 链使用的 Codex CLI；
- 完整 Gate 使用的 `bubblewrap` 和可用的 Linux namespace。

检查基础工具：

```bash
git --version
uv --version
codex --version
```

Rolo 不需要安装 wheel，也不要求预先创建配置、制品、输出或临时目录。

### 2.2 获取固定版本

```bash
git clone --branch v0.1.0-rc.2 --depth 1 \
  https://github.com/zarcherlot/rolo.git
cd rolo
```

该命令固定获取已经通过远端 CI 和真实 Agent 验收的 `v0.1.0-rc.2`，不会随 `main` 后续变化。

### 2.3 安装锁定依赖和生产沙箱

```bash
uv sync --frozen
```

Ubuntu/Debian 示例：

```bash
sudo apt-get update
sudo apt-get install --yes bubblewrap
```

完整 `adapt start` 会执行生产沙箱自检。如果目标内核禁止创建 user、mount 或 network
namespace，流程会在 Discovery 前安全停止。

### 2.4 完成 Codex 登录

完整 Agent 链首次运行前，以运行 Rolo 的同一操作系统账号执行：

```bash
codex login --device-auth
```

确定性证据采集不需要 Codex 凭据；启发式 Agent、Adapter Agent 和完整发布链需要完成登录。

### 2.5 默认目录与可选配置

Rolo 无须配置文件即可运行。Linux 默认路径为：

```text
~/.config/rolo/config.yaml           可选的用户配置
~/.local/state/rolo/config/          机器人身份和 Collector 状态
~/.local/share/rolo/artifacts/       Discovery、Wiki、Gate 和审计证据
~/.local/share/rolo/output/          不可变 Adapter release
系统安全临时目录                     Agent 临时工作区，结束后删除
```

运行时会自动创建所需目录，不需要设置 `ROLO_ARTIFACT_DIR` 或 `ROLO_OUTPUT_DIR`。

查看当前有效配置：

```bash
uv run robotctl config show
```

需要修改默认值时生成配置文件：

```bash
uv run robotctl config init
uv run robotctl config validate
```

`config init` 不会覆盖已经存在的文件。配置优先级为：命令行、环境变量、用户 YAML、`.env`、
内置默认值。

### 2.6 目标运行环境与可选 ROS 自动加载

非 ROS 工程无需配置或补造 ROS 环境。Rolo 直接采集目标操作系统、工程入口、依赖、CLI/API、
协议、进程和设备接口，并把 ROS Probe 的不可用记录为不适用边界，而不是工程缺陷。

目标或工程存在 ROS 证据时，通常不需要手工执行任何 `source`。Rolo 按以下顺序解析 setup
文件：

1. `~/.config/rolo/config.yaml` 中明确配置的 `ros.setup_files`；
2. 继承的 `ROS_DISTRO` 对应的 ROS base，或唯一的 `/opt/ros/<distro>/setup.bash`；
3. `<project-root>/install/local_setup.bash`；
4. 不存在 `local_setup.bash` 时使用 `<project-root>/install/setup.bash`。

Rolo 不加载 `.bashrc`、`.profile` 或 Agent 自主选择的脚本。存在多个 ROS 发行版或 overlay
候选时会失败关闭，部署者必须明确配置顺序：

```yaml
schema_version: rolo-config/v1

storage:
  config_dir: ~/.local/state/rolo/config
  artifact_dir: ~/.local/share/rolo/artifacts
  output_dir: ~/.local/share/rolo/output
  scratch_dir: null

agent:
  provider: codex
  executable: codex
  timeout_s: 1800

ros:
  auto_source: true
  setup_files:
    - /opt/ros/humble/setup.bash
    - /home/robot/wheeltec_ws/install/local_setup.bash
  domain_id: "0"
  rmw_implementation: rmw_fastrtps_cpp
```

修改后执行：

```bash
uv run robotctl config validate
```

setup 文件路径和 SHA-256 会写入签名目标证据。已固定的 setup 文件发生变化后，Collector
会拒绝继续采集，需要按[目标证据部署规范](TARGET_EVIDENCE_DEPLOYMENT.md)执行轮换和重新注册。

### 2.7 启动完整 Adapt

没有 URDF 时：

```bash
uv run robotctl adapt start \
  --robot-id wheeltec \
  --project-root /home/robot/wheeltec_ws \
  --timeout 1800
```

有 URDF 时：

```bash
uv run robotctl adapt start \
  --robot-id wheeltec \
  --project-root /home/robot/wheeltec_ws \
  --urdf /home/robot/wheeltec_ws/src/robot_description/urdf/robot.urdf \
  --timeout 1800
```

`--urdf` 可以省略。缺失的硬件规格会标记为未知，不会被启发式输出冒充为确定事实。

非 ROS Application/CLI 工程首次运行时，只固定已经人工审核的目标可执行文件。建议先只生成
Discovery 与 Wiki：

```bash
uv run robotctl adapt start \
  --robot-id lerobot-host \
  --project-root /home/robot/lerobot \
  --allow-executable "$(command -v lerobot-find-cameras)" \
  --allow-executable "$(command -v lerobot-info)" \
  --discover-only \
  --timeout 1800
```

`--allow-executable` 会在 Collector enrollment 时固定绝对路径和 SHA-256，只允许采集有界
`--help` 证据，不会执行实际业务子命令。确认 Wiki、Route 和缺口后，移除
`--discover-only` 重跑完整 Agent/Gate 链。已存在 Collector 若要改变 allowlist，必须执行
显式 rotation/re-enrollment，不能静默扩大采集面。

这一条产品命令会自动：

1. 准备用户级运行目录；
2. 注册或复用机器人身份和本地 Collector；
3. 解析并固定目标运行环境；仅在 ROS 相关时加载 ROS setup；
4. 采集并验证 Hardware、Linux、Application 及可选 ROS 签名证据；
5. 有界扫描机器人工程源码；
6. 运行启发式自主发现、Operation 映射和 Wiki 编写技能；
7. 启动真实 Adapter Agent 并冻结结构化代码输出；
8. 执行独立 Gate；
9. 生成 State Graph、Tool Catalog 和 handoff；
10. 发布不可变 Adapter release。

只运行 Discovery 与 Wiki 时增加：

```bash
uv run robotctl adapt start \
  --robot-id wheeltec \
  --project-root /home/robot/wheeltec_ws \
  --discover-only
```

## 3. 检查和验收

以下命令均为只读检查，不会调用目标 Operation：

```bash
uv run robotctl adapt status --robot wheeltec
uv run robotctl adapt operations summary --robot wheeltec
uv run robotctl adapt operations list --robot wheeltec --registration REGISTERED
uv run robotctl tool catalog --robot wheeltec
uv run robotctl state graph snapshot --robot wheeltec
```

检查单个 Operation 时，将 `OPERATION` 替换为实际名称：

```bash
uv run robotctl adapt candidates inspect OPERATION --robot wheeltec
uv run robotctl adapt operations inspect OPERATION --robot wheeltec
uv run robotctl tool schema OPERATION --robot wheeltec
```

### 3.1 生成回传验收包

```bash
uv run robotctl adapt acceptance-pack \
  --robot wheeltec \
  --output ./rolo-adapt-acceptance.json
```

向评审方回传：

- `rolo-adapt-acceptance.json`；
- 命令报告的 SHA-256；
- 流程失败时的终端错误信息。

验收包包含源码版本、Registry 身份与数量、目标证据 digest、Discovery 状态、eligible/deferred
Operation、Gate 与 release 身份，不包含凭据、调用载荷、私有源码归档或完整原始 Probe 数据。

### 3.2 完整 Adapt 判定标准

- Adapt 状态为 `COMPLETE`，独立 Gate 为 `PASSED`；
- Journey v2 中存在 Collector ID、目标指纹和 bundle digest；
- Registry 保持完整产品 Operation 集，而不是只剩本机候选；
- 纳入 bundle 的 Operation 为 `VERIFIED`，且唯一绑定到对应 release 入口；
- deferred Operation 为 `UNAVAILABLE`，不能以未验证状态进入门禁目录；
- State Graph 为 `robot-state-graph/v2`，并包含 Operation 到现场路由的边；
- release manifest 记录所有 Adapter 文件、受控 Runtime Context 和 Operation 级目标指纹；
- 再次运行等价发现后，Adapt 仍保持 `COMPLETE`。

Discovery 为 `PARTIAL` 不一定失败。缺失证据与本次目标 Operation 无关时可以继续；关键路由、
目标机身份、签名或 Gate 证据缺失时必须停止。

## 4. 模式 B：控制器与目标机分离

稳定版模式中的 SSH 只承载一次一请求的只读 Collector 协议，不提供交互式 Shell、任意命令执行、
断点调试或写 Operation。W7 开发预览另行定义 bootstrap/runtime 两类 forced-command credential；Bootstrap
只接受严格类型化的签名包事务，仍不开放 shell/argv。各 credential 必须使用独立账号或独立密钥并绑定固定命令。
运维人员需要登录目标机时，应使用另一套经过授权的管理账号和密钥。

> 开发分支说明：以下 4.0 节同时描述 W3 dry-run 与 W7 受审批 Bootstrap Job，尚不属于
> `v0.1.0-rc.2` 正式流程。W7 已能从控制器的不可变包仓库上传、安装 runtime，并在同一事务中
> 首次安装或 CAS 轮换目标侧 authorization key pin；它尚未代替 4.1-4.6 的稳定版主机账号、
> systemd、真实 sshd 与真机验收流程。

### 4.0 统一 Agent SSH Bootstrap dry-run（开发分支）

控制器侧首次预检只要求目标机具有受信任的 SSH 服务和 `python3`，不要求预先安装
`robotctl`。Rolo 对这个固定工具使用内置 `python3 -` stdin 协议，实际检查 Linux/CPU/Python、
bubblewrap、user/mount/network namespace、显式 `PATH`/`PYTHONPATH`、virtualenv、address-space
和 process/cgroup 预算。脚本和远程命令均不接受 Agent 拼接的 shell 参数。

先在控制器的 `<config_dir>/target-profiles/` 下准备 secret-free profile。SSH 私钥只使用引用，
不得写入 JSON。示例：

```text
target-profiles/
├── connections/conn-wheeltec.json
└── targets/wheeltec.json
```

```json
{
  "schema_version": "rolo-target-connection-profile/v1",
  "connection_profile_id": "conn-wheeltec",
  "transport": "SSH",
  "host": "192.0.2.10",
  "port": 22,
  "user": "rolo",
  "credential_ref": "file-credential:///home/controller/.ssh/rolo-wheeltec-bootstrap",
  "provisioning_user": "operator",
  "provisioning_credential_ref": "file-credential:///home/controller/.ssh/wheeltec-admin",
  "runtime_user": "rolo",
  "runtime_credential_ref": "file-credential:///home/controller/.ssh/rolo-wheeltec-runtime",
  "known_hosts_path": "/home/controller/.config/rolo/ssh/wheeltec_known_hosts",
  "trust_level": "STRICT",
  "expected_host_key_sha256": "SHA256:<独立核验的43字符Base64指纹>",
  "ssh_ca_ref": null,
  "proxy_jump_profile_id": null
}
```

三个 SSH 身份用途不同：`provisioning_*` 是目标机上已经存在、可执行经审批 host mutation 的管理员
身份；`user/credential_ref` 是主机置备后用于上传和安装签名 runtime 的 bootstrap forced-command
身份；`runtime_*` 是最终只允许固定 typed command 的运行期身份。它们可以共享 `rolo` 用户，但
bootstrap/runtime 必须使用不同密钥；provisioning 身份还必须与二者不同。省略新增字段仅用于兼容既有
单身份 profile，不满足新的自主主机置备门禁。

```json
{
  "schema_version": "rolo-target-profile/v1",
  "target_id": "wheeltec",
  "orchestrator_placement": "CONTROLLER",
  "transport": "SSH",
  "connection_profile_id": "conn-wheeltec",
  "workspace_root": "/home/robot/wheeltec_ws",
  "desired_rolo_version": "0.2.0",
  "trust_level": "STRICT",
  "release_signing_key_id": "release-key-2026",
  "release_signing_public_key_path": "/etc/rolo/trust/release-key-2026.pub.pem",
  "release_signing_public_key_sha256": "<规范化Ed25519公钥的64字符小写SHA-256>"
}
```

三个 `release_signing_*` 字段必须同时出现或同时省略。公钥路径是控制器上的绝对路径；digest
计算对象是解析 PEM/DER 后的 32-byte Ed25519 raw public key，而不是 PEM 文件的文本字节，因此
仅改变 PEM 换行不会改变 pin。dry-run 会重新计算 digest 并与 profile 固定值比较。

在执行任何 sudo 前先生成只读主机计划：

```bash
uv run robotctl target host plan \
  --target wheeltec \
  --bootstrap-public-key /home/controller/.ssh/rolo-wheeltec-bootstrap.pub \
  --runtime-public-key /home/controller/.ssh/rolo-wheeltec-runtime.pub
```

`TargetHostProvisioningPlan/v1` 会绑定 registration digest、两把不同的 Ed25519 公钥、完整
`authorized_keys`、v2 host template、每个文件的目标路径/owner/group/mode/digest，以及明确的
`groupadd`、`useradd`、`systemctl daemon-reload`、`systemctl enable` 影响；所有步骤都列入唯一的
`USE_SUDO` 审批范围。计划不会创建账号、写 `/etc` 或连接目标。systemd 只 enable、不 `--now`，必须等签名
runtime 激活并通过 health check 后再启动。

确认只读计划后，使用持久 Job 提交同一主机事务。提交、审批和执行是三个独立动作；提交者不能代替
`--approver` 作出批准：

```bash
uv run robotctl target host submit \
  --target wheeltec \
  --bootstrap-public-key /home/controller/.ssh/rolo-wheeltec-bootstrap.pub \
  --runtime-public-key /home/controller/.ssh/rolo-wheeltec-runtime.pub \
  --requested-by operator@example.com \
  --approver reviewer@example.com \
  --idempotency-key host-provision-wheeltec-0001

uv run robotctl target approval decide \
  --approval-id approval-0123456789abcdef0123456789abcdef \
  --principal reviewer@example.com \
  --idempotency-key host-provision-wheeltec-approval-0001 \
  --reason "已核对账号、路径、owner/group/mode、digest、systemd 与 forced-command key" \
  --approve

uv run robotctl target job run \
  --job-id deployment-0123456789abcdef0123456789abcdef
```

API 等价入口为 `POST /v1/targets/{target_id}/host-provisioning-jobs`，只返回 secret-closed Job、Approval
和 `plan_sha256`，不会返回 credential reference、known_hosts 路径、完整 authorized_keys 或安装脚本。
重复提交同一 idempotency key 返回同一冻结计划；远端 sudo 开始后连接中断时 Job 进入
`REQUIRES_RECONCILIATION`，不得自动重试或报告成功。更新既有主机计划必须提供
`--expected-current-plan-sha256` 做 compare-and-swap。

出现 `REQUIRES_RECONCILIATION` 后，先提交独立的 R2 特权只读观测 Job；不要再次执行原 host submit：

```bash
uv run robotctl target host reconcile \
  --job-id deployment-0123456789abcdef0123456789abcdef \
  --requested-by operator@example.com \
  --approver reviewer@example.com \
  --idempotency-key host-reconcile-wheeltec-0001

uv run robotctl target approval decide \
  --approval-id approval-fedcba9876543210fedcba9876543210 \
  --principal reviewer@example.com \
  --idempotency-key host-reconcile-wheeltec-approval-0001 \
  --reason "批准只读核对 commit marker、账号、密钥文件与 systemd 状态" \
  --approve

uv run robotctl target job run \
  --job-id deployment-fedcba9876543210fedcba9876543210
```

API 等价入口为 `POST /v1/jobs/{original_job_id}/host-reconciliation-jobs`。observer 仍通过 sudo 读取 root-owned
状态，因此需要 R2 `USE_SUDO` 审批，但它只运行产品固定脚本，不写账号、文件或 systemd。结果为 `EXACT`
时原作业完成；`NOT_COMMITTED` 时原作业变为 resumable，之后才允许显式 resume/run 新 attempt；
`DIFFERENT_CURRENT` 或 `DRIFTED` 保持 fail-closed，必须人工修复或选择后续 rollback。连接或协议失败不会改变
原作业，也不会触发 sudo apply 重放。

若需要恢复到一个已经审查并成功应用过的旧主机配置，引用“当前配置 Job”和“回滚目标 Job”提交 R3 CAS
事务；该命令不会删除 runtime 账号、runtime 数据或已安装制品：

```bash
uv run robotctl target host rollback \
  --current-job-id deployment-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --rollback-to-job-id deployment-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
  --requested-by operator@example.com \
  --approver reviewer@example.com \
  --idempotency-key host-rollback-wheeltec-0001
```

审批动作是独立的 `ROLLBACK_HOST_CONFIGURATION`，风险等级 R3。Controller 从旧 Job 只恢复两把已审查的
forced-command 公钥，并用当前 registration 重新生成 canonical dispatcher、launcher、authorized_keys 和
systemd unit；`expected_current_plan_sha256` 必须等于当前 Job 的 plan digest。执行继续复用固定 root installer，
因此目标 commit marker 不匹配时失败关闭。API 等价入口为
`POST /v1/jobs/{current_host_job_id}/host-rollback-jobs`。

签名 runtime Bootstrap Job 完成后，systemd unit 仍只有 enable、没有启动。首次启动必须同时引用已完成的 host
configuration Job 和 Bootstrap Job，先在目标侧复核 host commit marker 与 active runtime manifest，再执行固定
`systemctl start`：

```bash
uv run robotctl target host service-start \
  --host-job-id deployment-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --bootstrap-job-id deployment-cccccccccccccccccccccccccccccccc \
  --requested-by operator@example.com \
  --approver reviewer@example.com \
  --idempotency-key host-service-start-wheeltec-0001
```

该 Job 使用 R2 `START_TARGET_SERVICE` 审批和 provisioning SSH 身份；请求只包含 target、unit、host plan digest
和 runtime manifest digest，目标固定 root 脚本拒绝任一摘要不符。API 入口为 `POST /v1/host-service-jobs`。
若 `systemctl start` 后连接中断，原 Job 进入 `REQUIRES_RECONCILIATION`，不得直接重跑。此时提交
`robotctl target host service-reconcile --job-id ...`（API：
`POST /v1/jobs/{job_id}/host-service-reconciliation-jobs`）；R2 STATUS-only observer 不启动、停止或重启服务。
ACTIVE 才闭合原 Job，INACTIVE 才解锁新 attempt，host/runtime digest 漂移继续 fail-closed。

v2 host template 还包含两个固定且 digest-bound 的静态组件：bootstrap dispatcher 只接受
`runtime-capabilities`、`package-transfer`、`bootstrap` 三条精确 `SSH_ORIGINAL_COMMAND`；runtime launcher
每次执行前复核 active index、manifest digest、package identity、受控入口路径、size/mode 和入口 SHA-256。
未知命令失败关闭且不回显原文。

准备经过发布方 Ed25519 签名的离线目标端制品和独立固定的发布公钥，然后执行：

```bash
uv run robotctl target bootstrap dry-run \
  --target wheeltec \
  --package-root /srv/rolo/packages/rolo-target-0.2.0-linux-aarch64 \
  --public-key /etc/rolo/trust/release-key-2026.pub.pem \
  --signing-key-id release-key-2026 \
  --install-requires-sudo
```

命令按顺序验证严格文件集、manifest digest、Ed25519 签名和 pinned key，随后连接目标采集事实。
输出的 `BootstrapPlan` 包含结构化 blocker、每一步风险等级及
`INSTALL_TARGET_RUNTIME`/`USE_SUDO` 审批摘要。即使 preflight 为 `READY`，dry-run 也不会上传
制品、调用 sudo、创建账号、安装服务、激活版本或运行机器人 Operation。`target host plan` 同样只生成
摘要绑定的特权影响范围，不会应用它。W3 分支已经具备签名包传输、目标端二次验签、事务安装、健康检查、
回滚，以及完成主机级账号/systemd/authorized_keys 安装的 R3 apply Job 软件核心；但尚未完成真实 Linux
root/systemd/sshd 与 x86_64/AArch64 矩阵。不要把注入式执行器测试成功当作远程部署或真机安全验收完成。

#### W4 Ed25519 Collector 自动 Enrollment（开发分支）

W4 分支新增统一入口；目标必须已经注册为 Target，安装了 W3 runtime，并持有与本次 Command 绑定的
审批引用。普通用户使用 `--auto-configuration`：Controller 只把注册 Target 的 workspace root 和有限的
相对候选路径放入请求，ROS setup 的选择、文件存在性、symlink/边界检查和 SHA-256 固定均在目标侧完成。
因此不需要先登录目标机执行 `robotctl target-evidence collector-init`，也不需要把目标绝对路径误当成
Controller 本地路径：

```bash
uv run robotctl target enroll \
  --target wheeltec \
  --robot-id wheeltec \
  --auto-configuration \
  --approval-id approval-0123456789abcdef0123456789abcdef
```

非 ROS Application/CLI 若需要允许 Collector 读取某个 CLI 的 `--help`，只能追加已经审核且位于注册
workspace 内的相对普通文件；不接受绝对路径、`..`、symlink 或 glob：

```bash
uv run robotctl target enroll \
  --target lerobot-host \
  --robot-id lerobot-host \
  --auto-configuration \
  --help-executable-relative-path .venv/bin/lerobot-info \
  --no-ros-auto-source \
  --approval-id approval-0123456789abcdef0123456789abcdef
```

命令通过 Command Bus 生成 canonical Command。Local Target 在目标本地状态目录生成 Ed25519 私钥；
SSH Target 使用 bootstrap credential 调用同一目标侧状态机。输出只包含 descriptor、配置、公钥、
challenge attestation 和 controller pin，不包含私钥或私钥路径。重复相同配置会返回
`ALREADY_ENROLLED`，不会生成第二个 active identity。

需要轮换时必须提供当前 controller pin 中的 collector ID；新 identity 只有在旧 key 签署 transition
且 compare-and-swap 成功后才替换 pin：

```bash
uv run robotctl target enroll \
  --target wheeltec \
  --robot-id wheeltec \
  --auto-configuration \
  --approval-id approval-fedcba9876543210fedcba9876543210 \
  --expected-collector-id collector-0123456789abcdef0123456789abcdef
```

`--configuration-json` 保留为专家、迁移和恢复入口，携带完整的 target executable/ROS setup
path+digest pins；它不能和 `--auto-configuration` 同时使用。没有 `--auto-configuration` 时的空 JSON
仍保持兼容，但不会自动固定 ROS overlay 或 help executable，不建议用于新的自主部署。开发者可提供
`--request-id`、`--challenge-nonce`、`--issued-at` 和 `--expires-at` 复现同一 canonical Command；普通用户
应让 Rolo 生成这些值。

当前开发分支的 Local Adapt Journey 在发现同 target/robot 的 v4 controller pin 后，会优先采集并
验证 Ed25519 Bundle；没有 v4 pin 的既有安装继续使用 legacy HMAC deployment，不会自动迁移。
这仍不是稳定版流程。运行期 SSH 密钥现在只允许 proof-bound 的固定 `evidence-v4` 命令：R2
`COLLECT_RUNTIME_EVIDENCE` Approval 与 authorization proof 会绑定 principal、target、requested layers、
destination、完整无 proof 请求摘要和 expiry，目标再使用本地 authorization-key pin 复核。SSH 身份或随意
构造的 `approval_id` 都不能授权采集。

#### W5 签名发布、目标 `describe` 与原子激活（开发预览）

W5 软件核心已经定义目标工作区 manifest、位置化 Runtime Context、签名 release transfer、目标侧只读
staging、Collector 签名的 `TargetDescribeAttestation`、Controller Gate 收据以及原子 activation/rollback，
但尚未提供稳定的公开部署 CLI。控制器收到 `/home/robot/...`、目标 venv、`PATH` 或 `PYTHONPATH` 时只
校验结构和摘要，不会在控制器本机检查这些路径；文件存在性、规范路径、symlink 和 digest 必须由目标侧
companion 判断。

当前契约只允许 `describe` 返回排序后的 operation-to-entrypoint mapping 和既有 RPC protocol 字段，
不允许携带任意环境、日志或 secret，也没有 `invoke` 入口。目标侧服务已经能在执行前校验 frozen
release 的严格文件集、逐文件摘要、Release/Bundle mapping、entrypoint 与实际 sandbox launcher+预算
摘要。上传先进入非激活 staged 目录；只有 Controller 验证 attestation 并签发短时效 PASSED Gate 收据后，
目标才会在锁内原子切换 `current.json`。重复激活幂等，回滚使用 expected-current CAS，失败不会替换 current。

开发分支还提供目标侧证据协议。`project-evidence` 只检查 Controller 显式声明、排序且有数量上限的相对候选
文件，不接受 glob 或递归扫描；目标端生成 digest-bound manifest，未声明文件不会被收集。该协议现在可由
runtime forced credential 的固定命令进入，但必须携带独立 R2 Approval 签发的短时 `READ_PROJECT_EVIDENCE`
authorization proof，并由目标本地 pin 验证。`adapter-release-status` 也可使用 runtime forced credential：它重新验签
current、previous 和期望 staged release，只返回身份与摘要。Controller reconciliation 只生成
deploy/activate/rollback/manual-review 计划和下一步 CAS digest，不会自动执行写操作；状态无法验真时保持
blocked/unknown。

`source-discovery` 使用另一份 `ANALYZE_PROJECT_SOURCE` R2 Approval 和固定 forced command，对已批准相对 scan roots
执行有预算的递归解析，只回传严格结构化事实和摘要；源码/文档正文、原始诊断与绝对路径不进入 Controller。

这仍是 API/companion 级开发预览：Windows 端到端测试使用注入 runner，SSH 测试使用 fake transport；
Linux production sandbox 和真实 sshd/断网/重连尚未验收。runtime forced credential 目前只允许只读
release status，以及 proof-bound 的固定 project evidence/source discovery；仍明确拒绝 stage、describe 和 activate。后者的
bootstrap 固定命令必须携带 W6 scoped authorization proof。authorization pin 的正式 Bootstrap 安装以及真实主机验收完成前，
不要把 W5/W6 Schema 或软件测试当作生产远程部署成功。

#### W6 Job、Event 与 Approval（开发预览）

开发分支已提供原子 Job snapshot、hash-chain 事件日志、step checkpoint、per-target lease、取消/重试/恢复、
独立 Approval request/decision 以及 SSE formatter 的内部 API。服务重启时，若事件已经 fsync 而 Job snapshot
尚未替换，会从已验证 journal recovery snapshot 重放；远端副作用未知则进入
`BLOCKED/REQUIRES_RECONCILIATION`，不会显示成功或自动重试。

Approval 现在绑定 requester、独立 approver、job、target、command digest、action、精确 request scope 和
expiry，并禁止 Agent 自批。Controller 可从已批准记录签发最长 10 分钟的 Ed25519 authorization proof；
proof 绑定完整请求摘要，目标只读取本地 authorization-key pin，不信任请求随附的授权公钥。stage、
activate/rollback、describe、project-evidence 和 source-discovery 的 target companion 已拒绝裸 `approval_id`、错 action/target、
过期或篡改 proof。

目标侧 Bootstrap transaction 已支持 authorization pin 首次安装和 CAS 轮换：pin 必须绑定本次 target 与
approval，只有 bootstrap credential 的固定 `INSTALL_ACTIVATE` 接受；package 验签/preflight 成功、runtime
激活后才提交 pin。若进程在激活后、pin 提交前中断，同一请求可按 active manifest 恢复；旧 current-key 摘要的
轮换会失败关闭。Controller 内部 Job runner 现已把摘要绑定 spec、独立 Approval、断点上传、目标
`INSTALL_ACTIVATE`、pin 提交、checkpoint 和 final artifact 串联；Controller 在 step 完成后中断不会重复远端
执行，transport 状态未知则要求 reconcile。W7 已补上受约束的 Controller package registry 和公开 CLI/API
submission；API 只接受不可变 `package_ref`，不能指向任意 Controller 路径。本地 CLI 才能从显式源目录执行
`package import`，导入时会按 TargetProfile release pin 验签、拒绝 symlink/额外文件/摘要漂移，并在复制后复验。
真实 sshd cancel confirmation、SSH Adapt 的目标侧运行时探测、自动 Agent/release 审批链和生产主机安装仍未完成，
因此不能把软件预览当成生产部署验收。Local discovery 与 metadata/structured-source SSH Adapt Job 已可运行，具体限制见下文。

#### W7 持久 Job API/CLI（开发预览）

先注册 secret-free Target metadata。SSH 形式必须引用外部 credential，并明确 known_hosts 与 host-key pin；
`target add` 本身不连接目标：

```bash
robotctl target add wheeltec \
  --local \
  --workspace /home/robot/wheeltec_ws \
  --desired-version 0.2.0 \
  --release-signing-key-id release-key-2026 \
  --release-signing-public-key /etc/rolo/trust/release-key-2026.pub.pem \
  --idempotency-key target-wheeltec-20260825

robotctl target add remote-arm \
  --ssh robot@192.168.1.20 \
  --credential-ref file-credential:///absolute/path/to/ssh/remote-arm \
  --known-hosts /absolute/path/to/known_hosts \
  --host-key-sha256 'SHA256:<pinned-fingerprint>' \
  --workspace /home/robot/robot_ws \
  --desired-version 0.2.0 \
  --release-signing-key-id release-key-2026 \
  --release-signing-public-key /etc/rolo/trust/release-key-2026.pub.pem \
  --idempotency-key target-remote-arm-20260825
```

连接评估先创建 profile-bound Job，再由同一 CLI runner 推进。`--active-probe none` 只验证注册契约；`help` 和
`runtime-readonly` 会通过统一 Local/SSH executor 执行固定、只读、有界 inspection：

```bash
robotctl target connect assess \
  --target remote-arm \
  --active-probe runtime-readonly \
  --idempotency-key assess-remote-arm-20260825

robotctl target job run --job-id deployment-0123456789abcdef0123456789abcdef
```

首次 Bootstrap 前，在 Controller 配置要安装到目标侧的独立 Ed25519 authorization 公钥。key id 与公钥路径必须
一起配置；需要运行 target runtime rollback 等受控写操作时，还必须配置匹配的私钥路径。Bootstrap 只把公钥 pin
安装到目标机，私钥必须留在 Controller 并由运行 `robotctl` 的专用账号最小权限读取：

```bash
export ROLO_DEPLOYMENT_AUTHORIZATION_KEY_ID=controller-authorization-2026
export ROLO_DEPLOYMENT_AUTHORIZATION_PUBLIC_KEY_PATH=/etc/rolo/trust/controller-authorization-2026.pub.pem
export ROLO_DEPLOYMENT_AUTHORIZATION_PRIVATE_KEY_PATH=/etc/rolo/private/controller-authorization-2026.pem
```

缺少私钥时仍可构造并安装公钥 pin，但 rollback runner 会在派发目标写操作前失败关闭。公私钥不匹配同样会被拒绝；
不得把私钥放进 Target package、SSH 传输、浏览器响应、Codex prompt 或普通日志。

然后由本地 CLI 把发布包导入不可变仓库。输出中的 `record.package_ref` 是后续 CLI/API 唯一接受的包引用：

```bash
robotctl target package import \
  --target wheeltec \
  --source /srv/rolo/packages/rolo-target-0.2.0-linux-aarch64
```

正式发布包必须包含固定的 `target-package.cdx.json`。该 CycloneDX 1.6 SBOM 由
`TargetPackageBuilder` 确定性生成，记录 application 的 package/version/architecture/Python 约束和每个运行时
文件的 SHA-256、角色、mode 与大小；SBOM 文件本身以 `SBOM` role 和 digest 进入 Ed25519 签名 manifest。
`target package import`/Bootstrap 验证不接受缺失 SBOM，也不会只检查其 JSON 语法：installer 会把组件逐项与
签名 manifest 交叉比对。不要手工修改 SBOM；runtime 树变化后必须重新 build、签名并产生新的 manifest digest。

提交 Bootstrap 会冻结 Target registration、workspace、package/manifest/release key、runtime CAS、authorization
pin、独立 approver 和 expiry，并同时创建 R3 Approval。默认要求目标 runtime 不存在；升级时改用
`--expected-current-state present` 并提供当前 manifest digest：

```bash
robotctl target bootstrap submit \
  --target wheeltec \
  --package-ref 'rolo-target@<64字符manifest SHA-256>' \
  --requested-by operator@example.com \
  --approver reviewer@example.com \
  --expected-current-state absent \
  --idempotency-key bootstrap-wheeltec-20260825

robotctl target approval decide \
  --approval-id approval-0123456789abcdef0123456789abcdef \
  --principal reviewer@example.com \
  --idempotency-key approve-bootstrap-wheeltec-20260825 \
  --reason '已核对目标、发布签名、manifest 与授权公钥摘要' \
  --approve

robotctl target job run --job-id deployment-0123456789abcdef0123456789abcdef

robotctl target adapt submit \
  --target wheeltec \
  --active-probe runtime-readonly \
  --no-run-adapter-agent \
  --timeout-s 1800 \
  --idempotency-key adapt-wheeltec-20260825

robotctl target project-evidence submit \
  --target wheeltec \
  --requested-by operator@example.com \
  --approver reviewer@example.com \
  --idempotency-key project-evidence-wheeltec-20260825

robotctl target source-discovery submit \
  --target wheeltec \
  --scan-root . \
  --requested-by operator@example.com \
  --approver reviewer@example.com \
  --idempotency-key source-discovery-wheeltec-20260826

robotctl target job get --job-id deployment-0123456789abcdef0123456789abcdef
robotctl target job events --job-id deployment-0123456789abcdef0123456789abcdef
robotctl target job cancel --job-id deployment-0123456789abcdef0123456789abcdef

robotctl target tui --page fleet
robotctl target tui --page target --target wheeltec
robotctl target tui --page job --job-id deployment-0123456789abcdef0123456789abcdef
robotctl target tui --page approval --approval-id approval-0123456789abcdef0123456789abcdef
robotctl target tui --page blocker --watch --refresh-s 2
```

提交返回 `CREATED` 只表示 Job/spec/Approval 已持久化；审批返回 `APPROVED` 也不表示安装完成。只有 `job run`
返回 Job `COMPLETE` 且 Bootstrap artifact 为 `SUCCEEDED`，才能说明软件事务完成。SSH transport 在 mutation 后
状态未知时 Job 会进入 `BLOCKED/REQUIRES_RECONCILIATION`，不会自动重跑远端写操作。目标注册、包内容或 release
pin 在提交后漂移都会失败关闭。同一 Idempotency-Key 的重试复用首次冻结的时间和 spec；不同 body 会冲突。

当前 `target adapt submit` 是可运行的 **Local/discovery-only** W7 slice：workspace 总是来自已注册 Target，调用方
不能在提交时替换路径；CLI/API 冻结 registration digest、`AdaptStartParameters`、probe 和超时，再由
`target job run` 推进现有 Adapt Journey。只有 Journey 返回 `DISCOVERY_COMPLETE` 时 Job 才进入 `COMPLETE`；
结构化阻塞进入 `BLOCKED`，控制器崩溃后已有 Journey artifact 会恢复而不会重复执行。执行已经开始但尚无持久
结果时，重启后必须 reconcile，不能自动重跑。

SSH Target 不允许 Controller 把 `/home/...` 之类目标路径当成本机路径扫描。target-side project-evidence Job
可通过 CLI、HTTP 或 Session Agent 创建，并由 TUI/Workbench 显示与复现：它冻结 Target registration、
workspace 与显式候选列表，创建独立 R2 Approval；批准后 Runner 签发最长 5 分钟的 proof，通过 runtime SSH
fixed command 采集有界 metadata/digest artifact。默认只检查根目录下六个常见元数据文件；`--candidates-json`
可显式替换，但不接受绝对路径、父级路径、glob、重复项或未排序列表。该能力不返回文件内容，也不会采纳目标
输出建议的新路径。

需要分析项目结构时，再单独创建 `source-discovery` Job。它有自己的 `ANALYZE_PROJECT_SOURCE` R2 Approval，默认
扫描已注册 workspace 的 `.`；`--scan-root` 只能重复指定 workspace 相对目录，不接受绝对路径、`..`、symlink
逃逸或未批准根。目标侧使用固定 `robotctl target-executor source-discovery` 命令验证短时 Ed25519 proof 后，按
固定文件数、单文件字节数、总字节数和超时预算递归解析。返回值只包含严格结构化的依赖声明、入口点、ROS
interface/name、语义候选、相对路径、计数和摘要；不返回源代码、README/launch 正文、原始诊断或目标建议的命令。

项目、源码和运行时证据是三份独立请求，必须分别批准、分别运行。运行时请求固定为
`hw/linux/ros` 三层，只读窗口最长 5 分钟；目标侧 collector 使用已登记 Ed25519 key 签名，目标 runtime
forced command 在采集前还会用本地 authorization pin 验证 Controller 的短时 proof。下面的 ID 只是示例，
应替换为每一步真实返回值：

```bash
robotctl target source-discovery submit \
  --target wheeltec \
  --scan-root . \
  --requested-by operator@example.com \
  --approver reviewer@example.com \
  --idempotency-key source-discovery-wheeltec-20260826

robotctl target runtime-evidence submit \
  --target wheeltec \
  --requested-by operator@example.com \
  --approver reviewer@example.com \
  --approval-ttl-s 300 \
  --timeout-s 45 \
  --idempotency-key runtime-evidence-wheeltec-20260826

robotctl target approval decide \
  --approval-id approval-0123456789abcdef0123456789abcdef \
  --principal reviewer@example.com \
  --idempotency-key approve-project-evidence-wheeltec-20260825 \
  --reason '已核对目标、workspace 和候选文件范围' \
  --approve

robotctl target job run --job-id deployment-0123456789abcdef0123456789abcdef

robotctl target approval decide \
  --approval-id approval-fedcba9876543210fedcba9876543210 \
  --principal reviewer@example.com \
  --idempotency-key approve-source-discovery-wheeltec-20260826 \
  --reason '已核对目标、workspace、scan root 与源码分析预算' \
  --approve

robotctl target job run --job-id deployment-fedcba9876543210fedcba9876543210

# 对 runtime-evidence 返回的第三份 Approval 做独立审批，再立即运行该 Job。
robotctl target job run --job-id deployment-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa

robotctl target adapt submit \
  --target wheeltec \
  --active-probe runtime-readonly \
  --no-run-adapter-agent \
  --project-evidence-job-id deployment-0123456789abcdef0123456789abcdef \
  --source-discovery-job-id deployment-fedcba9876543210fedcba9876543210 \
  --runtime-evidence-job-id deployment-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --runtime-evidence-max-age-s 300 \
  --idempotency-key ssh-adapt-wheeltec-source-20260826
```

HTTP 等价入口为 `POST /v1/targets/{target_id}/project-evidence-jobs`、
`POST /v1/targets/{target_id}/source-discovery-jobs` 与
`POST /v1/targets/{target_id}/runtime-evidence-jobs`。前者 body 使用
`approver_principal`、可选 `candidates`、`approval_ttl_s` 和 `timeout_s`，仍必须携带绑定身份与
`target:write` 的认证 headers；后者增加 `scan_roots` 和固定 `limits`。Session Agent 的
`SUBMIT_PROJECT_EVIDENCE`/`SUBMIT_SOURCE_DISCOVERY`/`SUBMIT_RUNTIME_EVIDENCE` 只能完成请求和审批交接，不能自批。
TUI Job 页会显示可复现的规范化 submit 命令；运行时 Approval 还显示固定 layers、collector descriptor digest
和 expiry。

Adapt submission 会重新验证 project-evidence Job 已 `COMPLETE`、目标和 registration digest 一致、artifact/snapshot/
workspace/manifest digest 完整且未超过 `--project-evidence-max-age-s`。指定 source Job 时还会验证其已 `COMPLETE`、
目标/registration/workspace 与 project-evidence 相同、artifact/request/summary digest 完整且未超过
`--source-discovery-max-age-s`。当 `active_probe=runtime-readonly` 时，还必须绑定完成态 runtime-evidence Job；提交端和
Runner 都重新加载当前 collector pin、复验 bundle Ed25519 签名、request/target/registration/collector/payload digest
及最长 300 秒 freshness，然后把三组值冻结进 v4 Adapt spec。Runner 在 Journey 前再次读取不可变 artifact；
发生篡改、过期、注册漂移、workspace 漂移或 Job/target 混用时失败关闭。`AdaptStartParameters/v2`
把根路径位置显式标为 `TARGET`，不会对该路径调用 Controller `Path.resolve()/exists()`；Journey 收到的是
`TARGET_METADATA`、经过摘要验证的 `target_application_probe` 和空的本地 source/build/install roots。

当前 SSH 模式已经支持 **metadata-only**、可选的 **proof-bound structured source discovery**，以及绑定独立
runtime-evidence Job 的 **proof-bound runtime-readonly discovery**。没有 runtime Job 时必须使用
`--active-probe none`；有 runtime Job 时使用 `--active-probe runtime-readonly`，Journey 只消费重新验签后的
`hw/linux/ros` ProbeResult，不会再次临时 SSH 探测。绑定 source Job 后仍使用明确的 `TARGET_SOURCE` 低置信度层级，
且不会把远端相对路径当成 Controller 本地文档或读取项目正文。Adapt 继续拒绝
`--run-adapter-agent`，直到 Adapter 生成、Gate、
stage、activate/rollback 分别接入 release-scoped Approval；不能把 metadata/source `DISCOVERY_COMPLETE` 解释为 Adapter
release 已生成、发布或激活。

受控写 HTTP 接口即使只监听 loopback，也必须配置 `ROLO_API_TOKEN`，并同时发送以下 headers：

```bash
export ROLO_API_TOKEN_PRINCIPAL=operator@example.com
export ROLO_API_TOKEN_PERMISSIONS=target:write,approval:write
```

```text
Authorization: Bearer <ROLO_API_TOKEN>
Idempotency-Key: adapt-wheeltec-20260825
X-Rolo-Principal: operator@example.com
X-Rolo-Permissions: target:write
```

请求中的 principal/permissions 必须包含在该 token 的 Controller 侧绑定中，不能由客户端自行扩大。
审批决定改用 `approval:write`。请求 body 是严格模型，不接受 shell/argv 或额外字段。当前 API 已提供 Target
注册/查询、连接评估 Job 创建、`POST /v1/jobs/{id}/run`、bootstrap/adapt/project-evidence/source-discovery/runtime-evidence Job 创建、Job 查询、JSON/SSE 事件、
取消和审批决定。Bootstrap body 使用 `package_ref`、`approver_principal`、CAS 与 timeout 等严格字段；额外的
`package_root`、shell 或 argv 会返回 422。Bootstrap、connection assessment、Local discovery、SSH metadata/source
Adapt handler 及三个 proof-bound evidence runner 已接入；自动 Agent/release 审批链、多主体 token/OIDC、除 runtime rollback 提交外的交互式
TUI 控件、真实 sshd 主机安装和远端 cancel confirmation 尚未接入。

独立 `rolo-deployment-control` GUI 在登录页输入 token 与其绑定 principal 后，先调用：

```text
GET /v1/deployment-session
Authorization: Bearer <ROLO_API_TOKEN>
X-Rolo-Principal: operator@example.com
```

成功响应只包含 principal、`target:write`/`approval:write` 权限和 `client-memory-only` 声明，并带
`Cache-Control: no-store`；探测本身不创建 Job，也不需要 Idempotency-Key。token 不持久化，刷新页面或点击
Disconnect 后必须重新认证。当前一个 Controller 进程只配置一个 token/principal；绑定其他审批人的决定必须由
相应独立主体的认证配置完成，不能在浏览器中修改 `X-Rolo-Principal` 冒充审批人。

GUI 的 SSH Target 表单要求用户勾选“已通过独立可信信道核对 fingerprint”，但仍由后端严格模型和 SSH
known_hosts/pin 做最终验证。GUI 不上传 SSH private key，只提交 opaque credential ref。Bootstrap 创建响应只回传
Job、Approval、package ref 和 manifest digest；Controller package path、公钥正文和内部 authorization pin 不进入
浏览器。现有 `rolo-vis` 继续是独立只读插件，不共享该 token，也没有任何隐藏写入口。

独立 `rolo-deployment-control` 还提供“Target evidence chain”面板：项目元数据、源码分析和运行时证据按钮分别创建
R2 Approval，源码范围首版固定为 workspace root `.`，运行时范围固定为 `hw/linux/ros`。用户可只绑定前两份完成态
Job 提交 `active_probe=none`，或再绑定最长 300 秒的新鲜 runtime Job 提交 `runtime-readonly` Adapt。GUI 不提供任意
路径选择、文件正文预览、shell/argv，也不会把 Approval
与 Job run 合并成一次隐式动作。

`target tui` 默认是只读终端工作台：Fleet、Target、Job、Approval 和 Blocker/Recovery 页面直接读取同一份
TargetProfile、Job/Event/Approval 状态，并显示可复现的 canonical CLI。刷新或 `--watch` 不创建 Job、不重试
远端动作，因此断线后重新打开页面不会改变幂等状态。唯一的交互式写入口是显式
`--submit-runtime-rollback`：它使用有界字段提示和二次确认创建 rollback Job/R3 Approval，但不批准请求，也不执行
目标写操作，并且不能与 `--watch` 合用。TUI 不是自由终端，也不读取 SSH private key；审批继续使用显式
`target approval decide`。

W8 GUI 开发预览通过 `GET /v1/deployment-workbench?page=fleet|target|job|approval|blocker` 读取同一投影。
配套 `rolo-vis` 只有在 `/health` 声明 `deployment.workbench-read-model/v1` 时才显示 Deployment 页面；页面展示
Target、SSH fingerprint 摘要、持久 Job 状态、recovery 和 canonical CLI。浏览器响应采用字段 allowlist，拒绝
credential ref、known_hosts Controller 路径、package root、私钥或公钥正文。当前 `rolo-vis` 插件仍保持
read-only：Add Target 等写控件禁用，实际注册、审批、run/cancel 继续使用上面的 authenticated CLI/API。

#### W9 Codex Session Agent（brokered autonomous CLI 开发预览）

首版不要求 Codex 先输出整轮 intent/plan；Codex 每次根据自然语言与前一条安全回执自主选择一个有限动作。该体验
不是自由终端：Controller 外的 authenticated broker 冻结 principal、target allowlist、permission、action
budget、timeout、cancel、sequence 和 idempotency；Codex 不能提交 shell/argv、读取 SSH credential、修改
Controller store 或调用 Approval decision。

Session Agent 默认关闭，必须配置独立的模型 provider credential。不要复用浏览器 Controller token、SSH key
或目标 runtime credential：

```bash
export ROLO_SESSION_AGENT_ENABLED=true
export ROLO_SESSION_AGENT_API_KEY='<dedicated-provider-key>'
export ROLO_SESSION_AGENT_MODEL='<approved-codex-model>'
export ROLO_SESSION_AGENT_BASE_URL='https://api.openai.com/v1'
export ROLO_SESSION_AGENT_EXECUTABLE='codex'
export ROLO_SESSION_AGENT_PROVIDER_TIMEOUT_S=120
```

本地 Controller CLI 从 `ROLO_API_TOKEN_PRINCIPAL` 读取绑定主体，并只把 Controller 配置中已有的
`target:write` 下放给 broker；没有 `--principal`、`--shell` 或 `--approve` 参数：

```bash
robotctl target agent run '检查 wheeltec 的连接并创建必要的只读评估 Job' \
  --target wheeltec \
  --max-tool-calls 4 \
  --timeout-s 120 \
  --idempotency-key agent-wheeltec-assess-20260826
```

同一个 Idempotency-Key 与同一请求重试会返回已持久化的整轮结果，不会重新调用 Codex 或重复创建 Job；相同 key
对应不同 message、allowlist 或 budget 会冲突。浏览器 GUI 使用 `POST /v1/session-agent/turns`，请求中必须明确
`allowed_target_ids`，Controller bearer 只在浏览器到 API 的认证 header 中，绝不进入 Codex prompt 或子进程
shell environment。`approval:write` 会被 Session Agent API 明确拒绝；需要批准时，Agent 只返回
`APPROVAL_REQUIRED`，由独立审批主体通过原 Approval drawer/CLI 完成。

Codex 可选择 `SUBMIT_PROJECT_EVIDENCE` 和 `SUBMIT_SOURCE_DISCOVERY`，但两者都只返回 Approval handoff；后续审批仍由
独立主体完成。`PROVISION_HOST` 暂不在 Agent catalog 中，因为它要求显式提供两把不同的 forced-command 公钥；
Codex 既不能读取 Controller key 文件，也不能生成目标身份。请使用本节 4.0 的认证 CLI/API/GUI 创建主机
置备 Job；后续若开放自然语言入口，只允许选择 Controller 预注册的 opaque key-set ref。

Codex provider 使用空白临时 workspace、read-only sandbox、ephemeral、ignore-user-config/ignore-rules 和空 shell
environment。回传模型的 history 会去除 canonical CLI，并且只包含 secret-closed projection；target banner、
README、日志和 stdout/stderr 不进入上下文。Session command 与整轮 turn 已使用跨 Controller 进程 guard；取消
会独立持久化并传播到活跃 Job，不被最终回执覆盖。当前开发预览仍缺少共享文件系统/Controller 崩溃故障注入、
专用 OS user/container 级隔离和真实 SSH prompt-injection eval，因此生产部署前继续保持 feature flag 关闭。

#### W10 Target runtime rollback（开发预览）

目标 runtime 激活后若在观察期发现回归，应停止扩批并提交独立的 R3 rollback Job；不要用 raw SSH、直接编辑
`current.json` 或调用内部 Python 类。提交时必须从已保存的 install/upgrade evidence 获取当前与 previous 的精确
manifest digest：

```bash
robotctl target runtime rollback \
  --target wheeltec \
  --package-id rolo-target \
  --expected-current-manifest-sha256 <当前digest> \
  --expected-previous-manifest-sha256 <前一版本digest> \
  --requested-by operator@example.com \
  --approver reviewer@example.com \
  --idempotency-key rollback-wheeltec-20260826

# 等价的有界交互式提交；仍然只创建 Job 与 R3 Approval
robotctl target tui \
  --submit-runtime-rollback \
  --target wheeltec \
  --requested-by operator@example.com \
  --idempotency-key rollback-wheeltec-20260826
```

该命令只冻结 JobSpec 并创建 `ROLLBACK_TARGET_RUNTIME` R3 Approval，不会立即修改目标。独立审批后仍需显式执行
`robotctl target job run --job-id <job-id>`。API 对应
`POST /v1/targets/{target_id}/runtime-rollback-jobs`；Session Agent 可选择
`SUBMIT_RUNTIME_ROLLBACK`，但只能返回 `APPROVAL_REQUIRED`，不能批准自己的请求。重复同一请求与
Idempotency-Key 返回原 Job；相同 key 携带不同 digest 会冲突。

Runner 在执行前重新核对 Target registration、release signing public-key pin 和已批准请求的精确 payload digest，
再用 Controller 私钥签发最长 5 分钟的 `ROLLBACK_TARGET_RUNTIME` authorization proof。SSH rollback 通过 bootstrap
credential 的固定 `target-executor bootstrap` 命令派发；已安装 runtime 在读取 previous package 或改动 current 前，
必须用目标本地 authorization-key pin 验证 proof 的签名、target、action、Approval、expiry 与完整请求摘要。
runtime forced credential 仍保持只读。previous package 随后重新验签并执行 health check；current/previous 双 CAS
不匹配不会切换 current。派发后 SSH 断线或异常导致结果不明时，Job 进入
`BLOCKED/REQUIRES_RECONCILIATION`，不得盲重试。

当前 CLI/API/Broker、独立 authenticated GUI 和有界交互式 TUI 提交控件均已接入；target-side authorization proof
的签发、目标 pin 校验、缺失/过期/错配拒绝已有软件测试。真实 x86_64/AArch64 upgrade/rollback、断线、重启与
外部安全评审证据尚未完成，因此仍不是生产验收结论。

启用前先运行以下只读检查：

```bash
robotctl target agent readiness
```

输出是 secret-closed 的 `SessionAgentProductionReadinessReport/v1`。本机配置即使全部通过，真实 provider、专用
OS 隔离、SSH prompt injection、多 worker 故障注入和 Linux x86_64/ARM64 仍会保持 `NOT_VERIFIED`，因此当前
`production_ready` 必须为 `false`。不要用静态 readiness 结果替代 W10 真机矩阵。

维护者可在已安装受审核 `robotctl`、固定 host key 且使用受限账号的 Linux sshd 上运行 opt-in 验收：

```bash
export ROLO_RUN_REAL_SSH_ACCEPTANCE=1
export ROLO_REAL_SSH_HOST='<target-host>'
export ROLO_REAL_SSH_PORT=22
export ROLO_REAL_SSH_PROVISIONING_USER='<existing-admin-user>'
export ROLO_REAL_SSH_PROVISIONING_IDENTITY_FILE='<absolute-admin-private-key-path>'
export ROLO_REAL_SSH_BOOTSTRAP_USER='<bootstrap-forced-command-user>'
export ROLO_REAL_SSH_BOOTSTRAP_IDENTITY_FILE='<absolute-bootstrap-private-key-path>'
export ROLO_REAL_SSH_RUNTIME_USER='<runtime-forced-command-user>'
export ROLO_REAL_SSH_RUNTIME_IDENTITY_FILE='<absolute-runtime-private-key-path>'
export ROLO_REAL_SSH_KNOWN_HOSTS='<absolute-known-hosts-path>'
export ROLO_REAL_SSH_HOST_KEY_SHA256='SHA256:<independently-verified-fingerprint>'
export ROLO_REAL_SSH_TARGET_ID='wheeltec'
export ROLO_REAL_SSH_PACKAGE_ID='rolo-runtime'
export ROLO_REAL_SSH_PACKAGE_MANIFEST_SHA256='<64位小写摘要>'
pytest -q tests/test_real_ssh_target.py
```

测试分别验证 provisioning/runtime typed inspection 与 bootstrap 固定 capability protocol，且不会把私钥、
known_hosts 路径写入结果。默认 skip、fake transport 或仅在开发机通过均不等于真机验收；报告还必须绑定 OS image、CPU 架构、
Rolo/package digest 和 host-key fingerprint。真实密钥值不得进入 CI 日志或验收报告。

注册 profile 后，推荐同时通过产品入口生成一份自动化 receipt：

```bash
robotctl target acceptance real-ssh \
  --target wheeltec \
  --environment ubuntu-2404-x86-canary-01 \
  --architecture x86_64 \
  --os-image-sha256 '<64位小写摘要>' \
  --package-id rolo-runtime \
  --package-manifest-sha256 '<64位小写摘要>' \
  --acceptance-suite tests/test_real_ssh_target.py \
  --test-report ./evidence/real-ssh.junit.xml \
  --output ./evidence/w10-real-ssh.json
```

该命令只调用固定 inspection/status catalog，不接受 shell/argv。runtime 身份还会调用只读 bootstrap `STATUS`，
把目标实际 current package ID/manifest 与声明值核对；receipt 的 current/previous 投影不含 install path。
suite 与 JUnit 从实际文件计算摘要；JUnit 至少要执行四个
真实用例，全 skip、failure、error、DTD/entity、超限或摘要错配均失败。receipt 不包含 host、credential reference、
known_hosts 路径、测试用例名称、stdout/stderr 或密钥材料，只保存汇总、必要绑定摘要和公开 host-key pin。
即使三个身份探测、JUnit 与平台一致性均通过，
也只表示 `automated_result=PASSED`；输出固定保留 `matrix_status=NOT_VERIFIED`、
`manual_review_required=true`、`production_ready=false`，必须与完整 pytest/JUnit 报告和人工复核记录一起归档。

维护者也可从 `main` 手动触发 `.github/workflows/w10-real-ssh-acceptance.yml`。该工作流只调度带
`self-hosted`、`linux`、`rolo-w10` 和对应架构 label 的受保护 runner，并要求 `rolo-w10-acceptance` Environment
审批。所有 SSH/profile 配置和 `ROLO_W10_EVIDENCE_DIR` 都必须预置为 Environment secret；报告只保存在 runner
本地的按 run/attempt 隔离目录，不自动上传到 GitHub。集中归档前必须另行批准目的地和脱敏策略。

在这条 W7 新链中，不需要先在目标机手工执行 legacy `robotctl target-evidence collector-init`：Bootstrap 负责
runtime 与 authorization pin，后续 `robotctl target enroll` 负责 v4 Collector identity。4.1 的
`target-evidence collector-init` 仍只适用于 `v0.1.0-rc.2` legacy HMAC Collector 流程；两条流程不要混用。

### 4.1 准备目标机运行目录

目标机只需要 Git checkout、锁定环境和 Collector，不需要 Codex、Agent 工作区或 Tool Gateway
访问权限。以下示例将固定版本放在 `/opt/rolo`，并让非交互 SSH 会话可以通过
`/usr/local/bin/robotctl` 找到入口：

```bash
sudo useradd --create-home --shell /bin/bash rolo-evidence
sudo install -d -m 0755 -o rolo-evidence -g rolo-evidence /opt/rolo
sudo -u rolo-evidence git clone --branch v0.1.0-rc.2 --depth 1 \
  https://github.com/zarcherlot/rolo.git /opt/rolo
cd /opt/rolo
sudo -u rolo-evidence uv sync --frozen
sudo ln -s /opt/rolo/.venv/bin/robotctl /usr/local/bin/robotctl
/usr/local/bin/robotctl --help >/dev/null
```

已有 `rolo-evidence` 账号或 `/usr/local/bin/robotctl` 时不要重复创建或覆盖，应核对它们是否指向
固定的 `v0.1.0-rc.2` 环境。该账号不应具有 `sudo` 权限。它必须能够只读访问机器人工程、已批准
的 ROS setup 和需要枚举的设备；仅按实际需要授予 Unix group 或 ACL，不要直接授予管理员权限。

创建仅该账号可读的 Collector 目录并初始化：

```bash
sudo install -d -m 0700 -o rolo-evidence -g rolo-evidence /etc/rolo
sudo -u rolo-evidence /usr/local/bin/robotctl target-evidence collector-init \
  --robot-id wheeltec \
  --project-root /home/robot/wheeltec_ws \
  --config /etc/rolo/target-evidence-collector.json \
  --secret-file /etc/rolo/target-evidence-collector.key \
  --descriptor-out /home/rolo-evidence/wheeltec-collector.json
sudo chmod 0600 /etc/rolo/target-evidence-collector.json \
  /etc/rolo/target-evidence-collector.key
```

使用 ROS 且自动选择存在歧义时，按真实加载顺序重复传入：

```bash
--ros-setup /opt/ros/humble/setup.bash \
--ros-setup /home/robot/wheeltec_ws/install/local_setup.bash
```

ROS 或非 ROS 目标需要采集某个已审核程序的受限 `--help` 时，可增加：

```bash
--allow-executable /opt/robot/bin/wheeltec_driver
```

第三方程序可能为 `--help` 实现副作用，只能 allowlist 经人工审核的可执行文件，也可以完全
省略此类证据。

### 4.2 创建专用 SSH 密钥并限制账号

在控制器上为这一台目标机创建独立 Ed25519 密钥。推荐使用口令并在运行前加载到
`ssh-agent`；无人值守场景应把密钥放入受控的秘密存储，不能提交到源码仓库：

```bash
install -d -m 0700 ~/.ssh
ssh-keygen -t ed25519 -f ~/.ssh/rolo-wheeltec -C rolo-wheeltec-evidence
ssh-add ~/.ssh/rolo-wheeltec
```

通过物理控制台或已有的管理通道，把 `~/.ssh/rolo-wheeltec.pub` 的内容安装到目标机
`/home/rolo-evidence/.ssh/authorized_keys`。生产配置推荐使用以下单行格式；将
`AAAAC3...` 替换为控制器公钥的完整内容：

```text
restrict,command="/usr/local/bin/robotctl target-evidence collector-run --config /etc/rolo/target-evidence-collector.json" ssh-ed25519 AAAAC3... rolo-wheeltec-evidence
```

然后在目标机核对权限：

```bash
sudo chown -R rolo-evidence:rolo-evidence /home/rolo-evidence/.ssh
sudo chmod 0700 /home/rolo-evidence/.ssh
sudo chmod 0600 /home/rolo-evidence/.ssh/authorized_keys
```

`restrict` 会禁用 PTY、端口转发、Agent 转发和 X11 转发。旧版 OpenSSH 不支持 `restrict` 时，
使用 `no-agent-forwarding,no-port-forwarding,no-X11-forwarding,no-pty` 等价限制，并继续保留
固定 `command=`。不要用该专用密钥执行 `scp`、交互式 Shell 或 SSH tunnel。

### 4.3 独立固定 SSH 主机密钥

在目标机物理控制台或可信管理通道读取 Ed25519 主机公钥及其 SHA-256 指纹：

```bash
sudo cat /etc/ssh/ssh_host_ed25519_key.pub
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
```

在控制器上通过另一个可信通道核对指纹后，创建专用 `known_hosts`。不要直接信任首次连接提示，
也不要把未经独立核对的 `ssh-keyscan` 输出当作可信主机密钥：

```bash
install -d -m 0700 ~/.config/rolo/ssh
printf '%s\n' 'wheeltec-host ssh-ed25519 <目标机主机公钥的Base64部分>' \
  > ~/.config/rolo/ssh/wheeltec_known_hosts
chmod 0600 ~/.config/rolo/ssh/wheeltec_known_hosts
ssh-keygen -F wheeltec-host -f ~/.config/rolo/ssh/wheeltec_known_hosts
```

为了明确指定地址、账号和私钥，在控制器的 `~/.ssh/config` 增加：

```sshconfig
Host wheeltec-rolo
  HostName 192.0.2.10
  User rolo-evidence
  IdentityFile ~/.ssh/rolo-wheeltec
  IdentitiesOnly yes
  HostKeyAlias wheeltec-host
```

把 `192.0.2.10` 替换为目标机实际 IP 或 DNS 名称。自定义端口可增加 `Port`，需要跳板机时可
增加 `ProxyJump`。`--ssh-target` 只接受 `host` 或 `user@host`，不接受 `-p` 等 SSH 参数；复杂
连接应封装为上述仅含字母、数字、点、下划线或连字符的 Host 别名。

### 4.4 分通道置备 Collector 身份与验签秘密

部署时必须使用相互独立的通道传递：

- descriptor：普通配置通道；
- Collector secret：独立秘密通道；
- SSH host key：独立核验的 `known_hosts`。

将目标机上的 `/home/rolo-evidence/wheeltec-collector.json` 通过普通配置管理通道传到控制器，
将 `/etc/rolo/target-evidence-collector.key` 通过秘密管理系统、加密介质或其他独立秘密通道置备
到控制器。例如最终文件可放置为：

```text
~/.config/rolo/collectors/wheeltec-collector.json
~/.config/rolo/secrets/wheeltec-collector.key
```

控制器上的 secret 必须设为 `0600`，且不得使用受限的 `rolo-evidence` SSH 密钥从目标机
下载。descriptor、secret 和 SSH host key 三者来自同一未验证 SSH 会话时，不构成独立置备。

### 4.5 配置远程模式并执行 SSH 冒烟采集

控制器同样克隆 `v0.1.0-rc.2` 固定标签并执行 `uv sync --frozen`。先单独配置并采集一份新鲜
证据，以同时验证 SSH 认证、主机密钥固定、远端 `robotctl`、Collector 配置和 HMAC 验签：

```bash
cd /path/to/controller/rolo
chmod 0600 ~/.config/rolo/secrets/wheeltec-collector.key
uv run robotctl target-evidence configure \
  --robot-id wheeltec \
  --mode remote \
  --collector-descriptor ~/.config/rolo/collectors/wheeltec-collector.json \
  --verification-secret ~/.config/rolo/secrets/wheeltec-collector.key \
  --ssh-target wheeltec-rolo \
  --known-hosts ~/.config/rolo/ssh/wheeltec_known_hosts \
  --collector-config /etc/rolo/target-evidence-collector.json

uv run robotctl target-evidence collect \
  --robot-id wheeltec \
  --output ./wheeltec-target-evidence.json \
  --timeout 45
```

成功时第二条命令返回 `status: VERIFIED`，并报告与 descriptor 一致的 `collector_id` 和
`target_host_fingerprint`。任何密码提示、首次连接确认提示、主机密钥错误、签名错误或超时都
应视为失败；不要改用 `StrictHostKeyChecking=no` 绕过。

首次配置会固定 Collector 身份、secret 摘要、SSH target、`known_hosts` 路径和远端配置路径。
以后更换其中任一项都必须走显式 rotation/re-enrollment，不能直接覆盖部署文件。

### 4.6 在控制器启动远程 Adapt

冒烟采集通过后，完成 Codex 登录并复用已经固定的远程部署：

```bash
uv run robotctl adapt start \
  --robot-id wheeltec \
  --project-root /path/to/controller/source-copy \
  --evidence-mode remote \
  --discover-only \
  --timeout 1800
```

确认 Discovery、Wiki 和目标路由后，移除 `--discover-only` 运行完整 Agent/Gate/release 链。
如果跳过 4.5 的独立配置，也可以在首次 `adapt start` 中传入
`--collector-descriptor`、`--verification-secret`、`--ssh-target`、`--known-hosts` 和
`--collector-config` 全部参数；先冒烟采集更容易定位连接和验签问题。

远程模式固定使用 SSH `BatchMode=yes`、
`StrictHostKeyChecking=yes` 和显式 `known_hosts`；目标身份、Collector ID、签名或 SSH host key
不匹配时必须停止。

控制器上的 build/install 目录必须是未经修改的目标机制品副本，不能把控制器本机编译结果
当作目标证据。

## 5. 常见故障处理

### 5.1 ROS 候选存在歧义

执行 `uv run robotctl config init`，编辑 `~/.config/rolo/config.yaml` 中的
`ros.setup_files`，再运行 `uv run robotctl config validate`。不要通过修改 `.bashrc` 绕过。

### 5.2 手工 `ros2 node list` 正常，但 Probe 不可用

保留本次运行的 `ros.json`，检查 `command_diagnostics`。它会区分继承环境的尝试和干净
base setup 重试，并保留有界退出码与 stderr。Probe 不可用不能解释成“ROS 图为空”。

非 ROS 目标没有 ROS setup 或 ROS 图属于正常状态，不应执行本节排障，也不应为了通过检查而
安装 ROS；应转而核对 Application/CLI、协议、进程和设备接口证据。

### 5.3 Adapt 返回 `BLOCKED`

```bash
uv run robotctl adapt discover review --robot wheeltec
uv run robotctl adapt operations summary --robot wheeltec
uv run robotctl adapt operations list --robot wheeltec --applicability OBSERVED
uv run robotctl adapt run --robot wheeltec --dry-run
```

重点核查目标软件栈实际使用的路由：ROS 目标检查 Topic/Service/Action 与 setup，非 ROS 目标
检查 CLI/API、协议、进程和设备接口；两者都要核对工程根路径、证据时效、目标指纹和签名。

### 5.4 生产沙箱自检失败

```bash
bubblewrap --version
```

确认目标内核允许 user、mount 和 network namespace。真实目标机禁止设置
`ROLO_ADAPTER_UNSANDBOXED_DEV=1`；该选项仅用于单元测试和离线 Demo。

### 5.5 身份、签名或 SSH pin 变化

以下情况不能绕过：

- Collector 或目标指纹不匹配；
- payload hash 或 HMAC 签名不匹配；
- setup 文件路径或 digest 变化；
- SSH host key 校验失败；
- 签名证据已经过期。

停止采集，核验物理目标机，初始化新 Collector 或执行显式轮换与 re-enroll，再采集新 bundle。
旧 bundle 只能作为审计证据，不能重复用于新的 Discovery。

### 5.6 SSH 远程采集失败

先在控制器上重跑最小采集，不要直接反复运行完整 Adapt：

```bash
uv run robotctl target-evidence collect --robot-id wheeltec --timeout 45
```

按错误类型检查：

- `Permission denied (publickey)`：确认 `ssh-agent` 已加载正确私钥、SSH Host 别名选中了
  `rolo-evidence` 账号，并核对目标机 `.ssh` 与 `authorized_keys` 的属主和权限；
- `Host key verification failed`：核对 `HostKeyAlias` 与专用 `known_hosts` 第一列是否一致，并通过
  独立通道复核目标机指纹；不要自动删除旧 pin；
- `remote target evidence collector failed`：在目标机管理控制台确认
  `/usr/local/bin/robotctl`、Collector state、secret、工程和 ROS setup 对 `rolo-evidence` 可读，且
  固定 `command=` 中的配置路径与控制器 `--collector-config` 一致；
- `collector state belongs to a different target host`：Collector state 被复制到了另一台机器，
  必须在实际目标机重新初始化并显式 re-enroll；
- `signature mismatch`、`collector identity mismatch` 或证据过期：停止连接，核对 descriptor、
  secret、系统时间和目标身份，不要重建或替换部署文件来绕过；
- 超时：检查网络、跳板机和目标负载；可以在 `1` 到 `300` 秒之间调整 `--timeout`，但超时后
  不会回退采集控制器本机证据。

需要查看 SSH 握手细节时，可临时用相同 Host 别名和固定 `known_hosts` 执行 OpenSSH 的 `-vvv`
诊断，但受限账号仍会强制运行 Collector，空请求预期会被拒绝。不要为了调试移除
`BatchMode`、`StrictHostKeyChecking`、`UserKnownHostsFile` 或 `authorized_keys` 的强制命令。

## 6. 真机安全边界

Adapt 阶段禁止：

- 绕过 Collector、目标指纹、签名或 SSH host-key 校验；
- 用控制器本机 ROS 图替代目标机证据；
- 手工把未验证 Operation 标记为 `VERIFIED`；
- 允许 Agent 自主加载任意 shell 脚本；
- 在没有后续安全流程时执行写 Operation；
- 关闭真实目标机的生产沙箱；
- 将 Collector secret 或其他凭据写入源码仓库。

完成 Adapt 后，先回传验收包和 SHA-256 并通过评审，再进入 Diagnose/Verify、写 Operation 和
真实行为闭环。

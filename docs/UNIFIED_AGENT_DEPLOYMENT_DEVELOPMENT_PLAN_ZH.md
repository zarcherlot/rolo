# Rolo 统一 Agent 部署与远程适配开发计划

状态：`PROPOSED`

基线：`v0.1.0-rc.2`

计划日期：`2026-08-25`

## 0. 决策摘要

本计划接受以下产品方向：

1. 用户只面对一个 Rolo 会话 Agent；该 Agent 可以连续完成对话、目标检查、部署、注册、
   证据采集和 Adapt。
2. 会话 Agent 与部署执行器可以属于同一产品主体、同一任务甚至同一服务进程，但必须保留
   工具权限、凭据、审批和审计边界。
3. 自然语言不要求先转换成用户可见的完整静态计划；真正执行的工具调用、状态变更、审批、
   重试和回滚必须具有结构化契约。
4. 目标机逻辑上仍需完成本地 Collector enrollment。用户不应再被要求手工运行
   `robotctl target-evidence collector-init`；Local 或 SSH Target Executor 在目标机上幂等执行。
5. CLI、TUI、GUI 和自然语言共用同一 Application Command、Job 和 Event 层，不分别实现
   部署逻辑。
6. SSH 第一阶段同时承担连接和 bootstrap；部署完成后切换到最小权限的目标端入口。
7. Adapter Agent 不获得部署 SSH 凭据，也不成为远端管理员。
8. 现有 Adapt、Discovery、Wiki、Operation Mapping、Gate、Catalog、State Graph 和 release
   保持权威，不因新交互层降低证据或门禁要求。

这是一项产品控制面扩展，不是重写 Adapt 核心。

## 1. 产品目标

用户可以通过以下任一入口完成等价任务：

```bash
rolo target add wheeltec --ssh robot@192.168.1.20
rolo adapt start --target wheeltec --workspace /home/robot/wheeltec_ws
```

```text
通过 SSH 连接 192.168.1.20，把它注册为 wheeltec，
然后发现 /home/robot/wheeltec_ws 并执行只读适配。
```

GUI/TUI 应提供相同的目标选择、连接检查、风险提示、审批、进度、阻塞原因和制品下钻。
所有入口必须产生相同的 Run、Event、Evidence、Gate 和 Audit 记录。

### 1.1 成功标准

- 首次接触一台满足前置条件的 Linux 目标机时，用户不需要手工输入 Collector 命令；
- Local 和 SSH 两种 Target Executor 通过同一套 conformance contract；
- SSH bootstrap 可幂等重试，失败不会留下被误认为已注册的半成品；
- GUI/TUI/CLI/Natural Language 创建的等价任务产生相同规范化 Command；
- Agent 可以动态检查和修正路径，不需要预先冻结所有步骤；
- 任何安装、sudo、主机密钥首次接受、身份替换和升级都进入审批与审计；
- SSH credential、Collector 私钥和 API token 不进入 Agent prompt、artifact 或普通日志；
- 目标证据继续绑定 robot、collector、target、nonce、freshness 和 payload digest；
- 完整 Adapt 仍必须通过现有独立 Gate 才能发布 release。

### 1.2 非目标

首个 MVP 不实现：

- 自由远程终端或浏览器内 Shell；
- 远程 IDE、断点调试、任意进程注入；
- 无人批准的任意 root 命令；
- Windows、FreeRTOS、CyberRT 目标端 Provider；
- 多租户 SaaS 控制面；
- 让 Adapter Agent 直接部署或更新目标机；
- 用自然语言文本替代 Operation Contract、Policy、Gate 或 Audit；
- 用 SSH 成功连接冒充真机行为、安全或可靠性验收。

## 2. 统一产品模型

现有 `EvidenceDeploymentMode.LOCAL/REMOTE` 只描述证据传输，不足以表达新产品。新增三个正交
维度：

| 维度 | 首版取值 |
|---|---|
| Orchestrator placement | `TARGET_LOCAL`、`CONTROLLER` |
| Target transport | `LOCAL`、`SSH` |
| Interaction surface | `CLI`、`TUI`、`GUI`、`NATURAL_LANGUAGE` |

典型组合：

| 场景 | Orchestrator | Transport | 说明 |
|---|---|---|---|
| 目标机直接运行 Rolo | `TARGET_LOCAL` | `LOCAL` | 当前默认路径的产品化 |
| 控制器远程适配 | `CONTROLLER` | `SSH` | 控制器运行 Agent/Gate，目标机运行最小 companion |
| GUI 管理目标机本地 Rolo | `TARGET_LOCAL` | `SSH` bootstrap + API | SSH 用于安装/隧道，业务由目标 API 承载 |
| GUI 管理控制器 Rolo | `CONTROLLER` | `SSH` | GUI 连接控制器，控制器管理目标 |

不得再用一个 `remote=true` 同时推断运行位置、证据来源、凭据位置和 release 部署位置。

## 3. 总体架构

```text
CLI / TUI / GUI / Natural Language
                 |
                 v
       Application Command Bus
                 |
       Policy / Approval / Audit
                 |
                 v
       Resumable Deployment Job
         |                 |
         v                 v
 LocalTargetExecutor   SshTargetExecutor
         |                 |
         +--------+--------+
                  v
          target-side rolo-target
        bootstrap / enroll / probe
                  |
          signed target evidence
                  v
          existing AdaptJourney
                  |
       Agent -> Gate -> immutable release
```

### 3.1 单一 Agent，分级工具权限

用户只感知一个 `RoloSessionAgent`。内部提供结构化工具：

```text
target.connection.inspect       READ_ONLY
target.hostkey.approve          APPROVAL_REQUIRED
target.bootstrap.plan           READ_ONLY
target.bootstrap.execute        HOST_MUTATION
target.enroll                   IDENTITY_MUTATION
target.evidence.collect         READ_ONLY
adapt.start                     LONG_RUNNING_JOB
target.upgrade                  HOST_MUTATION
target.enrollment.rotate        IDENTITY_MUTATION
```

同一 Agent 可以依次调用这些工具，但工具运行时负责：

- 参数和 Schema 校验；
- 获取 credential reference 对应的秘密；
- 权限与审批检查；
- SSH/本地命令执行；
- 输出限额和脱敏；
- 状态落盘、幂等、取消和审计。

Agent 只能看到 credential reference，不读取私钥正文。

### 3.2 自然语言边界

自然语言可以动态调用工具，不要求每次生成完整 JSON Plan。以下内容仍必须结构化：

- target identity 与 connection profile；
- workspace 和 Rolo version；
- 目标动作、风险和所需权限；
- host-key decision；
- approval decision；
- job/step/event 状态；
- artifact、digest、enrollment 和 release 身份；
- retry、cancel、rollback 和 rotation。

系统必须始终可以从一次自然语言任务导出等价 canonical CLI，用于复现和审计。

## 4. 信任与安全模型

### 4.1 两阶段 SSH 身份

首次 bootstrap 使用部署身份，可拥有经过批准的安装权限；部署完成后使用目标最小权限身份：

```text
bootstrap credential
  -> platform inspection
  -> signed package installation
  -> account/service creation
  -> enrollment
  -> bootstrap credential no longer used by ordinary Adapt

runtime credential
  -> fixed or typed rolo-target protocol
  -> no PTY
  -> no port/agent/X11 forwarding by default
  -> no sudo
```

bootstrap credential 不能进入 Adapter Agent workspace 或 prompt。

### 4.2 SSH 主机信任等级

首版定义：

| 等级 | 规则 | 默认用途 |
|---|---|---|
| `STRICT` | 预置 host key 或企业 SSH CA | 生产默认 |
| `CONFIRMED` | GUI/TUI 展示指纹并由用户明确确认 | 首次实验室接入 |
| `TOFU_DEV` | 首次记录，明确标注低保证 | 本地开发，默认关闭 |

任何等级变化都生成 transition audit。主机密钥变化不能静默接受。

### 4.3 Collector 签名迁移

当前 v2 使用 HMAC shared secret，远程模式要求控制器持有 verification secret。产品化自主部署
应新增 `robot-target-evidence-collector/v4`：

- 目标机生成 Ed25519 key pair；
- 私钥保持目标本地 `0600`，可选 TPM-backed provider；
- descriptor 携带 public key、key ID 和算法；
- bundle 使用 detached Ed25519 signature；
- rotation transition 由旧 key 签名，新 key 重新固定；
- 控制器不再复制 Collector 签名秘密。

迁移期继续只读支持 v1-v3 HMAC bundle；新自主 bootstrap 默认生成 v4。旧协议不能被静默升级或
冒充 v4。

### 4.4 Agent 与执行器边界

- 会话 Agent 可以决定下一项工具调用；
- 执行器只执行已注册工具，不执行模型拼接的隐藏 shell 字符串；
- 专家模式可以提供显式 raw SSH escape hatch，但默认关闭、逐次审批并完整审计；
- 高风险参数必须在执行前向用户显示规范化摘要；
- Agent 不得批准自己的权限提升；
- Adapter Agent 只能访问现有 bounded inspection surface。

## 5. 新增领域契约

建议新增以下版本化 Schema：

```text
schemas/TargetProfile.schema.json
schemas/TargetConnectionProfile.schema.json
schemas/TargetConnectionAssessment.schema.json
schemas/BootstrapPlan.schema.json
schemas/DeploymentCommand.schema.json
schemas/DeploymentJob.schema.json
schemas/DeploymentStep.schema.json
schemas/DeploymentEvent.schema.json
schemas/ApprovalRequest.schema.json
schemas/TargetEnrollmentV4.schema.json
schemas/TargetRuntimeStatus.schema.json
```

### 5.1 TargetProfile 最小字段

```json
{
  "schema_version": "rolo-target-profile/v1",
  "target_id": "wheeltec",
  "orchestrator_placement": "CONTROLLER",
  "transport": "SSH",
  "connection_profile_id": "conn-wheeltec-lab",
  "workspace_root": "/home/robot/wheeltec_ws",
  "desired_rolo_version": "v0.2.0",
  "trust_level": "STRICT"
}
```

不得写入 SSH private key、password、token 或 Collector private key。

### 5.2 DeploymentCommand

所有交互入口规范化为命令，例如：

```json
{
  "schema_version": "rolo-deployment-command/v1",
  "command": "BOOTSTRAP_AND_ADAPT",
  "target_id": "wheeltec",
  "workspace_root": "/home/robot/wheeltec_ws",
  "active_probe": "runtime-readonly",
  "run_adapter_agent": true,
  "requested_by": "session-agent",
  "interaction_surface": "NATURAL_LANGUAGE"
}
```

`requested_by` 不是授权；执行时仍需要主体身份、policy 和 approval evidence。

### 5.3 Job 与 Event

Job 状态：

```text
CREATED
CONNECTING
HOST_KEY_APPROVAL_REQUIRED
PREFLIGHT
BOOTSTRAPPING
ENROLLING
COLLECTING_EVIDENCE
DISCOVERING
ADAPTING
GATING
COMPLETE
BLOCKED
FAILED
CANCELLED
```

每个 Event 至少绑定：

```text
job_id
step_id
target_id
event_type
timestamp
attempt
status
sanitized_summary
artifact_refs
approval_ref
```

## 6. 代码组织建议

新增：

```text
src/rolo/targets/
├── models.py
├── profiles.py
├── credentials.py
├── trust.py
├── executor.py
├── local.py
├── ssh.py
├── bootstrap.py
├── enrollment.py
├── packaging.py
└── conformance.py

src/rolo/jobs/
├── models.py
├── store.py
├── events.py
├── runner.py
├── approvals.py
└── recovery.py

src/rolo/application/
├── commands.py
├── command_bus.py
├── target_service.py
└── adapt_service.py

src/rolo/api_routes/
├── targets.py
├── jobs.py
├── approvals.py
└── events.py
```

修改：

- `commands/lifecycle.py`：从直接编排迁移为 Application Command client；
- `commands/target_evidence.py`：保留兼容入口，接入 v4 enrollment；
- `stages/adapt/target_evidence.py`：增加非对称签名和 transport-neutral verifier；
- `stages/adapt/journey.py`：拆出 checkpoint/event hook，不改变 Gate 权威；
- `core/config.py`：增加非秘密 connection/profile 配置；
- `api.py`：保留 read models，将写路由拆到独立 router；
- `runtime.py`：注入 Command Bus、Job Store、Credential Provider；
- `schema_export.py`：导出新 Schema；
- `docs/TARGET_DEVICE_OPERATION_MANUAL_ZH.md`：增加 Agent-assisted flow，保留手工严格流程。

GUI 工作预计主要发生在配套 `rolo-vis` 仓库，本仓库负责稳定 API、SSE、Schema 和 read model。

## 7. 实施工作包

### W0：ADR、威胁模型与产品契约

状态：`PENDING`

目标：冻结术语、信任根、运行位置和首版范围，避免 UI 与 transport 先行后返工。

交付物：

- Orchestrator/Transport/Interaction 三维 ADR；
- 单一 Agent、多工具权限 ADR；
- SSH bootstrap threat model；
- HMAC v2/v3 到 Ed25519 v4 迁移 ADR；
- 新 Schema 初稿；
- Linux x86_64/ARM64 支持矩阵；
- `rolo-target` 是一次性入口还是常驻服务的决定。

验收：

- 明确 bootstrap credential 和 runtime credential 生命周期；
- 明确首次 host-key trust UX；
- 明确哪些动作自动执行、哪些必须审批；
- 明确 release 最终存储和运行位置。

估算：`1-2 人周`

### W1：Application Command Bus 与 TargetProfile

状态：`PENDING`

依赖：W0

目标：让 CLI、API 和未来 UI 使用同一业务入口。

交付物：

- `TargetProfile`、`ConnectionProfile` 和无秘密持久化；
- credential reference SPI；
- `DeploymentCommand` validator；
- in-process Command Bus；
- 当前 `adapt start` 通过 Command Bus 调用的兼容路径；
- canonical CLI renderer。

验收：

- 当前本地 `adapt start` 行为和输出保持兼容；
- CLI 与直接 service 调用生成同一 Command digest；
- profile/artifact 不包含秘密；
- 未知字段和非法路径失败关闭。

估算：`3-4 人周`

### W2：LocalTargetExecutor 与 SshTargetExecutor

状态：`PENDING`

依赖：W0、W1

目标：统一目标检查和命令执行，不把 raw SSH 暴露给业务层。

交付物：

- `TargetExecutor` protocol；
- local/ssh 双实现；
- SSH config、Port、Identity、ProxyJump 和 known_hosts 支持；
- bounded stdin/stdout/stderr、timeout、cancel 和 process cleanup；
- read-only inspection tools；
- Target Executor conformance kit。

验收：

- Local 与 SSH 对同一 inspection contract 返回一致模型；
- `BatchMode` 和 strict host-key policy 不可被 Agent 参数关闭；
- command arguments 不经过 shell 拼接；
- 网络中断、超时、非零退出和超限输出具有确定错误码；
- SSH secret 不进入日志。

估算：`3-4 人周`

### W3：目标端制品与幂等 Bootstrap

状态：`PENDING`

依赖：W2

目标：替换正式产品对 `git clone + uv sync` 的依赖。

交付物：

- x86_64/ARM64 可校验目标端制品；
- release manifest 与签名/digest；
- platform/preflight detector；
- upload、verify、install、activate、health-check、rollback；
- 最小权限账号和 systemd/forced-command 模板；
- bootstrap dry-run 与 approval summary；
- idempotent install state。

验收：

- 相同版本重复 bootstrap 不产生额外身份；
- 上传中断不会激活不完整版本；
- health check 失败自动恢复旧版本或保持未激活；
- 离线目标可以从控制器上传制品安装；
- sudo 动作逐项列入审批摘要。

估算：`4-6 人周`

### W4：Enrollment v4 与 Collector 自动初始化

状态：`PENDING`

依赖：W0、W2、W3

目标：目标本地生成身份与私钥，用户无需手工运行 `collector-init`。

交付物：

- Ed25519 Collector descriptor/bundle；
- target-local key generation；
- controller public-key pin；
- challenge/nonce/freshness 验证；
- v4 rotation transition；
- v1-v3 只读兼容；
- `target.enroll` 工具；
- 现有 `collector-init` 兼容 wrapper。

验收：

- private signing key 从不离开目标；
- descriptor 或 bundle 篡改失败关闭；
- replay、过期、robot/collector/host mismatch 被拒绝；
- 并发 enrollment 只有一个成功；
- 断电/中断不会产生可被误用的半注册身份；
- 本地与 SSH 自动 enrollment 使用同一状态机。

估算：`3-5 人周`

### W5：远程 Workspace 与 Adapt 集成

状态：`PENDING`

依赖：W2、W4

目标：去除“控制器必须手工准备未经修改的目标制品副本”的主要使用障碍。

交付物：

- `TargetWorkspaceRef`；
- 目标端有界源码/制品 manifest；
- 签名摘要和选择性 artifact transfer；
- remote project evidence detection；
- `AdaptJourney` transport-neutral target probes；
- controller/target artifact provenance；
- release placement 明确化。

验收：

- 控制器不把自己的 build/install 冒充目标制品；
- 目标路径越界、symlink escape 和超限传输被拒绝；
- 同一 workspace snapshot 可重复得到相同 manifest digest；
- target evidence 失败不回退控制器探针；
- 现有 Local Journey 回归不变。

估算：`4-6 人周`

### W6：Job、Event、Approval 与恢复

状态：`PENDING`

依赖：W1；与 W2-W5 并行演进

目标：支撑长任务、GUI/TUI、断线重连和自然语言动态执行。

交付物：

- atomic Job Store；
- append-only sanitized Event log；
- step checkpoint；
- per-target lock；
- cancel/retry/resume；
- approval request/decision；
- restart recovery；
- SSE stream。

验收：

- 服务重启后可恢复或明确终止未完成 Job；
- 同一目标不能并发执行冲突部署；
- approval 绑定 command digest、principal、expiry；
- 取消后远端进程被终止或标为需要人工确认；
- Event 不泄漏 secret 或任意文件内容；
- Job 完成状态与最终 artifact 一致。

估算：`4-6 人周`

### W7：受控写 API、CLI 与 TUI

状态：`PENDING`

依赖：W1、W6；SSH 完整体验依赖 W2-W5

交付物：

```text
POST /v1/targets
POST /v1/targets/{id}/connection-assessments
POST /v1/targets/{id}/bootstrap-jobs
POST /v1/targets/{id}/adapt-jobs
GET  /v1/jobs/{id}
GET  /v1/jobs/{id}/events
POST /v1/jobs/{id}/cancel
POST /v1/approvals/{id}/decisions
```

同时交付：

- CLI target/connect/bootstrap/adapt 命令；
- 兼容现有 `robotctl adapt start`；
- TUI Fleet/Target/Job/Approval/Blocker 页面；
- canonical CLI 显示；
- API token、body limit、idempotency key 和审计。

验收：

- CLI、TUI 和 API 创建相同命令时 Command digest 一致；
- 所有 mutating API 需要身份、权限和 idempotency key；
- TUI 断线重连不重复创建 Job；
- API 不接受自由 shell；
- 当前 read-only API 兼容。

估算：`4-7 人周`，其中 TUI `2-4 人周`

### W8：GUI Workbench 部署体验

状态：`PENDING`

依赖：W6、W7

目标：在现有只读 rolo-vis 工作台上增加目标接入与任务控制，不引入自由终端。

页面：

- Add Target；
- SSH fingerprint confirmation；
- Connection Assessment；
- Bootstrap Plan 与权限摘要；
- Live Job Timeline；
- Approval Drawer；
- Blocker/Recovery；
- Adapt result、Gate、Evidence 和 canonical CLI。

验收：

- GUI 不持有 SSH private key；
- 刷新页面后恢复当前 Job；
- 高风险审批显示目标、动作、版本、路径和 digest；
- GUI 与 TUI 显示相同状态语义；
- 无 SECRET payload 进入浏览器响应。

估算：`5-8 人周`；若不能复用现有 rolo-vis，再增加 `6-10 人周`

### W9：自然语言 Session Agent

状态：`PENDING`

依赖：W1、W6、W7；可在 CLI/TUI 稳定后开始

目标：一个 Agent 动态调用目标、部署和 Adapt 工具。

交付物：

- bounded tool catalog；
- conversation-to-command adapter；
- missing-input clarification；
- tool result summarization；
- approval handoff；
- canonical CLI reproduction；
- prompt-injection and untrusted target-output isolation；
- Agent action budget、timeout 和 cancel。

验收：

- Agent 不读取 credential material；
- 目标机 banner、README、日志不能改变工具 policy；
- Agent 不能批准自己的 host mutation；
- 等价自然语言与 CLI 产生等价 Command；
- 模型失败不会跳过 Gate 或把 Job 标为成功；
- 不确定目标、路径或权限时请求澄清，不猜测执行。

估算：`3-5 人周`

### W10：真机、多架构与生产硬化

状态：`PENDING`

依赖：W2-W9

覆盖：

- Ubuntu/Debian x86_64；
- Ubuntu/Debian ARM64；
- 无外网目标；
- 非 root 目标；
- sudo 需要交互审批；
- SSH jump host；
- host key rotation；
- 网络抖动/断线；
- 磁盘不足；
- 中途重启；
- ROS 与非 ROS workspace；
- 多目标并行和单目标互斥；
- upgrade/rollback/enrollment rotation。

交付物：

- 真机验收矩阵；
- E2E SSH server fixture；
- chaos/failure-injection tests；
- installer SBOM 和签名验证；
- 安全评审和操作手册；
- RC rollout 与 rollback runbook。

估算：`5-8 人周`

## 8. 分阶段发布

### Phase A：安全 SSH CLI Prototype

范围：W0-W2 的最小实现、现有 HMAC 兼容、CLI only。

用途：验证一个会话 Agent 通过 typed SSH tools 完成 inspect 和现有 Collector 调用。

限制：不宣称完成生产自主 bootstrap。

估算：`8-12 人周`

### Phase B：Linux 单用户产品 MVP

范围：W0-W7、Enrollment v4、CLI/TUI、Job/Event/Approval、x86_64/ARM64 基线。

成功结果：用户无需手工执行 Collector 命令，可以从控制器完成 SSH 部署、注册、只读证据采集
和 Adapt。

估算：`30-45 人周`

### Phase C：统一交互产品

范围：W8-W9，扩展 GUI 和自然语言 Session Agent。

估算：在 Phase B 之上增加 `8-13 人周`；不能复用 rolo-vis 时增加更多前端投入。

### Phase D：生产 Fleet

范围：W10，并补充 RBAC、SSH CA、企业秘密管理、集中审计、多用户和 fleet rollout。

累计估算：`55-80 人周`

## 9. 推荐团队与日历

最低有效配置：

| 角色 | 主要负责 |
|---|---|
| Backend/Platform | Target Executor、Bootstrap、Packaging、Enrollment |
| Control Plane | Command、Job、Event、API、Audit |
| Product/UI | TUI、rolo-vis、Approval UX |
| Agent/Safety（可兼职） | Tool contract、自然语言、安全测试 |

日历估算：

- 1 名熟悉当前代码的工程师：MVP `7-10 个月`；
- 3 名工程师：MVP `3-4 个月`；
- 4-6 人团队：生产化 `4-6 个月`。

估算包含自动化测试和文档，不包含外部安全认证、特定厂商机器人集成或大规模现场试点。

## 10. 迁移与兼容

- 保留 `robotctl adapt start --evidence-mode local|remote` 至少一个兼容周期；
- 保留 `target-evidence collector-init/configure/collect` 作为专家和恢复入口；
- 新 `rolo target ...` 命令内部走 Command Bus；
- v1-v3 deployment/bundle 只读兼容，新自主部署默认 v4；
- 已固定的 HMAC deployment 不自动转为 Ed25519；必须显式 migration/rotation；
- 当前 artifact、Registry、Contract、Gate 和 release digest 不因 UI 来源变化；
- read-only Web API 保持兼容，新增写 API 使用独立 versioned models；
- `TARGET_DEVICE_OPERATION_MANUAL_ZH.md` 保留手工严格置备，新增 Agent-assisted 章节。

## 11. 测试策略

### 11.1 单元与属性测试

- Schema strict validation；
- Command canonicalization/digest；
- path、argv、host、port 和 proxy validation；
- secret redaction；
- enrollment signature/replay/rotation；
- Job state transition 和 idempotency；
- approval digest/expiry/principal binding。

### 11.2 Executor conformance

同一 fixture 对 Local/SSH Executor 验证：

- stdout/stderr/exit/timeout；
- cancel/process-tree cleanup；
- file transfer digest；
- host-key policy；
- unavailable dependency；
- bounded output；
- no shell interpolation。

### 11.3 Integration

- 容器或 VM 中真实 `sshd`，不得只 monkeypatch `subprocess.run`；
- bootstrap/install/upgrade/rollback；
- target enrollment 和 fresh bundle；
- controller Adapt Journey；
- API -> Job -> SSH -> target -> evidence -> Gate；
- SSE reconnect 和 restart recovery。

### 11.4 真机验收

自动化工程测试不能代替：

- 真实 ARM64 目标；
- 真实 ROS graph；
- 非 ROS Application/CLI；
- 网络中断和目标重启；
- 操作系统权限差异；
- 目标主机替换、host key rotation 和 enrollment rotation。

## 12. 风险与控制

| 风险 | 控制 |
|---|---|
| Agent 获得无限 SSH 权限 | typed tools、credential isolation、approval、raw shell 默认关闭 |
| 同信道 bootstrap 削弱独立信任 | SSH CA/指纹确认、Ed25519 enrollment、可选物理确认 |
| GUI/TUI/CLI 行为漂移 | 单一 Command Bus 和 Command digest conformance |
| 长任务中断留下半安装 | staged activation、checkpoint、idempotency、rollback |
| 目标输出 prompt injection | 标记 untrusted、结构化解析、不给输出定义 policy 的能力 |
| ARM64/离线部署失败 | 预构建制品、manifest、离线上传、架构 CI |
| Job 状态与 artifact 不一致 | atomic index、final integrity validation、恢复审计 |
| 远程源码和本地副本混淆 | TargetWorkspaceRef、目标 manifest、provenance |
| 产品范围失控 | Phase gate、MVP 非目标、每阶段独立验收 |

## 13. Phase Gate

### Gate A：允许进入 Bootstrap 实现

- W0 ADR 和威胁模型通过评审；
- TargetProfile/Command Schema 冻结 v1；
- credential 和 host-key policy 明确；
- raw shell 默认策略明确。

### Gate B：允许进入 GUI/Natural Language

- CLI 经真实 SSH E2E 完成 bootstrap/enroll/collect/adapt；
- Job 可恢复且审批绑定 digest；
- Local/SSH Executor conformance 通过；
- secret redaction 测试通过；
- Enrollment v4 replay/rotation 测试通过。

### Gate C：允许生产 RC

- x86_64/ARM64 真机矩阵通过；
- upgrade/rollback/断线/重启测试通过；
- 安全评审无 P0/P1 未解决问题；
- GUI/TUI/CLI/NL 等价命令测试通过；
- 手册、恢复流程和 rollback runbook 完成。

## 14. 前四周建议 Backlog

### Week 1

- 完成 W0 ADR 和 threat model；
- 确定 v4 签名库和目标包形式；
- 建立 TargetProfile、DeploymentCommand Schema；
- 建立真实 `sshd` CI fixture 技术验证。

### Week 2

- 实现 Command Bus skeleton；
- 实现 credential reference/redaction；
- 实现 LocalTargetExecutor contract；
- 让现有本地 `adapt start` 走兼容 Command path。

### Week 3

- 实现 SshTargetExecutor read-only inspect；
- 加入 strict/confirmed host-key assessment；
- 建立 Local/SSH conformance suite；
- 输出 canonical CLI。

### Week 4

- 实现 bootstrap dry-run 和 typed step model；
- 加入 Job/Event 最小持久化；
- 通过真实 SSH 完成 `inspect -> existing collector collect`；
- 评审 Phase A 数据，再决定进入 package installer 或先修正契约。

## 15. 完成定义

本计划完成不是指“Agent 能 SSH 登录”，而是以下条件全部成立：

- 用户通过 CLI、TUI、GUI 或自然语言均可创建统一的目标任务；
- 一个会话 Agent 可以自主推进读取和低风险步骤；
- 所有状态变更都有结构化工具、审批、Job、Event 和 Audit；
- 目标机 enrollment 自动且目标本地执行；
- 目标私钥不离开目标，控制器可验证证据；
- SSH bootstrap、升级和回滚幂等可恢复；
- Local/SSH 两种拓扑共享 Adapt/Gate 权威；
- Adapter Agent 无部署凭据；
- 真机、多架构和故障矩阵通过；
- 当前 CLI、evidence 和 artifact 兼容策略有测试保护；
- 发布说明明确哪些结论只是软件验证，哪些已经完成真机验收。

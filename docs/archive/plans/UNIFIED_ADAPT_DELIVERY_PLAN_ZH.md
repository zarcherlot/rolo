# Rolo 统一 Adapt 入口交付计划

状态：`ACTIVE`

基线：`main@a75ea0b`

启动日期：`2026-08-26`

## 0. 交付决策

用户不再执行一套独立的 setup 流程。产品入口只要求用户说明“适配哪个目标”：

```bash
# 本地
rolo adapt /home/robot/wheeltec_ws --robot wheeltec

# 远程
rolo adapt ssh://robot@192.168.1.20/home/robot/wheeltec_ws --robot wheeltec
```

自然语言入口表达同一件事，并生成同一个规范化 Command：

```text
适配本机的 /home/robot/wheeltec_ws，机器人命名为 wheeltec。

通过 SSH 适配 192.168.1.20 上的 /home/robot/wheeltec_ws，
机器人命名为 wheeltec。
```

本地路径与 SSH URI 是两种 Target Reference；CLI、自然语言、TUI 和 GUI 只是同一
Application Command 的不同适配器。`robotctl adapt start` 和细粒度
`target-evidence` 命令继续作为兼容、诊断和恢复入口，不再作为产品 happy path。

## 1. 用户需要承担的最小动作

首次使用不能消除、但可以集中处理的动作只有：

1. 在 Orchestrator 安装一次 Rolo；
2. 完整 Agent 链首次运行前完成一次 Codex 认证；
3. 首次连接远程目标时确认主机指纹；
4. 安装或升级目标 companion 前批准一次主机变更。

以下实现细节由 Rolo 自动管理，默认不出现在产品命令中：

- `--evidence-mode`；
- Collector descriptor、verification secret 和 config path；
- `collector-init/configure/collect`；
- target profile 创建和复用；
- 本地或 SSH Target Executor 选择；
- enrollment、证据采集、Adapt Journey 与断点续跑。

## 2. 不变边界

简化只发生在控制面，不降低现有权威边界：

- 远程主机密钥变化必须失败关闭；
- 安装、sudo、身份替换和升级必须审批并审计；
- SSH credential 和 Collector 私钥不得进入 Agent prompt 或普通 artifact；
- 远程采集失败不得回退到控制器本机证据；
- Adapter Agent 不获得部署凭据、Gate 权限或发布权限；
- 只有现有独立 Gate 可以发布不可变 release；
- `robotctl adapt start` 在兼容周期内保持行为和输出兼容。

## 3. 最小领域模型

### 3.1 Target Reference

```text
LocalTargetRef
  workspace: absolute path

SshTargetRef
  host: DNS/IP
  user: optional SSH user
  port: optional port
  workspace: absolute POSIX path
```

解析规则：

- 普通文件系统路径解析为 `LocalTargetRef`；
- `ssh://` URI 解析为 `SshTargetRef`；
- URI 不承载密码、私钥正文或任意 SSH 参数；
- 相对本地路径在 CLI 边界规范化为绝对路径；
- SSH workspace 必须是绝对 POSIX path；
- target identity 与 workspace identity 分离，不能用路径冒充机器人身份。

### 3.2 Adapt Command

```text
AdaptCommand
  robot_id
  target_ref
  urdf_ref?
  run_agent = true
  active_probe = runtime-readonly
  timeout?
```

CLI 和自然语言必须落到这一模型。Command 可以导出等价 canonical CLI，但不包含凭据。

### 3.3 Target Profile

第一次远程运行成功后幂等保存 Profile；后续运行直接复用。Profile 保存 connection metadata、
host-key pin、companion/enrollment identity 和 credential reference，不保存私钥正文。

## 4. 交付波次

### W0：统一入口与本地闭环

目标：在不改变 Adapt 核心的前提下交付可用的 `rolo adapt <local-path>`。

范围：

- 增加 `rolo` console script；
- 增加 Target Reference 解析和验证；
- 将当前 `adapt start` 的业务调用抽到共享服务函数；
- 新入口将本地路径映射到现有 `AdaptJourneyService`；
- 保留 `robotctl adapt start` 的参数、退出码和 JSON 输出；
- 增加解析、CLI 转发与兼容回归测试。

退出标准：

- `rolo adapt PATH --robot ID --discover-only --active-probe none` 完成本地 Journey；
- 旧命令的现有测试不回归；
- SSH URI 返回稳定、明确的“尚未支持”错误，而不是误用本地路径；
- `ruff` 与目标测试通过。

### W1：统一 Target Executor 与自动远程 bootstrap

目标：同一命令接受 SSH URI，并自动完成安全的首次接入。

范围：

- `LocalTargetExecutor` / `SshTargetExecutor` conformance contract；
- connection inspect 和结构化 bootstrap plan；
- 显式 host-key decision；
- 签名 `rolo-target` 包的 upload、verify、install、health-check 和 rollback；
- 目标本地生成身份和非对称签名密钥；
- 自动 enrollment 和 Target Profile；
- 远程 workspace evidence，不再要求控制器源码副本。

退出标准：

- 真实 SSH E2E 从一个管理身份完成 bootstrap、enroll、collect 和 discover-only；
- 重跑不重复创建账号、密钥或安装；
- 主机密钥、目标身份、签名或 workspace provenance 不匹配时失败关闭；
- Local/SSH executor 使用同一 fixture 通过 conformance。

### W2：可恢复 Adapt Job

目标：长时间 Adapt 支持重连、恢复、取消和一致的进度表达。

范围：

- `AdaptJob`、`JobStep`、`JobEvent` 和 checkpoint schema；
- 单写者状态机与幂等 command key；
- bootstrap、enroll、collect、discover、agent、gate、publish 分步事件；
- CLI 以前台方式消费 Job，同步行为保持兼容；
- API/TUI/GUI 读取同一 Job/Event，不复制业务逻辑。

退出标准：

- 进程重启后可以从安全 checkpoint 恢复；
- 重复请求不会产生第二次发布或身份替换；
- canonical CLI、审批、事件和 artifact 可互相追踪。

### W3：自然语言薄适配器

目标：自然语言调用同一个 Command/Job 层，不建设第二套编排器。

范围：

- 首版以 Codex skill 提供自然语言入口；
- skill 只调用结构化 inspect、plan、approve 和 adapt 工具；
- 高风险动作继续由执行器请求审批，Agent 不能自批；
- 会话始终展示或导出 canonical CLI、Job ID 和最终 Gate 结果。

退出标准：

- 四个等价场景（本地/远程 × CLI/自然语言）产生等价 `AdaptCommand`；
- 自然语言输入不能注入 SSH 参数、shell 或 credential；
- CLI 与自然语言产出的 Evidence、Gate、release 具有相同验证路径。

### W4：产品化安装

目标：取消 Git checkout 与 `uv sync` 作为用户安装方式。

范围：

- Orchestrator 的固定版本签名发行包；
- 目标侧最小 `rolo-target` 包；
- 安装前平台检查、签名验证和依赖诊断；
- `doctor` 给出可执行修复建议；
- 升级、回滚和 SBOM。

安装器不能静默完成 Codex 登录、接受 SSH 主机密钥或执行未经批准的 sudo。

## 5. Worktree 与合并设计

所有开发分支使用 `codex/` 前缀；worktree 放在主 checkout 外，避免测试和文件扫描误入其他
工作树。

```text
main
 └─ codex/unified-adapt-integration
     ├─ codex/unified-adapt-entrypoint       W0：TargetRef + rolo CLI + 兼容层
     ├─ codex/unified-target-executors       W1：Local/SSH executor + bootstrap
     ├─ codex/unified-adapt-jobs             W2：Job/Event/checkpoint
     └─ codex/unified-adapt-natural-language W3：Codex skill 与等价性测试
```

实际依赖并非四个分支同时启动：

1. `unified-adapt-entrypoint` 从 `origin/main` 创建并先完成；
2. 建立 `unified-adapt-integration`，合并 W0；
3. `unified-target-executors` 从已含 W0 的 integration 创建；
4. W1 合并后再创建 `unified-adapt-jobs`；
5. Job contract 稳定后才创建自然语言 worktree。

建议目录：

```text
C:/Users/zarch/Desktop/robot_loop                 main 与计划文档
C:/Users/zarch/Desktop/robot_loop-worktrees/
  unified-adapt-entrypoint/                       当前开发
  unified-adapt-integration/                      波次集成与全量验证
  unified-target-executors/                       W1 开始时创建
  unified-adapt-jobs/                             W2 开始时创建
  unified-adapt-natural-language/                 W3 开始时创建
```

每个功能分支只修改自己的领域；跨分支 Schema 先进入 integration，再由下游分支同步。禁止复制
Adapt Journey、Evidence verifier、Gate 或 release 发布逻辑。

## 6. 首个开发切片

本次立即启动 `codex/unified-adapt-entrypoint`：

1. 新增 Target Reference parser；
2. 抽取旧 CLI 的共享 Adapt 启动函数；
3. 新增 `rolo` 产品 CLI；
4. 新增本地 happy-path 和兼容测试；
5. 运行目标测试和 lint；
6. 通过后建立 integration 分支并合并 W0。

W0 不自动安装任何软件、不建立 SSH 连接，也不改变证据或 Gate 语义。这样可以先稳定最终用户
接口，再在 W1 中接入有审批和审计的远程执行器。

## 7. 完成定义

统一入口全部完成时必须满足：

- 用户从安装到 Adapt 不需要阅读 Collector 运维步骤；
- 本地和远程只由 Target Reference 区分；
- CLI、自然语言、TUI 和 GUI 共用 Command/Job/Event；
- 第一次远程部署可审阅、可拒绝、可重试、可回滚；
- 日常 Adapt 不再使用 bootstrap credential；
- 专家命令仍能独立诊断和恢复；
- 安全边界、签名证据、Gate 和不可变 release 不因 UX 简化而降级。

## 8. 开发进度

### W0：已完成

- 功能提交：`79d4c95 feat(cli): add unified local adapt entrypoint`；
- 集成提交：`6a8f56c merge: establish unified Adapt entrypoint`；
- 已交付 `rolo adapt <local-path>`、Target Reference parser 和旧 CLI 兼容层；
- 新入口、旧 Adapt Journey、lint 和全仓测试通过。

### W1.1：已完成

- 功能提交：`562875d feat(targets): add read-only target inspection`；
- 已交付 Local/SSH `TargetExecutor` 契约、连接评估和类型化 bootstrap plan；
- 缺少 host-key pin 时不发起 SSH；
- 已 pin SSH 只执行固定只读探针，禁用交互、转发和全局 known-hosts 回退；
- companion 安装只进入 `APPROVAL_REQUIRED` plan，不提供执行入口；
- 16 项目标测试、lint 和全仓测试通过。

### W1.2：已完成

- 引入版本化 Target Profile 与 credential reference；
- 实现 host-key decision 的显式记录，不自动接受首次连接；
- 定义签名 companion package manifest 和本地离线 verifier；
- 实现 bootstrap execute 的审批令牌边界与 dry-run 契约；
- W1.2 功能提交：`d674aa2 feat(targets): add profiles and approval-bound manifests`；
- profile init/show 不连接主机、不写入 secret，host-key approval 仅记录决定，不改写 SSH known_hosts。

### W1.3：已完成

- W1.3 功能提交：`aae384e feat(targets): execute approved companion bootstrap`；
- 集成提交：`merge: add approved companion bootstrap execution`；
- 固定 argv 的 SCP/SSH transport，强制 BatchMode、StrictHostKeyChecking、无转发和无全局 known-hosts 回退；
- 仅在 plan、approval request、approval decision、manifest、package hash、target 全部绑定且未过期时允许执行；
- 上传、root 安装、健康检查和清理均有明确失败态，失败不伪装为成功；
- 27 项 W1.3 定向测试、Ruff 和集成分支全量回归通过；未连接真实远端，也未执行真实主机变更。

### W2：首个切片已完成，持续推进

- 功能提交：`5b809c4 feat(jobs): add resumable job event checkpoint store`；
- 已引入 Job/Event/Checkpoint 统一执行契约与 JSON 原子持久化；
- 事件序号、Job revision 和乐观冲突检查已覆盖，支持断点状态保存与恢复读取；
- `rolo target inspect --job` 与 `rolo target bootstrap-plan --job` 已接入生命周期事件和 checkpoint；
- inspect/plan 的 job 输出保持原结果语义，同时提供 job_id 供恢复与审计查询；
- `rolo target bootstrap-request` 与 `rolo target bootstrap-approve` 已接入 plan-bound 审批链；
- `run_bootstrap_job` 已将审批后的 bootstrap execute 接入 Job/Event/Checkpoint；
- 执行前 authority checkpoint、成功/失败结果 checkpoint 和终态事件均可恢复读取；
- 真实远端变更继续保持显式审批和独立 transport 边界；
- 为 CLI、未来自然语言入口和 TUI/GUI 保持同一事件流与审计字段；
- 先实现本地持久化与恢复测试，再接入远程 bootstrap 的断点与重试策略。

### W3：首个切片已完成，持续推进

- 功能提交：`b504efe feat(w3): add job recovery and bounded natural language intents`；
- 新增 `rolo job list`、`rolo job recover`，恢复操作只读 checkpoint，不自动恢复主机变更；
- 新增确定性自然语言意图解析，支持 inspect、bootstrap-plan、job recover；
- 拒绝歧义请求与 shell 命令语法，所有意图仍映射到既有 CLI/Job 契约；
- 新增自然语言 bootstrap request/approve 意图及 canonical argv 适配器；
- 新增 `rolo job events` 有界分页查询；
- 相关测试与 Ruff 通过；下一步进入 W3 收口：统一执行适配器的实际调用编排与端到端等价性测试。
- 新增 `NaturalLanguageExecutionAdapter`，仅调用显式注册的 canonical handler；
- 未注册操作、缺少审批 actor 的自然语言请求均 fail-closed；
- CLI 与自然语言的 canonical argv 等价性测试已覆盖，W3 收口切片完成。

### 产品化阶段：首个基础切片已完成

- 产品化 worktree：`C:/Users/zarch/Desktop/robot_loop-worktrees/unified-adapt-productization`；
- JobStore 统一使用跨进程锁和原子替换写入，降低并发写入和崩溃残留风险；
- 新增稳定的 `JobPage` / `JobEventPage` 响应，包含 total、offset、next_offset；
- `rolo job list` 与 `rolo job events` 已返回统一分页结构；
- 并发 stale writer、原子恢复和分页边界测试通过；
- 产品化提交：`c98d7a9 feat(productization): add stable job and event pages`；
- 新增 `JobService`，并接入 FastAPI：`/v1/jobs`、`/v1/jobs/{job_id}`、`/v1/jobs/{job_id}/events`；
- API、CLI、自然语言和未来 TUI/GUI 共用同一 JobPage/JobEventPage/JobRecovery 模型；
- 服务层提交：`cd522c4 feat(productization): expose job service API`；
- API 与既有 control-plane 回归通过；
- 新增 `NaturalLanguageService`，`rolo natural --execute` 通过 canonical 服务执行显式请求；
- 新增 `ServiceJobQueryAdapter`，供 TUI/GUI 复用 JobService 查询、恢复和事件分页；
- 产品化提交：`cff5fa7 feat(productization): add formal natural service and query adapter`；
- 入口/API 回归与 Ruff 通过；
- 新增 `JobUiAdapter` 与稳定 JobList/JobDetail ViewModel，TUI/GUI 不再直接依赖存储细节；
- 新增 `rolo release-check`，验证关键模块导入与 `rolo`/`robotctl` console scripts；
- UI/发布提交：`6c6cb42 feat(productization): add UI view models and release smoke check`；
- UI、API、入口回归与 Ruff 通过；`release-check` 返回 PASS；
- 当前本地环境未提供 `build`/`hatchling` 打包工具；
- CI 新增 `package` job，使用锁定依赖运行 `release-check`、`uv build` 并检查 wheel/sdist 产物；
- CI 提交：`7c3ce45 ci: add release package gate`；
- 已完成 JobService/API 统一错误码：`JOB_NOT_FOUND`、`INVALID_PAGINATION`、`INVALID_JOB_ID`；
- FastAPI Job 路由统一返回 HTTP 状态与 `{code,message}` detail；
- 缺失 Job、非法分页和 UI 查询边界测试已覆盖；
- 错误语义提交：`45a89ba feat(productization): standardize job service errors`；
- 新增可选 API scope 配置 `ROLO_API_TOKEN_SCOPES`；配置后 Job 查询要求 `jobs:read`，缺失返回 `SCOPE_REQUIRED`；
- 未配置 scopes 时保持现有 loopback/token 兼容行为；
- 权限回归测试已覆盖；权限提交：`dd4e78a feat(productization): add scoped job API access`；
- 下一步继续产品化：发布产物验收与 UI 查询稳定性收口。

### 产品化收口：已完成

- UI 新增稳定错误状态模型，TUI/GUI 查询异常统一映射为可展示状态；
- CI `package` job 在构建后再次执行 `rolo release-check --require-artifacts`，确认 wheel/sdist 实际存在；
- 产品化收口提交：`62ce216 feat(productization): finalize UI errors and artifact gates`；
- 本地产品化测试、API 回归与 Ruff 通过；CI 构建产物需在远端 runner 实际运行后标记最终发布验收。

## 9. 上真机实测前的 P0 必要开发门槛

以下三项必须在产品化阶段完成后，才能进入真实机器人实测；它们不是可选增强，也不能以“先连真机再补”为由跳过：

1. **正式 bootstrap execute 入口（已完成开发，待集成回归）**
   - 提供 CLI、FastAPI 和自然语言 canonical operation；
   - 强制 plan、approval request、approval decision、manifest、package、target 全绑定；
   - 真实远端变更必须经过显式审批和 Job 审计。
   - P0-1 提交：`b946b03 feat: add formal bootstrap execute entrypoints`；
   - 已合并至 integration：`merge: formal bootstrap execute entrypoints`；
   - 默认 `plan-only` 不触发 transport，显式 `--execute` 才允许远端 mutation；API 执行要求 `jobs:execute` scope（未配置 scope 时保持 loopback/token 兼容）。
2. **真实 companion 包构建与签名验收（构建切片已完成，发布验收待 staging）**
   - 生成目标架构包、签名 manifest、hash/version/publisher 校验；
   - 完成构建产物、发布公钥和版本撤回流程验收；
   - 解决当前环境缺少 `pip`、`build`、`hatchling` 导致的 wheel/sdist 验收缺口。
   - 已新增 `rolo target companion-build`：离线生成最小 `rolo-target`、签名 manifest，并立即回验 package hash/signature；提交：`6580b43 feat: add signed companion package builder`。
   - 已新增 `CompanionReleasePolicy` 与 `rolo target companion-verify --policy`，支持 publisher allow-list、版本撤回和 hash 撤回；提交：`6fcee52 feat: enforce companion release revocation policy`。
   - 当前仍缺目标架构真实构建 runner、发布公钥托管与版本撤回演练，不能据此放行真机。
3. **失败回滚与幂等策略（开发切片已完成，staging 验证待执行）**
   - 覆盖安装失败、健康检查失败、断网、超时、重复提交和旧版本升级；
   - 明确卸载/回滚、临时包清理、Job 重试和人工恢复语义；
   - 必须先在非生产 staging 主机完成真实 SSH 验证。
   - 已实现成功 Job 按 `plan_sha256 + target` 幂等返回；安装失败清理临时包；健康检查失败仅在旧 companion 已成功备份时恢复，不做无条件删除；正式 CLI/API/自然语言入口默认启用该策略。
   - P0-3 提交：`69ddc08 feat: add bootstrap rollback and idempotency`；相关回归与 Ruff 通过。
   - 仍需 staging 主机验证断网、超时、重复提交、旧版本升级和人工恢复 runbook，完成前不得进入真机。

### P0 本地开发收口

- 新增 `scripts/rolo-staging-harness.py`，可在本地隔离环境运行 bootstrap/job/package 验收矩阵并输出 JUnit 报告；
- CI package job 已加入 companion 构建、签名、验证和 Linux 可执行位门禁；
- 新增 bootstrap 输入安全检查：known_hosts 与 verification key 必须存在、非空，POSIX 下拒绝过宽权限；
- staging harness、bootstrap、Job、companion package 与安全检查回归通过；
- 集成提交：`544da6b test: add local staging harness and companion CI gate`、`27d8e79 feat: close local staging and bootstrap security gates`；
- 剩余仅为外部 staging 主机上的真实 SSH 与 runbook 演练，不属于本地代码开发阻塞。

只有上述三项全部通过 staging 验证、现场安全评审和 runbook 演练，才允许真机软件 bootstrap；真机首次操作仍仅限只读 inspect 和受控软件变更，不触发执行器动作。

<!-- status: active; authority: plan; owner: ROLO maintainers; last_reviewed: 2026-08-29; source_of_truth: docs/reference/ENGINEERING_STATUS.md -->

# 后续开发整合与真机验证 RUNBOOK

本文给出 R5 合入后的唯一推荐推进顺序：先固定可复现基线，再按小切片整合后续开发，最后
在 WSL、固定 Linux/ROS 目标和物理机器人上逐级取证。本文不重新定义 Contract、Schema、
安全策略或 release authority；冲突时以代码门禁、版本化 Schema、
[工程状态台账](../reference/ENGINEERING_STATUS.md) 和
[最高开发准则](../architecture/DEVELOPMENT_PRINCIPLES.md) 为准。

## 1. 当前结论与范围

`codex/registry-redesign-r5` 当前已具备：Registry v2、Agent-native 只读 shadow/canary
通道、Stage Runner、真实 `DiagnosisEpisode`/`VerificationEvidencePackage v2` contract、
profile 绑定的 `local-target` Linux/ROS provider、handoff materializer 和插件 manifest。

当前证据最高为固定 WSL/Linux/ROS 软件目标 `E3`，不是物理机器人闭环 `E4`。以下事实
必须保持分离：

- native gate `PASS` 只证明受控观测健康，不授予 release authority；
- WSL 上的真实 ROS 工作负载不是物理机器人 acceptance；
- middleware 的 environment-limited 超时可保持 release-neutral，但必须保留原因和证据；
- fake/replay、单次 shadow 或单次 canary rehearsal 都不能支持 `active`；
- HW USB、写操作、导航、校准、reset、actuator、power 和 firmware 不在首轮 canary 范围。

## 2. 合入基线

### 2.1 分支顺序

1. 将 `codex/registry-redesign-r5` 与最新默认分支合并并通过本节全部门禁；
2. 以合入后的默认分支创建新的 `codex/post-r5-integration` 集成分支；
3. 对 `codex/p1-real-three-stage` 只做按功能切片的语义移植，不做整分支盲合并；
4. 每个切片独立提交，必须同时更新状态台账、实现地图、Schema、测试和本 RUNBOOK 的
   完成标记；
5. 任何切片门禁失败时停止后续移植，保留上一提交作为可回退点。

每次进入下一阶段前记录：

```bash
git rev-parse HEAD
git status --short
git log -1 --format='%H %cI %s'
```

要求工作树干净，报告中的 revision 与部署到目标机的 revision 完全一致。

当前可供真机验证的已推送基线为 `origin/codex/post-r5-integration` @
`918fea1a2fffd49e1977cf7b0a913268cc0a7c7b`。部署前必须重新执行
`git fetch origin`、`git rev-parse origin/codex/post-r5-integration`，并把输出写入
`revision.txt`；若远端 revision 变化，则停止本轮部署并重新生成整包证据。

### 2.2 合入门禁

```bash
uv sync --frozen
export ROLO_ADAPTER_MAX_PROCESSES=512
uv run python scripts/check_docs.py
uv run python -m rolo.cli tool contract validate --registry-version v2
uv run python scripts/validate_registry_migration.py
uv run pytest -q
```

通过条件：

- 文档治理、链接、状态台账路径检查全部通过；
- deterministic regression report 为 0 项；
- tracked Schema 与 export 集合、内容摘要完全一致；
- handoff materializer、真实目标 contract、插件 manifest 测试通过；
- v1 兼容面未删除，v2 与 Native family 没有混入同一权威集合；
- 无未解决冲突、未跟踪生成物或工作区本地配置进入提交。

## 3. 剩余开发项与完成定义

按优先级执行；前一项没有满足完成定义时，不开始依赖它的真机放量。

| ID | 优先级 | 开发项 | 完成定义 | 真机前门禁 |
|---|---|---|---|---|
| DEV-01 | P0 | 三阶段实现收敛 | 对并行分支的 Episode capture、Verify target provider/materializer、provenance、evidence package 和 run recovery 做字段级对照；选定一个 canonical producer/consumer，删除重复实现前提供迁移测试 | 同一输入只生成一种 Schema/version，tracked/export 一致，旧 handoff 要么兼容要么明确拒绝 |
| DEV-02 | P0 | Agent handoff 可信重试 | 为模型输出的 `files[].sha256` 过期/不匹配提供受信的重新冻结、同 workspace 有界重试或可恢复失败协议；不得放宽 digest 校验 | 注入 stale digest 必须 fail-closed；重试后仍由 Rolo 重新计算并绑定全部文件摘要 |
| DEV-03 | P0 | 目标身份与部署供应链 | 将 profile、machine-id、workspace inode/ctime、ROS domain/RMW 与 approved deployment、SSH host-key/签名和采集 nonce 统一绑定 | 任一身份、签名、host-key、workspace 或 revision 漂移都在执行前拒绝 |
| DEV-04 | P1 | 物理 Episode capture | 把固定六阶段 Episode 接到真实机器人只读采集，冻结 baseline/observe/hypothesis/change/smoke/decision 与 provenance | 每窗口唯一 immutable Episode；缺阶段、乱序、hash 漂移或假数据不得 `COMPLETE` |
| DEV-05 | P1 | 真实 Verify provider/oracle | 整合 bounded case provider、materializer、readiness/health、replay capture 和人工批准计划 | case 与 evidence 一一对应；safe-stop/rollback 明确；未知或变异 operation 执行前拒绝 |
| DEV-06 | P1 | Native canary 选择与观察 | 增加并验证精确 robot/run/family allowlist、review packet 和可解释的 eligibility 分类 | 至少 10 个成功 canary 窗口，零高严重度 parity、零 silent drop，报告达到 `READY_FOR_REVIEW` |
| DEV-07 | P1 | 取消、租约和目标中断恢复 | 将 cancel、heartbeat、stale recovery、幂等和并发锁覆盖真实 provider 进程与重启 | kill/reboot/超时注入后只能 `CANCELLED`/`FAILED`，不能提升旧 handoff |
| DEV-08 | P2 | 跨平台/中间件矩阵 | 覆盖实际目标使用的 OS、ROS 发行版和 RMW；明确网络、DDS 和代理环境限制 | 每个支持组合有固定 profile、重现命令和证据包；未知组合保持 experimental |
| DEV-09 | P2 | Registry 退役准备 | 统计 v1 wrapper 消费者、回退演练和兼容窗口；形成单独人工评审 | 在 canary 稳定和消费者迁移前不删除 v1 wrapper/contract/audit 材料 |

### 3.1 并行分支整合规则

`codex/p1-real-three-stage` 与本分支都修改 Stage Runner、Diagnose/Verify handoff、Schema 和
Provider 边界。整合 DEV-01 时至少对照：

- 本分支：`src/rolo/stages/real_target.py`、`src/rolo/stages/diagnose/episode.py`、
  `src/rolo/stages/plugin_manifest.py`、`tests/test_real_target_contracts.py`；
- 并行分支：Episode capture、Verify target provider/materializer、target provenance、
  readiness/health、用户身份/session ticket、run cleanup/recovery 和插件示例；
- 共同修改面：`agent_runner.py`、`downstream.py`、`handoffs.py`、Verify service/acceptance、
  API/CLI、artifact layout 和 `schemas/`。

每次只移植一个 producer/consumer 闭环。先写兼容/拒绝测试，再移植实现，最后重新导出
Schema；禁止同时保留名称相同但字段或 authority 不同的 evidence package。

字段级归属和 P1 Verify provider 的暂缓合入结论记录在
[R5 canonical ownership 审计](../review/POST_R5_CANONICAL_OWNERSHIP_AUDIT.md)。

## 4. 开发—验证循环

每个 DEV 切片均执行以下顺序：

1. **Contract review**：明确输入、输出、身份、hash、authority、失败关闭和回退；
2. **本地测试**：成功、拒绝、tamper、超时/取消和旧版本兼容至少各一条；
3. **WSL rehearsal**：使用真实 ROS 工作负载而非 `rolo_p2_validation_fixture`；
4. **固定目标 E3**：连续 3～5 个 shadow 窗口，随后只读精确 selector canary；
5. **物理目标 E4**：执行真实 Episode 与批准的 Verify case，不扩大操作范围；
6. **人工评审**：检查 evidence、provenance、回退和负面样本后才更新成熟度；
7. **合入**：一个切片一个提交，报告 HEAD、命令、证据路径、hash 和未解决边界。

任何阶段失败，只修复当前切片并从本地门禁重新开始，不沿用失败提交生成的 artifact。

当前 DEV-01 已落地首个窄切片 `target inspection Episode capture`（提交 `4ae7e42`）：
它只生成 `METADATA_ONLY`、`UNVERIFIED`、不可变 Episode，不改变 release authority；后续
Verify provider/materializer 仍需与本分支 canonical producer 做字段级对照后再接入。

DEV-03 的首个身份边界切片已在独立分支实现：`user_identity.py` 持久化当前本地 session，
Stage Agent 授权恢复继续要求完全匹配当前用户、session、stage、provider、executor、plan
和输入摘要；声明了错误 stage 的插件在创建时拒绝。该切片不改变 canonical real-target 或
evidence v2 authority，合入前须通过成功、跨用户、跨 session、provider 越界和伪造 session
测试。

HTTP 控制面现通过 `GET /v1/session` 签发短时 HttpOnly `rolo_session` ticket；rolo-vis
启动或刷新时先取该 ticket。任何带 `authorization_ref` 的恢复请求必须通过当前用户和
持久 session 的 HMAC 校验，不能再用可伪造的明文 session header；缺失、篡改或过期均应
返回 403。真机验证需记录 `/v1/session` 的 session_id 与批准请求使用同一 artifact root。

当前还增加了 provider boundary 拒绝 fixture（`tests/test_post_r5_provider_boundary.py`）：
P1 v1 evidence/provenance 和缺少显式 safe-stop/rollback 的 payload 均必须 fail-closed。

下一条 adapter 切片已实现于 `src/rolo/stages/verify/legacy_adapter.py`：只有 plan digest、
canonical target provenance artifact/hash 和显式安全结果均匹配时，才允许把 P1 v1
payload 写成 main v2 evidence；它尚未接管 SSH provider 的实际执行。

SSH provenance collector 已补齐（`src/rolo/stages/verify/ssh_provenance.py`），但尚未接入
P1 provider；在真实目标上仍须验证 pinned host-key、远端身份字段和中断恢复后，才可进入
provider execution 切片。

SSH bounded provider execution 已在 `src/rolo/stages/verify/ssh_target_provider.py` 完成
软件闭环：固定三个只读 case → legacy source artifact → canonical v2 evidence。下一步仍
需在 pinned SSH 目标上做真实 timeout/cancel/并发锁注入，并接入 Verify handoff。

Verify handoff 接入已完成：`materialize_handoff()` 会重新验证 v2 evidence，并通过
`commit_verification_handoff` 绑定 Diagnose handoff；没有上游 Diagnose handoff 时必须
保持拒绝，不得单独制造 Verify latest handoff。

Provider 可靠性回归已补齐：`tests/test_ssh_provider_recovery.py` 注入 timeout、运行中
cancel、并发锁和 stale-lock 恢复。下一阶段须在 pinned SSH 目标复现同样故障，并记录
进程中断/重启后的 artifact、handoff 和回退结果。

DEV-07 的首个兼容切片已落地：`recover_all_stale_stage_runs` 与
`maintain_stage_runtime` 扫描选定 Stage/robot 的运行记录，在重启后将超出租约的
`RUNNING` 运行安全置为 `FAILED`，并清理指向终态/缺失运行的 stale `active-run.json`。
该切片保留既有精确 stage/robot recovery API，维护过程不恢复 executor、不重放目标操作，
测试覆盖跨 Stage 扫描、heartbeat 活跃保护、孤儿 marker、幂等重复运行。

## 5. WSL / 固定 Linux ROS rehearsal

目标命令和故障分类以
[目标机 P2 验证](TARGET_MACHINE_P2_VALIDATION.md) 与
[Diagnose/Verify 调试手册](TARGET_MACHINE_DIAGNOSE_VERIFY_DEBUG.md) 为准。

### 5.1 环境与基线

```bash
git pull --ff-only origin <integration-branch>
git rev-parse HEAD
uv sync --frozen
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=50
export ROS_LOCALHOST_ONLY=1
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROLO_ADAPTER_MAX_PROCESSES=512

ros2 doctor --report
ros2 node list
ros2 topic list
ros2 service list
ros2 topic echo /tf --once
```

记录实际 ROS/RMW、代理、进程预算和工作负载启动方式。`ros2 doctor --report` 必须进入
证据包；`/tf` 或 middleware 超时只有在明确分类为 environment-limited 且不影响预定 case
时才不阻断 native gate。

### 5.2 连续 shadow

```bash
export ADAPT_NATIVE_TOOL_MODE=shadow
export ADAPT_NATIVE_TOOL_ROBOT_IDS=<robot-id>
unset ADAPT_NATIVE_TOOL_RUN_IDS

uv run robotctl adapt run --robot <robot-id>
```

在相同 revision/profile/工作负载下连续执行 3～5 个窗口。每个窗口必须同时满足：

- deterministic regression 0 项，Schema tracked/export 完全一致；
- native gate 为 `PASS`，`blocking_reasons=[]`；
- parity 无高严重度 `DIFF`、未知 provider、歧义或 silent drop；
- rollout/summary/gate/call artifact 的 robot/run/session/catalog digest 一致；
- middleware environment-limited 只计入环境限制且 `influences_release=false`；
- Canonical eligibility、Bundle、Catalog 和 release 未被 shadow 改变。

### 5.3 Diagnose 与 Verify rehearsal

```bash
export CODING_AGENT_PROVIDER=local-target
export CODING_AGENT_EXECUTOR=local-target

uv run rolo target profile init "$PWD" --robot <robot-id>
uv run robotctl diagnose plan --robot <robot-id>
uv run robotctl diagnose run --robot <robot-id>
uv run robotctl diagnose run --robot <robot-id> --confirm --authorization-ref <artifact://...>

uv run robotctl verify acceptance-plan --robot <robot-id> \
  --plan-file <approved-plan.json> --confirm
uv run robotctl verify run --robot <robot-id>
uv run robotctl verify run --robot <robot-id> --confirm --authorization-ref <artifact://...>
```

无确认运行必须停在 `WAITING_FOR_AUTH`。确认后，Diagnose 必须生成唯一且完整的真实 Episode；
Verify 必须只执行批准的 bounded read-only case，并生成 provenance 绑定的 evidence package。

### 5.4 精确 native canary

只有连续 shadow 全部通过后才执行：

```bash
export ADAPT_NATIVE_TOOL_MODE=canary
export ADAPT_NATIVE_TOOL_ROBOT_IDS=<robot-id>
export ADAPT_NATIVE_TOOL_RUN_IDS=<exact-run-id>
uv run robotctl adapt run --robot <robot-id>
```

首轮只允许 Linux/ROS inspect/list/echo-once 类只读 family。canary 仍必须
`influences_release=false`，且 Canonical 路径始终可用。执行后恢复：

```bash
export ADAPT_NATIVE_TOOL_MODE=off
unset ADAPT_NATIVE_TOOL_RUN_IDS
```

Native canary 与 Operation Slice canary 是不同通道。若 `slice-observability` 报告
`SLICE_OUTSIDE_ELIGIBILITY` 或 `MINIMUM_SUCCESSFUL_CANARY_RUNS_NOT_MET`，不得把一次 native
canary 成功解释为 Slice 已可放量；完成 DEV-06 并累计至少 10 个成功 Slice canary 后再评审。

## 6. 物理真机 E4 验证

物理目标必须使用与报告一致的不可变提交和 approved deployment。按以下顺序执行：

1. 验证 SSH host key/签名、target fingerprint、workspace、OS user、ROS domain/RMW 和代码
   revision；
2. 启动真实机器人工作负载，记录安全观察者、急停/回退责任人和允许的只读 operation；
3. 采集 `ros2 doctor --report`、ROS graph、TF 和预批准目标状态；
4. 连续运行 3～5 个 native shadow 窗口；
5. 运行真实 Diagnose Episode，change 阶段首轮只能为 `NO_CHANGE`；
6. 发布经人工批准且摘要绑定的 Verify plan，执行 bounded read-only case；
7. 仅对精确 robot/run/family 做低流量 canary rehearsal；
8. 验证取消、进程中断、profile/host-key/hash 漂移和 mode `off` 回退；
9. 汇总正负样本与 SHA256，由人工签署 GO/HOLD/NO-GO。

首轮 E4 不授权写操作。需要写操作时必须另建安全评审、风险分析、safe-stop 和 rollback
演练，不得通过扩展现有只读 allowlist 偷渡。

## 7. 证据包

每个窗口保存：

```text
revision.txt
environment.txt
ros2-doctor-report.txt
native-tool-rollout.json
native-tool-summary.json
native-tool-gate.json
native-tool-execution-parity.json
context_metrics.json
diagnose/<robot>/latest/handoff.json
verify/<robot>/latest/handoff.json
SHA256SUMS
validation-report.md
```

`validation-report.md` 至少记录：目标身份、revision、Provider/executor、执行命令、窗口 ID、
Gate/Stage 结论、environment-limited 项、负面注入、回退结果和未解决问题。打包前执行：

```bash
find <evidence-root> -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
sha256sum -c SHA256SUMS
```

不得打包凭据、私有源码、未脱敏环境变量、无关进程参数或 USB 原始日志。

## 8. GO / HOLD / NO-GO

### GO（只进入下一灰度级别）

- 所有本地合入门禁通过；
- 3～5 个连续 shadow 窗口全部 `PASS`；
- 真实 Episode、Verify evidence、provenance 和所有摘要绑定有效；
- canary 精确命中批准 selector，Canonical 回退已演练；
- 无高严重度 parity、未知 provider、歧义、silent drop 或未解释环境失败；
- 对应 DEV 完成定义满足并经人工评审。

### HOLD（修复后从门禁重新开始）

- stale digest、Schema/export 漂移、handoff/materializer 失败；
- 样本不足、Slice eligibility 不满足或观察报告不是 `READY_FOR_REVIEW`；
- 可解释但尚未修复的 middleware/代理/RMW 环境限制；
- physical target、approved deployment 或人工安全责任人未就绪。

### NO-GO（立即关闭灰度）

- 身份、签名、host-key、provenance 或 artifact hash 不匹配；
- 未批准 operation 被执行、出现 mutation 或 release authority 被 native/fake 影响；
- 高严重度 parity、silent drop、错误 handoff 被提升或取消/回退失效；
- 无法把失败明确归类为代码、数据、Provider 或环境问题。

## 9. 回退

运行态优先关闭灰度，不删除证据：

```bash
export ADAPT_NATIVE_TOOL_MODE=off
unset ADAPT_NATIVE_TOOL_RUN_IDS
unset ADAPT_NATIVE_TOOL_ROBOT_IDS
```

代码回退使用可审计的 `git revert <slice-commit>`，不重写共享历史。保留失败窗口、摘要和
SHA256，用新的 revision/profile 重新生成 artifact；不得复用旧 catalog digest 或手工修补
handoff。Registry v1 wrapper、Contract 和审计材料在 DEV-09 人工批准前始终保留。

## 10. 合入与真机前检查表

- [ ] 默认分支已合入 R5，工作树干净，revision 已记录；
- [ ] DEV-01 的并行实现差异表和 canonical ownership 已评审；
- [ ] 全量测试、文档、Registry、迁移、Schema/export 和 handoff 门禁通过；
- [ ] WSL 使用真实 ROS 工作负载完成 3～5 个 shadow 窗口；
- [ ] native gate 持续 `PASS`，middleware 仅有可解释 environment-limited；
- [ ] Diagnose Episode 与 Verify evidence/provenance 完整；
- [ ] 精确 selector canary 与 mode `off` 回退已演练；
- [ ] Slice canary 至少 10 个成功窗口并达到 `READY_FOR_REVIEW`，或明确保持 HOLD；
- [ ] 物理目标部署、身份、人工安全责任和批准 operation 已冻结；
- [ ] evidence pack 的 SHA256 校验通过，敏感信息已脱敏；
- [ ] GO/HOLD/NO-GO 由人工签署，文档与工程状态台账同步。

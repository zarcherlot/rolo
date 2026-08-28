# R5 之后 P0–P2 产品化与真实闭环开发计划

状态：准备启动

本计划建立在 Registry Operation 双轨设计和 `c81cc43` 已合入 `main` 的基础上。Registry
真实目标机 shadow 仍在进行中，因此本计划不预设 shadow 已通过；在运行数据和人工评审
完成前，Registry canary/retirement 保持冻结。CLI、harness、目标机自举和真实机器人
Verify 可以与 shadow 并行开发，但不得把未完成的 shadow 结果当作 release 依据。

## 1. 总目标

形成以下可交付闭环：

```text
rolo / rolo run / MCP / rolo-vis
            |
   same-user authorization
            |
 Codex / Claude / plugin harness
            |
 Adapt -> Diagnose -> Verify
            |
 target bootstrap + evidence + acceptance
            |
 Rolo-owned gate and release
```

约束保持不变：Agent 不拥有 release authority；Agent-native Tool 不自动成为
`VERIFIED`；目标机 mutation、写操作、敏感数据和物理动作始终经过独立的 Rolo policy。

## 2. 阶段总览

| 阶段 | 目标 | 主要产物 | 门禁 |
|---|---|---|---|
| P0 | 真实可用与安全上线 | 远端 Adapt、bootstrap 供应链、认证模型、CLI/harness acceptance | 无未审计 mutation；真实 Codex smoke 通过 |
| P1 | 真实三阶段闭环 | plugin kit、真实 Episode、机器人 Verify provider、run recovery | Adapt→Diagnose→Verify 在至少一个目标上闭环 |
| P2 | 产品化与规模运维 | rolo-vis 正式版、API/MCP 稳定化、CI/CD、Registry canary/retirement | 可回滚、可观测、可发布、可升级 |

P0 的子项可以并行；P1 依赖 P0 的授权和 artifact 语义；P2 的 Registry canary/retirement
依赖真实 shadow 数据、人工评审和 P0/P1 的回滚能力。在此之前只允许生成 review packet，
不允许切换默认模式或删除 wrapper。

## 3. P0：真实可用与安全上线

### P0.1 统一远端 Adapt 产品路径

目标：让完成 bootstrap 的 SSH 目标可以从产品 CLI 使用，而不需要切换到专家命令。

交付：

- `rolo adapt ssh://... --known-hosts ...` 复用现有 target evidence deployment；
- target inspect、bootstrap plan、approval、execute 与 Adapt 使用同一 target identity；
- 远端 workspace、collector、SSH port、identity file 均 digest/pin；
- 本地路径和 SSH 路径共用同一 Adapt journey/result schema；
- 旧 `robotctl adapt start --evidence-mode remote` 保持兼容 alias。

验收：无 pinned host key、无 companion、deployment 变更或 workspace 不可读时均明确
`BLOCKED`，不启动 Agent、不写 target。

### P0.2 Companion 发布与供应链

交付：

- Linux `x86_64`/`aarch64` 正式构建矩阵；
- 签名 manifest、公开验证 key、key rotation/revocation；
- 版本兼容窗口、幂等升级和失败回滚；
- offline package、SBOM、可复现构建；
- CI 中加入 manifest/package/signature/health smoke。

验收：篡改包、错误版本、过期签名、错误 target、重复执行和 health failure 都必须
在 mutation 前或回滚路径中失败关闭。

### P0.3 生产身份与授权

交付：

- rolo-vis 使用 authenticated same-user session，而不只依赖静态 bearer token；
- authorization request 绑定 OS/user/session、stage、robot、provider、executor、
  model、plan digest、task digest 和 expiry；
- scope、CSRF、rate limit、审计 actor、过期清理；
- TLS/reverse-proxy 部署规范；
- API/MCP/CLI 共用同一授权判定。

验收：跨用户、跨 robot、跨 stage、跨 plan、重复 request、过期 request 和 token scope
错误均不能执行。

### P0.4 CLI 与 harness acceptance

交付：

- `rolo run`、`rolo adapt`、`rolo diagnose`、`rolo verify` 的端到端 CLI smoke；
- Codex 登录/未登录、API key env、provider/base URL、timeout、streaming 测试；
- `AGENTS.md` 创建、不覆盖、临时 workspace 清理；
- console、MCP、HTTP、rolo-vis 恢复同一 Stage run 的 acceptance；
- 无 ROS、无网络、无管理员权限时的可解释降级。

验收：console 只负责交互，所有 mutation 仍由 canonical service 和 Rolo gate 决定。

## 4. P1：真实三阶段闭环

### P1.1 第三方 Agent 插件开发包

交付：

- `rolo.harnesses` 和 `rolo.agent_executors` 的正式模板；
- Claude Code reference adapter；
- provider/model/key/install/auth callback contract；
- plugin manifest、版本兼容和卸载流程；
- conformance kit 与最小 fake provider。

验收：不修改 lifecycle、handoff、release 代码即可接入一个外部 executor；插件失败只能
导致该 run 失败，不能污染其他 robot 或 release。

### P1.2 真实 Diagnosis Episode

交付：

- target-side episode collector；
- observation bundle、clock sync、source provenance；
- Diagnosis report 与 immutable Episode 的一一绑定；
- 将 `UNVERIFIED_AGENT_OBSERVATION` 与真实 runtime episode 明确区分；
- 真实目标机上 baseline→observe→hypothesis→change→smoke→decision 闭环。

验收：没有真实 episode 时只能保持 `INCONCLUSIVE` 或 unverified，不得伪装成物理证明。

### P1.3 机器人 Verify/Acceptance Provider

交付：

- 至少一个真实机器人 provider；
- 状态、传感器、应用行为和安全前置条件；
- bounded case、oracle、timeout、cancel、safe stop/rollback；
- regression report、evidence package 和 target provenance；
- 真实失败分类与可重复回放。

验收：Verify 只有在 case/evidence 满足独立 contract 时才可 COMPLETE；Agent prose 不得
直接提升为 VERIFIED。

### P1.4 Stage run 恢复与并发治理

交付：

- RUNNING 崩溃恢复和 stale run 处理；
- robot/stage 并发锁；
- idempotency key、cancellation API；
- authorization request 过期归档；
- stdout/stderr 大日志分页、压缩和 retention；
- workspace GC。

验收：进程崩溃、网络断开、重复点击、重复提交和并发 run 都保持单次、可审计和可恢复。

## 5. P2：产品化与规模运维

### P2.1 rolo-vis 正式版

- 自动刷新或 SSE/WebSocket；
- run 状态、事件、artifact/evidence 分栏查看；
- bootstrap plan/approval 页面；
- 多 robot、错误、过期和权限状态；
- 无障碍、移动端和国际化基础；
- 前端版本、静态资源完整性和部署文档。

### P2.2 API/MCP 稳定化

- OpenAPI/API versioning；
- 统一错误码和分页模型；
- Stage event streaming；
- MCP tool schema version；
- client SDK 与迁移指南；
- backward compatibility contract。

### P2.3 CI/CD 与跨平台矩阵

- Python 3.10–3.13；
- Linux x86_64/aarch64、WSL2、Windows 本地只读；
- SSH remote Linux；
- 无 ROS、无网络、无 Codex 登录、代理网络；
- package/signature/SBOM/reproducible build；
- release-check、schema drift、Registry digest drift 强制门禁。

### P2.4 Registry canary 与 retirement

Registry 真实 shadow 仍在运行，完成后再执行：

1. 收齐连续 shadow 窗口并完成 parity/安全审查；
2. 选低风险 Linux/ROS 只读 family 进入 canary；
3. 根据真实窗口统计成功率、延迟、误裁剪、parity 和安全拒绝；
4. 人工评审并记录决策；
5. legacy ledger 逐项从 `SHADOW` 推进 `CANARY`；
6. 稳定后逐项推进 `RETIRED`；
7. 最后删除冗余 wrapper，保留旧 release 的审计读取能力。

禁止一次性删除 73 个 legacy operation，也禁止让 shadow 结果直接改变 release eligibility。

## 6. 并行开发矩阵

| 工作流 | 负责范围 | 依赖 | 推荐分支 |
|---|---|---|---|
| A | 远端 Adapt + companion supply chain | 当前 target bootstrap | `codex/product-remote-adapt` |
| B | 认证、授权、run recovery | 当前 Stage Agent runner/API | `codex/stage-auth-production` |
| C | Harness/plugin kit + CLI acceptance | 当前 harness SPI | `codex/harness-plugin-kit` |
| D | Episode/Verify provider | P0 授权和 artifact contract | `codex/real-stage-acceptance` |
| E | rolo-vis/API/CI 产品化 | B、C | `codex/rolo-vis-product` |
| F | Registry canary/retirement | shadow 数据 + D 回滚能力 | `codex/registry-canary-retirement` |

每个工作流都必须先写 characterization/negative tests，再修改生产代码；不得在同一个
分支同时改变 Registry 语义、授权模型和真实机器人动作。

## 7. 第一轮启动切片（建议现在开始）

第一轮不做大规模 UI 重写，先完成最小可验收闭环：

1. **A-1**：让 `rolo adapt ssh://...` 复用已批准的 remote deployment；
2. **B-1**：增加 authenticated same-user authorization 的接口草案和负向测试；
3. **C-1**：发布 harness/plugin template，并用 fake harness 跑 CLI/MCP/HTTP 同构测试；
4. **D-1**：选定一个真实机器人 Verify provider，冻结 case/evidence contract；
5. **F-1**：跟踪目标机 shadow，生成低风险 family 的 canary review packet（不切换 canary）。

第一轮完成条件：

- 至少一个远端目标可由产品入口完成 inspect→bootstrap→adapt；
- 至少一个 Stage run 可由 console 创建、由 rolo-vis 恢复；
- 一个外部 harness 可通过插件接口运行 fake stage；
- 一个真实 Verify case 能产生独立 evidence；
- 一个 Registry family 具备基于完整 shadow 窗口的人工 canary 决策材料；
- 全量测试、Schema drift、Registry digest 和安全负向测试均通过。

## 8. 不纳入本轮的事项

- 不在 Rolo 核心内绑定某一家第三方 Agent；
- 不自动把 Registry shadow/canary 结果提升为 release authority；
- 不在没有真实 safety review 的情况下实现 actuator/power/firmware/calibration 自动化；
- 不因 Operation 数量目标而删除仍被旧 release 使用的审计材料；
- 不把“CLI 能运行”当作真实机器人 acceptance 的替代品。

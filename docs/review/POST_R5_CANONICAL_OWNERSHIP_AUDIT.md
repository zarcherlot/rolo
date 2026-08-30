<!-- status: frozen; authority: reference; owner: ROLO maintainers; last_reviewed: 2026-08-30; source_of_truth: docs/reference/ENGINEERING_STATUS.md -->

# R5 合入后的 canonical ownership 审计

## 审计范围

本审计保留 P1 迁移期间的字段归属快照；当前实现状态以最新 `main`、工程状态台账和实现地图
为准，不再把历史暂缓结论当作当前代码状态。本审计对照以下 revision：

- R5/main：`origin/main@2b82ac1`（当前复核基线）
- P1：`origin/codex/p1-real-three-stage@f48b772`（历史比较对象）

审计重点是 Episode capture、target provenance、Verify provider、materializer 和
evidence package 的字段、Schema version、artifact 绑定与 handoff authority。

## 结论

| 能力 | canonical owner | P1 对应实现 | 决策 |
|---|---|---|---|
| 本地 Linux/ROS 目标身份与只读命令 | `src/rolo/stages/real_target.py` 的 `TargetBinding`、`LocalTargetCommandRunner` | P1 无等价实现 | 保留 main；作为首轮 E3/E4 的唯一 local-target producer |
| Episode 与 provenance | `src/rolo/stages/diagnose/episode.py` 的 `DiagnosisEpisode`、`TargetProvenance v1/v2` | `src/rolo/episode_capture.py` | Episode capture 已以窄切片接入；继续复用 main 的 v2 provenance 和 publication 校验 |
| Verify plan/oracle/replay | `src/rolo/stages/verify/acceptance.py` 的 `VerificationPlan`、`VerificationEvidencePackage v2` | P1 acceptance 扩展了 provider manifest 与 provider evidence index | main contract 保持权威；P1 扩展只能以兼容字段/API 形式移植 |
| SSH readiness/health provider | `src/rolo/stages/verify/ssh_provenance.py`、`ssh_target_provider.py` 的 canonical v2 provider | P1 的 SSH 专用 provider/manifest（历史比较对象） | 已合入 main；`rolo target verify-health` 提供有界只读入口，仍不等同于物理 E4 acceptance |
| Provider evidence materializer | `src/rolo/stages/handoffs.py` 与 `src/rolo/stages/verify/ssh_target_provider.py` | P1 provider evidence index（历史比较对象） | 已通过 v2 evidence 和 Diagnose handoff validator；保留单向 adapter，不维护第二套 authority |

## 不可直接合并的证据

P1 的 Verify 实现引入了与 main 不同的 authority 边界：

1. `VerificationTargetProvenance` 是 SSH 专用结构，包含 `host`、`known_hosts_sha256`
   和 `expected_companion`；main 已用 `TargetProvenance v2` 绑定 target binding artifact、
   collector session 和时钟信息。两者不是字段重命名关系。
2. P1 `VerificationEvidencePackage` 的 Schema 是
   `rolo-verification-evidence-package/v1`，main 的权威包是
   `rolo-verification-evidence/v2`，且 v2 要求 case results、safe-stop、rollback 与
   provenance hash。直接保留两套 package 会让同一 Verify run 产生两种 authority。
3. P1 `VerificationProviderManifest`/`VerificationProviderEvidenceIndex` 约束 provider
   operation 和 index digest；main 当前 acceptance contract 没有这组独立 v1 类型。
   必须先决定以 v2 contract 扩展 manifest，还是在 v2 外部建立明确的 adapter boundary。
4. 从 main 向 P1 做整分支 merge 会在 15 个共同修改路径产生冲突，包含 acceptance、
   handoffs、agent runner、target provider、两个 Schema 和测试；这证明整分支合并不是
   可审计的移植方式。

## 当前剩余验证门禁

历史 P1 payload 仍不得直接成为 authority；当前 main 的后续验证必须同时具备：

- 一个把 SSH host-key、workspace、user 和 machine/session 信息映射到
  `TargetProvenance v2`/`TargetBinding` 的明确 adapter；禁止把 credential 或未经批准的
  host identity 写入 evidence；
- 一组 fixture，分别证明旧 P1 package 被明确拒绝、或经过单向、可验证的 v1→v2 转换；
- case operation、evidence、provenance 和 handoff 的一一对应测试，覆盖 hash tamper、
  timeout、cancel 和未知 operation fail-closed；
- Schema export、tracked schema、文档台账和真机 runbook 同步更新。

在这些门禁完成前，SSH provider 只能声明固定软件目标的 E3/有界只读能力，不得宣称物理
目标 E4 或通用 acceptance oracle 已完成。

## 当前已落地切片

`codex/post-r5-integration` 已落地 `4ae7e42`（target inspection Episode capture）及
`7b943d2`（文档与状态登记）。该切片只生成 `METADATA_ONLY`、`UNVERIFIED` 的不可变
Episode，不改变 release authority，可作为后续 provider adapter 的输入边界。

本轮边界测试已落地在 `tests/test_post_r5_provider_boundary.py`：P1 v1 evidence package、
SSH 专用 provenance 以及缺失 safe-stop/rollback 的 v2 package 都会被 main contract
明确拒绝。它们不是迁移完成的证明，而是防止误合入的回归门禁。

本切片新增 `src/rolo/stages/verify/legacy_adapter.py` 和
`tests/test_legacy_provider_adapter.py`。adapter 只接受带有匹配 plan digest 的 P1 v1
payload，并强制调用方提供已发布且 hash 匹配的 main provenance artifact；inline SSH
provenance 不会被复制进 v2 package，safe-stop/rollback 也必须显式传入。

随后新增 `src/rolo/stages/verify/ssh_provenance.py`：通过 pinned SSH transport 读取
workspace stat、machine-id、user/uid 和 ROS/RMW 环境，生成 main `TargetBinding` artifact。
该 collector 不执行 shell、不写目标机，也不把 known-hosts 或凭据复制进 provenance；
当前 main 的 `ssh_target_provider.py` 已接入该 collector，并可产出经 adapter 校验的 v2
evidence；剩余工作是固定 SSH 目标上的真实验证。

当前切片已新增 `src/rolo/stages/verify/ssh_target_provider.py`：它复用 collector，执行
固定的 platform/workspace/companion 三个只读 case，先保留 legacy v1 source artifact，
再经 adapter 生成 main v2 evidence，并通过 `materialize_handoff()` 接入 canonical Stage
handoff；该 provider 仍未宣称物理目标 E4 或 release readiness。

当前 provider 已提供 `materialize_handoff()`：先重新验证 v2 evidence，再将 canonical
regression report 和 evidence package 交给 `commit_verification_handoff`；缺少上游
Diagnose handoff 时仍由既有 validator 拒绝。

可靠性回归门禁位于 `tests/test_ssh_provider_recovery.py`，覆盖 timeout、运行中 cancel、
并发锁拒绝和 stale-lock 恢复；这些测试仍是 fake transport 证据，不替代固定 SSH 目标验证。

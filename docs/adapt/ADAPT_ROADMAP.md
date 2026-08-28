<!-- status: active; authority: plan; owner: docs maintainers; last_reviewed: 2026-08-28 -->

# Adapt 路线图

状态：`active`
权威级别：开发路线与阶段状态（不替代运行契约、Schema 或验收门禁）

本文是 Adapt 相关计划的唯一当前入口。它只保留当前阶段、下一阶段和完成条件；历史计划
保存在 [`archive/plans/`](../archive/plans/)，用于追溯，不作为当前实施依据。

## 当前基线

- P0–P2 的 Operation 治理、Target Operation Slice、分页 workset 和平台无关 Capability SPI
  已集成；
- P3 的 shadow、Provider Conformance 和稳定观察能力已落地，native tool 默认仍保持关闭；
- 当前 294 项 Registry、Linux/ROS eligibility、Bundle、Catalog、policy 和 release 行为保持
  v1 兼容；
- 真实目标机 shadow、canary 窗口和人工评审完成前，不改变 release authority。

## 当前工作流

1. **目标证据**：只接受签名、目标绑定且新鲜的 Hardware/Linux/ROS/CLI 证据；
2. **Discovery 与 Slice**：生成有界候选和面向 Agent 的最小上下文；
3. **Shadow**：比较 Canonical Registry 与 Agent-native Tool 结果，但不影响现有 eligibility；
4. **Conformance**：Provider 和生成 Adapter 通过独立门禁后，才可进入 release；
5. **Canary 与回退**：按 robot/run allowlist 灰度，异常时自动回到 v1 权威路径。

## 下一阶段门槛

- 真实目标机 shadow 有足够样本，且差异已完成人工分类；
- native tool 的安全边界、超时、输出限额、脱敏和审计证据稳定；
- v1/v2 Registry 的身份、digest、兼容窗口和回退路径可重复验证；
- Provider-neutral Conformance Kit 能覆盖新增 Provider，不扩大 Agent 权限；
- canary 期间所有失败都能保持 fail-closed，并保留可审计 artifact。

## 历史计划

- [跨 OS/Middleware 能力与上下文治理开发计划](../archive/plans/ADAPT_CAPABILITY_DEVELOPMENT_PLAN.md)
- [P3 Adapt 平台无关能力链路硬化计划](../archive/plans/P3_ADAPT_HARDENING_PLAN.md)
- [R5 之后产品化与真实闭环计划](../archive/plans/POST_R5_PRODUCTIZATION_PLAN.md)
- [Registry 双轨重设计 Worktree 合并计划](../archive/plans/REGISTRY_OPERATION_WORKTREE_PLAN.md)

以上文档保留原始细节和当时的分支/提交上下文；如果与本文冲突，以本文和代码、Schema、测试
为准。

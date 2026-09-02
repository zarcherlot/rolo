<!-- status: active; authority: normative; owner: rolo maintainers; last_reviewed: 2026-09-02 -->

# Rolo v2 阶段词汇

Rolo v2 的产品主链路使用三个阶段名称：

| v2 名称 | 当前职责 | 现状 |
|---|---|---|
| **Probe** | enrollment、目标证据、inspect CLI、Native Tool Session 和 ToolPlan | 当前唯一重点实现 |
| **Trace** | 后续诊断、调参与过程追踪 | 仅保留兼容入口，暂不扩展 |
| **Certify** | 后续验收、回归和发布证明 | 仅保留兼容入口，暂不扩展 |

旧名称 `Adapt / Diagnose / Verify` 不再注册为 v2 用户命令，也不作为新 API 名称。
正在删除的旧模块路径只允许作为迁移期间的内部实现细节：

```text
adapt    -> probe
diagnose -> trace
verify   -> certify
```

Probe 的最小闭环是：

```text
SSH target enrollment
  -> pinned Credential/HostKey
  -> TargetEvidenceBundle
  -> NativeToolSession
  -> Agent ToolPlan
  -> independent Conformance
```

Trace 和 Certify 在本轮重构中不增加业务实现，也不参与 Probe 的可信性判断。它们
未来的入口不能绕过 Probe 的 target identity、evidence、session、allowlist 和 digest
校验。

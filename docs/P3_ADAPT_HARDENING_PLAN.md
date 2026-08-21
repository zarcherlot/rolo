# P3 Adapt 平台无关能力链路硬化计划

## 目标

P3 将 P0-P2 已建立的治理、上下文裁剪和 Capability SPI 接入可观测的 Shadow
运行链路，同时保持当前 294 Operation、Linux/ROS、Bundle、Catalog、policy 和 release
行为不变。

P3 不开发 Windows、FreeRTOS、CyberRT 或其他具体 OS/Middleware Provider。

## P3.0 基线保护门禁

- 固定 Operation 数量、治理台账数量、Contract Catalog digest；
- 固定完整 Registry digest；
- 固定 Operation ID、layer、contract version 和 contract SHA 身份 digest；
- Schema canonical export 必须与 tracked schemas 一致；
- Registry 或治理数据发生漂移时测试失败并报告漂移字段。

状态：首批实现已完成。

## P3.1 Shadow 链路闭环

每次真实 Adapt Agent Run 持久化：

- `target-operation-slice.json`；
- `target-operation-slice-shadow.json`；
- `platform-profile.json`；
- `capability-resolution-shadow.json`；
- 扩展后的 `context_metrics.json`。

Shadow Artifact 必须满足：

- `influences_release=false`；
- 当前 `eligible_operations` 仍是唯一执行和 Bundle 权威来源；
- 没有 Provider 时返回 `UNAVAILABLE`，不得导致 Adapt Run 失败；
- Platform Profile 只从现有 Discovery 派生通用事实，不执行平台命令；
- 记录 authoritative eligibility 与 shadow target-adapter 的双向差异；
- 记录 `RESOLVED / UNAVAILABLE / AMBIGUOUS` 数量。

状态：首批实现已完成，等待持续运行数据验证。

## P3.2 Provider 扩展宿主

- Provider 注册、发现、卸载和唯一 ID 校验；
- Manifest/Schema/版本兼容验证；
- 超时、取消和错误隔离；
- evidence 标准化；
- write capability 统一接入 Runtime policy；
- 空 Provider、未知 Provider、能力缺失均为正常状态。

状态：首批实现已完成。ProviderHost 当前保持与 Active Tool Catalog 和 release 解耦；
写能力默认拒绝，只有显式注入 Runtime policy authorizer 后才能调用 Provider。

## P3.3 Conformance Kit

- Fake Provider 开发模板；
- provider-neutral conformance runner；
- 无 service、无 filesystem、RTOS-like、channel-only 场景；
- Provider 冲突、超时、未知扩展和 policy 拒绝测试；
- Provider 开发与版本兼容指南。

状态：已完成首版。包含安全的结构化 Conformance Runner、Fake Provider 模板、严格报告
Schema，以及 service-less、filesystem-less、RTOS-like、channel-only、冲突、超时、未知
扩展和写策略 fail-closed 测试。Conformance 结果不影响 release。

## P3.4 Slice 灰度激活准备

- 增加默认关闭的功能开关；
- 支持按 Robot/Run 灰度；
- 比较旧 Plan 与 Slice Plan；
- 建立误裁剪、依赖缺失和预算超限告警；
- 提供即时回退到当前 eligibility 的机制。

是否正式激活必须基于 Shadow 数据单独决策，不属于当前首批实现。

## 当前基线影响

| 项目 | P3 首批影响 |
|---|---|
| Registry Operation | 保持 294 |
| Operation ID/layer/contract | 不变 |
| Linux/ROS | 不重构、不改变 |
| Bundle/Catalog/release | 不变 |
| Agent 执行 Operation | 继续由当前 eligibility 决定 |
| Artifact | 新增平台无关 Shadow 观察结果 |
| Provider | 默认空集合，不实现具体平台 |

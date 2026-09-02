<!-- status: draft; authority: plan; owner: rolo maintainers; last_reviewed: 2026-09-02 -->

# Rolo v2 最小代码范围

本文是第一次真机切片前的代码裁剪清单。它不把“文件少”当成目标，而以能否完成
`初始化 -> 受控 inspect -> Evidence -> Tool Session -> Conformance -> release` 为准。

## 必须保留（第一真机切片）

- `rolo.core`：配置、artifact、hash、持久化和基础模型；
- `rolo.agent_tools`：family Tool descriptor、Session、Broker、bounded runner；
- `rolo.targets`：本地/远程目标连接、身份、签名和只读 transport；
- `stages.adapt` 中的 enrollment、target evidence、hardware/OS/Middleware discovery、route、
  fingerprint、minimal models、conformance、release/runtime binding；
- `adapter_runtime.py`、`adapter_runner.py`、`runtime_context.py`、`invocation_policy.py`；
- 最小 CLI 入口：初始化、目标证据、inspect Tool、Tool Session、Conformance 状态；
- 当前 Agent 消费 Tool 的路径。

第一真机切片只覆盖低风险只读能力：OS host/process/resource、Middleware graph/node/topic、
hardware inventory/status。任何 write、运动、敏感资源和复杂 vendor adapter 都不属于
第一切片的通过条件。

## 进入“适配缺口”而非默认主路径

- Adapter Agent 编码、Bundle freeze、独立 Gate：只在 Rolo 已确认存在窄 gap 时启用；
- provider-specific adapter：只随真实目标和明确证据加入。

## 暂不进入 v2 核心闭环

以下历史能力不属于 v2 默认初始化路径，也不应阻塞第一真机切片：

- Wiki narrative/insight/diff/retrieval 全套；
- heuristic discovery planning、proposal orchestration 和 mapping Agent；
- target-operation-slice shadow/canary 观测；
- 历史 Registry、旧 lifecycle 和迁移报告；
- Web/Workbench 展示层、fleet/read-model 扩展和测试专用 fake provider；
- Diagnose/Verify 的高级回放、SSH 故障矩阵和非首轮证据投影。

## 删除原则

1. 先确认没有被第一切片入口或 runtime 导入；
2. 先把真实目标所需的最小路径跑通，再逐批删除历史代码；
3. 每批删除都必须有 import smoke、CLI smoke 和真机只读回归；
4. 历史 artifact 只读审计需要的 schema/loader 不与运行时路径混在一起；
5. 任何删除不得通过放宽权限、跳过 evidence 或绕过 Conformance 来换取“更短”。

## 当前审计结论

本 worktree 已完成第一轮 v2 裁剪：默认入口只依赖 Profile、Connector、Evidence、Tool
Session、ToolPlan 和 Conformance；历史模块即使保留在仓库，也不进入收集和测试路径。后续
扩展只新增可独立验证的 OS/Middleware/provider 或窄 Adapter，不恢复全量 Registry。

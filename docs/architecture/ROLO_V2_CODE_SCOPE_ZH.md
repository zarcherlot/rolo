<!-- status: draft-v2; authority: implementation scope; owner: rolo maintainers -->

# Rolo v2 最小代码范围

本文是第一次真机切片前的代码裁剪清单。它不把“文件少”当成目标，而以能否完成
`初始化 -> 受控 inspect -> Evidence -> Tool Session -> Conformance -> release` 为准。

## 必须保留（第一真机切片）

- `rolo.core`：配置、artifact、hash、持久化和基础模型；
- `rolo.agent_tools`：family Tool descriptor、Session、Broker、bounded runner；
- `rolo.targets`：本地/远程目标连接、身份、签名和只读 transport；
- `stages.adapt` 中的 enrollment、target evidence、hardware/linux/ros discovery、route、
  fingerprint、minimal models、conformance、release/runtime binding；
- `adapter_runtime.py`、`adapter_runner.py`、`runtime_context.py`、`invocation_policy.py`；
- 最小 CLI/MCP 入口：初始化、目标证据、inspect Tool、Tool Session、release 状态；
- Diagnose/Verify 的最小 handoff 和 Agent 消费 Tool 的路径。

第一真机切片只覆盖低风险只读能力：Linux host/process/resource、ROS graph/node/topic、
hardware inventory/status。任何 write、运动、敏感资源和复杂 vendor adapter 都不属于
第一切片的通过条件。

## 进入“适配缺口”而非默认主路径

- Adapter Agent 编码、Bundle freeze、独立 Gate：只在 Rolo 已确认存在窄 gap 时启用；
- `operation_registry_v2.py`：只作为 Canonical/Native/Provider 投影视图，不再驱动全量
  Linux/ROS 只读 wrapper；
- provider-specific adapter：只随真实目标和明确证据加入。

## 暂不进入 v2 核心闭环

以下能力可以保留在兼容目录，但不应阻塞第一真机切片，也不应进入默认初始化路径：

- Wiki narrative/insight/diff/retrieval 全套；
- heuristic discovery planning、proposal orchestration 和 mapping Agent；
- target-operation-slice shadow/canary 观测；
- 历史 v1 compatibility wrapper、旧 registry projection 和迁移报告；
- Web/Workbench 展示层、fleet/read-model 扩展和测试专用 fake provider；
- Diagnose/Verify 的高级回放、SSH 故障矩阵和非首轮证据投影。

## 删除原则

1. 先确认没有被第一切片入口、runtime 或 handoff 导入；
2. 先把真实目标所需的最小路径跑通，再逐批删除兼容代码；
3. 每批删除都必须有 import smoke、CLI smoke 和真机只读回归；
4. v1 artifact 只读审计需要的 schema/loader 不与运行时路径混在一起；
5. 任何删除不得通过放宽权限、跳过 evidence 或绕过 Conformance 来换取“更短”。

## 当前审计结论

当前仓库仍把许多历史 Adapt 能力作为默认依赖：`discovery.py` 顶层依赖 heuristic、Wiki、
proposal 和 software relevance 模块，CLI 和 schema export 也会拉入 shadow/read-model
扩展。因此不能在未重构入口前直接 `git rm` 大批文件；那会破坏现有 import 图，也无法证明
真机路径仍然可运行。

本 worktree 的下一步是先把最小 Tool Session/inspect 路径从这些可选模块中解耦，再按上面的
“暂不进入”清单分批删除。这样“极大幅度删减”是可验证的架构裁剪，而不是一次不可诊断的
大面积删库。

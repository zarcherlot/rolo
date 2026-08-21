# TargetOperationSlice 灰度说明

## 目标

Slice Canary 用于验证 Adapt Agent 是否可以只聚焦 `TARGET_ADAPTER` Operation，同时避免
误裁剪改变现有 Bundle、Catalog 和 release 契约。

灰度只改变 Compact Plan 中的编码焦点。以下集合始终保持原 eligibility：

- workspace inspection 的 `current-task`；
- Agent 最终 Bundle Operation 集合；
- 独立 conformance gate；
- Active Tool Catalog；
- release authority。

## 默认状态

默认配置：

```text
ADAPT_OPERATION_SLICE_MODE=shadow
ADAPT_OPERATION_SLICE_ROBOT_IDS=
ADAPT_OPERATION_SLICE_RUN_IDS=
ADAPT_OPERATION_SLICE_MAX_OPERATIONS=20
```

Shadow 模式生成决策、告警和差异 Artifact，但不改变 Agent 上下文。

## 灰度方式

### 单次运行

```text
robotctl adapt run --robot ROBOT_ID --slice-canary
```

该参数只选择本次新生成的 Adapt Run，不改变持久配置。

### Robot allowlist

```text
ADAPT_OPERATION_SLICE_MODE=canary
ADAPT_OPERATION_SLICE_ROBOT_IDS=robot-a,robot-b
```

Robot ID 使用去空后的精确匹配，不支持通配符。

### Run allowlist

```text
ADAPT_OPERATION_SLICE_MODE=canary
ADAPT_OPERATION_SLICE_RUN_IDS=RUN_ID
```

Run ID 同样使用精确匹配。程序化调用可以在已知 Run ID 时使用；命令行单次灰度建议使用
`--slice-canary`。

## 自动回退

以下情况阻止激活并立即回退到原 eligibility：

- Slice 包含不在 authoritative eligibility 中的 Operation；
- 当前 eligibility 非空但 Slice 为空；
- Slice 超过配置的 Operation 预算。

Slice 排除部分 eligible Operation 会产生 `ELIGIBLE_NOT_IN_SLICE` Warning，但不会改变
Bundle 权威集合；这是减少 Agent 编码焦点的预期灰度行为。

## Artifact 与遥测

每次真实 Agent Run 新增：

```text
slice-activation-decision.json
```

其 Schema 为 `robot-target-operation-slice-activation/v1`，包含：

- mode、selected、selected_by；
- outcome：`SHADOW_ONLY / NOT_SELECTED / ACTIVATED / FALLBACK`；
- authoritative、requested 和 effective Operation 集合；
- release authority 集合；
- 告警与 fallback reason；
- `affects_agent_context`；
- 固定的 `influences_release=false`。

`context_metrics.json` 同步记录激活模式、结果、是否影响上下文、告警数量和回退原因。

## 回退操作

出现异常时执行任一操作即可恢复原行为：

- 移除命令行 `--slice-canary`；
- 将 `ADAPT_OPERATION_SLICE_MODE` 改回 `shadow`；
- 从 Robot/Run allowlist 移除选择项。

不需要修改 Registry、Bundle、Catalog 或既有 release。

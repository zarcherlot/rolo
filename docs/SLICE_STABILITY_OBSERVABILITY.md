# Slice 稳定观察与人工评审

## 目标

稳定观察阶段使用真实 Adapt Run 已保存的 Artifact 评估 Shadow/Canary 表现，但不自动修改
激活模式、allowlist、Registry、Bundle、Catalog 或 release。

## 只读命令

```text
robotctl adapt slice-observability \
  --robot ROBOT_ID \
  --max-runs 50 \
  --min-successful-canary-runs 10
```

命令只读取：

- `slice-activation-decision.json`；
- `context_metrics.json`；
- `run.json`；
- `gate.json`。

它不会创建、更新或删除 Artifact。没有 Slice 决策文件的旧 Run 会被忽略。

## 观察指标

每个 Run 记录：

- mode、outcome、selected 和是否影响 Agent context；
- authoritative、requested、effective Operation 数量；
- 潜在和实际上下文缩减比例；
- Agent Run 状态；
- 独立 gate 状态；
- Prompt token 估算；
- Boot context token 估算与预算；
- Slice 告警和回退原因。

聚合报告记录：

- 样本数和 Canary 选择数；
- 激活、回退、成功 Canary 数量；
- Agent/gate 失败数量；
- 上下文预算超限数量；
- outcome 和 alert 分布；
- 平均潜在/实际缩减比例。

## 建议状态

### `INSUFFICIENT_DATA`

在没有回退、失败或预算问题的前提下，独立 gate 通过的成功 Canary 数量尚未达到配置
门槛。继续保持当前 Shadow/Canary 范围。

### `HOLD`

窗口内出现任一情况：

- Canary 自动回退；
- Adapter Agent 失败或超时；
- 独立 gate 失败；
- Boot context 超预算。

`HOLD` 不会自动撤销现有配置，操作者应停止扩大灰度并检查对应 Run Artifact。

### `READY_FOR_REVIEW`

成功 Canary 数量达到门槛，且窗口内没有上述阻断项。该状态仅表示可以进入人工评审，
不表示系统会自动扩大 allowlist 或将 Canary 设为默认。

## 人工评审清单

进入 `READY_FOR_REVIEW` 后仍需人工确认：

1. `ELIGIBLE_NOT_IN_SLICE` 是否均符合治理台账预期；
2. Bundle Operation 集合是否始终通过独立 gate；
3. 上下文缩减是否具有稳定收益；
4. Agent 是否增加额外 inspect 或产生不必要重试；
5. 机器人类型和 Discovery 证据是否具有代表性；
6. 回退到 `shadow` 的操作是否已验证。

## 当前边界

- 不自动变更 `ADAPT_OPERATION_SLICE_MODE`；
- 不自动维护 Robot/Run allowlist；
- 不把报告作为 release gate；
- 不以成功样本替代真实 OS/Middleware 产品化验证；
- 不实现任何具体平台 Provider。

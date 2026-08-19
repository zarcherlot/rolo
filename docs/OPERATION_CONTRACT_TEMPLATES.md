# Operation Contract 模板

本文给出与契约编译器门禁一致的最小模板。示例字段不是注释性建议：缺少对应机器字段时，
`robotctl tool contract validate` 会拒绝契约。新契约以 `1.1.0` 为当前基线；已有契约按
语义版本规则独立演进。

## R0 有界观测

```yaml
schema_version: robot-operation-contract/v1
contract_id: domain.resource.status
version: 1.1.0
lifecycle: GATEABLE
operation: domain.resource.status
layer: app
description: Read bounded resource state without changing it.
data_classification: INTERNAL
result_semantics: OBSERVATION
observation_overhead: BOUNDED
risk: R0
access: read
idempotent: true
cancelable: false
max_duration_s: 10
canonical_cli:
  [robotctl, tool, invoke, "{operation}", --robot, "{robot_id}", --input, "{input_json}"]
input_schema:
  type: object
  properties: {}
  additionalProperties: false
output_schema:
  type: object
  properties:
    status: {type: string}
    observed_at: {type: string}
  required: [status, observed_at]
  additionalProperties: false
error_codes: [UNAVAILABLE, TIMEOUT, OPERATION_FAILED]
retry_policy: bounded_exponential_backoff
```

## R1 高负载读取

R1 read 只适用于不改变目标持久状态、但会产生明显探测流量或观测负载的 operation。

```yaml
result_semantics: OBSERVATION
observation_overhead: ELEVATED
risk: R1
access: read
side_effects: [Generates bounded probe traffic on the selected bus.]
resource_locks: [hardware_bus_scan]
rate_limit: one scan per bus per 30 seconds
```

`ELEVATED`、非空 `side_effects` 和非 `on_demand` 的 `rate_limit` 缺一不可；read 不允许
R2/R3。

## R1 有界流式观测

短时 sample/watch/follow 不允许依赖进程超时隐式截断，必须声明 `BOUNDED_STREAM`，输入
同时要求 `duration_s`、`max_items` 和 `max_bytes` 的正数上下界，输出要求 `status`、
`observed_at`、`truncated` 以及 `items` 或 `artifact_ref`：

```yaml
execution_mode: BOUNDED_STREAM
result_semantics: OBSERVATION
observation_overhead: ELEVATED
risk: R1
access: read
cancelable: true
max_duration_s: 35
side_effects: [Creates a temporary subscription and consumes host resources.]
rate_limit: one active observer per resource
input_schema:
  type: object
  properties:
    duration_s: {type: number, minimum: 0.1, maximum: 30}
    max_items: {type: integer, minimum: 1, maximum: 1000}
    max_bytes: {type: integer, minimum: 1024, maximum: 1000000}
  required: [duration_s, max_items, max_bytes]
  additionalProperties: false
output_schema:
  type: object
  properties:
    status: {type: string}
    observed_at: {type: string}
    truncated: {type: boolean}
    items: {type: array, items: {type: object, properties: {}, additionalProperties: true}}
  required: [status, observed_at, truncated, items]
  additionalProperties: false
```

长期流使用互为配对的 `SESSION_START` / `SESSION_STOP`。start 必须限制 `ttl_s` 和
`max_bytes` 并返回 `session_id`、`expires_at`；stop 必须接收并回显 `session_id`。二者均为
write，因为它们创建或关闭 runtime session，但 Adapt 只验证 acknowledgement/handle，
不宣称流内容正确。

## R3 写操作

```yaml
data_classification: INTERNAL
result_semantics: ACKNOWLEDGEMENT_ONLY
observation_overhead: BOUNDED
risk: R3
access: write
idempotent: false
cancelable: false
preconditions:
  - Explicit authorization exists.
  - The target watchdog and safety route are active.
postconditions:
  - Only request acknowledgement is asserted in Adapt.
side_effects:
  - May cause physical motion.
resource_locks: [robot_motion]
error_codes:
  [UNAVAILABLE, TIMEOUT, INVALID_INPUT, NOT_AUTHORIZED, PRECONDITION_FAILED,
   OPERATION_FAILED]
output_schema:
  type: object
  properties:
    status: {type: string}
  required: [status]
  additionalProperties: false
```

R1/R2 write 在 runtime 还必须匹配受保护策略中的 OS 身份和精确 operation 白名单。R3
不能由该静态白名单放行，必须由管理员所有的外部授权提供器返回与单次 request、robot、
operation、输入 SHA-256 和不超过五分钟 expiry 绑定的能力。契约中的 `preconditions` 不能
替代这一运行时门禁。

Adapt 对该模板只验证 schema、binding 和 route。`status=SUCCEEDED` 只能表示请求通路返回了
接受响应，不能证明动作完成、结果正确、可靠性或安全性。

## SENSITIVE 数据

```yaml
data_classification: SENSITIVE
```

SENSITIVE 必须传播到 Registry、Tool Catalog 和契约摘要，不得复制进 Adapter Agent 摘要、
普通日志或无关产物。通用 operation 禁止声明 `SECRET`。Runtime 默认拒绝 SENSITIVE，
只有受保护 OS 身份策略可放行并写入无 payload 审计。文件、配置和日志还必须匹配受保护
内容资源规则；详见 [SENSITIVE_INVOCATION_POLICY.md](SENSITIVE_INVOCATION_POLICY.md)。

## 流式读取

流式契约采用已确认的混合模型：

- `sample`、`watch`、`follow`、`rate`、`bandwidth` 使用带 duration、item 和 byte 上限的
  有界采样；
- 真正持续流由 `stream.start` 返回 session handle，并由配对的 `stream.stop` 关闭；
- 普通 Tool Invoke 不承载无限输出。

有界流和 session 字段会进入契约摘要、Registry、Tool Catalog 与 conformance 比较；缺失
边界或配对关系时不能成为 `VERIFIED`。

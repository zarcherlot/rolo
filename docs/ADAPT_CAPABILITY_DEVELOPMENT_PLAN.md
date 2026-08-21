# Adapt 跨 OS/Middleware 能力与上下文治理开发计划

## 1. 总体原则

当前只建设跨 OS/Middleware 的抽象能力和扩展接口，不开发 Windows、FreeRTOS、
CyberRT 等具体 Provider，也不重写现有 Linux/ROS 实现。平台适配留到正式产品化阶段。

本计划的目标是控制当前开发规模，同时避免未来架构被 Linux/ROS 锁死。

## 2. 当前阶段目标与边界

本阶段只完成三件事：

1. 缩小 Adapt Agent 上下文和实际工作集；
2. 建立与具体 OS/Middleware 无关的能力模型；
3. 保持当前 294 Operation、Linux/ROS 行为、Bundle、Catalog 和 release 完全兼容。

本阶段明确不做：

- Windows Provider；
- FreeRTOS Provider；
- CyberRT Provider；
- Linux 到 OS 的实际 Operation 改名；
- ROS 到 Middleware 的实际 Operation 改名；
- 删除当前 294 Operation；
- 新 OS/Middleware 的真实设备验证；
- 双 Catalog 正式切换；
- 现有 Linux/ROS 实现重构。

## 3. P0：Operation 治理台账

### 3.1 建立 294 Operation 分类清单

新增独立治理文件，不修改当前 Registry。示例：

```yaml
operation: linux.process.list
semantic_layer: os
execution_class: AGENT_NATIVE
future_capability: os.workload.list
migration_status: PLANNED
current_registry_action: KEEP
```

分类清单包含：

```text
current_operation
current_layer
semantic_layer
execution_class
portable_semantics
future_capability
migration_status
migration_reason
current_registry_action
```

`execution_class` 取值：

```text
AGENT_NATIVE
PRODUCT_BUILTIN
TARGET_ADAPTER
PLATFORM_SPECIFIC
```

### 3.2 P0 基线影响

- 不改变 Registry digest；
- 不改变 294 数量；
- 不改变现有 CLI 和运行时；
- 为 Operation Slice 提供确定性筛选依据。

### 3.3 P0 交付物

- Operation 分类清单及 Schema；
- 清单完整性和引用有效性校验；
- 294 项全覆盖测试；
- 分类原则和迁移理由文档。

## 4. P1：Adapt Agent 上下文优化

### 4.1 新增 `TargetOperationSlice`

从当前 Registry、Discovery 和分类台账生成目标工作集：

```json
{
  "robot_id": "...",
  "discovery_id": "...",
  "registry_sha256": "...",
  "primary_operations": [],
  "dependency_operations": [],
  "agent_native_operations": [],
  "builtin_operations": [],
  "target_adapter_operations": [],
  "deferred_summary": {}
}
```

选择规则：

- observed candidate 作为 seed；
- 加入 eligible operation；
- 加入 paired、compensation、replacement 依赖；
- 只把 `TARGET_ADAPTER` 放入编码任务；
- `AGENT_NATIVE` 只用于发现和证据收集；
- `PRODUCT_BUILTIN` 不要求 Adapter 实现。

初期保持现有 eligibility 行为不变，Slice 以 shadow mode 生成并对比；稳定后再让 Slice
驱动 Agent Plan。

基线影响：

- 当前 Registry 仍为 294；
- Adapt Agent 实际处理的 Operation 显著减少；
- 当前 Bundle 格式不变；
- 初期不改变发布和 conformance 结果。

### 4.2 精简 Agent Snapshot

移除完整 `workset_operations` 详情，替换为：

- 全局轻量索引；
- 当前 Slice 状态；
- 当前任务完整契约；
- 非当前任务仅保留 operation、layer 和 digest。

要求：

- 不影响运行时；
- workspace-local inspection tool 同步支持新结构；
- Slice 内 Operation 可正常 `inspect`；
- Slice 外且未准备详情的 Operation 返回明确的 `NOT_IN_CURRENT_SLICE`，不得静默失败。

### 4.3 查询分页、搜索和限额

新增：

```text
operations list --scope current-task
operations list --scope target
operations list --limit 20 --cursor CURSOR
operations batch-inspect OPERATION...  # 最大 8 个
operations search QUERY
```

保留兼容入口：

```text
operations list --all
```

迁移初期旧命令默认行为不变；后续版本如需改为默认分页，必须提供迁移说明。

### 4.4 Compact Agent Plan

不再将完整 Adapt Plan 全量注入 Prompt，只注入：

- 当前任务；
- Slice ID；
- `TARGET_ADAPTER` Operation；
- deferred 聚合；
- Artifact 引用；
- 安全和交付规则。

完整 Plan 继续作为 Artifact 保存。本阶段不改变 Plan Schema 和持久化结果，只改变
Agent Prompt，并更新相应断言测试。

### 4.5 上下文预算与遥测

默认预算：

```text
Boot context                 <= 2,000 tokens
operations list 默认         20
operations list 最大         50
batch inspect 最大           8
单次查询结果                 <= 16 KiB
单任务 TARGET_ADAPTER        <= 20
```

记录：

- Prompt 大小；
- Slice 大小；
- 工具调用返回字节；
- Agent inspect 次数；
- Agent-native 与 Target-adapter 数量；
- Registry 总数变化对 Prompt 的影响。

### 4.6 P1 交付物

- `TargetOperationSlice` 模型、Schema 和构建逻辑；
- 确定性依赖闭包；
- 轻量 Agent Snapshot；
- 分页、搜索、batch inspect；
- Compact Agent Plan；
- 上下文预算和遥测；
- shadow 对比与规模回归测试。

## 5. P2：跨平台能力抽象

P2 只定义平台无关接口，不开发具体平台 Provider。

### 5.1 定义四层语义模型

目标语义层：

```text
hardware
os
middleware
application
```

本阶段不修改当前 Registry 的实际 layer：

```text
control
hw
linux
middleware
ros
app
```

采用独立外部映射：

```text
control    -> 产品控制面
hw         -> hardware
linux      -> os
middleware -> middleware
ros        -> middleware
app        -> application
```

基线影响：

- 当前 Operation ID 和 layer 保持不变；
- contract SHA 保持不变；
- Catalog digest 保持不变；
- 不触发当前 Schema MAJOR 升级。

### 5.2 定义通用 `CapabilityDescriptor`

Capability 不绑定具体 OS/Middleware：

```json
{
  "capability_id": "os.workload.inspect",
  "semantic_layer": "os",
  "version": "1.0",
  "access": "read",
  "risk": "R0",
  "input_schema": {},
  "output_schema": {},
  "constraints": [],
  "extensions": {}
}
```

首批抽象能力可以包括：

```text
os.runtime.status
os.workload.list
os.workload.inspect
os.resource.snapshot
os.log.query
os.time.status

middleware.graph.snapshot
middleware.endpoint.list
middleware.endpoint.inspect
middleware.channel.list
middleware.channel.sample
middleware.service.list
middleware.record.inspect
```

这些名称只表达抽象能力，不表示所有平台都必须支持。

新增 Schema 不进入当前 Active Tool Catalog，也不参与当前发布门禁。

### 5.3 定义 `ProviderManifest`

只定义未来 Provider 应提供的信息：

```json
{
  "provider_id": "opaque-provider-id",
  "provider_kind": "opaque-string",
  "provider_version": "...",
  "semantic_layers": ["os"],
  "capabilities": [],
  "transport": {
    "kind": "opaque-string",
    "properties": {}
  },
  "extensions": {}
}
```

设计要求：

- `provider_kind` 使用开放字符串，不建立 Windows/Linux/FreeRTOS 枚举；
- `transport.kind` 使用开放字符串；
- 平台特有数据进入受控 `extensions`；
- Core 不依赖具体命令、SDK 或平台路径；
- 未知 Provider 和 capability 缺失是正常状态。

### 5.4 定义 `PlatformProfile`

Platform Profile 只描述事实，不包含平台执行代码：

```json
{
  "profile_id": "...",
  "os": {
    "family": "opaque-string",
    "version": null,
    "features": []
  },
  "middleware": [],
  "available_transports": [],
  "extensions": {}
}
```

本阶段可从当前 Discovery 生成最低限度 profile，但不要求准确识别 Windows、FreeRTOS
或 CyberRT。

必须继续保留：

```text
linux.json
ros.json
probes["linux"]
probes["ros"]
```

### 5.5 定义 Provider SPI

只建立协议和类型：

```python
class CapabilityProvider:
    def probe(self) -> ProviderManifest: ...
    def capabilities(self) -> list[CapabilityDescriptor]: ...
    def inspect(self, request: InspectRequest) -> InspectResult: ...
    def invoke(self, request: InvokeRequest) -> InvokeResult: ...
```

要求：

- 所有方法允许返回 `UNAVAILABLE`；
- capability 缺失是正常状态；
- Provider 自己负责平台连接；
- Core 不执行平台特定命令；
- 写操作仍必须经过 Runtime policy；
- Provider 输出必须携带版本和 evidence；
- 当前 Linux/ROS 实现不要求迁入 SPI。

### 5.6 定义 `CapabilityResolver`

输入：

```text
目标语义 Operation
Platform Profile
Provider Manifest
Discovery evidence
```

输出：

```json
{
  "status": "RESOLVED | UNAVAILABLE | AMBIGUOUS",
  "capability_id": "...",
  "provider_id": "...",
  "route_ref": "...",
  "evidence": []
}
```

本阶段只实现：

- Resolver 数据模型；
- 确定性匹配规则；
- fake provider；
- 单元测试；
- shadow 输出。

Resolver 不接入当前发布门禁，不改变当前 eligible operation 和 Active Tool Catalog。

### 5.7 P2 交付物

- 四层外部语义映射；
- `CapabilityDescriptor`；
- `ProviderManifest`；
- `PlatformProfile`；
- Provider SPI；
- `CapabilityResolver`；
- fake provider fixtures；
- shadow resolution Artifact；
- 平台无关 conformance 测试。

## 6. 测试范围

### 6.1 Fake Provider 平台无关性验证

本阶段不建立 Windows、FreeRTOS 或 CyberRT 测试环境，使用以下抽象 fixtures：

```text
full_os_provider
rtos_like_provider
service_less_provider
filesystem_less_provider
graph_middleware_provider
channel_only_middleware_provider
```

重点验证：

- 没有 service capability 时系统正常；
- 没有 filesystem 时不会生成 file Operation；
- 只有 task、没有 process 时 workload 抽象仍成立；
- 只有 channel、没有 ROS topic 时 middleware 抽象仍成立；
- 未知 Provider kind 可以被解析；
- `extensions` 不影响 Core digest。

### 6.2 当前 Linux/ROS 回归测试

只验证本轮开发没有改变现状：

- 当前 294 Operation 仍存在；
- 现有 `linux.*` CLI 继续工作；
- 现有 `ros.*` CLI 继续工作；
- 当前 Bundle 可以加载；
- 当前 release 不会意外变为 stale；
- 当前 Catalog 和策略继续生效；
- 不要求现有实现迁入新 Provider SPI。

### 6.3 Registry 规模测试

人工增加 1,000 个无关 Operation，验证：

- Agent Prompt 大小基本不变；
- `TargetOperationSlice` 不变；
- Agent Snapshot 不包含全部契约；
- 分页和输出预算生效。

## 7. 延期到产品化阶段的开发项

以下全部从当前实施范围移除。

### 7.1 OS 适配

- Windows Process/SCM/Event Log/CIM Provider；
- FreeRTOS task/runtime stats/heap Provider；
- Linux Provider 重构；
- QNX、Zephyr 等适配；
- PowerShell transport；
- serial/JTAG/RTT transport；
- 真实 OS capability conformance。

### 7.2 Middleware 适配

- ROS Provider 重构；
- CyberRT topology/channel/record Provider；
- DDS vendor Provider；
- ROS/CyberRT 消息映射；
- 真实 middleware graph normalization；
- 真实 Middleware conformance。

### 7.3 Registry 正式迁移

- `linux.*` 到 `os.*`；
- `ros.*` 到 `middleware.*`；
- `hw.*` 到 `hardware.*`；
- 删除 Control Operation；
- 删除 Agent-native Operation；
- Hardware resource family 合并；
- Application lifecycle family 合并；
- 双 Active Tool Catalog；
- Bundle Manifest v3；
- 旧 policy 和 operation alias 迁移。

### 7.4 运行时产品化

- OS Policy Gateway；
- Engineering/Admin Catalog；
- Provider 远程部署；
- Provider 身份认证；
- Provider 升级和版本协商；
- 生产设备回归矩阵；
- 跨平台安装与运维。

## 8. 版本计划

### 8.1 当前版本：上下文治理

交付：

- Operation 分类台账；
- `TargetOperationSlice`；
- 轻量 Snapshot；
- 分页、搜索、batch inspect；
- Compact Agent Plan；
- 上下文预算和遥测。

当前基线：

- 294 Operation 不变；
- Linux/ROS 不变；
- Bundle、Catalog 和 release 不变。

### 8.2 下一版本：平台无关扩展点

交付：

- 四层语义映射；
- `CapabilityDescriptor`；
- `ProviderManifest`；
- `PlatformProfile`；
- Provider SPI；
- `CapabilityResolver`；
- Fake Provider conformance；
- shadow Artifact。

当前基线：

- 继续使用现有 Linux/ROS 实现；
- 新 Provider 架构不参与生产发布；
- 不产生真实跨平台适配成本。

### 8.3 产品化版本：按市场目标选择适配

届时根据正式支持目标选择 Windows、FreeRTOS、CyberRT 或其他 OS/Middleware，再开发：

- 具体 Provider；
- 真实 transport；
- 真实 conformance；
- Registry v2；
- 双栈迁移；
- 旧 Operation 退役。

## 9. Worktree 分工与合并顺序

### 9.1 `codex/adapt-operation-governance`

目录：`C:\Users\zarch\Desktop\robot-loop-governance`

负责 P0：

- 294 Operation 分类台账；
- 分类 Schema 和校验；
- 四层外部语义映射；
- 治理文档和完整性测试。

### 9.2 `codex/adapt-context-slice`

目录：`C:\Users\zarch\Desktop\robot-loop-context`

负责 P1：

- `TargetOperationSlice`；
- 依赖闭包；
- 轻量 Snapshot；
- 分页、搜索和 batch inspect；
- Compact Agent Plan；
- 上下文预算、遥测和规模测试。

### 9.3 `codex/adapt-capability-spi`

目录：`C:\Users\zarch\Desktop\robot-loop-capabilities`

负责 P2：

- 平台无关 Capability 模型；
- Provider Manifest 和 Platform Profile；
- Provider SPI；
- Capability Resolver；
- Fake Provider 和 shadow Artifact；
- 平台无关测试。

该分支禁止实现任何具体 OS 或 Middleware Provider。

### 9.4 `codex/adapt-capability-integration`

目录：`C:\Users\zarch\Desktop\robot_loop`

负责：

- 合并和冲突处理；
- Schema export 和生成文件；
- 共享文档；
- 跨分支回归测试；
- 最终基线兼容验收。

合并顺序：

1. `codex/adapt-operation-governance`；
2. `codex/adapt-capability-spi`；
3. `codex/adapt-context-slice`；
4. 集成 Schema、文档和全量验证。

## 10. 当前基线影响总结

| 项目 | 当前阶段影响 |
|---|---|
| Registry Operation 数量 | 保持 294 |
| Operation 名称 | 不变 |
| Layer 字段 | 不变，新增外部语义映射 |
| Contract SHA | 不变 |
| Registry/Catalog digest | 不变 |
| 当前 Bundle | 完全兼容 |
| 当前 Active Release | 不失效 |
| Linux/ROS 功能 | 不重构、不改变 |
| Adapt Agent 工作量 | 显著下降 |
| Agent Prompt | 显著缩小 |
| 新 OS/Middleware 扩展能力 | 具备 Schema、SPI 和 Resolver 接口 |
| Windows/FreeRTOS/CyberRT | 本阶段不实现 |
| 产品化迁移成本 | 保留，但边界和接口提前固定 |

## 11. 最终验收标准

- 294 Operation 分类台账完整且通过校验；
- 当前 Registry 数量、Operation 名称、layer、contract SHA 和 v1 digest 均未变化；
- 当前 Bundle、Catalog、release、policy 和 Linux/ROS 行为保持兼容；
- Slice 在 shadow 阶段不影响 eligibility、conformance 和发布；
- Adapt Agent 只注入和实现有界的当前目标工作集；
- 增加 1,000 个无关 Operation 不会导致 Prompt 线性增长；
- Capability、Provider 和 Resolver 能表达无 service、无 filesystem、RTOS-like、
  channel-only 和未知 Provider 环境；
- 本轮没有新增或重构任何具体 OS/Middleware Provider。

当前开发工作集中在减少 Adapt Agent 负担和避免未来架构锁死，不提前承担多平台适配、
真实设备验证和旧 Registry 大规模迁移成本。

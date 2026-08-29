# Operation 治理台账

`operation_dispositions.yaml` 是当前 294 项 Canonical Operation 的独立治理台账。它只描述
未来责任边界和迁移方向，不参与当前 Registry、Catalog、Bundle、conformance 或运行时路由。

## 分类原则

- `AGENT_NATIVE`：Agent 可通过受授权的通用检查面收集只读证据，不要求目标 Adapter
  重复封装。
- `PRODUCT_BUILTIN`：由 Rolo 产品控制面或未来统一策略网关负责，不要求目标 Adapter
  实现。
- `TARGET_ADAPTER`：需要目标机器人提供稳定的硬件或应用语义绑定。
- `PLATFORM_SPECIFIC`：依赖具体 OS/Middleware Provider，并延期到产品化阶段。

四层语义映射独立于当前 Registry：`hw -> hardware`、`linux -> os`、
`middleware/ros -> middleware`、`app -> application`。当前 `control` 层映射到
`product_control`，明确表示它属于产品控制面而不是机器人四层之一。

## 当前处置规则

| 当前范围 | execution class | 理由 |
|---|---|---|
| `control.*` | `PRODUCT_BUILTIN` | 产品控制面由 Rolo 持有 |
| `hw.*` | `TARGET_ADAPTER` | 需要目标硬件绑定与安全验证 |
| `linux.*` 只读 | `AGENT_NATIVE` | 可由受授权的通用检查面收集证据 |
| `linux.*` 写入 | `PRODUCT_BUILTIN` | 需要统一策略、授权和审计 |
| `middleware.*` | `AGENT_NATIVE` | 当前均为只读检查能力 |
| `ros.*` 只读 | `AGENT_NATIVE` | 当前可通过 ROS 工具收集证据 |
| `ros.*` 写入 | `PLATFORM_SPECIFIC` | Provider 化和安全治理延期到产品化 |
| `app.*` | `TARGET_ADAPTER` | 保留稳定应用语义，由目标 Adapter 绑定 |

`portable_semantics` 表示语义能否在 Provider 层之外保持稳定，并不表示每个平台都必须
支持该能力。ROS TF、Action、Lifecycle 等专属概念以及 ROS 写操作被明确标为不可移植。

## 完整性约束

加载器使用严格 Pydantic Schema，并与 `canonical_operation_registry()` 做确定性比对：

- 不允许未知字段；
- 不允许重复 Operation；
- 不允许缺失或多余 Operation；
- `current_layer` 必须与当前 Registry 完全一致；
- `semantic_layer` 必须符合固定外部映射；
- 当前处置必须为 `KEEP`。

因此修改台账不会改变现有 Operation ID、layer、contract SHA 或 Registry/Catalog digest。
新增、删除或重命名 Canonical Operation 时，完整性测试会要求同步做出显式治理决定。

# Registry Operation 完整说明

## 1. 目的与边界

Registry Operation 是 Rolo 产品拥有的、跨机器人复用的规范化操作语义，例如
`linux.service.restart`、`ros.topic.info` 和 `app.task.start`。它回答的是“产品允许 Agent
表达什么意图、输入输出和安全边界是什么”，而不是“当前陌生主机上恰好安装了哪些命令”。

必须区分以下四类对象：

| 对象 | 所有者 | 含义 | 能否直接调用 |
|---|---|---|---|
| Registry Operation | 产品 | 稳定操作名称及所属层级 | 不能；它只是产品词汇 |
| Operation Contract | 产品 | 输入输出、错误、安全、版本和执行语义 | 不能；它是可校验契约 |
| Discovery Candidate | 目标机器 | probe 从二进制、文档、运行环境等证据推断出的潜在绑定 | 不能；候选不能自证正确 |
| Active Tool Catalog entry | 目标机器的 gated release | 契约、candidate、adapter 和 conformance 对齐后的运行时路由 | 只有 `AVAILABLE`/`VERIFIED` 项可进入调用流程 |

Registry 不能由陌生主机扫描结果临时生成。Discovery 可以发现“如何实现一个既有 operation”，
但不能创造产品语义；Adapter Agent 也只能实现 `GATEABLE` 或 `RELEASED` 契约，不能把
`DRAFT` 自行解释后注册。

当前 Registry 基线为 294 个 operation，全部具有明确产品契约：62 个 `RELEASED`、232 个
`GATEABLE`、0 个 `DRAFT`。产品文档按 Hardware、Linux、Middleware、
Application 四层展示；代码内部用 `control`、`hw`、`linux`、`middleware`、`ros`、`app`
六个命名空间完成路由和策略校验。完整清单见
[CANONICAL_OPERATIONS.md](CANONICAL_OPERATIONS.md)，当前契约及摘要由
[OPERATION_CONTRACTS.md](OPERATION_CONTRACTS.md) 给出。

## 2. 一份完整契约包含什么

每个非 `DRAFT` operation 必须有机器可校验的 Operation Contract。主要字段如下：

| 维度 | 字段 | 要求 |
|---|---|---|
| 身份 | `contract_id`、`operation`、`layer` | contract ID 必须等于 canonical operation |
| 演进 | `version`、`lifecycle`、`replacement_operation` | 使用语义版本；弃用项必须指向有效替代项 |
| 数据 | `input_schema`、`output_schema`、`error_codes` | 输入输出封闭、可验证；错误码有界 |
| 行为 | `access`、`result_semantics`、`execution_mode` | read/write、观察/确认/session 语义必须一致 |
| 风险 | `risk`、`data_classification` | 动作风险与数据泄露风险相互独立 |
| 运行 | `max_duration_s`、`rate_limit`、`retry_policy` | 必须有明确上限，禁止隐式无限运行 |
| 状态 | `idempotent`、`cancelable`、`compensation_operation` | 可取消写操作必须有有效补偿 operation |
| 静止 | `requires_quiescence` | R2 参数应用类操作必须取得覆盖完整调用时限的执行静止 lease |
| 安全 | `preconditions`、`postconditions`、`side_effects`、`resource_locks` | R3 四项不得为空；其他写操作也应明确声明 |
| 语义 | `semantic_units`、`coordinate_frames`、`time_semantics` | 单位、坐标系和时间来源不能由 adapter 猜测 |
| 能力 | `capability_requirements`、`canonical_cli` | 声明目标能力与唯一规范调用入口 |
| 配对 | `paired_operation` | session start/stop 必须双向配对 |
| 完整性 | 单契约 SHA-256、catalog SHA-256 | Active release 必须绑定一致的契约摘要 |

规则上的几个关键不变量：

- `read` 只能是 R0 或 R1，返回 `OBSERVATION`；`write` 返回
  `ACKNOWLEDGEMENT_ONLY`，不能把“请求已接受”描述为目标状态正确或安全。
- `SESSION_START` 返回带有效期的 `SESSION_HANDLE`，并与 `SESSION_STOP` 互相配对。
- `BOUNDED_STREAM` 必须同时限制 `duration_s`、`max_items`、`max_bytes`，允许取消，并报告
  是否截断。
- 通用 operation 禁止声明或输出 `SECRET`。
- canonical CLI 只允许使用输入 Schema 中的字段，以及 `operation`、`robot_id`、
  `input_json` 三个运行时上下文占位符。

## 3. 契约生命周期

生命周期描述“产品语义成熟度”，不是目标机器的安装或可用状态。

| 状态 | 含义 | Adapter Agent | 能否成为目标 `VERIFIED` |
|---|---|---|---|
| `DRAFT` | 只有产品词汇，契约仍不完整或语义尚未决策 | 不得实现或注册 | 否 |
| `GATEABLE` | 契约明确，可由 discovery + adapter + conformance 在目标上实现 | 可以有界实现 | 可以 |
| `RELEASED` | 产品维护的稳定跨目标语义，已有可复用实现或充分兼容性证据 | 可以使用 builtin 或 gated adapter | 可以 |
| `DEPRECATED` | 仍保留迁移兼容，但不再用于新注册 | 不得新增绑定 | 否；迁移到替代项 |

目标状态是另一条轴：`UNAVAILABLE`、`AVAILABLE`、`ROUTE_VERIFIED`、`VERIFIED`。其中
`ROUTE_VERIFIED` 仅表示目标路由存在，仍缺少 provider/schema/revision 证据，不能调用或发布为
`VERIFIED`。例如
`linux.service.restart` 可以是 `GATEABLE`，但在没有 systemd、没有 candidate 或尚未完成
adapter 门禁的主机上仍为 `UNAVAILABLE`；同一契约在另一台主机上可以是 `VERIFIED`。

因此：

```text
产品语义：Registry -> Contract lifecycle
目标实现：Discovery candidate -> Adapter bundle -> Conformance -> Active Tool Catalog
```

二者必须会合才能调用，但不能互相代替。

## 4. 升级规则

### 4.1 DRAFT -> GATEABLE

必须同时满足：

1. operation 不是已有 operation 的近义词，也不能通过既有 operation 的参数表达；
2. 意图、边界、输入、输出、错误码和 canonical CLI 已明确；
3. `risk`、`access`、数据分级、结果语义、执行模式和时限一致；
4. 写操作声明前置条件、后置条件、副作用、资源锁及必要的补偿 operation；
5. R1 读取声明 `ELEVATED` observation overhead、具体副作用和有界 rate limit；
6. R3 四个安全字段完整，并要求外部 R3 授权；
7. session 和 bounded stream 的结构性不变量全部满足；
8. 契约编译、Schema 校验和相关测试通过，生成文档与源码一致。

该升级不要求已经拥有目标真机。Linux、ROS 等跨平台语义可以提前形成 `GATEABLE` 契约；
真机决定的是 adapter 是否存在、通路是否通过门禁以及目标 availability，而不是契约能否写清楚。

### 4.2 GATEABLE -> RELEASED

满足以下任一产品条件，并完成兼容审查后才可升级：

- Rolo 自身维护的 builtin 已实现，缺少外部软件时有确定的 `UNAVAILABLE` 或降级结果；
- 同一语义已在多类目标实现中保持一致，输入输出和错误契约没有依赖单一厂商偶然行为；
- 已具备长期兼容、版本迁移、conformance 和回归验证，产品愿意承担稳定性责任。

单台目标通过 Adapt 门禁并不自动使契约 `RELEASED`。它只使该目标的 catalog entry 成为
`VERIFIED`。反过来，`RELEASED` 也不表示每台目标都具备该能力。

### 4.3 目标项升级为 VERIFIED

目标 entry 至少要满足：

1. 契约为 `GATEABLE` 或 `RELEASED`；
2. discovery 给出与 operation 对齐的 candidate 和可追溯证据；
3. builtin 或独立 adapter bundle 提供精确 route；
4. 输入输出 Schema、错误码、contract digest、release manifest 与路由一致；
5. conformance 验证 operation 存在、可路由且响应结构符合契约；
6. gated release 被原子激活后才写入 Active Tool Catalog。

Adapt 的通路门禁只证明“operation 存在并可按契约路由”，不证明动作结果正确、可靠或安全。
目标状态闭环、行为正确性和物理安全属于后续诊断与验证阶段。

## 5. 降级、回滚与移除规则

“降级”必须先区分产品契约和目标实现：

- 目标软件、驱动、设备或证据消失：将目标 entry 从 `VERIFIED` 降为 `UNAVAILABLE`，撤销
  active adapter release 或重新门禁；不修改产品契约生命周期。
- adapter 出现安全问题：立即撤销目标 release/route/authorization，并保留审计；不能靠把
  契约改回 `DRAFT` 掩盖实现缺陷。
- 产品语义发现破坏性错误：发布新的 major version，保留迁移说明；不得静默改变已发布语义。
- 语义尚未成熟：继续保持 `DRAFT`，不要为了提高数字而填充模糊契约。
- operation 已被替代：先置为 `DEPRECATED`，指定一个非 deprecated 的
  `replacement_operation`，完成调用方与 adapter 迁移后再从 Registry 移除。

禁止无说明地执行 `RELEASED -> GATEABLE` 或 `GATEABLE -> DRAFT`。若紧急安全事件要求停止
调用，应优先闭锁运行时授权和 active release；若产品承诺确实需要撤回，应以正式变更记录、
版本号和迁移路径处理。

版本号规则：

- `PATCH`：文字澄清、非语义性修正，输入输出和安全策略不变；
- `MINOR`：向后兼容地增加可选字段、错误码或能力说明；
- `MAJOR`：operation 含义、必填输入、输出语义、风险、数据分级、授权或副作用发生破坏性变化。

降低 `risk` 或 `data_classification` 不是普通兼容优化，而是扩大授权面的安全变化，必须按
major change 审查。提高风险或数据分级虽然更保守，也可能使现有调用失败，仍需明确迁移。

## 6. R0、R1、R2、R3 定义

`risk` 描述调用造成系统或物理影响的风险，不描述数据敏感度。

| 等级 | 定义 | 典型例子 | 授权与契约要求 |
|---|---|---|---|
| R0 | 低开销、无状态变更的有界观察 | 版本、状态快照、元数据 | read；有界时间和输出 |
| R1 | 高开销/主动探测观察，或不直接触发物理动作的低风险受控操作 | 总线扫描、有界 monitor | read 时必须 `ELEVATED`、声明副作用和 rate limit；若为 write 仍走写授权 |
| R2 | 改变主机、应用或非直接运动状态的操作 | service restart、map load、普通 cancel | write 默认拒绝；受保护 OS 身份 + 精确 operation 白名单 + 审计；必要时另加静止 lease |
| R3 | 直接或间接可能触发执行器、机器人运动或安全敏感行为 | task/test run、actuator command | 静态策略不得放行；必须使用单次、短时、请求绑定的外部授权能力 |

R3 包括名字看似抽象、但可能间接触发运动的 workflow，例如 `app.task.start`、
`app.test.run`、`app.regression.run`。普通 cancel 通常是 R2：它只请求中止，不能冒充
protective stop 或 emergency stop，也不能声称目标已经停止。
直接改变运动或执行器状态的普通 start、resume、pause、stop、execute、recover、home、open、
close 和 set 属于 R3。这里的普通 stop 即使最终映射为减速、保持或零速度命令，也不能降为
R2；它与 protective/emergency stop 使用不同契约和安全路径，响应仅确认命令已被接受。

R3 授权能力必须绑定随机 request、robot、operation、规范化输入 SHA-256 和到期时间，最长
五分钟。提供器必须由 root/Administrators/SYSTEM 所有且普通用户不可修改。任何超时、字段
不匹配、提供器异常或审计失败都闭锁拒绝。

`requires_quiescence=true` 只允许用于 R2 write。Runtime 必须从受保护的执行监督器取得与
request、robot、operation、输入摘要和完整调用时限绑定的 `robot_execution` lease；provider
必须在 lease 内阻止新执行启动。它证明“本次参数类变更在执行静止窗口内”，但不授权 R3
动作，也不证明参数变更后的行为正确。

## 7. 数据分级

| 分级 | 含义 | 默认策略 |
|---|---|---|
| `PUBLIC` | 可公开传播的产品版本或协议内容 | 仍受 operation 风险和目标 availability 约束 |
| `INTERNAL` | 主机、网络、ROS、硬件和机器人运行元数据 | 不等于公开；按部署策略留存 |
| `SENSITIVE` | 图像、地图、配置内容、日志、空间位置等 | runtime 默认拒绝；受保护身份策略与审计 |
| `SECRET` | 凭据、密钥、token、认证材料 | 通用 operation 禁止输出 |

正文类资源还要做资源级限制：稳定 resource ID 或受保护路径根、最大字节数和
`SENSITIVE` 声明缺一不可。正文通常返回受保护 artifact reference，不直接进入 Tool 结果或
Agent prompt。完整策略见 [SENSITIVE_INVOCATION_POLICY.md](SENSITIVE_INVOCATION_POLICY.md)。

## 8. 如何查询和使用

以下命令从仓库根目录执行；开发环境可在命令前使用 `uv run`。

### 8.1 查看产品契约

```bash
robotctl tool contract validate
robotctl tool contract show linux.service.restart
robotctl tool contract export --output docs/OPERATION_CONTRACTS.md
```

`show` 对 `DRAFT` 只展示词汇条目，不能据此生成 adapter；对 `GATEABLE`/`RELEASED` 展示
完整契约和摘要。

### 8.2 查看某个目标的工作集

```bash
robotctl adapt operations summary --robot ROBOT_ID
robotctl adapt operations list --robot ROBOT_ID
robotctl adapt operations inspect linux.service.restart --robot ROBOT_ID
```

`summary` 用于给 Adapter Agent 注入紧凑总体状态，`list` 按 applicability、implementation、
registration 筛选，`inspect` 按需取回单个 operation 的契约、candidate、注册状态和后续查询，
避免把 294 个 operation、源码和 README 全文塞入 prompt。

### 8.3 查看 Active Tool Catalog

```bash
robotctl tool catalog --robot ROBOT_ID
robotctl tool catalog --robot ROBOT_ID --layer linux
robotctl tool schema linux.service.restart --robot ROBOT_ID
```

只有 active gated release 中的 operation 会出现在目标 Tool Catalog。Catalog 是运行时路由
事实；完整 Wiki 是给人和 Agent 理解目标的证据地图，不能代替契约或 catalog。

### 8.4 调用 R2 operation

部署方先在受保护策略中精确放行 operation：

```yaml
schema_version: rolo-invocation-policy/v1
writes:
  allowed_users: [robot-operator]
  allowed_groups: [rolo-operators]
  allowed_operations: [linux.service.restart]
```

然后使用 discovery 返回的稳定资源 ID 调用：

```bash
robotctl tool invoke linux.service.restart \
  --robot ROBOT_ID \
  --input '{"resource_id":"service:robot-controller","timeout_s":30}'
```

返回值只确认 restart 请求是否被接受。调用方必须另行执行 service inspect/status，诊断阶段
再判断最终状态和行为是否正确。

### 8.5 调用 R3 operation

除 `SENSITIVE` 身份策略外，部署方必须通过 `ROLO_R3_AUTHORIZER` 配置外部授权提供器：

```bash
robotctl tool invoke app.task.start \
  --robot ROBOT_ID \
  --input '{"task_id":"task:delivery","input_set_id":"input:v1","execution_profile_id":"profile:safe","max_run_duration_s":300}'
```

Runtime 会将本次请求的身份、robot、operation 和输入摘要交给外部提供器，校验返回的短时
能力后才启动 gated adapter。CLI 参数、Agent 自述或 adapter 返回值都不能替代授权。

部署使用 `ROLO_INVOCATION_POLICY` 指定策略文件，`ROLO_INVOCATION_AUDIT_LOG` 指定审计
JSONL，`ROLO_R3_AUTHORIZER` 指定 R3 provider，`ROLO_QUIESCENCE_PROVIDER` 指定执行静止
provider。策略和 provider 的主机权限不满足要求时
调用闭锁拒绝。

## 9. 新增、修改和删除 operation

### 9.1 新增

1. 先审查现有 Registry，优先复用 operation 或增加向后兼容参数；
2. 确认它表达产品级意图，而不是某个厂商二进制的命令名；
3. 在 Registry 分组中加入唯一 operation；
4. 在对应 `src/rolo/operation_contracts/*.yaml` 编写契约；
5. 运行 contract validate、导出文档、Schema 与测试；
6. discovery 只产生候选和证据，Adapter Agent 在独立 output 工程中实现绑定；
7. 通过 conformance 后原子发布到目标 Active Tool Catalog。

### 9.2 修改

先判断是契约澄清、向后兼容扩展还是破坏性变化，再按 PATCH/MINOR/MAJOR 升级。同步更新
YAML、Schema、生成文档、策略示例、adapter conformance 和回归测试。不得只修改生成的
`OPERATION_CONTRACTS.md`。

### 9.3 弃用与删除

先提供有效替代 operation，将旧契约标记 `DEPRECATED` 并写迁移说明；停止新 candidate 和
adapter 注册；迁移现有 active release 后再从 Registry 删除。必要的 CLI 兼容别名可以暂时
保留，但不能再次出现在 Registry 或 Active Tool Catalog 中。

## 10. 审查清单

提交 Registry Operation 变更前逐项确认：

- operation 是否属于产品语义，且没有重复或近义项；
- lifecycle 与目标 availability 是否被正确区分；
- Schema 是否封闭、字段是否有单位/坐标系/时间语义及边界；
- read/write、risk、classification、result semantics 是否一致；
- R1 观察负载和流边界是否完整；
- R2 是否要求精确 write allowlist；R3 是否只能由外部短时能力放行；
- 参数应用类 R2 是否声明并实际执行 `requires_quiescence` 门禁；
- 写返回值是否仅为 ACK，状态闭环是否由独立观察 operation 完成；
- cancel、session、replacement 是否指向存在且有效的配对 operation；
- contract digest、adapter bundle、release manifest 和 Tool Catalog 是否一致；
- 文档、Schema、单元测试、conformance 和迁移记录是否同步。

## 11. 相关文档

- [CANONICAL_OPERATIONS.md](CANONICAL_OPERATIONS.md)：四层完整词汇清单；
- [OPERATION_CONTRACTS.md](OPERATION_CONTRACTS.md)：生成的当前契约清单和摘要；
- [OPERATION_CONTRACT_TEMPLATES.md](OPERATION_CONTRACT_TEMPLATES.md)：可复制契约模板；
- [OPERATION_CONTRACT_STANDARDIZATION.md](OPERATION_CONTRACT_STANDARDIZATION.md)：开放规范与行业标准演进；
- [OPERATION_TAXONOMY_AUDIT.md](OPERATION_TAXONOMY_AUDIT.md)：重复、近义和边界审计；
- [SENSITIVE_INVOCATION_POLICY.md](SENSITIVE_INVOCATION_POLICY.md)：SENSITIVE、R2/R3 运行时授权；
- [SOFTWARE_DISCOVERY.md](SOFTWARE_DISCOVERY.md)：candidate 与 probe 证据边界。

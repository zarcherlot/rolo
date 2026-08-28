<!-- status: active; authority: plan; owner: docs maintainers; last_reviewed: 2026-08-28 -->

# Registry Operation 双轨重设计与实施计划

状态：R0-R4 基础能力已落地；真实目标机 shadow 仍在进行，R5/R6 仍需 shadow 收敛、canary 运行窗口和人工评审。本文不改变当前
v1 Registry、294 项基线或旧 release；v2 Canonical、family-level Agent-native catalog、
Native Session/Broker、灰度开关和迁移校验已在 integration 分支实现，native 默认仍为
`off`。

## 1. 决策背景

当前 Registry 同时承担了四种职责：产品语义、Linux/ROS 主机探针、Adapter 路由以及
Rolo 控制面接口。这样可以形成严格的统一 Catalog，但也使大量本来可以由 Codex/Claude
Code 通过受控命令直接完成的能力，重复经过 Operation Contract、Adapter Bundle 和
Conformance。

本计划采用以下核心决策：

> Canonical Registry 只保留产品语义、安全边界、稳定下游契约和目标绑定；通用的
> Linux/ROS/部分 HW 观测能力进入 Agent-native Tool Catalog，由统一受控 Runner 直接执行。

这里的“直接执行”不是任意 shell。Agent-native Tool 仍必须经过 argv 白名单、参数边界、
超时、输出限制、环境清理、敏感信息脱敏、证据封装和审计。写操作、R2/R3、SENSITIVE
资源继续使用现有 Runtime policy、quiescence 和外部授权链路。

## 2. 目标与非目标

### 2.1 目标

- 消除只做命令转发的 Linux/ROS/HW Operation 与 Adapter wrapper；
- 保留 app、运动、硬件 mutation、workflow、敏感数据和安全控制的产品语义；
- 让 Adapt Agent 直接使用受控 Linux/ROS/HW 工具完成发现和诊断观测；
- 使 Canonical Registry 的规模由语义必要性决定，而不是由底层命令数量决定；
- 保留旧 release 的可审计性和明确的兼容窗口；
- 让新 Registry 与旧 294 项 Registry 可以 shadow 对比、灰度和回滚。

### 2.2 非目标

- 不以某个固定数量（140、170 或其他数字）作为验收目标；
- 不在本阶段开发 Windows、FreeRTOS、CyberRT 等具体 Provider；
- 不放开任意 shell、任意 Python 模块或任意网络访问；
- 不把 Agent 输出提升为 `VERIFIED` 或物理安全证明；
- 不在同一波次同时做大规模 Operation rename 和语义合并；
- 不删除旧 release 所需的 Registry/Contract 审计材料。

## 3. 目标架构

```text
                         +---------------------------+
                         | Canonical Operation       |
                         | Registry v2                |
                         | product semantics/safety  |
                         +-------------+-------------+
                                       |
                              contract/catalog/release
                                       |
+----------------------+       +-------v-------+       +----------------------+
| Agent-native Tool    |------>| Rolo policy   |<------| Provider Capability   |
| Catalog              |       | and evidence  |       | Catalog               |
| Linux/ROS/HW probes  |       | boundary      |       | platform-specific     |
+----------+-----------+       +-------+-------+       +----------------------+
           |                           |
           v                           v
    bounded argv runner          audit/artifact/evidence

                 +-------------------------------+
                 | Product Control Registry      |
                 | runtime/catalog/state/evidence|
                 +-------------------------------+
```

四个目录的职责必须分开：

| 目录 | 典型内容 | 是否进入 Canonical Registry |
|---|---|---|
| Canonical Operation Registry | app 语义、硬件 mutation、R2/R3、安全和稳定观测 | 是 |
| Agent-native Tool Catalog | `ps`、`systemctl`、`ros2 topic list`、只读设备查询 | 否 |
| Product Control Registry | runtime、Catalog、State Graph、episode、evidence | 独立维护 |
| Provider Capability Catalog | ROS/CyberRT/DDS/RTOS/厂商 Provider 能力 | 独立维护 |

## 4. Operation 处置模型

现有 `execution_class` 只描述执行归属，不足以决定是否需要产品 Operation。治理台账应增加
以下字段：

```yaml
current_operation: ros.topic.list
current_layer: ros
registry_role: AGENT_NATIVE
execution_path: ROS_CLI
downstream_contract_required: false
security_boundary_required: true
target_binding_required: false
replacement_operation: null
migration_status: SHADOW
```

`registry_role` 取值：

```text
CANONICAL
AGENT_NATIVE
PRODUCT_CONTROL
PROVIDER
LEGACY
```

`execution_path` 取值：

```text
ADAPTER
DIRECT_RUNNER
ROS_CLI
PROVIDER
INTERNAL_SERVICE
```

### 4.1 保留为 Canonical 的判断条件

一个 Operation 满足以下至少一项才进入 Canonical Registry：

1. 表达的是跨目标复用的产品意图，而不是命令名或 SDK 函数名；
2. 下游 Diagnose/Verify/Runtime 依赖稳定的输入输出、单位、坐标系或时间语义；
3. 涉及 R2/R3 写授权、quiescence、取消、补偿、急停或资源锁；
4. 需要目标硬件或应用层的稳定绑定；
5. 涉及 SENSITIVE 内容资源或受保护 artifact；
6. 需要进入 immutable release、State Graph、Tool Session 或长期审计链；
7. 是 session、workflow 或生命周期的一部分。

不满足这些条件的常规只读探针默认进入 Agent-native Tool Catalog。

### 4.2 建议的初始处置方向

**Linux：** host/process/service/container/network/resource/time 的常规只读查询优先转为
Agent-native；配置 apply/rollback、写操作、敏感文件和日志资源继续保留 Canonical。

**ROS：** graph/node/topic/service/action/parameter 的常规只读查询优先转为 Agent-native；
写操作、action cancel、bounded stream、敏感参数/TF/地图和需要稳定 schema 的数据继续保留。
底层 `ros2 topic echo` 只能是实现工具，不能重新成为 Canonical Operation。

**HW：** inventory/status/diagnostic 等标准只读查询可转为 Agent-native；actuator、power、
firmware update、calibration、reset、需要单位/校准/frame 的读取继续保留。

**Application：** base、teleop、navigation、manipulation、gripper、task、test、regression、
diagnosis、safety、calibration 和 map/parameter 变更继续以 Canonical 为主。底层 list/inspect
若仅服务于 Adapt 观测，可转为 Agent-native。

**Product Control：** `tool.catalog`、`tool.schema`、runtime、State Graph、episode、evidence、
checkpoint 不应被简单删除，而应迁入独立 Product Control Registry。

近义语义必须继续分离：teleop/base、普通 stop/safety stop、raw sensor/application sample、
status/health、plan/validate 与 execute/apply。依据见
[`archive/operations/OPERATION_TAXONOMY_AUDIT.md`](../archive/operations/OPERATION_TAXONOMY_AUDIT.md)。

## 5. Agent-native Tool 契约

Agent-native Tool 不需要为每个命令建立完整 Operation Contract，但必须有统一描述和结果
Schema：

```json
{
  "schema_version": "rolo-agent-native-tool/v1",
  "tool_id": "native.ros.topic.list",
  "family": "ros",
  "execution_path": "ROS_CLI",
  "argv_template": ["ros2", "topic", "list"],
  "access": "read",
  "risk": "R0",
  "max_duration_s": 8,
  "max_output_bytes": 200000,
  "evidence_kind": "ROS_GRAPH",
  "sensitive": false
}
```

执行结果统一为：

```json
{
  "schema_version": "rolo-agent-native-tool-result/v1",
  "tool_id": "native.ros.topic.list",
  "status": "SUCCEEDED",
  "argv": ["ros2", "topic", "list"],
  "observed_at": "...",
  "stdout_artifact": "artifact://...",
  "stderr_artifact": null,
  "truncated": false,
  "limitations": [],
  "evidence_refs": []
}
```

Tool Catalog 必须明确：允许的可执行文件、参数 schema、环境变量、工作目录、资源根、
超时、输出上限、数据分类和是否允许写入。不得接受任意 `argv` 或任意工具 ID。

## 6. Registry v1/v2 兼容策略

当前 v1 的 294 项 Registry、Contract Catalog digest 和 Adapt baseline 继续作为兼容基线。
新 v2 不能直接覆盖 v1：

- v1：旧 release 的加载、审计和兼容窗口；
- v2：新 release、新 Catalog 和新 Tool Session 的活动 Registry；
- 新 Proposal、Bundle、Tool Session 不得引用 `LEGACY` Operation；
- 旧 release 按自身绑定的 Registry/Contract digest 校验；
- v1 与 v2 的 release、Catalog、Contract 和 Tool Session 不得交叉调用；
- 迁移完成后，旧 Registry 只保留审计和明确授权的兼容用途。

当前 `registry_version`、`registry_sha256`、`contract_catalog_sha256` 机制可以复用，但解析
器必须支持按 release 绑定的 Registry，而不能永远只读取当前默认 Registry。

## 7. 分阶段实施

### R0：冻结边界和处置矩阵

- 为 294 项补充 `registry_role`、`execution_path` 和三个必要性字段；
- 生成 Canonical、Agent-native、Product Control、Provider、Legacy 五类清单；
- 为每个 Legacy 项记录替代项、原因、兼容窗口和 sunset 版本；
- 输出 Registry v2 投影 fixture，不修改 v1。

门禁：所有 294 项恰好覆盖；没有未决的安全、pair、compensation 或 replacement 引用。

### R1：实现 Agent-native Tool Runner

- 新增统一 bounded argv runner；
- 接入 Linux、ROS CLI 和首批只读 HW tool descriptors；
- 输出 evidence/artifact envelope；
- 复用现有 secret redaction、超时和审计设施；
- 不让 Agent-native Tool 直接进入现有 Active Tool Catalog。

门禁：成功、超时、不可用、输出截断、非法参数、越界路径、敏感数据和写入拒绝均有测试。

### R2：双目录 shadow

同一次 discovery 同时生成 v1 Canonical、v2 Canonical 和 Agent-native Tool 视图，比较：

- candidate/eligibility；
- 证据完整性；
- Adapter bundle 覆盖；
- Catalog/State Graph；
- Adapt Agent 任务是否仍可完成；
- 敏感和写操作是否仍闭锁。

R2 不改变 release，只产生 shadow artifacts。

### R3：迁移 release/session/runtime

- 增加按 Registry version/digest 解析的 resolver；
- 让旧 release 可按旧 Registry 验证；
- 新 release 只使用 v2 Canonical；
- 新 Tool Session 拒绝 Legacy Operation；
- 为旧 CLI 保留显式兼容 alias；
- 增加 v1/v2 交叉调用拒绝测试。

### R4：灰度切换

- 按 Robot/Run 启用 v2；
- 监控误裁剪、Agent 失败、gate 失败、直接工具失败和安全拒绝；
- 任何异常自动回退到 v1 eligibility 和 release 路径；
- 只有人工评审后才扩大范围。

### R5：删除冗余封装

在 R4 稳定后，才删除仅转发 Linux/ROS/HW 命令的 wrapper、Contract、Catalog fixture 和
conformance。旧 release 所需的 v1 contract/registry artifact 继续可审计读取。

## 8. 验收标准

### 结构

- 294 项全部有且仅有一个 role；
- Canonical 与 Agent-native 之间没有重复执行入口；
- 所有 pair、compensation、replacement 引用完整有效；
- Product Control 和 Provider 不再混入机器人 Canonical Registry。

### 行为

- Codex/Claude Code 可通过 Agent-native Tool 完成 Linux/ROS/首批 HW 只读发现；
- 不需要为每个直接命令创建 Adapter entrypoint；
- app、运动、硬件 mutation、敏感读取和 workflow 的产品契约不被弱化；
- Agent-native Tool 不能生成 `VERIFIED`、不能修改 Registry、不能绕过 Runtime policy。

### 兼容

- v1 release 可加载和审计；
- v2 release 可独立发布和调用；
- v1/v2 digest、Catalog、State Graph 和 Tool Session 不可交叉使用；
- Legacy Operation 进入新流程时返回明确迁移错误，而不是普通 unknown。

### 质量与观测

- direct-runner 的超时、输出、失败关闭和敏感策略有回归矩阵；
- shadow/canary 记录上下文缩减、直接工具成功率、误裁剪和安全拒绝；
- 文档、Schema、CLI、Catalog 和测试由同一版本生成并校验。

## 9. 首个实现切片

不应一次迁移全部 Linux/ROS/HW。建议首个纵向切片为：

```text
Linux: host status + process list/inspect + resource snapshot
ROS: graph snapshot + node/topic list/describe
HW: inventory + compute/thermal/status（只读）
保留: app.teleop.velocity、app.base.velocity、app.safety.*、app.task.*
```

首轮实现已经覆盖该切片所需的治理投影、受控 Agent-native Runner、v2 shadow 视图、版本绑定
resolver、family-level catalog、Native Session/Broker、Adapt workspace 接入和迁移报告。
Linux/ROS/HW 工具使用 `native.*` 命名空间；旧 4 项 fixed-argv catalog 仅保留兼容测试和
审计用途。后续仍需完成真实 Linux/ROS/HW 运行环境的 shadow/canary parity，并在稳定窗口后
删除冗余 wrapper。

迁移脚本同时生成 `rolo-legacy-operation-ledger/v1`：73 个旧命令形态 ID 当前处于 `SHADOW`，
各自绑定一个 family Tool；只有通过运行窗口和人工评审后，才允许逐项推进到 `CANARY`、
`RETIRED`。

首个切片跑通后，再扩展 service/container/network、参数/TF、sensor/bus 和更多诊断工具。
这样可以先验证“Agent-native Tool 能替代冗余封装”这一核心假设，而不是先进行一次大规模
Registry 重写。

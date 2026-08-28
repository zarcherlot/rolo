<!-- status: draft; authority: reference; owner: docs maintainers; last_reviewed: 2026-08-28 -->

# ROLO 白皮书

> 版本：Draft 0.2
> 日期：2026-08-27
> 状态：讨论稿
> 适用对象：机器人软件架构师、算法与嵌入式工程师、测试与运维工程师、技术负责人，以及构建机器人开发 Agent 的团队

## 摘要

ROLO（robot only loop once）是一套面向具身机器人研发的软件开发原则与参考架构。它把每一次有意义的执行视为一个可回放、可解释、可复现的证据切片：执行前固定意图、约束和版本，执行中记录请求、状态与外部观察，执行后解释预期与实际的差异，并把经过验证的认识沉淀为下一次运行可复用的软件、配置、测试和知识。

“only loop once”不是“一次尝试必须成功”，也不是禁止迭代，而是禁止在没有新证据、状态演进或可复现条件时盲目重试。每一轮都必须产生可验证的信息增量。

本文用大写 **ROLO** 指原则、架构和规范，用小写 `rolo` 指本仓库的 CLI、服务和参考实现。当前实现仍是 MVP：`adapt` 已形成较完整的发现、适配、门禁和发布链路；`diagnose` 具备 `robot_use` 与 handoff 边界，但完整诊断事务仍在演进；`verify` 提供正式验收的结构和入口。ROLO 不替代急停、碰撞检测、功能安全控制器、风险评估或人工授权。

## 1. 一个核心循环

ROLO 只保留一条产品主线：

```text
理解系统 → 明确意图 → 受控执行 → 观察结果 → 解释差异
        → 修正系统 → 回归验证 → 沉淀证据与知识
```

这条主线有四条不可跳过的约束：

1. **证据优先**：结论必须能回到带来源、时间、完整性、适用范围和限制的证据；`UNKNOWN`、`PARTIAL`、`UNOBSERVED`、`UNAVAILABLE` 是合法结果。
2. **契约优先**：上层表达产品意图，不直接依赖厂商 Topic、SDK 或脚本；具体接口由 Adapter 绑定。
3. **门禁优先**：Discovery、模型、Agent 或 Adapter 都不能自行宣布“可用”；发布由 ROLO 拥有的独立门禁决定。
4. **安全确定性**：模型可以解释、建议和生成候选实现，但不能授予物理安全权限；高风险授权、静止证明、急停和 interlock 由确定性系统或部署方控制。

## 2. 统一概念模型

### 2.1 证据等级

证据按“事实强度”而不是按组件划分：

| 等级 | 来源与含义 | 不能推出的结论 |
|---|---|---|
| `DECLARED` | URDF、manifest、配置或文档中的声明 | 不能推出目标运行时存在 |
| `DISCOVERED` | 从制品、源码、launch 或二进制静态提取的候选 | 不能推出在线通路 |
| `OBSERVED` | 目标环境中有界、只读探针观察到的事实 | 不能推出行为正确或安全 |
| `GATED` | Contract、Binding、Route 通过独立 conformance | 不能推出物理结果完成 |
| `DIAGNOSED` | 在用户约束内通过实验确认的行为或参数结论 | 不能替代正式验收 |
| `VERIFIED OUTCOME` | 按已接纳验收约束完成回归并打包证据 | 不能替代功能安全认证 |

等级不可跳跃：源码不能自动成为运行时事实，通路存在不能自动成为行为正确，命令被接受不能自动成为动作完成。

### 2.2 两类知识资产

- **机器证据**：Schema + manifest + SHA-256 固化的不可变输入，供门禁、运行时和回放使用。
- **Robot Wiki**：面向人的可编辑工程知识，允许修正文案、补充上下文和记录经验，但不得把推断伪装成机器事实，也不得复制完整 Registry。

二者职责互补：机器证据回答“观测到了什么”，Wiki 回答“团队如何理解和维护”。

### 2.3 产品词汇、目标适用性与运行可用性

这三个问题必须分开回答：

| 问题 | 权威对象 | 典型状态 |
|---|---|---|
| 产品允许表达什么意图？ | Canonical Operation Registry + Operation Contract | `RELEASED` / `GATEABLE` |
| 目标是否有相关证据？ | Discovery candidate + Route Evidence | `applicability` |
| 当前能否安全调用？ | Adapter + Independent Gate + Active Tool Catalog | `availability` / `registration` |

当前参考实现定义 294 个 operation，其中 62 个为 `RELEASED`、232 个为 `GATEABLE`。这只是产品词汇和契约成熟度，不表示任意机器人都支持这些 operation。

## 3. 架构：四层视图与三阶段生命周期

四层回答“系统由什么组成、接口在哪里”；三阶段回答“证据如何演进”。两者正交，不再为同一概念分别定义多套流程。

### 3.1 四层系统视图

```text
Application  建图、定位、导航、操作、测试、诊断、调优、任务
Middleware   节点、Topic、Service、Action、TF、参数、诊断
Linux        进程、服务、网络、文件、资源、软件包、时间
Hardware     传感器、执行器、总线、固件、电源、计算与热状态
```

它同时是 Robot Wiki、Stack Map 和 Canonical Operation 命名空间的主要信息架构。ROS 不是 Adapt 前置条件；非 ROS 工程可通过 Python console script 与目标机固定的 CLI 自描述证据建立 Application Route，源码声明不能替代目标观测。

### 3.2 三阶段生命周期

```text
adapt → diagnose → verify（可选）
```

| 阶段 | 输入 | 主要工作 | 产物与边界 |
|---|---|---|---|
| Adapt | 目标主机、工程制品、文档、URDF、只读运行时 | 有界 Discovery；生成 Wiki；匹配 operation；生成 Adapter 候选；独立验证 Schema/Binding/Route | machine-evidence manifest、Active Tool Catalog、State Graph、immutable release、adapt handoff；不证明物理行为 |
| Diagnose | 已验证 adapt handoff、用户约束、Episode/观察 | baseline → observe → hypothesis → change → smoke/regression → commit/rollback | 诊断结论、冻结配置、调参证据、diagnosis handoff；模型只是证据来源之一 |
| Verify | 已验证 diagnosis handoff、已接纳验收约束 | 正式用例、Oracle、超时/取消、全量回归和证据打包 | verification handoff；可选，但保留改动后的基本回归不可省略 |

## 4. Adapt 控制面

### 4.1 Discovery 与 Workset

Discovery 只读取显式提供的 build、install、documentation、launch、source、executable、URDF 和目标侧只读证据。优先级为：

```text
BUILD_ARTIFACT → DOCUMENTATION → PROBE；SOURCE 仅作补充
```

它不执行新发现的程序或 README 命令，不安装依赖，不枚举无关主机软件包。启发式 Agent、Operation Mapping 和 Wiki Agent 只能生成有界候选；确定性 Validator 负责证据引用、适用性和状态转换，Agent 结果保持 `DISCOVERED_UNVERIFIED`。

Operation Workset 是一次 Adapt 的只读查询视图，汇总 Registry、当前 candidate 和 gated release；它不是 Tool Catalog，也没有发布权限。Target Operation Slice 只用于减少 Agent 上下文，shadow/canary 不能扩大权限或自动改变发布配置。

### 4.2 Contract、Adapter 与独立门禁

Operation Contract 至少定义稳定 ID、版本与摘要、输入/输出 Schema、读写与 R0–R3 风险、数据分类、单位/坐标系/时间、前后置条件、副作用、资源锁、错误、重试、幂等、取消、补偿和回滚语义。

Adapter 将 Canonical Operation 映射到 ROS、CLI、device 或厂商接口。Adapter Agent 在隔离工作区中读取有界快照并提交候选文件；它不拥有 Registry、Contract、安全策略、Catalog、State Graph 或 release 权限。

Independent Gate 至少检查：

- Schema：结构、类型、Contract 版本和摘要；
- Binding：每个 operation 唯一解析到一个 entrypoint；
- Route：目标存在精确匹配的 ROS、CLI、device 或其他等价通路；
- 完整性：bundle 文件集、身份、依赖、State Graph、conformance 和目标指纹。

门禁不执行写操作来证明行为，不把文档、源码、模拟或 Agent 自评当成生产目标证据。通过后，ROLO 确定性构建 Active Tool Catalog 和 State Graph，并在源码树外发布按摘要固化的 immutable release。当前索引只指向最后一次成功发布；失败必须回滚索引并清理不完整 release。

Active Tool Catalog 保留完整产品词汇；不适用、未观察、未注册或因证据新鲜度不足的 operation 继续标记为 `UNAVAILABLE` 并给出原因。每个 operation 独立评估，单个缺口不会阻塞无关 operation。Capability/Provider 扩展默认保持 release-neutral：Provider conformance 只证明结构、版本、隔离和边界，不自动获得生产 Catalog 或写授权。

### 4.3 Handoff 与短旅程

阶段间通过结构化 handoff 传递身份、Schema、引用和 SHA-256；下游必须重新验证，不能仅凭文件存在打开下一阶段。

`rolo adapt <本地工作区> --robot <机器人 ID>` 是产品用户的首选入口，复用同一套服务和制品完成 enrollment、环境检查、签名目标证据、Discovery、Wiki、Adapter Agent、Gate、handoff 和 release。需要远程证据或专家参数时使用 `robotctl adapt start`。远程模式固定 Collector、验证密钥和 SSH host key；本地或远程失败都不能退回控制器探针。生成 Adapter 默认需要部署方提供受保护的 OS sandbox launcher；缺失时失败关闭。

## 5. Episode、观察与安全

### 5.1 Episode 是运行证据切片

一次有意义的执行应尽可能保留：意图与约束、命令与状态、传感器/遥测/外部观察、软件/配置/能力版本、判定、异常区间、诊断结论、变更、回滚和限制。缺失项必须显式标记，不能伪造完整闭环。

参考实现已提供只读 Episode collection/detail/timeline/asset/finding、revision 与 cohort 模型，以及不可覆盖的 producer revision、安全投影和 Evidence ID 映射。公开响应不暴露原始 payload、主机路径、凭据或模型 prompt/response。媒体交付、live stream、compare、replay、recollection、remediation 和完整工作台仍在演进。

### 5.2 `robot_use` 与 Agent 边界

`robot_use` 将图像、外部视角、时间戳关键帧、任务状态、控制命令、里程计和遥测组织为语义监督输入，可支持周期监督、状态触发、异常回溯和测试步骤后的验证。它不执行本地视觉检测，也不拥有安全决策权。

Agent 可以阅读有界证据、提出洞察、生成候选实现、设计诊断步骤和测试；不能扩大权限、自行注册 operation、跳过 Gate、把推断写回不可变机器证据，或把命令接受/仿真结果当成物理成功。

### 5.3 失败关闭与授权

契约摘要不一致、证据被篡改、身份/策略缺失、审计不可写、R3 授权无效、静止状态无法证明、资源越界、目标指纹漂移或运行环境不再新鲜时，系统拒绝执行。R0–R1 只读调用也必须从已验证 Catalog 和有效会话取得；R2/R3 写操作还需显式授权、超时、取消、补偿或回滚。ROLO 的软件策略不能替代硬件急停和功能安全控制器。

## 6. 供应链标准化路线

ROLO Contract 当前是内部参考规范。行业标准的正当性来自共同需求、公开评审、至少两个无共同代码来源的实现和持续互操作证据，而不是项目单方面宣布 operation 名称为标准。

标准化分三层：

1. **Core Contract**：身份、Schema、错误、风险、时间、版本和 conformance；
2. **Domain Profile**：移动底盘、传感器、机械臂、导航、电源、安全停止等公共语义；
3. **Protocol/Vendor Binding**：ROS、OPC UA、CLI、SDK 和设备协议的可替换映射。

建议流程为：问题陈述 → 多方用例与证据 → 公开 RFC → 独立原型 → 互操作/负向/回归测试 → 分歧登记 → 共识评审 → 试行 Profile → 版本与兼容性治理。厂商私有能力进入扩展命名空间，不伪装成公共核心；风险、数据分类或授权要求的放宽必须经过跨角色安全评审。

## 7. 当前成熟度与明确边界

### 已形成或已进入受限主线

- `adapt` 的 enrollment、签名目标证据、bounded Discovery、可编辑 Wiki、Adapter Agent 隔离工作区、独立 Gate、Catalog、State Graph、immutable release 和 handoff；
- 294 个 Canonical Operation 及机器可校验 Contract（62 `RELEASED`、232 `GATEABLE`）；
- Capability/Provider 基线、非 ROS Application/CLI Route、只读 Web read models、Episode 只读模型与安全投影；
- `robotctl adapt start`、本地/固定远端 Collector、ROS 环境 bootstrap 固定、目标侧 sandbox launcher 门禁、原子写入与并发锁；
- Python 3.10–3.13 的离线 Quickstart/CI 基线与可选 LeRobot 源码发现验收。

### 正在演进

- 真机、跨厂商和非 ROS Adapter 的规模化验证；
- Diagnose 的完整事务、调参和自动回归闭环；
- Episode 多源观察包的媒体、live stream、compare、replay、export 和 remediation；
- Verify Agent、正式用例/Oracle 和证据包；
- Web 工程工作台与从内部参考规范走向多实现互操作规范。

### ROLO 不作出的声明

- 294 个 operation 已成为行业标准；
- `GATEABLE` operation 在任意目标上可用；
- Adapt conformance 等于行为正确、可靠、性能达标或物理安全；
- 仿真、源码或模型推断可以替代真机证据；
- ROLO 已完成机器人功能安全认证。

## 8. 评价指标

优先衡量闭环质量而非命令数量：新成员理解系统的时间、从 `BLOCKED` 到可操作原因的时间、结论可追溯比例、operation 适用性/风险判断准确率、跨运行差异定位时间、带回滚和回归证据的改动比例、高风险调用的正确拒绝/授权比例、无新证据的重复尝试次数，以及独立实现和跨厂商互操作通过率。

## 9. 文档权威顺序

发生冲突时依次以以下内容为准：

1. 版本化 Schema、Operation Contract、运行时门禁规则；
2. 与代码一起测试的结构化模型和 conformance 用例；
3. 本白皮书、架构和安全策略；
4. 操作指南、验收清单和配置说明；
5. Proposal、Plan、Draft、评审样本和生成型参考。

低优先级材料不能覆盖高优先级事实；发现冲突应修正文档或显式记录开放问题。

## 10. 词汇表（最小集合）

| 术语 | 定义 |
|---|---|
| Canonical Operation | 跨目标稳定的产品意图标识；是词汇，不是目标可用性证明 |
| Operation Contract | 定义输入、输出、错误、风险、时间、单位、状态、取消和治理的机器规范 |
| Registry | ROLO 拥有的完整 operation 词汇与治理元数据 |
| Discovery | 有界静态/运行时证据采集；输出候选与观察，不做发布决策 |
| Route Evidence | 目标 endpoint 存在的结构化证据，可绑定类型、摘要、provider 和 runtime revision |
| Adapter | 将 Canonical Operation 映射到目标接口的机器人专属实现 |
| Provider | 将目标系统的具体能力规范化为 ROLO 证据或操作的组件；默认不获得生产发布权 |
| Independent Gate | 独立验证 Schema、Binding、Route、完整性和新鲜度的发布门禁 |
| Active Tool Catalog | 某台机器人当前通过门禁的可见控制面；运行时调用的权威入口 |
| State Graph | ROLO 根据门禁结果确定性构建的状态、资源、operation 和 route 关系图 |
| Workset / Slice | 一次 Adapt 的只读查询视图 / 受预算约束的 Agent 上下文子集；均无发布权限 |
| Episode | 一次执行的完整证据切片，用于回放、解释、比较和复现 |
| Handoff / Release | 阶段间摘要绑定交付物 / 按摘要固化并在源码树外发布的制品集合 |
| Core Contract / Domain Profile | 跨领域共享的契约核心 / 面向移动、传感器、导航、安全等领域的公共语义集合 |
| Protocol/Vendor Binding | 将公共语义映射到 ROS、OPC UA、CLI、SDK 或设备协议的可替换层 |
| Conformance | 实现对 Contract 的符合性检查；Adapt 主要覆盖 Schema、Binding、Route |
| Quiescence Lease | 受保护执行监督器签发的、证明指定时限内满足静止条件的绑定凭据；不授予运动权限 |
| `robot_use` | Diagnose 阶段的多模态语义监督；返回事实、候选原因和限制，不做安全裁决 |
| `ACKNOWLEDGEMENT_ONLY` | 只表示请求被接受或拒绝，不表示物理动作完成 |
| `RELEASED` / `GATEABLE` / `VERIFIED` | 分别表示产品契约已发布、可进入目标门禁、或结合对象已获得相应证据；`VERIFIED` 必须说明对象是 Tool 还是 Outcome |

## 参考文档

- [三阶段架构](ARCHITECTURE.md)
- [ROLO 最高开发准则](DEVELOPMENT_PRINCIPLES.md)
- [自动发现](../adapt/AUTODISCOVERY.md)
- [Canonical Operation 清单](../CANONICAL_OPERATIONS.md)
- [Registry Operation 指南](../operations/REGISTRY_OPERATION_GUIDE.md)
- [Operation Contract 标准化路线](../operations/OPERATION_CONTRACT_STANDARDIZATION.md)
- [SENSITIVE 调用策略](../operations/SENSITIVE_INVOCATION_POLICY.md)
- [P0 Adapt 验收边界](../validation/P0_ADAPT_ACCEPTANCE.md)
- [`robot_use` 多源观察草案](../web/ROBOT_USE_MULTISOURCE_OBSERVATION_DRAFT.md)
- [代码重构审计](../reference/CODE_REFACTOR_AUDIT.md)

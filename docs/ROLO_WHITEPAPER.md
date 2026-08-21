# ROLO 白皮书

> 版本：Draft 0.1<br>
> 日期：2026-08-21<br>
> 状态：讨论稿<br>
> 适用对象：机器人软件架构师、算法与嵌入式工程师、测试与运维工程师、技术负责人，以及构建机器人开发 Agent 的团队

## 摘要

ROLO（robot only loop once）是一套面向具身机器人研发的软件开发原则与参考架构。它要求每一次有意义的机器人执行都形成一个完整、可追溯的证据闭环：执行前明确意图、约束与版本，执行中记录命令、状态和外部观测，执行后解释预期与实际的差异，并把被验证的认识沉淀为下一次运行可以复用的软件、配置、测试和知识。

本文用“ROLO”指这套原则、架构与规范，用小写 `rolo` 指当前代码库、CLI 和参考实现。

这里的“only loop once”不是承诺机器人一次尝试就能成功，也不是禁止迭代。它强调的是：**同一个问题不能在缺少新证据、没有状态演进、无法复现的条件下盲目重复。每一次循环都必须产生可验证的信息增量。**

ROLO 通过三类机制落实这一原则：

1. 以 `adapt -> diagnose -> verify` 组织从系统理解到正式验收的生命周期；
2. 以 Canonical Operation、Operation Contract、Adapter、Active Tool Catalog 和 State Graph 建立跨机器人、跨中间件的统一控制面；
3. 以不可变机器证据、可编辑机器人 Wiki、Episode、Handoff、内容摘要和独立门禁，建立人、Agent 与机器人之间可审计的协作边界。

ROLO 当前是开发中的参考实现。Adapt 阶段已经具备较完整的发现、适配、契约门禁和发布链路；Diagnose 具备基础 `robot_use` 和 handoff 边界，但完整闭环仍在演进；Verify 当前主要提供正式验收的结构和入口。ROLO 不替代机器人本体的急停、碰撞检测、功能安全控制器、风险评估或人工授权。

## 1. 为什么需要 ROLO

机器人软件的问题通常不发生在单一算法内部，而发生在系统边界之间：硬件型号与驱动不一致、启动入口与实际部署不一致、ROS 图与文档不一致、坐标系或单位语义不一致、参数改动缺少基线、命令返回成功但机器人没有完成预期动作。

传统开发流程常见四个断点：

- **系统知识断裂**：设备信息、源码、启动脚本、厂商文档和现场经验分散在不同位置；
- **接口语义断裂**：不同机器人暴露不同 Topic、Service、SDK 和 CLI，上层工具必须重复适配；
- **执行证据断裂**：命令、遥测、视频、配置和诊断结论无法对齐到同一次运行；
- **组织记忆断裂**：问题虽然被临时修复，但修复依据、约束、回滚和回归结果没有沉淀。

Agent 可以加速阅读、编码和诊断，但也会放大不透明系统中的风险。如果 Agent 无法区分声明、观察、推断和验证，就可能把 README 中的命令当成安全事实，把静态 Topic 名称当成在线通路，把命令接受当成物理成功，或者把仿真结果当成真机证据。

ROLO 的目标，是让机器人研发从“依赖个人经验的反复试错”转向“由证据、契约和门禁驱动的受控演进”。

## 2. 核心命题

### 2.1 每次运行都是一个可学习单元

一次运行至少应回答：

- 当时希望机器人做什么；
- 使用了哪一版软件、配置、能力契约和环境；
- 实际发送了什么请求，系统经历了哪些状态；
- 机器人本体和外部观察到了什么；
- 哪些事实得到确认，哪些只是候选原因；
- 保留了什么修改，如何回滚；
- 哪些检查证明改动没有破坏既有能力。

如果这些问题无法回答，本次运行只能算一次操作，不能算一次完整的工程循环。

### 2.2 证据优先于结论

ROLO 中的结论必须能够回到证据。证据必须带来源、时间、完整性、适用范围和限制。系统应允许 `UNKNOWN`、`PARTIAL`、`UNOBSERVED` 和 `UNAVAILABLE` 成为合法状态，不用看似确定的结论掩盖信息缺口。

### 2.3 契约优先于具体接口

上层 Agent 不应直接依赖某个厂商 Topic、SDK 函数或脚本名称。ROLO 用稳定的 Canonical Operation 表达产品意图，用 Operation Contract 定义输入、输出、错误、风险、时间、单位、坐标系、取消和补偿语义，再由目标 Adapter 绑定到具体接口。

### 2.4 门禁优先于自我声明

发现器、Adapter Agent、厂商实现和模型都不能自行宣布能力已经可用。能力发布必须经过 ROLO 拥有的独立门禁。门禁验证契约、绑定和目标通路；行为正确性、可靠性、性能和安全则由后续诊断、回归和正式验收承担。

### 2.5 安全边界不能交给模型

模型可以提出解释、生成实现、建议检查或请求补充观察，但不能拥有物理安全授权。急停、保护停止、碰撞检测、硬件 interlock、执行静止证明、身份认证和高风险授权必须由确定性系统或部署方控制。

## 3. 设计原则

ROLO 的软件设计遵循以下原则。

### 3.1 事实、声明、推断与验证分层

- **声明（Declared）**：来自 URDF、manifest、配置或文档，说明系统声称具有什么；
- **静态发现（Discovered）**：从制品、源码、launch 或二进制静态提取的候选事实；
- **运行时观察（Observed）**：在目标环境中通过有界只读探针观察到的事实；
- **门禁确认（Gated）**：契约、绑定和目标通路通过独立 conformance；
- **诊断确认（Diagnosed）**：行为、结果或参数结论经过约束内实验验证；
- **正式验证（Verified outcome）**：按照被接纳的验收约束完成回归和证据打包。

这些等级不可跳跃。静态源码证据不能自动变成运行时事实，通路存在不能自动变成行为正确，命令被接受不能自动变成动作完成。

### 3.2 不可变机器证据与可编辑工程知识分离

机器证据使用 Schema、SHA-256 和 manifest 固化，供门禁和回放使用。机器人 Wiki 面向工程师阅读和维护，允许修正叙述、补充上下文和记录经验，因此不应被机器证据摘要锁死。

这两者不是重复产物：机器证据回答“当时观测到了什么”，Wiki 回答“团队如何理解和维护这台机器人”。

### 3.3 产品词汇与目标适用性分离

Canonical Operation Registry 是产品拥有的完整词汇，不由某次 discovery 动态扩展。某个 operation 是否适用于当前机器人，由 discovery candidate 表达；是否已经可调用，由目标 Adapter、route evidence 和独立门禁共同决定。

因此：

- Registry 中存在，不代表目标机器人支持；
- Discovery 发现候选，不代表已经注册；
- Adapter 实现存在，不代表通过门禁；
- Tool Catalog 中可用，不代表物理行为已经验证。

### 3.4 有界、最小和按需披露

探针、Agent 上下文、日志、流式观察和制品读取都必须有明确边界。ROLO 不默认把完整源码树、完整 Registry、完整 Wiki、原始日志或私有文件内容发送给 Agent，而是先提供摘要，再按具体缺口检索有界证据。

### 3.5 失败关闭

契约摘要不一致、证据被篡改、身份策略缺失、审计不可写、R3 授权无效、静止状态无法证明或资源越界时，系统拒绝执行。安全策略不能依赖“默认应该没问题”。

### 3.6 变更必须有回滚和回归

配置、参数、固件、任务和运动相关操作必须明确取消、补偿或回滚边界。Diagnose 阶段保留的每次变化，都必须运行受影响的 smoke、安全与回归检查。正式 Verify 可以是可选阶段，但保留改动后的基本回归不可省略。

## 4. 总体架构

ROLO 同时使用两组正交结构：四层系统视图和三阶段生命周期。

### 4.1 四层系统视图

```text
Application     建图、定位、导航、操作、测试、诊断、调优、任务
Middleware      ROS 节点、Topic、Service、Action、TF、参数、诊断
Linux           进程、服务、容器、网络、文件、资源、软件包、时间
Hardware        传感器、执行器、总线、固件、电源、计算与热状态
```

四层视图用于描述机器人“由什么组成、接口在哪里、依赖如何连接”。它既是 Robot Wiki 和 Stack Map 的信息架构，也是 Canonical Operation 命名空间的主要分层。

### 4.2 三阶段生命周期

```text
adapt  ->  diagnose  ->  verify
理解并接入     解释并改进       正式验收（可选）
```

#### Adapt：理解并接入

Adapt 对目标主机和应用进行有界发现，生成可编辑机器人 Wiki 和不可变机器证据；将发现到的接口与产品 Operation 匹配；由 Adapter Agent 生成目标绑定；再由 ROLO 独立完成 Schema、Binding 和 Route conformance，发布 Active Tool Catalog、State Graph、immutable release 和 adapt handoff。

Adapt 的结论是“这个受版本约束的操作可以解析到目标上已观察到的等价通路”，不是“机器人完成了动作”。Adapt 不通过执行写操作来证明能力存在。

#### Diagnose：解释并改进

Diagnose 读取经过验证的 adapt handoff 和用户约束，围绕一个具体问题形成闭环：建立基线、执行受控观察或试验、比较预期与实际、提出候选原因、修改配置或实现、运行受影响回归、保留或回滚变化，并输出 diagnosis handoff。

`robot_use` 位于该阶段，用于把图像、外部视角、遥测和任务上下文组织为语义监督输入。模型输出是诊断证据的一部分，而不是安全裁决。

#### Verify：正式验收

Verify 消费经过验证的 diagnosis handoff 和已接纳的验收约束，执行全量回归、生成报告和证据包，并发布 verification handoff。它可以由项目选择是否启用，但不应与日常诊断后的必要回归混淆。

### 4.3 生命周期数据流

```text
目标主机、制品、文档、URDF、只读运行时
                  |
                  v
       Discovery + Robot Wiki
                  |
        immutable manifest
                  |
                  v
      Operation Workset（查询视图）
                  |
           Adapter Agent
                  |
         frozen proposal
                  |
                  v
       ROLO independent gate
          /              \
 Active Tool Catalog   State Graph
          \              /
           immutable release
                  |
             adapt handoff
                  |
             Diagnose / Verify
```

## 5. 核心组件

### 5.1 Discovery

Discovery 使用明确提供的 build、install、documentation、launch、source、executable 和可选 URDF 作为输入。证据优先级为：

```text
BUILD_ARTIFACT -> DOCUMENTATION -> PROBE
SOURCE = SUPPORTING_ONLY
```

源码只用于补充缺口，不能覆盖更高优先级证据。Discovery 不执行新发现的程序、launch 文件或 README 命令，不安装依赖，不枚举无关主机软件包。运行时探针仅限已运行系统上的有界只读观察。

### 5.2 Robot Wiki

Robot Wiki 是每台机器人可持续维护的工程知识入口，覆盖硬件、Linux、Middleware、Application、启动拓扑、接口、依赖、能力候选、差异和未知项。它应明确标注证据来源、置信度与验证方法。

Wiki 不应复制完整 Registry，也不应把启发式推断写成机器事实。模型可以在严格 Schema 和证据边界内润色或补充洞察；模型不可用时必须回退到确定性生成，不得阻塞 discovery。

### 5.3 Canonical Operation Registry

Registry 定义稳定的产品操作词汇。当前参考实现包含 294 个 operation，分布在 Hardware、Linux、Middleware 和 Application 四层。operation 使用 `layer.resource.verb` 风格的稳定标识，例如：

- `linux.host.inventory`
- `ros.topic.sample`
- `app.navigation.start`
- `app.safety.emergency_stop`

Registry 负责“产品允许表达哪些意图”，不负责决定某个目标是否支持这些意图。

### 5.4 Operation Contract

每个 Canonical Operation 由机器可校验的契约定义。契约至少包含：

- 稳定 operation ID、版本、生命周期和内容摘要；
- 输入与输出 JSON Schema；
- read/write、R0-R3 风险和数据分类；
- 结果语义、最大时长、速率限制和观测开销；
- 单位、坐标系、时间语义和语义绑定；
- 前置条件、后置条件、副作用和资源锁；
- 错误、重试、幂等、取消、配对、补偿或回滚语义。

当前参考实现的 294 个 operation 均有正式契约，其中 62 个为 `RELEASED`，232 个为 `GATEABLE`。这表示产品语义已被定义，不表示 232 个目标相关 operation 已在任意机器人上可用。

### 5.5 Operation Workset

Workset 是面向一次 Adapt 的查询视图。它把产品 Registry、当前 discovery candidate 和当前 gated release 连接起来，并将以下状态分开：

- `applicability`：目标是否有适用证据；
- `implementation`：是否存在 builtin 或 Adapter 实现；
- `registration/availability`：是否已经通过门禁并发布。

Workset 不是 Tool Catalog，也没有发布权限。

### 5.6 Operation 治理台账与 Target Operation Slice

Operation 治理台账为完整产品词汇记录未来责任边界：哪些能力适合由 Agent 原生检查、ROLO builtin、目标 Adapter 或平台 Provider 承担。台账不改变当前 Operation ID、Contract、Registry、Catalog 或 runtime route；词汇变化必须同时给出显式治理决定。

Target Operation Slice 从完整 Workset 中提取一次 Adapt 真正需要关注的目标操作集合，以减少 Agent 启动上下文。Slice 首先以 shadow 方式运行：记录与权威 eligibility 的差异，但不影响 Bundle、独立 gate、Catalog 或 release。当前实现中的 canary 机制也只允许收缩 Agent 编码焦点；权限扩张、空 Slice 或预算超限必须自动回退。

Slice 是否可以扩大灰度，应由真实运行样本、Agent/gate 失败、上下文预算、误裁剪与回退数据进入人工评审决定，不能由一次成功运行自动提升为默认行为。

### 5.7 Capability 与 Provider 扩展模型

ROLO 的 `main` 已经建立平台无关的 Capability、Provider Manifest、Platform Profile、Provider SPI、Resolver、Provider Host 和首版 Conformance Kit，用于表达 Windows、RTOS、CyberRT、DDS 或其他 OS/Middleware 环境，而不把具体平台概念直接写入 Core Contract。这些能力已经进入参考实现，但没有接入生产发布权威。

该模型当前保持 release-neutral：

- Provider capability 不自动进入 Active Tool Catalog；
- Provider Host 不拥有 write 授权，缺少 runtime policy bridge 时必须失败关闭；
- Provider 缺失、未知或不可用是正常可观察状态；
- Provider conformance 只证明结构、版本、Manifest、Descriptor、超时隔离和安全边界，不证明真实设备行为；
- Shadow、Canary 和稳定性报告不能自行修改 Registry、Bundle、Catalog、release 或灰度配置。

具体 Windows、FreeRTOS、CyberRT、Linux 或 ROS Provider、动态插件加载、进程级隔离、签名分发和生产 Catalog 接入仍属于后续产品化工作。

### 5.8 Adapter 与 Adapter Agent

Adapter 把稳定的 Canonical Operation 映射到目标机器人的 ROS、CLI、device 或其他具体接口。Adapter Agent 可以读取有界的、固定 discovery 快照，为缺失能力生成独立实现和绑定说明。

Adapter Agent 只提交候选实现和本地静态检查结果。它不拥有产品 Registry、契约、安全策略、Tool Catalog、State Graph 或发布索引，也不能通过修改自己的输出宣布通过门禁。

### 5.9 Independent Gate

独立门禁至少验证：

- **Schema conformance**：结构、类型、契约版本和摘要一致；
- **Binding conformance**：每个 operation 唯一解析到一个 entrypoint；
- **Route conformance**：目标环境存在精确匹配的等价通路。

门禁不会把静态声明、模拟、文档或 Agent 自评当成生产目标运行时证据。Route Evidence v2 可以表达 ROS topic/service/action、device 和 CLI 路由，并绑定接口类型、Schema 摘要、provider、runtime revision 和观察时间。

### 5.10 Active Tool Catalog

Active Tool Catalog 是某台机器人当前可见控制面的门禁结果。它包含完整产品词汇，但只有通过条件的 operation 标记为可用；不适用、未观察或未注册能力保持 `UNAVAILABLE` 并携带原因。

调用方必须始终从 Active Tool Catalog 和绑定契约理解能力，不能从源代码中猜测可调用接口。

### 5.11 State Graph

State Graph 表达当前机器人状态、能力、资源和路由之间的关系。发布版本由 ROLO 根据门禁后的 bundle 和 discovery 证据确定性构建，而不是采用 Agent 自报图作为权威。

State Graph 用于回答“当前处于什么状态、允许哪些转换、哪个 operation 依赖哪个 route”，但不能替代机器人本体实时控制器的内部状态机。

### 5.12 Handoff 与 Release

每个阶段通过结构化 handoff 向下一阶段交付经过验证的引用和摘要。仅在约定路径创建一个文件不能打开下一阶段；读取方必须重新验证身份、Schema、引用和 SHA-256。

通过门禁的 Adapter 以不可变 release 发布到源码仓库之外。当前索引只指向最后一次成功发布；发布失败必须回滚索引并移除不完整 release。目标 route、平台或硬件指纹发生实质变化时，旧 release 不再可调用。

### 5.13 Adapt 短旅程

参考实现提供 `robotctl adapt start` 作为一站式产品入口，将身份注册、环境检查、有界工程证据识别、只读发现、Wiki、Adapter Agent、独立门禁、handoff 和 release 编排为同一旅程。该入口复用既有服务与制品，不创建第二套契约或授权模型。

短旅程不扩大权限：URDF 仍需显式选择，运行时探测默认只读，缺少目标运行时 route 时返回结构化阻塞，Adapter Agent 仍不能批准门禁或发布。`--discover-only` 可以只完成发现与 Wiki；细粒度命令继续作为工程调试入口。

## 6. 证据模型

### 6.1 证据的基本属性

所有可用于决策的证据应尽可能包含：

- `source`：来自哪个探针、文件、Provider 或人工流程；
- `observed_at`：何时观察；
- `subject`：针对哪个 robot、resource、operation 或 execution；
- `integrity`：内容摘要、manifest 和引用；
- `provenance`：原始、规范化、派生、模型推断或人工确认；
- `limitations`：截断、缺失、时钟偏差、覆盖不足或权限拒绝；
- `classification`：传播、访问和留存边界。

### 6.2 证据层级

ROLO 建议按以下层级表达，而不是压缩成单一布尔值：

| 层级 | 含义 | 不代表 |
|---|---|---|
| `DECLARED_UNVERIFIED` | 输入模型或配置中的声明 | 真实硬件已存在或限制已批准 |
| `DISCOVERED_UNVERIFIED` | 静态或低置信证据形成候选 | operation 已注册或可调用 |
| `OBSERVED_RUNTIME` | 目标运行时观察到 route 或状态 | 行为正确、可靠或安全 |
| `VERIFIED`（Tool） | 契约、绑定、route 通过 Adapt 门禁 | 物理结果完成 |
| `DIAGNOSED` | 在约束内对行为或原因形成结论 | 完整正式验收 |
| `VERIFIED`（Outcome） | 根据验收约束完成验证 | 功能安全认证 |

“Tool 的 VERIFIED”和“Outcome 的 VERIFIED”属于不同语境。界面、API 和文档必须附带对象，避免只显示一个模糊的 “verified”。

### 6.3 Episode

Episode 是一次运行的完整证据切片，目标上应包含：

- 意图、约束、计划和 operation contract；
- 命令、确认、状态转换和事件；
- 遥测、图像、空间数据和外部观察；
- 软件、配置、Adapter release 和目标指纹；
- observed facts、candidate causes 和证据冲突；
- 修改、回滚、测试、判定和最终 outcome。

当前参考实现已经具备部分 episode/evidence 控制面 operation，但完整 Episode 模型和可视化工作台仍是演进方向。

## 7. 风险、安全与授权

### 7.1 风险等级

ROLO 用 R0-R3 表达操作风险。风险与 read/write 相关但不等价。

| 等级 | 典型含义 | 示例边界 |
|---|---|---|
| R0 | 低开销、有界、无状态变化的读取 | 版本、健康、单次状态查询 |
| R1 | 高负载读取或受控的非运动状态变化 | 总线扫描、有界流、部分配置类动作 |
| R2 | 需要精确策略授权的写操作 | 配置应用、参数设置、普通取消 |
| R3 | 可直接或间接触发物理运动或高危状态变化 | 导航启动、teleop、机器人启停、急停请求 |

read operation 最高可为 R1；write operation 不得仅因为名称看似无害而规避风险分类。工作流操作如果可能间接触发执行器，同样属于 R3。

### 7.2 数据分类

| 分类 | 含义 |
|---|---|
| `PUBLIC` | 可公开传播的产品和协议信息 |
| `INTERNAL` | 主机、网络、ROS、硬件和运行元数据 |
| `SENSITIVE` | 图像、地图、位姿、配置正文、日志和文件内容 |
| `SECRET` | 凭据、密钥和认证材料；禁止由通用 operation 输出 |

风险表示动作和系统变更的危险，数据分类表示信息泄露风险。二者必须独立检查。

### 7.3 授权原则

- `SENSITIVE` 默认拒绝，必须由受保护的 OS 身份策略授权；
- write 默认拒绝，R1/R2 只允许精确 operation 白名单；
- R3 需要部署方拥有的外部 authorizer 为单次请求签发绑定 capability；
- 需要静止的写操作还必须取得覆盖调用时限的 quiescence lease；
- rollback token 只定位回滚状态，不是 bearer authorization；
- 审计不可写时失败关闭，审计记录不包含业务 payload。

### 7.4 物理安全边界

ROLO 的 contract、gate、Agent 和模型均不能证明功能安全。`app.safety.emergency_stop` 等 operation 只定义软件接口和授权语义，不替代硬接线急停、安全 PLC、碰撞检测、速度与力限制、现场风险评估或法规验收。

## 8. Agent 在 ROLO 中的角色

ROLO 将 Agent 视为受约束的工程参与者，而不是系统权威。

Agent 适合：

- 从有界证据中理解目标系统；
- 生成或修正 Adapter 实现；
- 提出待验证的系统洞察；
- 设计诊断步骤和测试；
- 比较 Episode 并提出候选原因；
- 在权限允许时请求补充只读观察。

Agent 不适合：

- 自行扩展 Canonical Operation Registry；
- 自行修改产品 Contract 或风险分类并立即生效；
- 把本地静态测试声明为目标运行时证明；
- 直接拥有发布、R3 授权或安全决策；
- 读取任意文件、执行任意 shell 或无限追加上下文；
- 把推断写回不可变机器证据。

这种边界使 Agent 的创造性用于理解、实现和解释，同时把身份、完整性、发布和安全留在确定性控制面。

## 9. 软件架构特征

### 9.1 本机优先

探针、证据存储、Adapter runtime 和策略执行默认位于机器人主机或可信控制主机。管理 API 默认监听 loopback；远程访问通过 SSH tunnel 或部署方提供的认证代理。

### 9.2 控制面与目标实现解耦

ROLO 控制面拥有 Registry、Contract、门禁、Catalog、State Graph、策略和审计。目标 Adapter 只负责把规范化请求映射到实际 endpoint。这使同一上层工作流可以适配 ROS 1、ROS 2、非 ROS CLI、设备接口或厂商 SDK。

### 9.3 Schema-first 与内容寻址

阶段输入输出、release、handoff、route evidence 和工具描述均使用版本化 Schema。关键对象使用 SHA-256 绑定。相同版本的 Contract 内容摘要不得变化；破坏性语义变化必须提升主版本。

### 9.4 外部不可变发布

机器人专属 Adapter 不写入 ROLO 产品源码树。Agent 工作区是临时且隔离的，最终文件经过规范化、冻结、门禁后发布到外部输出目录。产品代码和机器人实例资产因此保持清晰边界。

### 9.5 退化可见

证据不足、工具缺失、只读探针不可用或模型失败时，系统选择明确退化，而不是伪造完整性。低置信、限制、遗漏数和获取下一步都应进入制品。

## 10. 研发工作流

### 10.1 新机器人接入

1. 注册稳定 `robot_id`；
2. 提供可用的 build/install/doc/launch/source 和可选 URDF；
3. 运行静态或有界只读 discovery；
4. 工程师审阅并修正 Robot Wiki；
5. 检查 Operation Workset 的适用、可门禁和延期项；
6. Adapter Agent 生成目标 Adapter；
7. ROLO 独立 gate、发布 release、Catalog、State Graph 和 handoff；
8. 停止在写调用之前，转入 Diagnose 的安全流程。

### 10.2 问题诊断与改进

1. 固定 adapt handoff、软件和配置基线；
2. 写明期望、约束、可观测量和停止条件；
3. 采集初始 Episode；
4. 分离观察事实、候选原因和未知项；
5. 选择最小、可回滚的变化；
6. 在权限和安全边界内执行；
7. 比较 Expected vs Observed；
8. 运行受影响 smoke、安全与回归；
9. 保留或回滚变化，并形成 diagnosis handoff。

### 10.3 契约演进

1. 从真实的多目标实现差异中识别公共语义；
2. 编写或修改 Contract，并确定兼容性版本；
3. 更新 Schema、负向用例和 conformance；
4. 通过 Registry 词汇与歧义审计；
5. 在至少两个独立实现上验证互操作语义；
6. 再考虑进入开放参考规范或标准化流程。

## 11. 当前实现成熟度

截至本白皮书日期，参考实现处于 `0.1.0` 开发阶段。PR #8 已把此前的远端集成基线合入 `main`；进入 `main` 只表示参考实现已经具备相应代码、Schema 和测试，不等于形成生产 release、完成真机验证、获得安全认证或成为行业标准。

### 已形成闭环

- 三阶段状态与结构化 handoff 骨架；
- 有界 discovery、机器证据 manifest 和可编辑 Robot Wiki；
- 294 个 Canonical Operation 及机器可校验 Contract；
- Adapter Agent 的隔离工作区、结构化交付与冻结快照；
- Schema、Binding、Route 的独立 Adapt gate；
- Active Tool Catalog、ROLO-owned State Graph 和不可变 release；
- 通用调用入口、摘要校验、目标指纹和分级授权基础；
- SENSITIVE、R2、R3、quiescence 和无 payload 审计边界；
- `robot_use` v1 的基础语义监督接口。

### 已进入 `main`、仍保持受限或只读

- 完整 Operation 治理台账、Target Operation Slice shadow 和有界 Agent 上下文；
- 平台无关 Capability、Provider Manifest/SPI、Platform Profile 与 shadow resolution；
- Provider Host、Provider-neutral conformance kit、release-neutral shadow artifact；
- 默认关闭且可自动回退的 Slice canary，以及只读稳定性报告、API 和人工评审门槛；
- 面向 Robot Wiki、拓扑、Capability、Lifecycle、Blocker 和 Discovery history 的只读模型及 API；
- 将注册、检查、发现、Wiki、Agent、门禁、handoff 与 release 串联起来的 `robotctl adapt start` 短旅程。

这些能力保持当前 294 Operation、Contract、Linux/ROS、Bundle、Catalog 和 release 权威边界不变。Provider 默认不进入生产 Catalog，Slice 不扩大执行权限，稳定性报告不能自动改变灰度配置，短旅程也不能绕过独立门禁。

### 正在演进

- 真机、跨厂商和非 ROS Adapter 的规模化验证；
- Diagnose 的完整事务、调参和自动回归闭环；
- 多源 Observation Bundle、有限补充观察和 Episode 模型；
- Verify Agent、正式用例生成和证据包；
- Web 工程工作台、Stack Map、Capability Explorer 和 Episode Studio；
- 从内部参考规范走向多实现互操作规范。

### 明确不作出的声明

- 不宣称 294 个 operation 已成为行业标准；
- 不宣称 GATEABLE operation 在任意目标上可用；
- 不宣称 Adapt conformance 等于行为正确或物理安全；
- 不宣称仿真、源码或模型推断可以替代真机证据；
- 不宣称 ROLO 已完成机器人功能安全认证。

## 12. 供应链共识、治理与行业标准化

ROLO Operation Contract 当前定位为内部参考规范。长期目标是逐步形成被机器人供应链共同维护和采用的行业标准，而不是由 ROLO 项目单方面宣布一组 operation 名称为标准。

行业标准的正当性来自共同需求、独立实现、公开评审和持续互操作证据。ROLO 必须从一开始就把供应链参与者当成规范共同作者，而不只是 Adapter 的被集成对象。

### 12.1 需要形成共识的参与者

| 参与方 | 关注点 | 对规范的主要贡献 |
|---|---|---|
| 芯片、SoC、GPU 与计算平台厂商 | 资源、加速、驱动、时间和可观测性 | 计算与运行时能力模型、性能和故障语义 |
| 传感器、执行器、总线与控制器厂商 | 设备身份、单位、标定、状态和故障 | Hardware Domain Profile 与稳定设备 binding |
| 机器人本体和整机厂商 | 运动、安全、生命周期和整机能力 | 移动、操作、电源、安全与维护语义 |
| ROS、其他中间件与协议社区 | 图、消息、服务、Action、时间与坐标系 | Protocol Binding、Schema 映射和互操作约定 |
| 操作系统、容器、边缘与云平台 | 部署、身份、审计、远程运维和制品 | 运行时、策略、身份和可移植部署边界 |
| 仿真、数字孪生和数据平台厂商 | 场景、回放、合成数据和物理/仿真区分 | Simulation Binding、Episode 和证据交换格式 |
| 安全组件、测试实验室和认证机构 | 风险、停止、验证、审计和合规 | 安全边界、负向用例、证据要求和认证隔离 |
| 系统集成商与解决方案商 | 跨厂商组合、交付和现场维护 | 组合场景、兼容性缺口和迁移经验 |
| 研究机构与开源社区 | 新能力、可重复实验和参考实现 | RFC、原型、公共数据集和 conformance fixtures |
| 终端用户、运维与测试团队 | 可用性、可靠性、维护成本和责任边界 | 真实用例、验收约束、故障分类和优先级 |

任何单一参与方都不应控制 Core Contract。供应链上游提供底层事实，中游验证组合互操作，整机与集成商验证产品语义，终端用户和安全方验证规范是否能支持真实责任边界。

### 12.2 共识形成机制

ROLO 应建立公开、可追踪的规范流程：

1. **问题陈述**：先记录跨厂商重复出现的工程问题，不以既有实现预设答案；
2. **用例与证据征集**：至少收集多个供应链角色、多个目标平台的输入；
3. **公开 RFC**：同时提供人类可读语义、机器 Schema、正向/负向示例和安全边界；
4. **独立原型**：候选公共语义至少由两个无共同代码来源的实现验证；
5. **互操作测试**：用 golden cases、错误注入、版本回归和真实设备记录验证等价行为；
6. **分歧登记**：无法统一的差异进入 capability、extension 或 vendor binding，不强行写入核心；
7. **共识评审**：公开记录支持、反对、保留意见、利益冲突和最终理由；
8. **试行与采纳**：先发布候选 Profile，积累部署数据后再进入稳定版；
9. **持续治理**：通过兼容性窗口、废弃策略和 conformance suite 管理演进。

共识不要求所有厂商在每个问题上意见完全一致。可接受的共识是：主要异议已经被记录和处理，公共语义具有多方实现证据，保留差异有明确扩展点，且没有参与方因不采用某一厂商技术而被排除。

### 12.3 中立治理原则

- 规范、Schema、RFC、会议纪要、测试结果和版本历史应公开可获得；
- Core Contract 的治理席位应覆盖供应链不同环节，避免单一厂商或单一技术栈形成控制权；
- 参考实现与规范文本分离，ROLO 自身实现也必须接受同一 conformance suite；
- 投票权、维护权和商标/兼容性声明规则应透明，并公开利益冲突；
- 规范讨论只聚焦技术互操作、安全和用户价值，不交换价格、市场划分或其他竞争敏感信息；
- 厂商私有能力通过明确命名空间和扩展机制存在，不得伪装成公共核心语义；
- 兼容性标志应基于可重复测试结果，而不是厂商自我声明或付费成员身份；
- 中小厂商、开源项目、研究机构和终端用户应有低成本参与渠道。

### 12.4 三层标准化结构

标准化产物分为三层：

1. **Core Contract**：共同的身份、Schema、错误、风险、时间、版本和 conformance 规则；
2. **Domain Profiles**：移动底盘、传感器、机械臂、导航、电源、安全停止等领域公共语义；
3. **Protocol/Vendor Bindings**：ROS、OPC UA、厂商 SDK、CLI 和设备协议到 Domain Profile 的映射。

规范核心应聚焦稳定身份、输入输出、错误、风险、时间、单位、坐标系、生命周期和 conformance。厂商 Topic、SDK 名称、源码路径和单一机器人 Adapter 应留在可替换 binding 层。这样既保护厂商差异化能力，也防止上层应用被单一实现锁定。

### 12.5 分阶段演进

1. **内部参考规范**：稳定 Schema、版本、摘要、门禁和负向测试；建立公开问题清单和首批供应链顾问组；
2. **供应链工作组规范**：邀请各环节参与者共同选择 Domain Profile，完成至少两个独立实现和跨厂商互操作活动；
3. **开放参考规范**：发布规范文本、Schema、参考实现、conformance suite、兼容性结果和公开 RFC 流程；
4. **行业联盟规范**：建立中立治理、商标和认证规则，形成可持续的多方维护组织；
5. **正式标准提案**：在具备广泛采用、多厂商实施报告和安全边界共识后，向范围匹配的标准组织提交成熟的 Core Contract 与 Domain Profile。

进入下一阶段的依据不是 operation 数量或 ROLO 自身测试覆盖率，而是供应链代表性、独立实现数量、互操作成功率、未解决分歧、安全审查和真实部署反馈。

### 12.6 版本与兼容性治理

契约采用语义版本：文字澄清使用 PATCH，向后兼容扩展使用 MINOR，单位、风险、必填输入或行为语义变化使用 MAJOR。`RELEASED` 契约通过废弃和迁移窗口演进，不直接退回不成熟状态。

公共规范还应定义支持周期、兼容性矩阵、扩展命名空间、测试结果有效期和安全勘误通道。任何降低风险等级、数据分类或授权要求的变化，都必须接受跨角色安全评审，不能作为普通兼容优化合入。

## 13. 评价指标

ROLO 的价值不应只用“自动执行了多少命令”衡量。更合适的指标包括：

- 新成员理解机器人系统上下游所需时间；
- 从 `BLOCKED` 定位到可操作原因所需时间；
- 结论成功追溯到有效证据的比例；
- 对 operation 可用性、风险和边界判断的准确率；
- 两次运行之间关键差异的定位时间；
- 保留改动具备回滚和受影响回归证据的比例；
- 高风险意图在调用前被正确解释、拒绝或授权的比例；
- 相同问题在没有新证据的情况下被重复尝试的次数。
- 参与规范评审的供应链环节覆盖度与独立组织数量；
- 每个稳定 Domain Profile 的独立实现数和跨厂商互操作通过率；
- RFC 中保留异议、厂商扩展和安全问题的关闭周期；
- 第三方无需读取 ROLO 源码即可实现并验证兼容 Adapter 的成功率。

## 14. 词汇表

### Active Tool Catalog

某台机器人当前经过独立门禁的产品操作目录。包含完整产品词汇及每个 operation 的可用性、契约和 Adapter 绑定。它是运行时调用的权威入口。

### Adapt

三阶段生命周期的第一阶段。负责发现、Robot Wiki、目标 Adapter、State Graph、conformance、release 和 adapt handoff；不负责证明物理结果正确。

### Adapter

将 Canonical Operation 的稳定语义映射到目标 ROS、CLI、device 或厂商接口的机器人专属实现。

### Adapter Agent

在隔离工作区中读取有界证据、生成 Adapter 候选实现的 Agent。它不拥有门禁或发布权。

### Artifact

由 ROLO 生成、引用或保护的文件型制品。关键 Artifact 带 Schema、摘要、来源和访问边界。

### Binding

Canonical Operation 与目标 Adapter entrypoint、endpoint、类型和 Schema 之间的映射。

### Canonical CLI

由 Operation Contract 定义的统一命令形态。它表达产品意图，不暴露厂商私有调用细节。

### Canonical Operation

跨目标稳定的产品级操作标识，例如 `app.navigation.start`。它是词汇，不是某个目标能力已经可用的证明。

### Checkpoint

对 ROLO 控制面状态、配置引用、任务进度和证据索引的可恢复记录。除非契约明确说明，否则不意味着恢复真实机器人进程或运动。

### Conformance

实现对契约的符合性检查。Adapt 主要覆盖 Schema、Binding 和 Route；Behavior 与 Safety/acceptance evidence 属于后续阶段。

### Conformance Suite

用于验证独立实现是否符合公共规范的一组机器可执行测试、golden cases、负向用例和结果格式。ROLO 参考实现也必须接受同一套测试。

### Core Contract

跨领域共享的契约核心，定义 operation 身份、Schema、错误、风险、时间、版本和 conformance 规则，不包含单一厂商接口。

### Diagnose

第二阶段。围绕用户约束进行行为诊断、调参、回归、冻结配置和 diagnosis handoff。

### Discovery

对目标硬件、主机、Middleware 和 Application 的有界证据采集与静态分析。其输出是候选与观察，不是发布决策。

### Domain Profile

围绕移动底盘、传感器、机械臂、导航、电源或安全停止等领域形成的公共 operation 与语义集合。

### Episode

一次机器人执行的完整证据切片，用于回放、解释、比较和复现。

### Evidence

支持事实或结论的可追溯信息。应包含来源、时间、完整性、主体、限制和分类。

### Handoff

阶段间的结构化、摘要绑定交付物。下游必须重新验证，不能只相信路径存在。

### Independent Gate

由 ROLO 拥有、独立于 Agent 和 Adapter 的发布门禁。负责验证契约、绑定、route、包和 release 完整性。

### Operation Contract

Canonical Operation 的机器可校验规范，定义输入、输出、错误、风险、时间、单位、坐标系、状态变化和治理信息。

### Operation Workset

面向一次 Adapt 的只读查询视图，将 Registry、discovery candidate 和当前 release 联系起来。它不是发布目录。

### Provider

将目标系统的某类具体能力规范化为 ROLO 证据或操作的组件，例如 Hardware Evidence Provider 或未来 Observation Provider。

### Protocol/Vendor Binding

将 Core Contract 或 Domain Profile 映射到 ROS、OPC UA、CLI、设备协议或厂商 SDK 的可替换绑定层。

### Quiescence Lease

由受保护执行监督器签发、证明目标在指定时限内满足执行静止条件的绑定凭据。它不授予运动权限。

### Registry

ROLO 产品拥有的 Canonical Operation 完整词汇及治理元数据。

### RFC

面向供应链公开评审的规范变更提案，应同时说明问题、用例、机器 Schema、兼容性、安全边界、实现证据、异议和决策理由。

### Release

通过门禁并按摘要固化的目标 Adapter、Tool Catalog、State Graph 和相关制品集合。

### Robot Wiki

面向人的可编辑机器人系统知识库。它由证据生成但不等同于不可变机器证据。

### `robot_use`

Diagnose 阶段的多模态语义监督能力。它组合图像、遥测、任务状态和外部观察，返回事实、候选原因和限制；不拥有安全决策权。

### Route Evidence

关于目标 endpoint 是否存在的结构化证据。Route Evidence v2 支持 ROS topic/service/action、device 和 CLI，并可绑定类型、摘要、provider 与 runtime revision。

### State Graph

由 ROLO 基于门禁结果构建的状态、资源、operation 和 route 关系图。

### Verify

第三阶段。根据已接纳的验收约束执行正式回归、报告和证据打包；该阶段可选。

### `ACKNOWLEDGEMENT_ONLY`

写 operation 的结果语义：响应只表示请求被接受或拒绝，不表示物理动作完成、状态收敛或安全成立。

### `GATEABLE`

产品契约已足够完整，可以在具备目标 candidate、Adapter 和 route evidence 后进入门禁的生命周期状态。

### `RELEASED`

产品内部已发布并受兼容性治理的契约状态。它仍不等于某台机器人上的 operation 已可用。

### `VERIFIED`

必须结合对象理解。对 Tool 表示 Adapt 契约、绑定与 route 已门禁；对 Outcome 表示后续行为或验收结论已获得相应证据。

## 15. 文档权威顺序

当实现、生成物和说明文档存在差异时，按以下顺序处理：

1. 版本化 Schema、Operation Contract 和运行时门禁规则；
2. 与代码一起测试的结构化模型和 conformance 用例；
3. 本白皮书、架构和策略规范；
4. 操作指南、验收清单和配置说明；
5. 产品提案、特性计划和讨论草案；
6. 示例、评审样本和生成型参考文档。

低优先级文档不能覆盖高优先级事实。发现冲突时，应修正文档或显式记录开放问题，而不是在实现中隐式选择。

## 16. 结语

ROLO 试图建立的不是一个更会“操作机器人”的 Agent，而是一种更可靠的机器人软件开发方式：系统先被理解，能力先被契约化，证据先被保存，风险先被门禁，变化先被验证，然后知识才被沉淀。

它最终追求的循环是：

> **看懂系统 -> 明确意图 -> 安全执行 -> 观察结果 -> 解释差异 -> 修正系统 -> 回归验证 -> 沉淀知识。**

当每一次运行都完成这个闭环，下一次就不再是对同一个未知问题的重复尝试，而是在更高证据基础上的一次新运行。这就是 robot only loop once。

## 参考文档

- [三阶段架构](ARCHITECTURE.md)
- [自动发现](AUTODISCOVERY.md)
- [软件发现边界](SOFTWARE_DISCOVERY.md)
- [Canonical Operation 清单](CANONICAL_OPERATIONS.md)
- [Registry Operation 指南](REGISTRY_OPERATION_GUIDE.md)
- [Operation Contract 标准化路线](OPERATION_CONTRACT_STANDARDIZATION.md)
- [SENSITIVE 调用策略](SENSITIVE_INVOCATION_POLICY.md)
- [P0 Adapt 验收边界](P0_ADAPT_ACCEPTANCE.md)
- [`robot_use` 多源观察草案](ROBOT_USE_MULTISOURCE_OBSERVATION_DRAFT.md)
- [Web 可视化工作台产品方案](WEB_VISUALIZATION_PRODUCT_PROPOSAL.md)

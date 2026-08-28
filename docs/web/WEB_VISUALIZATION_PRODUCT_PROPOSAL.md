<!-- status: active; authority: reference; owner: docs maintainers; last_reviewed: 2026-08-28 -->

# rolo Web 可视化工作台产品方案

## 1. 产品判断

rolo 的 Web 端不应被定义为“机器人监控大屏”，也不应只是 CLI 的图形外壳。

rolo 已经拥有四类结构化资产：

1. 机器人 Wiki 与软硬件发现结果；
2. 294 个 canonical operations、Tool Catalog 与 Operation Contract；
3. `adapt -> diagnose -> verify` 三阶段门禁及其 handoff；
4. 可校验的运行制品、证据引用、哈希和审计记录。

因此 Web 产品最有价值的定位是：

> **面向具身机器人研发团队的证据驱动工作台：把“机器人是什么、现在能做什么、为什么失败、是否可以继续”放进同一个可追溯界面。**

建议产品名暂定 **rolo Workbench**，核心承诺是：

> **From symptom to evidence, from evidence to action.**

Web 端首先降低理解和协作成本，其次才承载操作。它不能越过机器人本机的安全控制、策略授权、急停和物理结果验证。

## 2. 核心用户与任务

| 用户 | 进入工作台时最想回答的问题 | 关键页面 |
|---|---|---|
| 新加入的研发工程师 | 这台机器人由什么组成，软件怎么连接，能力从哪里来？ | Robot Overview、Stack Map、Wiki |
| 算法/应用工程师 | 某能力是否可用，输入输出和前置条件是什么，失败在哪里？ | Capability Explorer、Operation Detail |
| 测试工程师 | 这次运行哪里异常，依据是什么，与基线相比发生了什么？ | Episode Studio、Evidence Timeline、Compare |
| 现场/运维工程师 | 当前阶段被什么阻塞，下一步需要谁处理？ | Fleet、Lifecycle、Blocker Inbox |
| 安全/审核负责人 | 谁在什么时间调用了什么，高风险动作为何被允许或拒绝？ | Audit Center、Authorization Detail |

第一版优先满足前三类用户，因为当前实现最成熟的资产集中在 discovery、adapt、catalog、state graph 与可追溯 artifact。

## 3. 产品对象模型

界面不应直接暴露文件目录，而应围绕六个稳定产品对象组织：

```text
Robot
├── Identity & Runtime Health
├── Knowledge Snapshot
│   ├── Wiki
│   ├── Hardware / Linux / Middleware / Application
│   └── Dependency & Unknowns
├── Capability
│   ├── Canonical Operation
│   ├── Contract
│   ├── Observed Binding
│   └── Availability / Risk / Policy
├── Lifecycle Run
│   ├── Discover
│   ├── Adapt
│   ├── Diagnose
│   └── Verify
├── Episode
│   ├── Command / Task
│   ├── Telemetry / Frames / Events
│   ├── Supervision / Diagnosis
│   └── Outcome / Regression
└── Evidence
    ├── Artifact Reference
    ├── Provenance
    ├── Digest
    └── Audit Event
```

`artifact://...`、SHA-256、schema version 等是可信度来源，但默认作为“证据详情”展示，不应成为用户理解产品的第一层语言。

## 4. 信息架构

建议采用“Fleet 全局层 + Robot 工作层 + Evidence 抽屉”的三层结构。

### 4.1 全局导航

- **Fleet**：机器人列表、健康度、生命周期阶段、阻塞和最近活动；
- **Runs**：跨机器人运行历史、对比、失败聚合；
- **Audit**：敏感读取、写操作、R3 授权的允许/拒绝记录；
- **Contracts**：产品级 canonical operation registry 与版本治理；
- **Settings**：连接、权限、留存、显示偏好。

### 4.2 单机器人导航

- **Overview**：当前态势与下一步；
- **Stack Map**：全栈关系图；
- **Capabilities**：能力、契约和可用性；
- **Lifecycle**：三阶段门禁和每次运行；
- **Episodes**：运行回放、诊断和比较；
- **Wiki**：面向人的知识页面。

### 4.3 全局证据抽屉

任何状态、警告、结论或图节点都能打开统一证据抽屉：

- “这个结论来自哪里”；
- 观察时间、来源和置信度；
- 对应 probe、candidate、contract 或 artifact；
- schema version 与 digest 校验状态；
- 相关运行和上下游 handoff；
- 可复制的 canonical CLI，仅作为复现路径而非默认交互。

这会形成 rolo 最关键的交互原则：**所有结论都可以下钻到证据，所有证据都能回到上下文。**

## 5. 四个核心工作区

## 5.1 Robot Overview：不是 KPI 大屏，而是“下一步决策页”

首屏只回答五个问题：

1. 连接是否健康；
2. 当前可信知识的新鲜度如何；
3. 生命周期走到哪一步；
4. 现在最大的阻塞是什么；
5. 最近一次有意义的变化是什么。

推荐布局：

- 顶部：机器人身份、环境、在线状态、最后观察时间；
- 左侧主区域：`Adapt -> Diagnose -> Verify` 阶段轨道，每阶段显示状态、负责人语义、产物与 blocker；
- 右侧：最多 5 条“需要处理”，按安全性和阻塞程度排序；
- 下方：最近运行、能力覆盖变化、依赖变化、最近审计事件。

不要用几十个小卡片制造“看起来很实时”的噪声。rolo 当前更重要的是阶段可信度与证据完整性，而不是毫秒级遥测。

## 5.2 Stack Map：把机器人 Wiki 变成可探索的系统地图

Stack Map 使用四层泳道表达：

```text
Hardware -> Linux -> Middleware/ROS -> Application
```

节点代表板卡、传感器、设备、服务、进程、包、节点、Topic、Service、Action 和应用；边代表运行、依赖、发布、订阅、调用、坐标关系和能力绑定。

关键交互：

- 按层、状态、证据来源、置信度过滤；
- 搜索一个组件后只保留一跳/两跳依赖，避免“毛线团”；
- 点击节点显示属性、发现来源、相关能力、风险和未知项；
- “Explain path”：选择两个节点，解释它们通过什么关系连接；
- “Diff snapshot”：比较两次 discovery，突出新增、消失、版本变化和证据退化；
- 与 Wiki 双向联动：图节点跳到 Wiki 段落，Wiki 中的实体可在图上定位。

视觉语义必须稳定：

- 绿色：已观察且通过门禁；
- 蓝色：已观察但仍待适配/验证；
- 黄色：部分发现、推断或存在限制；
- 红色：失败、冲突或安全阻塞；
- 灰色虚线：声明存在但目标运行时未观察到。

颜色不能是唯一信息编码，必须配合图标、标签和边样式。

## 5.3 Capability Explorer：294 个操作不是列表，而是一张能力覆盖地图

默认视图按领域展示能力覆盖：Hardware、Linux、Middleware、Application，并在下一层按对象/动词分组。

每个 operation 行至少显示：

- lifecycle：DRAFT / GATEABLE / RELEASED / DEPRECATED；
- applicability：是否适用于当前机器人；
- registration / availability：是否绑定到已门禁 adapter；
- access 与 risk：read/write、R0-R3；
- data classification：PUBLIC / INTERNAL / SENSITIVE / SECRET；
- binding evidence 与最近验证时间；
- paired / replacement / compensation operation。

Operation Detail 推荐分为五个页签：

1. **Overview**：一句话用途、当前可用性、风险和前置条件；
2. **Contract**：输入/输出 schema 自动表单化，单位、坐标系、时间语义；
3. **Binding**：该机器人上的真实 endpoint、观察证据与 adapter entrypoint；
4. **Evidence**：conformance、gate、限制和 digest；
5. **History**：契约版本、可用性和调用审计变化。

第一版不开放任意调用。后续增加 **Operation Console** 时遵循渐进授权：

- R0 read：确认后执行；
- R1/R2 read 或 write：显示影响范围、策略检查与审计提示；
- R3：必须走外部 capability authorizer，Web 端只展示 challenge/结果，不能自授予；
- SECRET：通用界面永不展示 payload；
- 写操作必须展示 resource lock、最大时长、取消能力、补偿/回滚路径；
- acknowledgement 不能显示成“任务成功”，必须与物理结果证据分离。

## 5.4 Episode Studio：rolo 最终应该形成的核心差异化界面

Episode Studio 将一次任务的计划、命令、机器人状态、遥测、视频帧、Agent 事件、诊断和回归结果对齐到同一时间轴。

推荐布局：

- 左上：视频/关键帧，多相机可切换；
- 左下：任务步骤与状态转换；
- 中部：共享时间轴，包含命令、告警、遥测峰值、Agent 判断、配置变化和 checkpoint；
- 右侧：当前时间点的结构化证据、候选原因、置信度与建议检查；
- 底部：Expected vs Observed、约束判定和最终 outcome。

核心交互：

- 点击异常自动定位前后时间窗；
- 粗到细缩放，保留相同事件上下文；
- 将 `robot_use` 的 observed facts 和 candidate causes 贴回具体帧和时间段；
- 同一测试的两次运行叠加比较；
- 参数或软件版本变化自动成为对比维度；
- 每个诊断结论标明“观察事实”“模型推断”“人工确认”，防止混为一谈；
- 导出一个不包含 SECRET 内容的 evidence package 或审核链接。

当前代码尚未实现完整 Episode 模型和 Diagnose 闭环，因此该工作区应作为第二阶段产品目标，不能在第一版假装已有实时数据能力。

## 6. 三个横向能力

### 6.1 Blocker Inbox

将 pipeline assessor、discovery warning、missing dependency、gate error、policy denial 和人工待办统一成结构化 blocker：

- 影响哪个机器人/阶段/能力；
- 是事实、风险还是缺少授权；
- 谁最适合处理；
- 推荐下一步和复现入口；
- 解除 blocker 需要出现什么证据。

这样 Overview 不只显示“BLOCKED”，而能告诉用户为何阻塞以及如何解除。

### 6.2 Snapshot Compare

比较对象不是原始 JSON，而是领域变化：

- 机器人组件、版本、节点、Topic、依赖的新增/消失；
- capability applicability 与 availability 变化；
- contract digest 或 adapter release 变化；
- 生命周期阶段、blocker 和证据完整性变化；
- Episode 的配置、行为和结果变化。

### 6.3 Audit Center

按时间、机器人、operation、principal、策略域、允许/拒绝过滤。详情只展示规范化元数据和原因，不泄露输入输出 payload。对 R3 展示 authorization ID、绑定的 operation/input digest 与有效期，不把 capability 本身暴露为可复制凭据。

## 7. Web 端架构建议

### 7.1 部署模型

坚持 rolo 现有的本机优先边界：

```text
Browser
  -> SSH tunnel / authenticated reverse proxy
  -> rolo Web API on robot or trusted control host
  -> read models / policy-enforced command gateway
  -> hash-verified artifacts + active release + audit log
```

- 默认继续绑定 loopback；
- 远程访问通过 SSH tunnel 或部署方提供的认证反向代理；
- 浏览器不直接读取 artifact 文件系统；
- 浏览器不持有 adapter 凭据、策略文件或 R3 authorizer 能力；
- 所有命令仍通过 runtime 的统一 policy enforcement 与 audit；
- 多机器人部署时由可信 control host 聚合只读状态，不绕开每台机器人的本地门禁。

### 7.2 前端技术形态

建议使用 React + TypeScript 的单页应用，重点库按能力选择：

- 关系图：React Flow 或 Cytoscape；
- 时间轴与大数据列表：Canvas/WebGL 图表 + virtualization；
- JSON Schema 表单：用于 Operation Contract 输入，但必须增加单位、坐标系、风险说明和业务校验；
- Markdown：Wiki 阅读与受控编辑；
- Server-Sent Events：运行事件和状态更新；真正需要双向低延迟控制时再引入 WebSocket。

不建议第一版直接让前端解析几十种 artifact schema。后端应提供稳定的 UI read model，隔离 artifact 版本演进。

### 7.3 建议新增的 API

现有 `/health`、`/v1/robots`、`/v1/robots/{id}/pipeline`、agentd discovery/tools/pipeline 可支撑概念验证，但不足以支撑完整工作台。

第一版建议增加只读 API：

```text
GET /v1/robots/{id}/overview
GET /v1/robots/{id}/wiki
GET /v1/robots/{id}/topology
GET /v1/robots/{id}/topology/diff?from=&to=
GET /v1/robots/{id}/capabilities
GET /v1/robots/{id}/capabilities/{operation}
GET /v1/robots/{id}/runs
GET /v1/robots/{id}/runs/{run_id}
GET /v1/robots/{id}/runs/{run_id}/events        # SSE
GET /v1/evidence/{opaque_id}
GET /v1/audit
```

后端规则：

- 用 opaque evidence ID 替代浏览器传入任意 artifact path；
- 解析 artifact ref 时继续执行现有的越界防护；
- 响应带 `observed_at`、`freshness`、`source_kind`、`confidence` 和 `integrity_status`；
- 明确区分 `declared`、`observed`、`gated`、`diagnosed`、`verified`；
- 列表 API 必须分页、过滤并限制响应体；
- payload 中的路径、日志正文和配置内容按 data classification 脱敏或拒绝。

后续写 API 只提供命令意图，不允许前端提交自由 shell：

```text
POST /v1/robots/{id}/operations/{operation}/prepare
POST /v1/robots/{id}/operations/{operation}/invoke
POST /v1/invocations/{invocation_id}/cancel
```

`prepare` 返回规范化输入摘要、策略结果、影响说明、锁、时限和所需授权；`invoke` 必须绑定 prepare 生成的短期 intent，服务端再次校验契约、策略和输入摘要。

## 8. MVP 范围与演进

### Phase 0：信息架构验证（1-2 周）

- 使用 fixture 和现有 schema 做点击原型；
- 验证 Overview、Stack Map、Capabilities、Lifecycle 四个页面；
- 与 3-5 名机器人研发/测试用户完成任务走查；
- 暂不连接真实写操作。

### Phase 1：只读可信工作台（4-6 周）

- Fleet 与 Robot Overview；
- 三阶段 pipeline 与 blocker；
- Wiki 阅读；
- discovery 拓扑与 snapshot diff；
- Capability Explorer、contract 与 binding evidence；
- Adapt run、gate、handoff 和 artifact 证据详情；
- SSH tunnel 场景下的本地部署。

成功标准：工程师无需查找 artifact 目录或询问项目作者，就能在 5 分钟内回答“当前卡在哪里、某能力能否使用、依据是什么”。

### Phase 2：Episode 与诊断工作区（6-10 周，依赖后端能力）

- Episode 数据模型与摄取；
- 多源时间同步；
- 视频/遥测/命令/状态/Agent 事件时间轴；
- `robot_use` 事实与推断标注；
- baseline compare 与诊断 handoff。

### Phase 3：受控操作台

- schema 驱动输入；
- prepare/invoke 两步交互；
- read、R1/R2 write、R3 的分级授权；
- cancel、compensation、rollback 与锁状态；
- 审计中心和正式 Verify 证据包。

不建议在 Phase 1 加入遥控、自由终端、自由文件浏览和任意命令。这些能力会显著扩大安全边界，却不会验证 rolo 的核心产品价值。

## 9. 产品设计原则

1. **证据优先于结论**：结论必须能下钻，推断必须显式标注；
2. **状态必须带时间**：不展示没有 `observed_at` 或 freshness 的“当前状态”；
3. **未知是合法状态**：UNKNOWN、UNOBSERVED、PARTIAL 不伪装成离线或失败；
4. **门禁不等于物理成功**：conformance、endpoint observed、acknowledgement、diagnosed outcome、verified outcome 分层展示；
5. **风险就地呈现**：用户在点击动作之前看到分类、影响、时限、取消和回滚；
6. **渐进披露**：默认使用产品语言，证据抽屉再展示 schema、digest、CLI 和原始字段；
7. **对比优先于绝对值**：机器人问题经常来自“这次和上次哪里不同”；
8. **安全边界服务端拥有**：前端永远不是策略、授权或物理安全的最终判定者。

## 10. 关键指标

不要用页面访问量评价产品。建议跟踪：

- Time to system understanding：新成员找到一个组件上下游的时间；
- Time to blocker explanation：从看到 BLOCKED 到定位可操作原因的时间；
- Evidence trace success：用户能否从结论到达有效证据；
- Capability answer accuracy：用户判断 operation 可用性、风险和边界的正确率；
- Run comparison time：找到两次运行关键差异的时间；
- Unsafe intent prevention：高风险操作在调用前被正确解释、拦截或授权的比例；
- CLI fallback rate：完成核心任务时仍需手工查找文件或执行只读 CLI 的比例。

## 11. 最终建议

第一版聚焦 **“Robot Digital Twin for Engineers”**，交付 Overview、Stack Map、Capability Explorer、Lifecycle/Evidence 四件套。它们与现有成熟的 discovery/adapt 资产吻合，能最快证明 Web 端价值。

Episode Studio 是长期最有差异化的核心，但它依赖 Diagnose、运行事件和时间同步模型成熟，应该先定义数据契约、后做完整体验。受控操作台则放在可信只读模型和策略链路稳定之后。

这个顺序可以避免把 rolo 做成又一个漂亮但不可信的机器人仪表盘，并逐步形成真正独特的闭环：

> **看懂系统 -> 找到证据 -> 判断能力 -> 观察运行 -> 解释异常 -> 安全地采取行动 -> 验证结果。**

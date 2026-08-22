# P4 Adapt 启发式 Agent、Registry Core 与 Verified Tool Gateway 改版计划

## 0. 决策与启动结论

本轮改版采用“启发式 Agent 提案、Rolo 确定性裁决、Verified Operation 工具化”的分层方案：

1. Adapt Agent 负责有界自主发现、现有 Operation 映射和 Wiki 叙述；Adapter 编码继续由
   现有 Adapter Executor 承担，不在首版包装成独立技能；
2. Agent 的输出始终是提案或候选，不是机器事实、Registry 变更或发布授权；
3. Registry 继续拥有完整 Operation 词汇表，独立 conformance gate 继续决定能否进入
   Active Tool Catalog；
4. 只有 release 中状态为 `VERIFIED` 的 Operation，才能通过 Tool Gateway 提供给后续
   Diagnose/Verify Agent；
5. Registry Core 本轮以完整 294 项 Operation 为权威基线先行开发；Contracts 不枚举
   Operation，因此兼容未来数量变化，但约 140 项精简不作为 P4 启动或合入前置；
6. 所有新技能统一使用 `rolo-` 前缀。

这允许启发式能力加速“不知道目标工程有什么”的阶段，同时保留当前架构中最重要的安全
边界：Agent 不能用语言推断替代现场证据，也不能自我验证后直接获得执行权限。

## 1. 当前基线

### 1.1 已具备的能力

- Discovery 已能从确定性探针生成 `DISCOVERED_UNVERIFIED` 候选；
- Operation eligibility 要求 Registry 生命周期允许、路由已声明且目标路由有精确观测；
- Conformance gate 会独立验证期望 Operation、契约覆盖、路由证据及 Catalog 完整性；
- Adapter Runtime 只加载哈希验证通过的 release，并只调用 `VERIFIED` 工具；
- P1 已提供 Target Operation Slice、分页 workset/Wiki 检索和有界 Agent 上下文；
- Wiki Agent 已是低/中置信度的只读辅助能力，不具备发布权。

### 1.2 当前缺口

- Discovery 的语义映射仍以少量固定规则为主，难以覆盖新机器人工程的命名和组织方式；
- Adapter Agent 的大型提示词与执行器耦合，难以独立版本化、测试和复用；
- Agent 还没有统一的“证据引用式 Operation 提案”契约；
- `agentd` 目前只提供工具列表，没有面向后续 Agent 的受控调用会话；
- Diagnose/Verify handoff 尚未冻结到具体 release、Catalog 哈希和允许工具集合；
- Registry Core 需要先完成 294 项下的身份摘要、契约覆盖、Catalog 完整性和兼容门；未来
  如果精简到约 140 项，仍需另行冻结保留清单、兼容清单和迁移门。

## 2. 目标架构与信任边界

```text
确定性只读探针
      |
      v
rolo-adapt-discovery -----> 有界探针计划/证据缺口提案
      |                     （编排器执行白名单探针）
      v
冻结的 Discovery Evidence
      |
      v
rolo-operation-mapping ---> AgentOperationProposal
      |                     （只能引用现有证据与 Registry Operation）
      v
确定性 Proposal Validator --> OperationCandidate: DISCOVERED_UNVERIFIED
      |
      v
Adapter Executor ----------> Adapter Bundle + 本地静态 conformance 结果
      |
      v
Rolo 独立 conformance / promotion / release
      |
      v
Verified Active Tool Catalog
      |
      v
Tool Session + Policy Gateway + Adapter Runtime
      |
      v
Diagnose / Verify / 后续 Agent
```

不可跨越的边界：

- Agent 不得创建、删除、重命名 Registry Operation；
- Agent 不得直接生成权威 `RouteEvidence`、硬件存在性或运行成功事实；
- Agent 不得把自身生成的 Adapter 测试结果标记为最终 Verified；
- Agent 不得生成或修改最终 Active Tool Catalog；
- Tool Gateway 不得调用会话中未冻结、未 Verified 或策略未授权的 Operation；
- Wiki 内容不得反向提升 Operation eligibility。

## 3. Adapt 技能体系

技能按单一职责拆分，不建立只做转发的总路由技能。首版只保留三个技能。工作流由 Adapt 编排器决定阶段，技能
只负责严格输入/输出契约内的启发式工作。

### 3.1 `rolo-adapt-discovery`

**职责**：阅读已采集的工程结构、配置、manifest、接口描述和失败记录，找出证据缺口，提出
下一轮只读发现动作。

**输入**：

- `robot_id`、`discovery_id`、目标指纹；
- 当前证据索引及摘要，不直接注入全部原始文件；
- 可调用的白名单 probe/query 定义；
- 时间、轮次、结果字节数和失败次数预算。

**输出**：`rolo-adapt-discovery-plan/v1`

- 需要调用的白名单 probe/query ID；
- 参数、预期证据类型和选择理由；
- 未知项、停止条件和剩余预算；
- 每个动作的风险等级，只允许默认无副作用的 R0 发现动作。

**禁止**：任意 shell、启动 launch 文件、写配置、控制硬件、把推断写成观测事实。

**执行方式**：技能只提案；编排器校验动作 ID、参数 schema 和预算后执行，再把结果写入
机器证据。Agent 失败时保留已有确定性 discovery 结果。

### 3.2 `rolo-operation-mapping`

**职责**：将冻结的 Discovery Evidence 映射到现有 Registry Operation，解决不同工程中
包名、topic、service、endpoint 和 executable 命名不一致的问题。

**输入**：

- 冻结的 discovery/evidence 索引；
- Target Operation Slice，而不是完整 Registry；
- 候选 Operation 的精确契约、治理分类和路由规则；
- Wiki 检索结果，仅作为辅助线索。

**输出**：`rolo-operation-proposal-bundle/v1`

- `operation`：必须精确匹配已有 Registry ID；
- `evidence_refs`：必须能在当前 discovery 中解析；
- `route_resource_ids`、`executable_ids`、`hardware_resource_ids`；
- `confidence`：首版只允许 `LOW` 或 `MEDIUM`；
- 简短映射理由、反证和需要的 verification；
- 未映射能力与 Registry 缺口建议，缺口建议不自动新增 Operation。

**禁止**：创建新 Operation、构造不存在的 route、声明运行成功、给出 `VERIFIED` 结论。

### 3.3 Adapter Coding 不设独立技能

首版不创建 `rolo-adapter-coding`。Adapter 编码是 Adapt 的核心执行步骤，而不是用户可独立
选择的启发式任务；现有 Executor 已经拥有隔离工程、bundle/package 契约、预算、静态测试和
独立 gate 接口。再增加一层技能会复制输入契约、扩大版本组合，并容易让“编码规则”和
“发布权限”边界分散。

本轮只做以下重构：

- 将大型硬编码提示词拆为 Executor 内部、可版本化的 `AdapterCodingPolicy`；
- 输入仍只包含 eligible Operation、精确 contract、已验证 route/resource 和 Provider SPI；
- 输出仍是 Adapter bundle/package、本地静态 conformance 和 manifest；
- 最终 Tool Catalog、promotion 和 release 仍由 Rolo 独立完成。

只有出现以下证据时，才把它提升为 `rolo-adapter-coding` 技能：

- 至少两个外部 Agent/IDE 需要独立调用同一编码工作流；
- 编码策略需要脱离 Rolo Executor 分发和版本化；
- 独立技能能减少而不是复制 schema、沙箱和权限实现。

### 3.4 `rolo-wiki-authoring`

**职责**：从现有 `robot-wiki-heuristics` 迁移并拆清“确定性事实表”和“Agent 叙述”，为
后续适配复用可追溯经验。

**输入**：

- 已冻结 evidence、proposal、conformance 和 release 摘要；
- 确定性生成的表格骨架；
- 允许引用的证据 ID 和脱敏规则。

**输出**：主 schema 改为 `rolo-wiki-insights/v1`，兼容解析器在一个迁移周期内继续接受
`robot-wiki-insights/v1`，并新增可选的：

- 发现路径与失败模式摘要；
- Operation 映射理由与反证；
- Adapter 约束、已知局限和复验条件；
- 与上一版本的差异；
- 每条陈述的 evidence refs、置信度和作者技能版本。

**禁止**：覆盖确定性事实表、写入密钥/设备隐私数据、通过 Wiki 改变 eligibility 或 release。

### 3.5 技能目录和版本约束

```text
skills/
  rolo-adapt-discovery/
    SKILL.md
    references/output-schema.md
  rolo-operation-mapping/
    SKILL.md
    references/output-schema.md
  rolo-wiki-authoring/
    SKILL.md
    references/output-schema.md
```

`robot-wiki-heuristics` 在一个兼容周期内保留只读 fallback 和弃用提示；调用方切换到
`rolo-wiki-authoring` 并通过 shadow 比较后再删除旧目录。其他两个技能是新增项，不设置旧名。

每个 `SKILL.md` 必须：

- 描述精确触发条件和非目标；
- 引用由代码模型导出的严格 schema，避免在多个技能中复制契约；
- 明确预算、停止原因、失败回退和禁止权限；
- 返回可机器校验的 JSON，不允许 placeholder 或额外字段；
- 将技能版本、模型标识和输入 artifact hashes 写入产物 provenance。

## 4. Operation 提案契约与确定性校验

### 4.1 新模型

建议增加：

```text
AgentOperationProposal
  operation
  evidence_refs[]
  route_resource_ids[]
  executable_ids[]
  hardware_resource_ids[]
  confidence
  rationale
  counter_evidence[]
  requested_verification[]
  skill_name / skill_version / model_id

OperationProposalBundle
  schema_version
  robot_id / discovery_id / target_fingerprint
  registry_sha256
  proposals[]
  unmapped_capabilities[]
  unknowns[]
  budgets / metrics / provenance
```

Proposal 不直接携带新建的权威 `RouteEvidence` 对象，只能通过 ID 引用已有证据。

### 4.2 Proposal Validator

确定性校验器负责：

1. 校验 robot、discovery、target fingerprint 和 Registry 哈希身份；
2. 确认 Operation 存在于当前 Registry 和 Target Operation Slice；
3. 确认全部 evidence/resource/executable ID 能在冻结 artifact 中解析；
4. 根据现有规则重新计算 route match，不信任 Agent 给出的匹配结论；
5. 去重并报告冲突，不以较高语言置信度覆盖机器反证；
6. 只物化 `DISCOVERED_UNVERIFIED` 候选；
7. Agent 超时、schema 错误或无有效提案时，回退到现有确定性候选路径。

### 4.3 Contracts 对 294/约 140 项 Registry 的兼容

Contracts 可以与 Registry Core 同步开发。`AgentOperationProposal`、`OperationProposalBundle`
和 `ToolSessionDescriptor` 不把 Operation 列表生成为 `Literal`/enum，也不依赖固定数量；
Operation ID 是受长度和格式约束的 opaque canonical ID，是否存在由注入的 Registry 解析器
确定。

兼容边界如下：

- schema 同时接受当前 294 项 Registry 和目标约 140 项 Registry 生成的合法 artifact；
- artifact 必须携带 `registry_version`、`registry_sha256` 和适用时的 contract hashes；
- Validator、release 和 Tool Session 只接受与当前活动 Registry 精确同 hash 的 artifact；
- “兼容两种规模”只表示共用同一 schema/代码，不表示 294 与约 140 的 release 可以交叉调用；
- Contracts worktree 维护 294 基线 fixture 和约 140 投影 fixture，但不修改 Registry、contract
  YAML、governance 或生成文档；
- Registry Core 冻结后，只替换目标 fixture/hash 并运行兼容矩阵，不修改已经冻结的字段语义。

## 5. Verified Operation 交给后续 Agent

### 5.1 Tool Session

后续 Agent 不直接读取全局 Runtime，也不使用“最新 release”这种漂移引用。每次 handoff 创建
冻结的 `ToolSessionDescriptor`：

- `robot_id`、`release_id`、Catalog hash、State Graph hash；
- 允许的 Operation 子集及 contract hashes；
- caller/stage、风险上限、调用/时间/结果字节预算；
- 创建时间、过期时间和策略版本；
- session nonce 与完整 artifact provenance。

### 5.2 Tool Gateway 首版范围

- 只开放已 Verified、只读、低风险 R0/R1 Operation；
- `list` 返回会话内工具，不返回全局 Catalog；
- `invoke` 再次验证 session、Operation、schema、策略、release 新鲜度和目标身份；
- Adapter Runtime 仍是唯一执行器；
- 每次调用及结果均写入审计 evidence/Episode；
- 超时、取消、并发和结果截断有统一语义。

写入、运动和硬件控制不进入首版。它们需要单独加入外部授权、quiescence、取消/急停、前后置
条件验证和设备级测试，不能仅靠 Operation 已 Verified 放行。

## 6. Registry Operation 数量变化的影响

### 6.1 当前测量基线

当前代码及 Wave 1 Registry Core 均以 294 个 Operation 为权威基线。本轮先稳定完整词汇、
identity/hash、contract/governance 覆盖和 Catalog 行为，不在并行开发期间删除 Operation。

| 维度 | 数量 |
|---|---:|
| built-in | 62 |
| GATEABLE | 232 |
| control / hw / linux / middleware / ros / app | 13 / 40 / 63 / 3 / 38 / 137 |
| PRODUCT_BUILTIN / TARGET_ADAPTER | 33 / 177 |
| AGENT_NATIVE / PLATFORM_SPECIFIC | 73 / 11 |

现有 artifact 的近似规模：

| Artifact | 294 项当前规模 | 140 项线性估算 | 预计减少 |
|---|---:|---:|---:|
| 完整 Registry JSON | 535 KB | 255 KB | 52% |
| Contract YAML | 256 KB | 122 KB | 52% |
| Governance ledger | 110 KB | 53 KB | 52% |
| 生成的 Operation Contract 文档 | 546 KB | 260 KB | 52% |

源码侧 contract + governance 的直接线性成本约为 1.2 KB/Operation；实际维护成本更高，因为
每个 Operation 还会进入 schema、文档、Catalog 完整性、release digest 和回归测试。

140 项估算只保留为未来容量规划，最终大小取决于保留 Operation 的 contract 复杂度。Registry
缩减对 Agent prompt 的收益小于 52%，因为当前 Target Operation Slice 已经避免完整注入；它
不是本轮 Contracts、Skills、Proposal、Gateway 或 Downstream 开发的阻塞条件。

### 6.2 对本方案的影响模型

| 变化 | Agent 上下文 | 构建/校验 | 治理与兼容性 | 方案处理 |
|---|---|---|---|---|
| 维持 294 | Slice 下保持有界 | 当前量级 | 无删除迁移；身份和覆盖可先稳定 | P4 当前权威基线 |
| 294 → 约 140 | Slice 下只小幅下降 | Catalog/文档约减半 | 154 项左右的旧引用迁移是主成本 | 后续独立 RFC，不阻塞 P4 |
| 维持 130–150 | 上下文稳定 | 明显低于当前量级 | 审核边界清晰 | 未来可选预算带 |
| 新增 1–12 | 基本不变 | 线性小幅增加 | 每项均需契约与治理决定；摘要失效 | 独立 Registry RFC |
| 再增长到 200+ | Slice 下仍有界 | Catalog/完整性 O(N) 增加 | 重新审视 Core 选择标准 | 不自动放宽预算带 |
| 新增约 1000 | 禁止完整注入提示词 | Registry/Catalog 增加约 2–3 MB | 人工治理不可接受 | 分页、分片和多层 Registry 另案 |
| 删除/重命名 | Slice 可控 | 摘要和 release 全部重算 | 兼容别名、旧 Wiki/release 迁移最贵 | 非紧急不做；单独 RFC |

关键结论：P4 可以并且应当先在 294 项上开发。Contracts 通过数量无关 schema 与精确
`registry_version + registry_sha256` 绑定隔离未来变化；从 294 精简到约 140 需要发布新的
Registry identity 和迁移规则，但无需推翻 Proposal 或 Tool Session 字段语义。

### 6.3 Registry 变更触发门

只有同时满足以下条件，才允许从“缺口建议”进入 Registry 变更：

1. 至少两个不同目标工程出现同一通用语义缺口，或现有 Operation 明确无法表达；
2. 缺口不是厂商、仓库或包名特有概念；
3. 已给出 contract、风险等级、execution class、Provider 边界和验证方法；
4. Governance ledger 能保持对 Registry 的精确一对一覆盖；
5. 已评估对旧 release、Wiki、别名和下游 Tool Session 的迁移影响。

LeRobot 首轮适配先映射到保留的通用 Operation。数据集采集、策略训练/推理等确有缺口时，也应
抽象为跨工程语义，而不是使用 `lerobot.*` 命名。

### 6.4 未来 294 → 约 140 的迁移规则

保留项必须至少满足一项：进入 P0/P4 纵向闭环、已有真实 route/Adapter、属于必要的安全与
证据基础设施、或能被两个以上不同工程以同一语义验证。仅有远期愿景、与具体平台强绑定、
重复表达或当前没有验证路径的项移出活动 Registry。

移出项不立即物理消失：

- 写入版本化 `legacy-operation-dispositions`，记录旧 ID、原因和替代项；
- 旧 release 可审计读取，但不得用已移出 Operation 创建新的 Tool Session；
- 不在同一波次重命名保留项，避免把删除和 rename 风险叠加；
- 精确覆盖测试届时从 294 改为约 140 活动项 + 全部 legacy disposition；
- Registry、contract、governance、schema、Catalog fixture、Wiki 引用和 release migration 必须
  在同一 worktree 内原子更新。

## 7. 分阶段实现与改动量

### 7.1 Wave 0：共同设计基线（本提交）

- 以远端 Python/CI/LeRobot 分支为代码父基线；
- 提交本计划，冻结 294 项当前基线、三个技能、Tool Gateway 边界和 worktree 所有权；
- 不在 Wave 0 修改 Registry、Discovery、eligibility、Catalog 或 release 行为。

### 7.2 Wave 1：全部 worktree 并行开发（约 1–3 周）

- Registry Core 在完整 294 项上稳定 identity/hash、contract/governance、Catalog 和覆盖测试；
- Contracts 新增 Proposal/Bundle/Tool Session schema 和 Validator 接口，不枚举 Operation，
  使用真实 294 基线 + 约 140 合成投影双 fixture；
- Skills、Proposals、Tool Gateway、Downstream Agents 均从 Wave 0 创建独立 worktree，按文件
  所有权同步开发；
- 下游 worktree 使用 Contracts draft 接口或本地 fixture，不复制 Registry，不提前获得发布权；
- 并行开发不改变顺序集成门，跨分支接口通过提交 hash 显式同步。

### 7.3 Wave 2：顺序集成与启发式 shadow（约 2–3 周）

- 建立三个 `rolo-` 技能、严格输出契约和离线 fixture；
- Discovery 接入计划提案、Operation proposal artifact 和确定性 Validator；
- Adapter Executor 使用内部 `AdapterCodingPolicy`，保持 Bundle/conformance 接口兼容；
- 先 shadow 比较，不影响现有候选和发布结果。

### 7.4 Wave 3：只读 Verified Tool Gateway（约 1–2 周）

- 增加冻结 Tool Session、会话内 list/invoke 和策略校验；
- Diagnose/Verify handoff 绑定 release/Catalog/State Graph 哈希；
- 只读 R0/R1 Operation 接入 Adapter Runtime 并写入审计 evidence。

### 7.5 后续：写入/运动能力（额外约 3–5 周）

- 外部授权、设备锁、quiescence、取消/急停；
- 前后置条件与独立机器验证；
- 真机失败恢复和安全测试。

不设置独立 Coding 技能预计减少约 5–8 个技能/胶水/测试文件和 0.5–1 周；本轮保持 294 项，
不计入未来精简迁移的 1–2 周。只读 MVP 合计预计改动 5,000–8,000 行、25–40 个文件、4–6 周/
单工程师；含写入/运动和完整下游 Agent 执行器的方案约 8,000–13,000 行、30–50 个文件、
7–11 周。多 worktree 可以缩短多人协作的日历时间，但不降低总工程量和顺序集成成本。

## 8. Worktree 设计

### 8.1 集成基线

| 项目 | 建议值 |
|---|---|
| 集成分支 | `codex/adapt-heuristic-agent-integration` |
| 集成目录 | `C:\Users\zarch\Desktop\robot_loop`（当前共同基线 worktree） |
| 代码父基线 | `origin/codex/p0-python-ci-lerobot@e1dd27c` |
| 补入提交 | 当前唯一分叉提交 `de78a27`（白皮书与 main 对齐） |
| 共同起点 | 上述两者之上包含本计划的 Wave 0 提交 |
| 集成分支独占 | 生成 schema/docs、最终架构文档、跨分支回归与冲突解决 |

远端分支与原当前分支的 merge-base 是 `32e5e70`：原当前分支领先 1 个提交，远端分支领先
2 个提交。三方合并预演没有内容冲突，但远端修改了 `active_discovery.py`、CI、`pyproject.toml`、
`uv.lock` 和 LeRobot E2E，因此它必须先进入共同起点。不要 rebase 已发布的
`codex/adapt-capability-integration`；从远端分支新建集成分支，再 cherry-pick `de78a27` 和
Wave 0 设计提交，既保留历史，也避免后续 Proposal worktree 重做 Discovery 冲突。Registry
Core 继续使用既有 `codex/adapt-capability-integration`：在其独立 worktree 中先 merge Wave 0，
再在完整 294 项上开发，不改写该分支的远端历史。

Wave 0 已按上述策略在当前 worktree 建立新集成分支。后续子 worktree 才使用下表的独立目录，
并且只从 Wave 0 提交或其已合并后继提交创建。

### 8.2 工作分支

| Worktree / 分支 | 文件所有权与交付 | 依赖 | 禁止触碰 |
|---|---|---|---|
| `robot-loop-registry-core` / `codex/adapt-capability-integration`（既有） | 先合入 Wave 0；再稳定 294 项 identity/hash、contract/governance、Catalog 和覆盖测试 | Wave 0 | Agent、Runtime 业务代码 |
| `robot-loop-adapt-contracts` / `codex/adapt-agent-contracts` | 与 Operation 数量无关的 Proposal、Bundle、Tool Session 模型；真实 294/合成约 140 双 fixture；schema 导出；validator 接口 | Wave 0 | Registry、contract YAML、governance、生成文档 |
| `robot-loop-adapt-skills` / `codex/adapt-agent-skills` | 三个 `rolo-` 技能；Wiki 兼容迁移；fixture；技能校验测试 | Wave 0 + Contracts draft | Registry、Discovery 主流程 |
| `robot-loop-adapt-proposals` / `codex/adapt-proposal-orchestration` | Discovery skill runner、mapping provider、proposal artifact、validator、fallback/metrics | Wave 0 + Contracts draft；集成时要求正式 Contracts | Runtime gateway、Registry 词汇 |
| `robot-loop-adapt-tool-gateway` / `codex/adapt-tool-gateway` | Tool Session、会话 list/invoke、policy/audit、Runtime 接线 | Wave 0 + Contracts draft；集成时要求正式 Contracts | Discovery 和技能提示词 |
| `robot-loop-adapt-downstream` / `codex/adapt-downstream-agents` | Diagnose/Verify handoff 绑定与只读工具消费 | Wave 0 + Contracts/Gateway draft；集成时要求正式 Gateway | Registry 和 Adapter 生成 |

所有目录建议位于 `C:\Users\zarch\Desktop`，避免嵌套在当前仓库。当前工作树中的未跟踪测试
产物不带入新 worktree，也不删除或暂存。

### 8.3 启动与合并波次

1. **Wave 0**：远端 P0/CI/LeRobot + `de78a27` + 本设计，形成共同基线；
2. **Wave 1 启动同步**：Registry Core 先 merge Wave 0；Contracts、Skills、Proposals、
   Tool Gateway、Downstream Agents 全部从 Wave 0 创建独立 worktree；
3. **Wave 1 并行开发**：Registry Core 保持 294 项；Contracts 固化数量无关 schema；其余分支
   使用 draft interface/fixture 开发，任何分支不得修改其他分支所有权文件；
4. **Wave 2A**：先把 Registry Core 合回 integration，再合入 Contracts 并运行 294 identity/hash
   与 schema 矩阵；
5. **Wave 2B**：依次合入 skills、proposals、tool-gateway；每一步重放定向与全量测试；
6. **Wave 3**：gateway 稳定后合入 downstream；proposal shadow 达标后启用新候选路径；
7. **最终集成**：Registry Core → contracts → skills → proposals → tool-gateway → downstream；
8. 最后由 integration 独占生成 schema/docs，并运行 Python 矩阵、LeRobot opt-in、全量回归、
   shadow 与 canary。

Registry Core 与其他 worktree 同步开发，但在集成序列中先行。它保持 294 项权威词汇并稳定
Registry、contract、Catalog 和 release 摘要；其他分支不得自行增删 Operation 或更新冲突的
生成物。

## 9. 验收门

### 9.1 技能与契约

- 三个 `rolo-` 技能可独立加载，description 能准确区分触发场景；
- 所有成功输出通过严格 schema；未知字段、placeholder、错误 artifact hash 必须失败；
- 相同输入 fixture 能稳定引用相同 evidence/Operation，不要求叙述逐字一致；
- Agent 超时、拒绝、格式错误时，现有确定性 Discovery 路径仍成功结束。

### 9.2 权限与安全

- 构造“虚假高置信度 route”不能产生 eligible Operation；
- Agent 提议不存在的 Operation、跨 discovery 引用或伪造 resource ID 必须被拒绝；
- 未 Verified、release 过期、Catalog hash 漂移或 session 过期的调用必须 fail closed；
- Wiki 内容变化不得改变 Operation eligibility、Catalog 或 release digest；
- Adapter Coding Policy 变化仍必须经过现有 bundle/conformance gate，不能因未设技能而弱化；
- 首版 Tool Gateway 无写入/运动 Operation。

### 9.3 规模与性能

- 注入 1,000 个无关 Operation 后，各技能提示上下文仍受 Slice 上限约束；
- Registry/Catalog 校验时间与内存记录基线，并设回归阈值；
- Tool Session 只携带任务允许子集，不复制完整 Catalog；
- proposal/evidence/artifact 均支持分页读取，单次结果有字节上限。

### 9.4 发布策略

1. local-static fixture；
2. shadow：只记录 Agent 提案，不改变候选；
3. compare：比较确定性路径与 Agent 路径的覆盖、误报、成本和延迟；
4. canary：只对允许列表 robot/project 启用新候选路径；
5. default-on：只有误报为零且回退、审计、预算指标稳定后启用；
6. Tool Gateway 独立 canary，不与 proposal 路径同时首次放量。

## 10. 启动检查清单

- [x] 本计划评审通过并提交为设计基线；
- [x] 以远端 `codex/p0-python-ci-lerobot`、`de78a27` 和本提交形成 Wave 0；
- [x] 记录 294 项 Registry/contract/governance/Catalog 摘要和性能基线；
- [x] 为 Proposal、Bundle、Tool Session 实现数量无关的 `v1` schema；
- [x] 为既有 `codex/adapt-capability-integration` 创建 Registry Core worktree，并无冲突合入 Wave 0；
- [x] 从 Wave 0 创建全部并行 worktree；Contracts 建立真实 294 + 合成约 140 双 fixture；
- [ ] 各 worktree 按所有权完成开发，Registry Core 与 Contracts 先通过 294 hash/schema 矩阵；
- [ ] LeRobot E2E 作为首个真实工程验收，不为其保留仓库专用 Operation；
- [ ] 建立 1,000 无关 Operation 的上下文与 Catalog 规模测试；
- [ ] shadow 指标至少包含有效提案率、错误引用率、误报率、token/延迟、fallback 原因；
- [ ] 在只读 MVP 通过前，不启动写入/运动 Tool Gateway。

## 11. Go / No-Go 标准

已经可以在完整 294 项 Registry 上并行开发。第一阶段只做三个 `rolo-` 技能、Agent 提案和
只读 Verified Tool Gateway；约 140 项精简留作独立后续 RFC。若要求首版
同时支持重新扩张 Registry、运动控制和自动发布，则应判定 No-Go 并拆成独立项目，因为这会
同时扩大语义治理、安全授权和真机验证三个风险面。

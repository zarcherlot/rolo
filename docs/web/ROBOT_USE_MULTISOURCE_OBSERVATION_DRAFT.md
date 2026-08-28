<!-- status: draft; authority: reference; owner: docs maintainers; last_reviewed: 2026-08-28 -->

# `robot_use` 多源观察与可视化诊断草案

> 状态：讨论草案（Draft）  
> 用途：记录产品方向、架构边界和候选开发路线，供后续排期与设计评审使用。  
> 当前承诺：本文不表示相关能力已经进入当前开发范围，也不改变现有 Operation Contract、API 或安全策略。

## 1. 背景与判断

rolo 当前将 `robot_use` 定义为语义视觉监督能力：组合机器人本体或第三视角相机、带时间戳的关键帧、任务状态、控制命令、里程计和遥测，交给多模态模型分析。

这一方向应进一步扩展。机器人研发中的有效观察不仅来自真实相机，还来自外部测量系统和工程可视化工具：

- 本体 RGB、深度、热成像等视觉传感器；
- 外部相机、Vicon 等外部测量或定位系统；
- lidar、point cloud、costmap、path、TF、odometry 和任务状态；
- RViz、MoveIt、MuJoCo、Isaac Sim 等工具生成的可视化视角；
- 必要时，由 Agent 在目标主机上调用受控工具取得的补充截图。

因此，`robot_use` 不应仅被理解为“向 GPT 提交若干图片”，而应逐步演进为：

> **面向 Agent 的多源具身观察编排与语义监督系统。**

它负责把同一执行时间窗内的原始观测、结构化状态、派生视图和任务上下文组织成可追溯的证据包，支持多模态模型分析，并在证据不足时通过受控、只读、有预算的方式申请补充视角。

## 2. 与现有产品方向的关系

本草案延续而不推翻当前设计：

- [`README.md`](../../README.md) 已将本体/第三视角相机、遥测和任务状态纳入 `robot_use`；
- [`ARCHITECTURE.md`](../architecture/ARCHITECTURE.md) 已把 `robot_use` 放在 Diagnose 阶段，并明确完整闭环仍待实现；
- [`WEB_VISUALIZATION_PRODUCT_PROPOSAL.md`](WEB_VISUALIZATION_PRODUCT_PROPOSAL.md) 已提出 Episode Studio、多相机、共享时间轴和事实回贴；
- Canonical Operations 已包含 camera、lidar、costmap、path、TF、pose、telemetry、event、episode 和 evidence 等基础能力；
- [`SENSITIVE_INVOCATION_POLICY.md`](../operations/SENSITIVE_INVOCATION_POLICY.md) 已建立图像、地图和空间数据的默认拒绝、主机身份授权与无业务 payload 审计边界。

本草案主要补充四个缺失部分：

1. 将“图像帧”抽象为更通用的观察资产；
2. 将 RViz、MoveIt 和模拟器视角纳入正式证据来源；
3. 支持模型提出结构化补充观察请求；
4. 在 Episode Studio 中统一呈现多视角、来源、推理和证据关系。

## 3. 产品目标与非目标

### 3.1 产品目标

- 在同一时间基准上组合多种真实、外部、结构化和派生观察；
- 让每个模型结论能够回溯到具体证据、时间和来源；
- 在信息不足时允许 Agent 请求一个明确、有界的补充视角；
- 支持导航、操作、真实机器人和仿真场景，而不绑定单一厂商工具；
- 将观察、推断、人工确认和安全判定明确分层；
- 为后续 Episode Studio、Diagnosis 闭环和运行对比提供稳定数据契约。

### 3.2 非目标

- 不用多模态模型替代碰撞检测、功能安全、急停或物理 interlock；
- 不把 RViz、MoveIt 或仿真画面视为真实物理结果的自动证明；
- 不开放 Agent 任意操作目标桌面、任意截图或无限追加上下文；
- 不在第一版提供通用远程桌面、自由终端或实时遥控；
- 不为每种可视化软件创建一套厂商专属的产品 operation；
- 不声称从单张二维截图可以可靠恢复精确三维距离或碰撞关系。

## 4. 观察证据分类

不同来源的证据地位必须显式区分。

| 类型 | 示例 | 解释原则 |
|---|---|---|
| 原始视觉观测 | RGB、深度图、热成像、外部相机画面 | 可以支持直接可见事实，但仍受遮挡、视角和成像质量限制 |
| 结构化观测 | Vicon 刚体位姿、TF、odometry、costmap 栅格、PointCloud2 | 应以结构化数据进入上下文；通常不应只通过截图传递 |
| 标准化派生视图 | costmap PNG、点云固定视角、规划场景渲染 | 是原始/结构化数据的确定性投影，必须记录转换和图例 |
| 工具 GUI 截图 | RViz、MoveIt、MuJoCo、Isaac Sim 窗口截图 | 是界面状态的间接证据，应作为原生导出不可用时的 fallback |

还应区分观察对应的世界：

- `PHYSICAL`：来自当前真实机器人和环境；
- `SIMULATED`：来自仿真运行；
- `REPLAYED`：来自 rosbag、日志或历史 Episode 回放。

模型、界面和导出报告都不得隐藏这些差异。

### 4.1 Vicon 的处理

Vicon 不应简单等同于“第三视角相机”。多数场景中其主要价值是结构化、带时间戳的刚体 pose。推荐同时提供：

- Vicon pose、质量指标和外部坐标系；
- Vicon 与 `map`、`odom`、`base_link` 的标定/变换关系；
- 可用时的外部相机画面或场景渲染；
- 与本体 odometry、TF 和命令状态的时间对齐结果。

这样可以区分“物理上没有移动”“里程计报告移动但外部测量未移动”“真实轨迹与规划轨迹发生偏差”等不同问题。

## 5. 候选总体架构

```text
真实机器人 / 外部测量 / 仿真
    │
    ├── 本体相机、深度、点云
    ├── Vicon、外部相机、外部定位
    ├── TF、里程计、遥测、任务状态
    └── RViz / MoveIt / MuJoCo / Isaac Sim
                     │
              Observation Providers
                     │
              Observation Assets
       原始数据 + 派生视图 + 来源 + 时间 + 坐标系
                     │
              Observation Bundle
       同一执行/时间窗 + 同步质量 + 任务上下文
                     │
                 robot_use
                     │
       ├── observed facts
       ├── candidate causes
       └── requested checks
                     │
        受策略限制的补充观察循环
                     │
          Supervision / Diagnosis / Episode
```

### 5.1 Observation Provider

Provider 将目标系统的具体能力映射为产品级观察资产。Provider 可以由目标 adapter、Rolo builtin 或专用桥接组件实现，但不改变产品语义。

候选 Provider 包括：

- Camera Provider；
- External Tracking Provider；
- ROS Spatial Data Provider；
- Deterministic Renderer；
- RViz Capture Provider；
- MoveIt Scene Provider；
- MuJoCo Provider；
- Isaac Sim Provider。

Provider 的职责是采集、规范化、记录 provenance 和返回受保护 artifact；它不负责给出最终诊断。

### 5.2 Context Assembler

Context Assembler 根据 `execution_id`、时间窗、任务阶段和触发原因选择观察资产，并负责：

- 时间对齐和同步质量评估；
- frame、TF 和 calibration 关联；
- 过期、缺失或冲突证据标记；
- 字节、图片数量、分辨率和模型上下文预算；
- 生成不可变的 Observation Bundle manifest。

### 5.3 Multimodal Supervisor

多模态模型只承担语义监督：

- 对照 task contract 识别 expected/observed 差异；
- 分离直接事实和候选原因；
- 明确证据限制与冲突；
- 证据不足时输出 `UNKNOWN` 或结构化补充检查；
- 不直接拥有执行、运动或安全授权。

## 6. 候选数据契约

以下字段仅表示设计方向，正式字段、枚举和版本应在实现前单独评审。

### 6.1 `ObservationSource`

描述一个可稳定识别的观察源：

- `source_id`、名称和 Provider；
- modality 和 world kind；
- 绑定 endpoint 或 adapter capability；
- frame、calibration 和 clock domain；
- 当前 availability、freshness 和限制；
- 支持的 capture mode 或 view recipe；
- data classification 和 observation overhead。

### 6.2 `ObservationAsset`

替代仅能表达图片的 `ImageFrame`，候选字段包括：

- `asset_id`、`source_id`；
- `modality`；
- `captured_at`、`received_at`；
- `frame_id`；
- `artifact_ref`、media type、SHA-256、大小和尺寸；
- `evidence_kind`：`RAW`、`NORMALIZED`、`RENDERED`、`GUI_SCREENSHOT`；
- `world_kind`：`PHYSICAL`、`SIMULATED`、`REPLAYED`；
- calibration ref、TF snapshot ref；
- renderer、工具版本、view recipe、图层、viewport 和图例；
- clock offset、同步质量；
- data classification；
- limitations。

原始点云、costmap 等可以保留原始 artifact，同时关联一个或多个便于模型理解的 rendered assets。

### 6.3 `ObservationBundle`

表示一次模型判断的不可变输入：

- `bundle_id`、`robot_id`、`execution_id`；
- 触发类型和触发原因；
- `window_start`、`window_end`；
- task contract 及其 revision/digest；
- observation asset 引用；
- command、telemetry、event 和 state 引用；
- synchronization assessment；
- 缺失、过期、被策略拒绝的数据源；
- 总字节、采集耗时和模型输入预算；
- manifest digest 和创建时间。

### 6.4 `RobotUseSupervision v2`

建议增强：

- observed fact 引用具体 `asset_id`、时间点/区间；
- 可选图像区域、对象或空间 frame；
- 事实类型：`DIRECT_OBSERVATION`、`DERIVED_OBSERVATION`、`CORROBORATED`；
- candidate cause 引用支持/反对证据；
- 显式 evidence conflicts；
- 结构化 requested checks；
- 已使用、失败或被拒绝的补充检查；
- 最终 confidence、limitations 和 provenance。

### 6.5 `RequestedCheck`

将当前自由文本检查请求升级为结构化意图：

- 所需 capability/operation；
- `source_id` 或 `view_recipe_id`；
- 目标时间点/时间窗；
- 请求原因和希望解决的不确定性；
- 优先级；
- 最大字节、最大耗时和 freshness；
- 是否接受 rendered 或 screenshot fallback。

它只是观察请求，不是权限，也不能携带任意 shell、文件路径或 GUI 操作脚本。

## 7. 可视化工具接入原则

### 7.1 通用原则

优先级建议如下：

1. 原生结构化数据；
2. 确定性、可复现的标准渲染；
3. 工具原生导出接口；
4. 目标桌面 GUI 截图。

普通 GUI 截图容易受到窗口遮挡、DPI、分辨率、主题、Wayland/X11、远程桌面和操作者状态影响，因此只应作为 fallback，并记录窗口身份、截图区域和工具版本。

### 7.2 RViz / ROS 导航

建议提供固定、不可变的 view recipes，例如：

- `nav/global_costmap_path_robot`；
- `nav/local_costmap_scan_footprint`；
- `nav/tf_localization_health`；
- `mapping/pointcloud_map_alignment`。

costmap 必须带固定图例，标明 free、occupied、inflated、unknown 等含义。点云应保留原始 artifact，并生成固定相机参数的多视角图或 depth/range 投影。

### 7.3 MoveIt

不应只截取 3D 窗口。推荐组合：

- planning scene revision；
- robot state；
- goal/trajectory；
- collision objects；
- collision/contact 或 planning failure 摘要；
- 固定视角渲染图。

### 7.4 MuJoCo / Isaac Sim

Provider 应同时记录：

- 仿真时间和步进状态；
- scene/model revision；
- 相机内外参；
- 关键对象和机器人状态；
- renderer/version；
- viewport 或 sensor 输出。

所有相关资产必须明确标记为 `SIMULATED`，不能用于证明真实世界中的物理结果。

## 8. Agent 补充观察闭环

建议采用有限状态和预算控制，而不是开放式截图循环：

1. 根据触发策略采集初始 Observation Bundle；
2. 模型返回初步监督结果和零个或多个 Requested Check；
3. Diagnosis Agent 从 Active Tool Catalog 中匹配可用的只读观察能力；
4. Runtime 执行契约、身份、SENSITIVE、开销、速率、审计和 artifact 边界检查；
5. Provider 取得补充资产并生成新的 bundle revision；
6. 模型进行有限次数的复判；
7. 达到轮数、时限、字节或调用预算后，输出最终结果或 `UNKNOWN`。

候选默认限制：

- 最多 1–2 轮补充观察；
- 每轮只执行白名单中的只读 operation；
- 每个 operation 自带 max duration、max bytes 和 observation overhead；
- 不因 Requested Check 自动获得 SENSITIVE 访问权；
- 不允许补充观察隐式启动仿真、规划、导航或物理运动；
- 每次请求、允许、拒绝、采集和使用结果均可审计。

## 9. Canonical Operation 策略

现有原始能力优先复用：

- `app.camera.snapshot`；
- `app.lidar.snapshot`；
- `app.navigation.costmap.inspect`；
- `app.navigation.path.inspect`；
- TF、localization pose、telemetry、event、episode 和 evidence 等相关 operation。

若现有词汇无法表达“取得一个预注册工程可视化视角”，再考虑增加少量厂商无关 operation，例如：

- `app.visualization.list`；
- `app.visualization.status`；
- `app.visualization.snapshot`。

RViz、MoveIt、MuJoCo 和 Isaac Sim 应作为 Provider/binding，而不是进入核心 operation 名称。

`app.visualization.snapshot` 的候选输入应使用稳定 `source_id`、预注册 `view_recipe_id` 和严格上限；初版不提供任意 `configure`、点击、缩放、图层修改或桌面脚本能力。是否新增这些 operation，必须遵循 Registry 和 Operation Contract 的现有治理流程，不能由 discovery 自动扩展产品词汇。

## 10. Web 产品方案补充

### 10.1 Observation Sources

在 Robot Overview 或 Stack Map 中增加观察源视图，展示：

- 本体、外部、结构化和可视化来源；
- modality、frame、calibration、clock domain；
- availability、freshness 和同步质量；
- `PHYSICAL`、`SIMULATED`、`REPLAYED`；
- 支持的 view recipes；
- 相关 capability、binding evidence 和策略分类。

### 10.2 Episode Studio Perspective Tray

将当前“视频/关键帧”区域扩展为多视角托盘：

- 本体相机；
- 外部/Vicon 视角；
- costmap；
- point cloud 标准视角；
- RViz 综合视角；
- MoveIt planning scene；
- 仿真器相机或场景视角。

所有视角共享时间游标，并显示：

- raw/rendered/screenshot；
- physical/simulated/replayed；
- frame、采集时间、延迟和同步质量；
- renderer、图层和图例；
- GPT 是否实际使用该证据；
- 该视角是初始策略采集还是模型补充请求。

### 10.3 推理与补充视角历史

右侧诊断区应解释：

- 为什么请求这个补充视角；
- 请求是否被允许以及拒绝原因；
- 新视角解决了什么不确定性；
- 哪个事实或候选原因因此改变；
- 哪些结论仍缺少物理或结构化证据。

## 11. 安全、隐私与可靠性边界

- 图像、地图、点云、空间位置和 GUI 截图默认按 `SENSITIVE` 处理；
- GUI 截图可能包含人员、终端、凭据或其他应用窗口，截图范围必须受控；
- 浏览器和模型不能获得本地任意 artifact 路径；
- artifact 必须经过大小、类型、digest、边界、留存和访问检查；
- 审计记录不包含业务 payload、原始图像或模型上下文；
- 模型补充观察不能绕过 OS principal、Invocation Policy 或 R3 authorizer；
- Observation Provider 不得拥有运动授权；
- 模型输出不能替代安全控制器、规划器、碰撞检测或人工安全确认；
- 时间同步、TF 和 calibration 不可信时，空间结论必须降级为 `UNKNOWN` 或明确限制；
- costmap 颜色、点云投影和模拟器渲染必须有稳定语义，不能依赖未经记录的用户界面偏好。

## 12. 候选开发路线

本路线按依赖顺序组织，不表示已经排期。

### Milestone A：观察契约与设计验证

- 定义 Observation Source、Asset、Bundle；
- 定义 Requested Check 和 Supervision v2；
- 确定时间、TF、calibration、render provenance 规则；
- 用 fixture 表达“本体 RGB + Vicon pose + costmap + RViz 图”；
- 评审与现有 episode/evidence/operation contract 的关系。

退出条件：一个 bundle 能无歧义表达多源证据和它们之间的时间、坐标及派生关系。

### Milestone B：采集与制品骨架

- 统一受保护 artifact 解析；
- Observation Provider 接口；
- manifest 和 digest；
- 时间窗组装与同步质量；
- 媒体标准化、大小和模型输入预算；
- 缺失、过期、冲突和授权拒绝状态。

退出条件：无需调用模型即可可靠生成、校验和回放一个 Observation Bundle。

### Milestone C：ROS 2 导航纵向切片

- 本体 RGB；
- Vicon 或外部定位 pose；
- TF/odometry；
- local/global costmap；
- lidar/point cloud 标准渲染；
- RViz 固定 recipe 快照。

退出条件：能够诊断一个包含规划、定位、里程计和外部观察差异的导航 Episode。

### Milestone D：`robot_use` 有界补充观察

- 初始分析；
- 结构化 Requested Check；
- Tool Catalog 匹配；
- 策略、审计和预算门禁；
- bundle revision；
- 有限次数复判；
- 最终事实和原因绑定 evidence IDs。

退出条件：模型能安全请求一个额外只读视角，并证明该视角是否改变了结论。

### Milestone E：MoveIt 与仿真 Provider

- MoveIt planning scene、trajectory、collision 和渲染；
- MuJoCo 状态、相机和仿真时间；
- Isaac Sim viewport/sensor/scene revision；
- physical/simulated/replayed 强制分层。

### Milestone F：Episode Studio

- Perspective Tray；
- 多源同步回放；
- facts/causes/evidence 回贴；
- 补充观察历史；
- baseline 对比；
- diagnosis handoff 和 evidence package。

## 13. 建议的首个 MVP

首个 MVP 建议选择 ROS 2 移动机器人导航，而不是同时覆盖所有工具：

- 一路本体 RGB；
- 一路 Vicon pose 或外部相机；
- odometry/TF；
- Nav2 local costmap；
- lidar/point cloud 标准渲染；
- 一个固定 RViz view recipe；
- 一次初始模型判断；
- 最多一次补充观察；
- Episode 中的证据回贴。

这一切片同时覆盖原始视觉、外部真值、结构化空间数据、派生视图和 Agent 补充观察，能够较早验证核心产品价值。

## 14. 候选验收标准

- 每个模型事实都能定位到至少一个 observation asset；
- 每个 asset 都有来源、时间、world kind、evidence kind 和完整性信息；
- 同步或 calibration 不可靠时不会输出伪精确空间结论；
- GUI 截图和原生结构化数据在产品中不会混为同一证据等级；
- Agent 不能请求未注册视角、任意桌面区域或任意命令；
- 补充观察达到预算后能够稳定终止并返回 `UNKNOWN`；
- SENSITIVE 拒绝不会导致降级为无审计的直接文件读取或截图；
- 仿真资产不会被用于证明真实物理执行成功；
- Episode 可以复现模型当时实际看到的完整 bundle；
- 用户能回答“结论基于哪个视角、为什么又请求一个视角、它改变了什么”。

## 15. 开放问题

在进入开发前仍需决策：

1. Observation Source/Asset/Bundle 属于 Rolo 控制面 schema，还是先作为 Diagnose 内部 schema；
2. 是否新增通用 visualization operations，还是先通过现有 operation 和内部 Provider 验证；
3. bundle revision 采用不可变父子链还是每次生成完整 manifest；
4. 模型补充观察是 `robot_use` service 内部编排，还是由 Diagnosis Agent 统一编排；
5. Vicon、RViz、MoveIt 和模拟器的首批参考 binding 由哪些版本和部署形态验证；
6. 确定性点云/costmap 渲染由 Rolo 提供还是由目标 adapter 提供；
7. GUI 截图在无可信桌面会话时应返回 `UNAVAILABLE`，还是允许受限的 headless renderer fallback；
8. Observation Bundle 与未来正式 Episode manifest、evidence package 的边界如何划分；
9. 模型输入的默认图片数量、分辨率、detail 等级和成本预算如何配置；
10. 哪些监督结论允许进入自动 Diagnosis 流程，哪些必须等待人工确认。

## 16. 暂定结论

`robot_use` 的长期差异化价值不在于“让 GPT 看摄像头”，而在于把真实传感器、外部测量、机器人状态和工程可视化视角组织为同一套有时间、有坐标、有来源、可审计的观察证据。

推荐的演进顺序是：

> **定义观察契约 → 建立采集与制品骨架 → 验证 ROS 导航纵向切片 → 加入有界补充观察 → 扩展 MoveIt/仿真 → 建设完整 Episode Studio。**

在进入实施前，应先完成数据契约、证据等级、时间同步和安全边界评审；不建议直接从自由 GUI 截图或前端多窗口开始开发。

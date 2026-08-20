# Operation Contract 标准化演进路线

## 定位

Rolo Operation Contract 当前是产品内部的、机器可校验的机器人操作契约。长期目标不是把
294 个 operation 名称直接宣布为行业标准，而是以多厂商、多机器人实现和 conformance
数据为基础，将其中稳定的公共语义发展为开放互操作规范，并在条件成熟后推动行业标准化。

当前成熟度：**内部参考规范（Internal Reference Specification）**。

Registry Operation 的日常治理、生命周期升级/降级和运行时使用规则见
[REGISTRY_OPERATION_GUIDE.md](REGISTRY_OPERATION_GUIDE.md)。

可复制的 R0、R1、R3 与数据敏感度最小模板见
[OPERATION_CONTRACT_TEMPLATES.md](OPERATION_CONTRACT_TEMPLATES.md)。

当前基线：294 个产品 operation 中，62 个契约为 `RELEASED`、206 个为 `GATEABLE`、
26 个保持 `DRAFT`。已提前发布的通用 Linux 只读能力包括主机状态与 uptime、文件
SHA-256、文件元数据和有界目录清单、路由与网卡信息、CPU/内存/磁盘/GPU 资源、进程与
容器资源快照、二进制与软件包完整性、软件包元数据、连接与 DNS 状态和时钟状态。这些
契约及 builtin 不依赖
具体机器人型号；目标主机只决定调用时返回 `SUCCEEDED`、`PARTIAL` 或 `UNAVAILABLE`。
Rolo runtime health/version、Active State Graph snapshot/query、证据元数据解析以及 middleware
status/graph snapshot 也已形成相同的产品契约与 builtin 闭环。
ROS node/topic/service/action 的第一批通用只读发现接口也已发布；没有 ROS CLI 时明确降级。
目标相关的 compute、clock、thermal、storage、sensor、actuator、bus、firmware 和 power
只读语义已形成 `GATEABLE` 契约；它们需要 discovery candidate、adapter 绑定和目标通路
证据后才能在具体机器人上成为 `VERIFIED`，不会因为产品契约已明确而伪装成通用 builtin。
应用层的 robot、camera、lidar、IMU、GNSS、odometry、base、manipulation、gripper、
localization、map、navigation 和 safety 观测语义也按相同原则进入 `GATEABLE`；位姿、地图
标识和安全区几何被标记为 `SENSITIVE`。
校准、任务、测试、回归、诊断、参数元数据和调优 workflow 的低敏感读取语义已进入
`GATEABLE`。在 SENSITIVE 默认拒绝、受保护 OS 身份策略和无 payload 审计链路完成后，
任务/测试/回归结果、测试与诊断证据引用、诊断结论、参数值、状态快照、事件查询和遥测
快照/导出也已进入 `GATEABLE`；它们仍需目标 discovery、adapter 绑定和门禁证据才能在
具体机器人上成为 `VERIFIED`。
ROS action goal 状态、TF tree/snapshot/lookup/monitor 和节点参数导出，以及应用层 lidar
snapshot、navigation costmap/path inspect 已形成同样的 `GATEABLE` 敏感只读契约。空间
位置、路径、坐标变换和批量参数均不得因“只读”而绕过 SENSITIVE 授权；monitor 使用有界
流，批量参数导出使用 R1 观测负载控制。
Navigation/manipulation/test/regression 的 plan operation 仅计算或返回有界计划，不调度、
启动或授权执行；calibration/parameter validate 只返回校验结果，不 apply/set；map export
只创建有界 artifact，不切换 active map。这些 operation 因计算或序列化负载使用 R1 时，
仍保持 `access=read`，并通过 postcondition 明确排除执行和目标状态变更。

正式契约以 `1.1.0` 为当前基线；`linux.host.inspect` 完成迁移后已退出产品 Registry，
其 CLI 兼容别名仍转发到 `linux.host.inventory`；`ros.node.status` 以 `2.0.0` 收敛为紧凑
可见性状态。数据敏感度
纳入契约摘要、Registry、Tool Catalog 和独立门禁：

- `PUBLIC`：允许公开传播的产品版本和协议信息；
- `INTERNAL`：主机、网络、ROS、硬件和机器人运行元数据；
- `SENSITIVE`：图像、地图、配置内容、日志和文件内容；
- `SECRET`：凭据、密钥和认证材料，禁止通过通用 operation 输出。

`risk` 表示物理动作和系统变更风险，`data_classification` 表示信息泄露风险。降低数据
分类属于破坏性安全策略变更；Adapter bundle 通过契约摘要间接绑定分类，运行时 Tool
Catalog 则显式暴露分类供调用方执行访问、留存和审计策略。

分类字段本身不是身份认证。契约编译器禁止任何通用 operation 声明或输出 `SECRET`；
Rolo runtime 对 `SENSITIVE` 默认拒绝，只接受由主机保护的策略文件中的 OS 用户/组授权，
并将允许与拒绝结果写入不含业务 payload 的审计日志。策略文件可被普通用户组修改、缺少
策略或缺少审计路径时均闭锁拒绝，不能用普通布尔参数冒充认证。部署要求见
[SENSITIVE_INVOCATION_POLICY.md](SENSITIVE_INVOCATION_POLICY.md)。

Write operation 独立于数据分类执行默认拒绝。R1/R2 只能通过受保护 OS 策略中的精确
operation 白名单放行；R3 静态策略无权放行，必须由管理员所有的外部提供器返回与单次
request、robot、operation、输入 SHA-256 和五分钟内 expiry 绑定的能力。Adapt 的
“operation 存在”验证不执行或绕过该 runtime 授权。

文件、配置和日志正文还需第二层受保护资源分类：显式路径根或稳定 resource ID、SENSITIVE
声明和最大字节数缺一不可；可能包含 SECRET 的资源不配置。相关 Tool 只返回 protected
artifact 引用，不将正文直接放入通用调用结果或 Agent prompt。
因此 `linux.file.read`、config inspect/validate/diff、process/service/container logs 以及通用
log query/follow 只进入 `GATEABLE`，不会发布为无条件跨主机 builtin。

通用 Linux host power、process、service、container、schedule 和 time synchronization 写操作
已形成 `GATEABLE` 1.1.0 契约。输入使用发现得到的稳定资源身份，运行时仍要求精确 operation
白名单；输出仅确认请求被接受，目标状态必须通过 status/inspect 另行观测。ROS 2 managed
node activate/deactivate 采用同一边界，修正了 activate 被名称启发式误判为只读的历史问题。

`linux.config.apply` 不接受可变路径：输入必须包含 protected artifact 引用、当前内容
SHA-256、最大字节数和稳定目标资源身份，runtime 在授权后、adapter 执行前重新解析并核对
artifact。apply 返回 `rollback://` opaque token；该 token 只定位 adapter 保存的回滚状态，
自身不授予权限，rollback 仍必须重新通过 SENSITIVE 与 write 授权。两者都只确认请求接受，
不把配置加载成功、服务重载成功或运行状态收敛写入 Adapt 结论。

Odometry reset、localization initialize/reset/relocalize 以及 map create/save/load/clear/import 已形成
非直接运动状态变更契约。它们禁止暗含速度、导航或建图执行；map create/import 只创建非激活
记录，import 使用与 config apply 相同的 digest-pinned protected artifact 边界。Tuning candidate
evaluate 固定为对既有候选、基线和证据的 R1 有界只读计算，不 apply 参数、不运行测试，也不
触发机器人运动。

`task.start`、`test.run`、`regression.run` 和 `diagnosis.run` 可能通过目标定义间接触发执行器，
统一采用 R3，不因外层名称是 workflow 而降为 R2。它们只返回 run ID 和接受确认，必须绑定
普通 cancel operation；为补齐该不变量，Registry 新增 `app.regression.cancel`。普通 cancel
为 R2 且只请求中止，不冒充 protective/emergency stop，也不声称目标已经停止。契约编译器
现在拒绝任何缺少 active write compensation contract 的 cancelable write。

Teleop、base、manipulation、gripper、navigation 和 task 的直接物理控制已形成 `GATEABLE`
契约。会启动、恢复、暂停、停止、执行、回零或改变执行器目标的 operation 统一采用 R3；
普通 cancel 保持 R2，因为它只向 supervisor 请求取消。普通 stop 即使以减速、保持或零速度
实现，仍是直接改变运动状态的 R3，但不得声称触发了 protective stop 或 emergency stop。
所有响应只确认命令或请求被接受，物理结果和停止状态必须在后续诊断阶段另行观测。

`access=read` 不再被错误地等同于 `risk=R0`。只读 operation 可以因总线探测流量、持续
采样负载等原因成为 R1，但必须声明 `ELEVATED` observation overhead、具体副作用和非
`on_demand` 的速率上限；read 仍禁止 R2/R3。`hw.bus.scan` 是当前首个受该门禁约束的
GATEABLE 契约。

短时采样、watch 和 rate/bandwidth 观测采用 `BOUNDED_STREAM`：输入必须同时限制时长、
条数和字节数，调用可取消，输出必须报告截断状态。真正持续的摄像头流采用互为配对的
`SESSION_START` / `SESSION_STOP`，start 返回带过期时间的 opaque session handle。通用
runtime 不允许把无限输出伪装成普通 request/response。

Rolo 控制面的 episode list/inspect/export 与 checkpoint list/create/restore 已形成
`GATEABLE` 契约。Episode 查询和导出只处理有界 manifest、事件元数据与 artifact 引用；
checkpoint restore 只产生新的 Rolo 控制面 revision，不应用真实参数、不恢复主机进程、
不恢复任务执行，也不触发机器人运动。

Application parameter set/rollback 与 tuning baseline/candidate create、commit/rollback 已形成
`GATEABLE` 契约。Baseline/candidate 只创建 inactive 记录；candidate patch 使用有界、摘要
固定的 protected artifact。真正应用参数的 set/rollback/commit/rollback 为 R2，并声明
`requires_quiescence=true`：runtime 必须从受保护执行监督器取得覆盖完整调用时限的绑定 lease，
无法证明执行静止时闭锁拒绝。该 lease 不能授权任务、测试或机器人运动。

ROS parameter set/load/rollback 采用相同 R2 静止门禁。Set 使用当前规范化 typed value 的
SHA-256 做乐观并发保护；load 只接受有界、摘要固定的 protected artifact；set/load 返回的
rollback token 不授予权限，rollback 必须重新通过 SENSITIVE、write 与 quiescence 三重门禁。
这些 operation 均禁止隐式 node transition、进程重启、任务启动或机器人运动。

## 标准化范围

适合成为规范核心的内容包括：

- operation 的稳定身份、层级和生命周期；
- 输入、输出和错误模型；
- read/write、风险等级、幂等性、取消和补偿语义；
- 单位、坐标系、时间戳和观测时刻；
- 前置条件、后置条件、副作用、资源锁和速率限制；
- 契约版本、内容摘要、兼容性和废弃规则；
- Adapter、Tool Catalog 与 conformance 的一致性要求。

以下内容不应进入规范核心：

- 厂商私有 Topic、Service、Action、SDK 函数或 CLI 名称；
- 针对单一机器人生成的 adapter 实现；
- 源码布局、构建目录和部署路径；
- 未经真机验证的推测性硬件参数；
- 对执行结果正确性、可靠性或功能安全认证的替代性声明。

## 分层模型

标准化产物按三层组织：

1. **Core Contract**：定义共同的契约结构、生命周期、版本规则和 conformance 语义。
2. **Domain Profiles**：分别定义移动底盘、传感器、导航、机械臂、电源、安全停止等
   领域 operation 集合及公共语义。
3. **Protocol/Vendor Bindings**：描述 ROS、OPC UA、厂商 SDK、CLI 和其他协议如何映射到
   Domain Profile；绑定可替换，不改变 operation 的产品语义。

Rolo Registry 是完整产品词汇；只有具备明确契约的 operation 才能进入 `GATEABLE` 或
`RELEASED`。某台机器人上的 `VERIFIED` 是该契约、目标通路证据和 adapter 绑定共同通过
门禁后的实例状态，不是全行业适用性声明。

## 与现有规范的关系

本规范优先复用现有生态语义，而不是重新定义：

- ROS 单位、坐标系、移动平台 frame 和诊断约定应与相关 REP 对齐；
- 工业设备信息模型和纵向集成优先评估映射到 OPC UA Companion Specifications，特别是
  OPC UA for Robotics；
- 工业机器人和服务机器人的安全要求继续由适用的 ISO/IEC 标准、法规和安全工程流程
  负责。

参考：

- [ROS Enhancement Proposals](https://docs.ros.org/en/independent/api/rep/html/rep-0000.html)
- [OPC UA Companion Specifications](https://opcfoundation.org/about/opc-technologies/opc-ua/ua-companion-specifications/)
- [OPC UA for Robotics](https://reference.opcfoundation.org/specs/OPC-40010-1/full)
- [ISO/TC 299 Robotics](https://www.iso.org/committee/5915511/x/catalogue/)

`app.safety.emergency_stop` 等契约只定义软件接口、前置条件和门禁要求。契约通过或 operation
被标记为 `VERIFIED`，均不表示机器人获得功能安全认证，也不替代风险评估、硬件安全回路和
正式验收。

## 演进阶段

### 阶段 A：内部参考规范

- 对 294 项产品词汇持续执行显式保留、迁移和移除审计；
- 将 operation 从 `DRAFT` 逐项提升为 `GATEABLE`；
- 为契约建立固定 Schema、语义版本和 SHA-256 绑定；
- 使用至少两个不同开源机器人项目验证 discovery、adapter 和静态 conformance；
- 不以源码启发式结果直接补写规范事实。

退出条件：契约编译、版本绑定、门禁拒绝和运行时拒绝形成自动化闭环。

### 阶段 B：多实现互操作规范

- 每个候选 Domain Profile 至少具备两个相互独立的 adapter 实现；
- 在不同厂商或不同中间件设备上验证同一 operation 的等价输入、输出和错误行为；
- 建立 golden cases、负向用例和兼容性回归；
- 记录无法统一的差异，并下沉到可选能力或厂商 binding；
- 引入公开 RFC、变更提案和评审记录。

退出条件：公共语义不依赖单一厂商、单一 ROS 包或单一 Agent 的启发式判断。

### 阶段 C：开放参考规范

- 发布规范文本、机器可读 Schema、参考 adapter 和 conformance suite；
- 定义命名空间、扩展点、版本支持周期和废弃窗口；
- 建立厂商声明与测试结果分离的认证记录；
- 接受外部实现反馈，完成至少一个主要版本的兼容性演进。

退出条件：第三方无需读取 Rolo 源码即可实现并验证兼容 adapter。

### 阶段 D：行业标准提案

- 选择与范围匹配的标准组织或联合工作组；
- 优先提交 Core Contract 和成熟 Domain Profile，不提交厂商绑定；
- 提供多厂商实施报告、conformance 结果和安全边界说明；
- 根据目标组织要求形成规范文本、术语、信息模型和测试规范。

该阶段是否启动由生态采用度决定，不以 operation 数量或内部测试覆盖率单独判断。

## 契约治理

契约采用语义版本：

- PATCH：文字澄清或不改变机器行为的修正；
- MINOR：向后兼容的可选字段、错误细化或能力扩展；
- MAJOR：新增必填输入、删除字段、改变单位/坐标系、风险策略或行为语义。

同一版本的契约内容摘要不得变化。Adapter bundle 和 Active Tool Catalog 必须绑定完全相同的
契约版本及摘要；不一致时，Adapt 门禁和运行时均应拒绝。`RELEASED` 契约不能退回
`GATEABLE`，废弃应先进入 `DEPRECATED` 并保留明确迁移窗口。

## Conformance 边界

标准 conformance 分为：

- **Schema conformance**：结构、类型、版本和摘要一致；
- **Binding conformance**：operation 能唯一解析到目标 entrypoint；
- **Route conformance**：目标环境中存在等价通路；
- **Behavior conformance**：输入、输出、错误和状态变化符合契约；
- **Safety/acceptance evidence**：由诊断、验证及适用安全流程独立处理。

Adapt 阶段只负责前三项，并且 Route conformance 只证明通路存在，不以一次调用的
success/failure 判断行为正确性。Behavior、可靠性、性能和安全结论属于后续阶段。

写 operation 的 `result_semantics` 必须为 `ACKNOWLEDGEMENT_ONLY`：Adapt 最多证明请求
能够到达等价目标通路并获得接受或拒绝响应，不能把响应解释为动作完成、状态收敛、可靠性
或安全性成立。R3 契约必须同时声明前置条件、确认后置条件、副作用和资源锁，输出必须要求
`status`，并显式包含 `NOT_AUTHORIZED` 与 `PRECONDITION_FAILED` 等安全拒绝路径。上述字段
缺失时，契约编译和独立 conformance 门禁都会拒绝发布。

## 近期工作

1. 继续完成高复用 operation 的契约：设备状态、传感器读取、底盘状态、导航和诊断。
2. 建立契约历史基线，使 CI 自动检查版本递增和破坏性变更。
3. 用真实 ROS 1、ROS 2 和非 ROS 设备验证相同 Domain Profile。
4. 将单位、frame、时间和错误语义映射到 ROS REP 与 OPC UA 信息模型。
5. 在具备多实现证据后发布首个外部 RFC；在此之前不使用“行业标准兼容”声明。

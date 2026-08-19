# Operation Contract 标准化演进路线

## 定位

Rolo Operation Contract 当前是产品内部的、机器可校验的机器人操作契约。长期目标不是把
297 个 operation 名称直接宣布为行业标准，而是以多厂商、多机器人实现和 conformance
数据为基础，将其中稳定的公共语义发展为开放互操作规范，并在条件成熟后推动行业标准化。

当前成熟度：**内部参考规范（Internal Reference Specification）**。

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

- 保持 297 项产品词汇稳定；
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

## 近期工作

1. 完成高复用 operation 的契约：设备状态、传感器读取、底盘状态、导航和诊断。
2. 建立契约历史基线，使 CI 自动检查版本递增和破坏性变更。
3. 用真实 ROS 1、ROS 2 和非 ROS 设备验证相同 Domain Profile。
4. 将单位、frame、时间和错误语义映射到 ROS REP 与 OPC UA 信息模型。
5. 在具备多实现证据后发布首个外部 RFC；在此之前不使用“行业标准兼容”声明。

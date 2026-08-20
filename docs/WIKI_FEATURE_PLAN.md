# Robot Wiki 特性计划

本文记录以 Wheeltec 真机采集结果为样本形成的 Wiki 整改计划。优先级以“能否在本地通过
固定输入稳定验证、是否直接降低工程误判”为主要依据。

## 本轮高优先级

| 编号 | 特性 | 状态 | 本地验收依据 |
|---:|---|---|---|
| 1 | 按源文件、构建 target 和入口归属可执行程序的静态接口 | 已实现 | 同工程多入口夹具不再互相继承 Topic |
| 3 | 静态提取 launch 参数默认值、include、条件、remap 与 URDF 引用 | 已实现 | Python/XML launch 夹具，无执行行为 |
| 4 | 区分 ROS 发行版、RMW、Domain 的环境配置、默认值和安装候选 | 已实现 | 伪 `/opt/ros` 目录与隔离环境夹具 |
| 5 | 将操作系统设备端点归为物理候选、内部流水线端点或未归并端点 | 已实现 | 仅稳定序列号/拓扑可形成物理候选 |
| 6 | 在 Wiki 中给出与上一份可验证 discovery 的工程字段差异 | 已实现 | 平台、ROS、应用、硬件、操作候选和 unknown 集合差异 |
| 7 | 以 Adapt Agent skill 生成有依据、低/中置信度且明确未验证的洞察 | 已实现，默认开启 | 严格 JSON schema、只读 sandbox、失败回退确定性规则 |
| 9 | 补齐 setuptools、CMake Python 安装入口与 C++ ROS 2 模板接口归属 | 已实现 | 字面量与符号表达式分层，注释接口排除，未归属项显式展示 |

## 低优先级留存

### 2. 将 `unknowns: list[str]` 升级为结构化缺口

目标模型至少应包含 `category`、`subject`、`reason_code`、`evidence_refs`、
`acquisition_method`、`verification` 和 `blocking_scope`。本轮继续兼容字符串 unknown，并在 Wiki
渲染时分类，原因是模型升级会影响 discovery schema、旧制品迁移、下游 workset 和 API，改动面
大于当前展示收益。后续应先设计 v3 schema 和旧数据迁移，再替换字符串启发式分类。

### 8. Wiki 质量门禁

目标是在发布 `latest.json` 前计算可读性、重复率、无证据事实、错误兼容性提升、接口归属覆盖率、
关键章节完整度和最大篇幅等指标。门禁规则目前留存但不阻断 discovery，原因是缺少足够多真机 Wiki
建立阈值，过早设硬门槛容易把“设备确实无法获取”误判成生成失败。待积累 Wheeltec 及其他平台样本
后，先以告警模式运行，再决定哪些指标可作为阻断项。

## 远程设备迭代项

- 在正确 ROS 环境启动机器人后，核对静态接口归属和在线节点/Topic 的差异。
- 用 udev、media graph、VID/PID、序列号和业务配置验证设备端点归并。
- 审核 Agent skill 的推断是否改变工程师下一步动作，删除泛化或重复建议。
- 累积多次 discovery，校准差异噪声和未来 Wiki 质量门禁阈值。

# ROLO 文档入口

本目录不再提供全部文档的逐项导航。专题文档、草案、验收记录和生成型参考由仓库搜索、相关正文链接及 Git 历史发现，避免把临时材料与规范性内容放在同一层级。

## 核心入口

- [最高开发准则](DEVELOPMENT_PRINCIPLES.md)：所有代码、测试、文档和发布的最高验收规则；
- [10 分钟 Quickstart](QUICKSTART_10_MIN.md)：从干净 checkout 安装并跑通离线 Demo；
- [目标机部署与 Adapt 操作手册](TARGET_DEVICE_OPERATION_MANUAL_ZH.md)：固定版本部署、本地或远程证据采集、完整 Adapt、验收与故障处理；
- [ROLO 白皮书](ROLO_WHITEPAPER.md)：开发原则、软件架构、证据与安全模型、行业标准化路线和词汇表；
- [三阶段架构](ARCHITECTURE.md)：当前参考实现的 `adapt -> diagnose -> verify` 架构与制品流；
- [归档文档](archive/README.md)：已完成或被替代的计划、评审样本和一次性验证材料；
- [Registry Operation 指南](REGISTRY_OPERATION_GUIDE.md)：Canonical Operation、Contract 和门禁的使用与治理；
- [Registry Operation 重设计计划](REGISTRY_OPERATION_REDESIGN_PLAN.md)：Canonical Registry 与 Agent-native Tool 双轨边界、迁移阶段和验收标准；
- [Registry Operation Worktree 计划](REGISTRY_OPERATION_WORKTREE_PLAN.md)：实现 worktree、文件所有权、接口冻结和合并顺序；
- [Agent-native Tool 运行边界](AGENT_NATIVE_TOOLS.md)：受控 Linux/ROS/HW 观测、Native Session 和 v2 Registry 使用方式；
- [R5 WSL 验证](R5_WSL_VALIDATION_README.md)：拉取分支、离线校验和 shadow 灰度步骤；
- [目标机 / WSL P2 验证](TARGET_MACHINE_P2_VALIDATION.md)：目标机证据采集、产物自检和 canary 前置条件；
- [P0 Adapt 验收](P0_ADAPT_ACCEPTANCE.md)：当前实现边界与可执行验证基线。

中文项目入口位于仓库根目录 [README](../README.md)，英文项目介绍见 [README.en.md](README.en.md)。
面向用户的本地 Adapt 首选入口是 `rolo adapt <本地工作区> --robot <机器人 ID>`；需要
远程证据或专家参数时使用 `robotctl adapt start`。

## 文档权威顺序

1. 最高开发准则、版本化 Schema、Operation Contract、运行时门禁与对应测试；
2. 白皮书、架构与安全规范；
3. 操作指南和验收清单；
4. Proposal、Plan、Draft、评审样本与生成型参考。

低优先级材料不能覆盖高优先级事实。新增专题文档无需登记到本页；只有成为长期核心入口时才加入导航。

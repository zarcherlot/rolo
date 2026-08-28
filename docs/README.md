<!-- status: active; authority: guide; owner: docs maintainers; last_reviewed: 2026-08-28 -->

# ROLO 文档入口

本目录不再提供全部文档的逐项导航。专题文档、草案、验收记录和生成型参考由仓库搜索、相关正文链接及 Git 历史发现，避免把临时材料与规范性内容放在同一层级。

## 核心入口

- [最高开发准则](architecture/DEVELOPMENT_PRINCIPLES.md)：所有代码、测试、文档和发布的最高验收规则；
- [10 分钟 Quickstart](getting-started/QUICKSTART_10_MIN.md)：从干净 checkout 安装并跑通离线 Demo；
- [目标机部署与 Adapt 操作手册](target/TARGET_DEVICE_OPERATION_MANUAL_ZH.md)：固定版本部署、本地或远程证据采集、完整 Adapt、验收与故障处理；
- [ROLO 白皮书](architecture/ROLO_WHITEPAPER.md)：开发原则、软件架构、证据与安全模型、行业标准化路线和词汇表；
- [三阶段架构](architecture/ARCHITECTURE.md)：当前参考实现的 `adapt -> diagnose -> verify` 架构与制品流；
- [归档文档](archive/README.md)：已完成或被替代的计划、评审样本和一次性验证材料；
- [Adapt 路线图](adapt/ADAPT_ROADMAP.md)：当前阶段、下一阶段门槛和历史计划索引；
- [文档治理规则](DOCUMENT_GOVERNANCE.md)：状态、权威级别、去重和归档约定；
- [开放评审队列](review/OPEN_DECISIONS.md)：当前仍需产品、平台或安全负责人确认的事项；
- [Registry Operation 指南](operations/REGISTRY_OPERATION_GUIDE.md)：Canonical Operation、Contract 和门禁的使用与治理；
- [Registry Operation 重设计计划](operations/REGISTRY_OPERATION_REDESIGN_PLAN.md)：Canonical Registry 与 Agent-native Tool 双轨边界、迁移阶段和验收标准；
- [Agent-native Tool 运行边界](adapt/AGENT_NATIVE_TOOLS.md)：受控 Linux/ROS/HW 观测、Native Session 和 v2 Registry 使用方式；
- [R5 WSL 验证](validation/R5_WSL_VALIDATION_README.md)：拉取分支、离线校验和 shadow 灰度步骤；
- [目标机 / WSL P2 验证](target/TARGET_MACHINE_P2_VALIDATION.md)：目标机证据采集、产物自检和 canary 前置条件；
- [P0 Adapt 验收](validation/P0_ADAPT_ACCEPTANCE.md)：当前实现边界与可执行验证基线。
- [本地 Diagnose/Verify fake 流程](validation/LOCAL_DIAGNOSE_VERIFY_FAKE.md)：不依赖目标机的 contract、授权和 handoff 开发回归。

中文项目入口位于仓库根目录 [README](../README.md)，英文项目介绍见 [README.en.md](README.en.md)。
面向用户的本地 Adapt 首选入口是 `rolo adapt <本地工作区> --robot <机器人 ID>`；需要
远程证据或专家参数时使用 `robotctl adapt start`。

## 文档权威顺序

1. 最高开发准则、版本化 Schema、Operation Contract、运行时门禁与对应测试；
2. 白皮书、架构与安全规范；
3. 操作指南和验收清单；
4. Proposal、Plan、Draft、评审样本与生成型参考。

低优先级材料不能覆盖高优先级事实。新增专题文档无需登记到本页；只有成为长期核心入口时才加入导航。

计划、草案和历史审计不再与当前规范并列；请先查看文档头部的 `status` 和 `authority`，再决定
是否可作为实现依据。`OPERATION_CONTRACTS.md` 与 `CANONICAL_OPERATIONS.md` 是由源码契约生成的
参考输出，修改应回到 `src/rolo/operation_contracts/*.yaml`。

## 目录约定

当前专题文档位于 `getting-started/`、`architecture/`、`adapt/`、`operations/`、`setup/`、
`target/`、`web/`、`validation/` 和 `reference/`。`archive/` 只保存历史材料；根目录仅保留
导航、生成契约、Episode 兼容契约以及旧链接跳转页。

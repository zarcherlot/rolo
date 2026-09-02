<!-- status: archived; authority: reference; owner: product and platform maintainers; last_reviewed: 2026-09-02; source_of_truth: ../reference/ENGINEERING_STATUS.md -->

# 文档与产品开放评审队列

本文只记录当前文档中仍需要产品、平台或安全负责人确认的事项。它不是实现计划的替代品；
每项决策完成后，应回写对应规范、路线图或实现状态，并从本页移入已决策记录。

## 1. Registry native tool canary

- 来源：[Registry Operation 重设计计划](../operations/REGISTRY_OPERATION_REDESIGN_PLAN.md)、
  [Adapt 路线图](../adapt/ADAPT_ROADMAP.md)；
- 当前状态：真实目标机 shadow、canary 窗口和人工评审尚未完成；native tool 默认保持 `off`；
- 需要确认：是否已满足 parity 样本、失败关闭、审计 artifact 和回退条件；
- 通过条件：明确 canary allowlist、观察窗口、回退阈值和责任人。

## 2. TargetOperationSlice 稳定门槛

- 来源：[Slice 稳定观察与人工评审](../validation/SLICE_STABILITY_OBSERVABILITY.md)；
- 当前状态：成功 Canary 样本尚未达到配置门槛；
- 需要确认：样本数量、观察窗口、失败率、预算超限和人工评审的具体阈值；
- 通过条件：阈值进入配置和验证测试，且不自动扩大灰度范围。

## 3. `robot_use` 多源观察契约

- 来源：[多源观察与可视化诊断草案](../web/ROBOT_USE_MULTISOURCE_OBSERVATION_DRAFT.md)；
- 当前状态：仍为 Draft，候选字段、时间同步、证据等级和安全边界尚未冻结；
- 需要确认：Observation Bundle v1 的最小字段、来源可信度和跨模型完整性规则；
- 通过条件：形成版本化 Schema、负向用例和控制面投影边界。

## 4. Episode / Web 实现边界

- 来源：[Web 可视化工作台产品方案](../web/WEB_VISUALIZATION_PRODUCT_PROPOSAL.md)、
  [Episode read-model 契约](../EPISODE_READ_MODEL_CONTRACT_DESIGN.md)；
- 当前状态：Web 方案明确当前尚未实现完整 Episode 模型和 Diagnose 闭环；
- 需要确认：第一版是否只交付只读 read-model，还是同时纳入 Episode Studio 和实时数据流；
- 通过条件：明确 producer、projection、权限和隐私边界后再进入 UI 开发。

## 评审后的收敛动作

1. 在本页记录决策日期、决策人和结论；
2. 更新对应的规范/路线图，不在本页复制完整设计；
3. 将已决策项移入 `archive/review/` 或对应的历史记录；
4. 重新运行 `python scripts/check_docs.py`、契约测试和相关产品验收。

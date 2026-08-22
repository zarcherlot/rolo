# Blocker Inbox 分诊与解除证据

## 目标

Blocker Inbox 将已验证的 pipeline assessment 投影成结构化、只读的分诊信息，回答：

- 哪个机器人和阶段受到影响；
- 当前最适合处理的 Agent 角色；
- blocker 属于哪类规范化消息；
- 解除 blocker 后必须出现哪些新证据；
- 如何通过 canonical CLI 重新读取 pipeline 状态。

该模型不执行修复，不把消息分类显示成根因诊断，也不把阶段通过显示成物理结果成功。

## 只读端点

```text
GET /v1/blockers?limit=&offset=&robot_id=&stage=
GET /v1/blockers/{blocker_id}
```

健康响应使用 `workbench.blocker-detail/v1` 标识详情契约支持。

集合模型 `rolo-fleet-blocker-collection/v2` 增加：

- `category`：基于规范化 pipeline message 的分诊类别；
- `classification_basis=normalized_pipeline_message`；
- `impact`：当前阻止哪个阶段继续推进；
- `resolution_requirement_count`：详情中的解除条件数量。

详情模型 `rolo-fleet-blocker-detail/v1` 增加：

- 当前 stage status 和安全摘要；
- `READY / COMPLETE` 目标状态；
- 新鲜 assessment 与 opaque evidence ID 解除条件；
- 参数数组形式的 `robotctl pipeline-status --robot ROBOT_ID` 复现路径；
- `contains_secret_payloads=false` 和明确 limitations。

## 分类边界

分类仅规范化已有消息，不执行额外 probe，也不推断系统根因：

- `MISSING_VERIFIED_EVIDENCE`；
- `EVIDENCE_UNAVAILABLE_OR_INVALID`；
- `POLICY_OR_AUTHORIZATION`；
- `DEPENDENCY_OR_PREREQUISITE`；
- `PIPELINE_BLOCKER`。

消息、stage summary 和 recommended action 继续执行路径脱敏。浏览器只接收 opaque evidence
ID，不接收任意 Artifact 路径、日志正文、策略输入或 SECRET payload。


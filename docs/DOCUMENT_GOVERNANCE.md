<!-- status: active; authority: normative; owner: docs maintainers; last_reviewed: 2026-08-29 -->

# 文档治理规则

状态：`active`
权威级别：文档元规则（不替代具体领域规范）

## 文档头部元信息

新增或大幅修改的文档必须在标题前声明以下字段。使用 HTML 注释或 YAML front matter 均可，
但字段名称保持一致：

```yaml
status: active | frozen | draft | archived | generated
authority: normative | guide | plan | reference
owner: team-or-person
last_reviewed: YYYY-MM-DD
supersedes: optional/path
source_of_truth: optional/path
```

## 去重规则

1. 同一主题只能有一个 `authority: normative` 文档；
2. 计划只描述目标、阶段和门槛，不能复制契约或操作手册全文；
3. 操作手册只描述步骤，安全约束和契约定义应链接到规范文档；
4. `draft`、`plan` 和历史审计不能出现在当前规范的唯一入口中；
5. 生成文档必须注明生成源，禁止直接编辑生成输出；
6. 被归档文档保留 Git 历史；兼容跳转页只在迁移窗口内保留。窗口结束后删除前，必须完成
   迁移公告、全仓库及已知外部链接搜索、最终链接检查和文档治理检查。
7. 根目录只保留导航、生成契约和被既有 API/测试固定引用的兼容契约；新增专题必须进入主题目录。

## 当前入口

- 当前文档导航：[README.md](README.md)
- 工程状态台账：[reference/ENGINEERING_STATUS.md](reference/ENGINEERING_STATUS.md)
- v2 Agent-native Tool 标准：[AGENT_NATIVE_TOOLS.md](adapt/AGENT_NATIVE_TOOLS.md)
- v2 实现地图：[IMPLEMENTATION_MAP.md](reference/IMPLEMENTATION_MAP.md)
- v2 工程状态：[ENGINEERING_STATUS.md](reference/ENGINEERING_STATUS.md)

## 审查清单

- 是否已有同主题权威文档？
- 新内容应合并、链接还是归档？
- 是否更新了替代关系、入口和反向链接？
- 是否需要更新 Schema、代码、测试或生成命令？
- 若变更了公开入口、阶段实现、Schema、artifact 或测试证据，是否同步更新工程状态台账？
- 是否能通过 Markdown 链接和生成物一致性检查？

本地可运行 `python scripts/check_docs.py` 执行与 CI 相同的目录、元信息和链接检查。

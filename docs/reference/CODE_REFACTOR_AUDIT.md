<!-- status: active; authority: reference; owner: docs maintainers; last_reviewed: 2026-08-28 -->

# 代码重构审计

> 审计日期：2026-08-27
> 范围：`src/rolo`、`tests/` 与当前白皮书所描述的控制面
> 目标：在产品定义、公开接口和安全边界不变的前提下降低重复与变更耦合

## 结论先行

代码库的主要问题不是缺少抽象，而是同一领域概念在多个 read model、stage service 和证据流程中重复表达。当前最安全的第一步是收敛“制品路径准备”这一真实重复；更大范围的合并应以 characterization tests 和模块级批次推进，不能直接重写 `discovery.py`、`active_discovery.py` 或各类 Episode read model。

本次已实施一个行为保持重构：`ArtifactStore.append_jsonl`、`write_json`、`write_text` 的目录准备逻辑统一到 `_prepare_path`。JSON 序列化方式、原子写入、追加顺序、返回路径和并发语义均保持不变。

## 基线与证据

| 检查 | 结果 |
|---|---|
| 工作区 | 修改前无未提交变更 |
| 全量测试（临时目录指向工作区） | 648 passed, 8 skipped；2 个既有失败，均为 `ROLO_OUTPUT_DIR`/source-tree 路径约束测试环境问题 |
| `ruff check src tests` | Passed |
| 重构前 characterization gate | 新增测试尚未修改生产代码前通过 |
| 重构后 ArtifactStore + persistence | 5 passed |

直接运行 `uv run pytest` 不可用，因为当前环境未安装 `uv`；使用仓库已有 `.venv` 等价执行。系统默认临时目录会触发 Windows 权限错误，因此验证命令显式设置了工作区内 `.pytest-tmp`。

## 已完成的最小重构

### 观察到的摩擦

`src/rolo/core/artifacts.py` 中三个公开写方法都重复执行：

1. `self.ensure()`；
2. 拼接 `root / relative_path`；
3. 创建父目录。

这段重复没有表达不同策略，且未来修改制品路径边界时容易只改其中一处。

### 变换与保护

- 新增私有 `_prepare_path(relative_path)`，只负责目录准备和路径拼接；
- 三个公开方法继续各自负责 JSONL 追加、JSON 原子写入和文本原子写入；
- 新增 `tests/test_artifacts_legacy_characterization.py`，固定嵌套路径、Unicode、JSON 格式、追加顺序和返回路径；
- 保留既有 `tests/test_persistence.py` 的并发与原子写入测试。

这次变换没有新增公共 API、依赖、权限、验证规则或序列化字段。

## 重复与冗余审计结果

### P0：已处理

| 区域 | 证据 | 处理 |
|---|---|---|
| 制品写入准备 | `core/artifacts.py` 三个方法重复 mkdir/路径拼接 | 合并为 `_prepare_path`，保留公开写策略分离 |

### P1：建议下一批处理

| 区域 | 重复形态 | 最小安全方案 | 风险与保护测试 |
|---|---|---|---|
| `stages/adapt/target_evidence.py` 与 `core/persistence.py` | 两套 `_atomic_write_text`；临时文件、fsync、replace 语义相近但细节不同 | 先为 re-enrollment/transition 写并发、`require_absent`、失败清理 characterization，再评估复用 `core.persistence.atomic_write_text` | 高：签名部署与轮换；`test_target_evidence_deployment.py` 全集 |
| `episode_projection.py` 与 `episode_observation_bundles.py` | 不可变 revision 的 digest、路径、发布和验证步骤高度同构 | 抽取仅承载“canonical JSON + digest + immutable write”的小函数；保留各自 Pydantic 语义校验 | 高：Episode projection/bundle 全集、schema 导出 |
| `episode_read_models.py`、`workbench_read_models.py`、`lifecycle_read_models.py` 等 | collection/detail/page 的分页、空集合、opaque reference 与一致性检查重复 | 先统一只读分页值对象或内部 `page_items` 函数，不合并领域模型 | 中高：各 read-model 测试与 API contract |
| `stages/adapt/discovery.py`、`active_discovery.py`、`heuristic_discovery.py` | 发现输入归一化、证据优先级和候选去重逻辑分散 | 先画调用图，按“事实来源优先级”提取纯函数；不移动探针/安全边界 | 高：Discovery、active、heuristic、target evidence 全集 |

### P2：保持现状，避免过度抽象

- `commands/*` 与 `stages/*` 的边界是产品命令域与生命周期边界，不应为了减少文件数合并。
- `Canonical Operation`、`Operation Contract`、`Tool Catalog`、`State Graph`、`Handoff` 虽然在文档中反复出现，但在产品语义上分别回答“词汇、契约、可见控制面、状态关系、阶段交付”；应通过文档明确职责，而不是代码层强行共享一个模型。
- Provider、Adapter、Agent 和 Gate 的重复校验看起来相似，但代表不同信任域；删除校验会改变失败关闭边界，暂不重构。

## 变更模拟

一个现实的下一步需求是“增加新的 immutable artifact 类型并保留原子写入与审计”。

- 重构前：需要在每个写方法中重复修改目录准备逻辑，并检查三处是否一致。
- 重构后：目录准备集中在 `_prepare_path`，新增 artifact 类型只需选择已有写策略；JSONL/JSON/text 的差异仍在调用点可见。

这说明本次抽取降低了真实的 change coupling，同时没有引入跨模块导航成本。

## 建议的后续批次

1. 为 `target_evidence` 的私有原子写入补 characterization，再决定是否统一到 `core.persistence`；
2. 将 Episode 两条发布链路的公共“规范化、摘要、不可变写入”提取为纯函数，先不合并领域校验；
3. 统一只读分页和 opaque reference 的内部工具函数，保持公开 Schema 与错误行为不变；
4. 最后再评估 Discovery 大模块拆分。拆分前必须保留端到端 Journey、目标证据绑定和安全负向测试。

每批都应遵循：先记录基线 → 增加 characterization → 小范围重构 → 运行窄测试 → 检查 diff → 再运行全套验证。任何行为变化（字段、排序、错误映射、权限、审计、事务或失败关闭）都应另立需求，不与重构混合。

# Registry Operation 重设计 Worktree 与合并计划

状态：已落地（首轮实现）。本文定义协作边界和合并顺序；对应 worktree 与分支已创建，首轮
R0-R2/R3 基础实现已合并到 `codex/registry-redesign-integration`。

## 1. 总体原则

- 当前 `main`/集成工作树继续作为 v1 294 项兼容基线；
- 每个 worktree 只拥有一类文件，禁止多个 worktree 同时修改 Registry 核心文件；
- 先合入接口和 Schema，再合入实现，最后合入 Registry 切换；
- 所有跨 worktree 依赖通过提交 SHA 和 fixture 传递，不复制另一 worktree 的实现；
- 任何改变 v1 digest、Catalog 或 release 行为的提交必须在 integration worktree 中显式审查。

实际工作树根目录：

```text
C:\Users\zarch\Desktop\robot_loop                              # integration
C:\Users\zarch\Desktop\robot_loop\.worktrees\registry-governance
C:\Users\zarch\Desktop\robot_loop\.worktrees\registry-native-tools
C:\Users\zarch\Desktop\robot_loop\.worktrees\registry-v2-core
C:\Users\zarch\Desktop\robot_loop\.worktrees\registry-runtime
C:\Users\zarch\Desktop\robot_loop\.worktrees\registry-validation
```

分支统一使用 `codex/registry-redesign-` 前缀。

当前 integration 已合并提交：角色投影、bounded Agent-native Runner、Agent-native Schema、
v2 shadow projection、version-bound resolver、family-level native catalog、Native Session/Broker、
Adapt 接入、迁移校验报告及 native tool ID 冲突测试。v1 Registry、release 和现有运行时默认
行为保持不变；`adapt_native_tool_mode` 默认 `off`。

## 2. Worktree 矩阵

| Worktree | 分支 | 主要职责 | 依赖 | 禁止修改 |
|---|---|---|---|---|
| integration | `codex/registry-redesign-integration` | 合并、生成文档、跨模块测试、最终切换 | 全部 | 在依赖未合并前不得改 v1 行为 |
| governance | `codex/registry-redesign-governance` | role/disposition 模型、294 项处置矩阵、legacy ledger | RFC 文档 | `operation_registry.py`、contract YAML、runtime |
| native-tools | `codex/registry-redesign-native-tools` | Agent-native Tool descriptor、bounded runner、evidence envelope | governance Schema 只读接口 | Canonical Registry、release/session |
| v2-core | `codex/registry-redesign-v2-core` | Canonical v2 投影、Product Control/Provider 分层、Contract catalog | governance 提供的角色矩阵 | native runner、release loader |
| runtime | `codex/registry-redesign-runtime` | Registry resolver、v1/v2 release/session 兼容、交叉调用拒绝 | v2-core API、native-tools result Schema | `_GROUPS` 大规模删改、生成文档 |
| validation | `codex/registry-redesign-validation` | 双 fixture、shadow/canary、迁移矩阵、验收脚本和文档校验 | 各 worktree 提交 SHA | 生产逻辑和基线常量 |

family-level descriptor、结构化参数和 ROS/Linux/HW mode 继续由 native-tools worktree 维护；
不再按每条命令拆出新的共享核心 worktree。

## 3. 文件所有权

### governance

允许修改：

```text
src/rolo/stages/adapt/operation_governance.py
src/rolo/stages/adapt/operation_dispositions.yaml
schemas/OperationDispositionLedger.schema.json
schemas/LegacyOperationDisposition.schema.json
tests/test_operation_governance.py
docs/OPERATION_GOVERNANCE.md
```

交付物：

- `RegistryRole`、`ExecutionPath` 枚举；
- 294 项精确覆盖的 role matrix；
- `legacy-operation-dispositions` Schema；
- pair、replacement、compensation 和安全边界的完整性校验；
- 不改变 v1 Registry digest 的回归证明。

### native-tools

建议新增目录：

```text
src/rolo/agent_tools/
tests/test_agent_native_tools.py
schemas/AgentNativeTool.schema.json
schemas/AgentNativeToolResult.schema.json
docs/AGENT_NATIVE_TOOLS.md
```

允许修改现有公共 Runner 的共享安全代码，但必须保持原调用者兼容。不得在本 worktree 中
删除或重命名 Canonical Operation。

交付物：

- Tool descriptor/result 模型；
- argv-only runner；
- Linux/ROS/首批 HW 只读 descriptors；
- 超时、截断、redaction、环境清理、路径边界和审计测试；
- Agent-native Tool 不产生 `VERIFIED` 的负向测试。

### v2-core

允许修改：

```text
src/rolo/stages/adapt/operation_registry_v2.py
src/rolo/operation_contracts_v2/*.yaml
src/rolo/stages/adapt/operation_registry.py  # 仅在 integration 批准后改 v1 兼容入口
schemas/CanonicalOperationRegistryV2.schema.json
tests/test_registry_v2.py
```

原则：

- 优先新增 v2 loader/projection，不直接覆盖 `canonical_operation_registry()` 的 v1 行为；
- v2 Canonical 只包含 `registry_role=CANONICAL`；
- Product Control、Agent-native、Provider 都有独立索引；
- 所有 contract pair/compensation/replacement 引用必须指向活动 v2 项或明确 legacy 规则。

交付物：

- v2 Registry identity 和版本号；
- v1/v2 投影 fixture；
- Canonical、Product Control、Agent-native、Provider 的边界检查；
- 生成文档的输入模型，不直接提交手工编辑的生成内容。

### runtime

允许修改：

```text
src/rolo/adapter_runtime.py
src/rolo/stages/adapt/agent_contracts.py
src/rolo/stages/adapt/conformance.py
src/rolo/stages/adapt/tool_gateway.py
src/rolo/stages/downstream_tools.py
tests/test_adapter_runtime.py
tests/test_tool_gateway.py
tests/test_downstream_tools.py
```

交付物：

- `RegistryResolver(version, digest)`；
- release-bound Registry 校验；
- v1/v2 Tool Session 隔离；
- Legacy Operation 新会话拒绝；
- v1/v2 交叉 digest、Catalog、State Graph 和 contract 拒绝测试；
- v1 release 审计读取和回滚路径。

runtime worktree 不拥有 `_GROUPS`、contract YAML 的业务取舍，避免把兼容逻辑和词汇删减
混在同一个提交中。

### validation

允许修改：

```text
tests/fixtures/registry_v1/
tests/fixtures/registry_v2/
tests/test_registry_migration.py
tests/test_shadow_registry.py
scripts/validate_registry_migration.py
docs/REGISTRY_OPERATION_REDESIGN_PLAN.md
docs/REGISTRY_OPERATION_WORKTREE_PLAN.md
```

如果生成文档需要变更，validation 只提交生成命令和校验，不手工修改 `OPERATION_CONTRACTS.md`
或 `CANONICAL_OPERATIONS.md`；最终生成由 integration 统一完成。

## 4. 接口冻结顺序

### I0：先冻结治理 Schema

governance 提交以下接口后，其他 worktree 才能开始：

```text
RegistryRoleDisposition
LegacyOperationDisposition
AgentNativeToolRef
```

接口只允许追加字段，不允许在同一轮变更字段语义。

### I1：冻结 Agent-native Tool result

native-tools 提交 descriptor/result Schema 后，v2-core 和 validation 可以消费；runtime 不得
把 Agent-native Tool 自动转换成 Canonical Operation。

### I2：冻结 v2 Registry resolver

v2-core 提供：

```python
load_registry(version: str | None = None, digest: str | None = None)
registry_identity(registry)
```

runtime 只依赖该接口，不读取 `_GROUPS` 或直接解析 contract YAML。

### I3：冻结 shadow report

validation 提供 v1/v2/native 三方差异 Schema，integration 才开始灰度逻辑和生成文档。

## 5. 合并顺序

1. **governance**：角色模型、legacy ledger、精确覆盖测试；
2. **native-tools**：Tool descriptor/result、bounded Runner、只读首批工具；
3. **v2-core**：v2 Canonical projection、独立 Product Control/Provider 索引；
4. **runtime**：release-bound resolver、session 隔离和交叉调用拒绝；
5. **validation**：双 Registry fixture、shadow/canary、迁移矩阵；
6. **integration**：生成 Schema/docs、接入 Adapt、运行全量回归，最后才启用 feature flag。

任何步骤失败时，只回退该 worktree 的提交，不回滚当前 v1 baseline。

## 6. 每个 Worktree 的验收命令

所有命令从仓库根目录执行。Windows 临时目录若受 ACL 限制，应将 `TEMP`/`TMP` 指向仓库内
可写目录后再运行。

```powershell
uv run ruff check .
uv run pytest tests/test_operation_governance.py
uv run pytest tests/test_registry_v2.py tests/test_registry_migration.py
uv run pytest tests/test_agent_native_tools.py
uv run pytest tests/test_adapter_runtime.py tests/test_tool_gateway.py tests/test_downstream_tools.py
uv run pytest
uv run robotctl tool contract validate
```

integration 的额外门禁：

```powershell
uv run python scripts/validate_registry_migration.py
uv run robotctl adapt slice-observability --help
uv run pytest tests/test_conformance.py tests/test_discovery.py tests/test_stages.py
```

## 7. 提交和冲突规则

- 每个提交只对应一个可回滚的边界：Schema、Runner、v2 loader、runtime compatibility、测试；
- 不允许在同一提交同时删除 Operation、改变 release identity、修改 policy 和更新文档；
- 生成文件必须由固定命令生成，并在提交中记录输入 digest；
- 修改 v1 `_GROUPS`、v1 contract YAML 或 `PINNED_ADAPT_BASELINE` 必须由 integration owner 批准；
- 任何新增 Canonical Operation 必须先有 role matrix entry 和 contract；
- Agent-native Tool 不得反向写入 `operation_dispositions.yaml` 的 Canonical 条目；
- merge 前必须提供“v1 行为不变”与“v2 行为新增”的分离测试结果。

## 8. Worktree Definition of Done

### governance

294 项精确覆盖、role 冲突拒绝、legacy 引用校验、v1 digest 不变。

### native-tools

至少一个 Linux、一个 ROS、一个 HW 只读 family 跑通成功/失败/超时/截断/拒绝路径，并有审计
和 evidence artifact；family 参数不得产生任意 argv。

### v2-core

可以从处置矩阵生成 v2 Canonical、Product Control、Agent-native、Provider 四个索引；
pair/compensation/replacement 完整；v1 loader 仍通过原测试。

### runtime

旧 release 可加载，新 release 可加载，v1/v2 不可交叉调用，legacy 不可进入新 Tool Session。

### validation

shadow report 可复现；差异有分类和阈值；canary 回退路径通过测试；无 silent drop。

### integration

全量测试、lint、Schema export、Contract validate、v1 baseline 和 v2 migration report 全部通过，
且 `adapt_native_tool_mode` 默认关闭；shadow/canary 报告、artifact/evidence 绑定和回退路径
通过后，等待人工评审再启用 active。

## 9. 第一轮建议切片

第一轮只接入：

```text
native-tools: Linux host/process/resource、ROS graph/node/topic、HW inventory/status
v2-core: 保留 app.teleop/base/safety/task 及必要的 HW mutation
runtime: 只做 release/session identity 隔离
validation: 一个 synthetic target + 一个 source-only negative path
```

第一轮的成功标准是证明直接工具可以替代冗余 wrapper，同时没有扩大 Agent 权限；不是一次
性完成全部 Registry 迁移。

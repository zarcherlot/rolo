<!-- status: active; authority: reference; owner: ROLO maintainers; last_reviewed: 2026-08-29; last_synced_commit: b8c4806ca5bdc6ca3b8b6a2bcb7625c87712928b -->

# 工程状态与可信度台账

本文是 ROLO 当前实现的状态索引，服务于 Codex、开发者和评审者。它不授予 release、
acceptance 或安全 authority，也不替代架构、操作手册、Contract、Schema 和测试。

## 1. 如何阅读

每一行代表一个可识别的功能域，而不是一个 Python 类。状态和证据必须同时阅读：

- `STABLE`：公开行为、失败边界和兼容策略已固定，并有可复现验证路径；
- `PARTIAL`：核心切片可用，但仍缺少部分场景、消费者或生产闭环；
- `EXPERIMENTAL`：接口或运行策略仍可能变化，通常受 feature flag、Provider 或环境限制；
- `DRAFT`：只有设计/早期实现，不能作为产品承诺；
- `DEPRECATED`：保留迁移或兼容用途，不应作为新代码入口；
- `BLOCKED`：存在未解决的外部依赖、风险或评审门槛。

证据等级不是成熟度的同义词：

| 等级 | 含义 |
|---|---|
| `E0` | 设计或文档证据 |
| `E1` | 单元、契约或拒绝路径测试 |
| `E2` | 本地离线端到端或可重复 fake/replay 路径 |
| `E3` | 固定目标机、Provider 或 fixture 验证 |
| `E4` | 真实目标机闭环验收 |

`E2` fake/replay 只能证明软件路径，不证明真实机器人行为。`STABLE` 也不代表物理安全；
所有写操作、目标机 acceptance 和 release authority 仍须遵循各自 Gate。

## 2. 当前功能台账

代码路径和测试路径使用反引号标记，由 `scripts/check_docs.py` 检查必须存在。新增公共
功能、API、Schema、artifact 或状态变化时，必须新增或更新一个 `FEAT-*` 行。

| feature_id | maturity | evidence | user surface | code_paths | test_paths | known limits |
|---|---|---|---|---|---|---|
| FEAT-ADAPT-LOCAL | STABLE | E2 | `rolo adapt` 离线/本地路径 | `src/rolo/product_cli.py`; `src/rolo/commands/lifecycle.py` | `tests/test_product_cli.py`; `tests/test_adapt_journey.py` | 不等同于真实目标机验收 |
| FEAT-ADAPT-GATE-RELEASE | STABLE | E2 | Adapt bundle、conformance、immutable release | `src/rolo/stages/adapt/service.py`; `src/rolo/stages/adapt/conformance.py`; `src/rolo/adapter_runtime.py` | `tests/test_conformance.py`; `tests/test_adapter_runtime.py`; `tests/test_adapt_journey.py` | Adapt 不证明物理结果、可靠性或安全性 |
| FEAT-TARGET-EVIDENCE | PARTIAL | E2 | 目标证据采集和部署前检查 | `src/rolo/stages/adapt/target_evidence.py`; `src/rolo/targets/executor.py`; `src/rolo/episode_capture.py` | `tests/test_target_evidence_deployment.py`; `tests/test_target_executors.py`; `tests/test_episode_capture.py` | 真实目标、SSH 和平台依赖仍需环境验证 |
| FEAT-REGISTRY-V2 | PARTIAL | E2 | v2 Canonical Registry 与迁移校验 | `src/rolo/stages/adapt/operation_registry_v2.py`; `src/rolo/stages/adapt/registry_resolver.py` | `tests/test_registry_v2.py`; `tests/test_registry_migration.py` | v1 兼容、v2 投影和 Native family 不能混用 |
| FEAT-NATIVE-TOOLS | EXPERIMENTAL | E3 | Native Session、Broker、family rollout | `src/rolo/agent_tools/native_tools.py`; `src/rolo/agent_tools/session.py`; `src/rolo/agent_tools/broker.py`; `src/rolo/agent_tools/rollout.py` | `tests/test_agent_native_tools.py`; `tests/test_native_tool_session.py`; `tests/test_native_rollout.py` | 固定 WSL/ROS 目标已完成 shadow/canary rehearsal；默认关闭且只读观测不能授予 release authority |
| FEAT-STAGE-RUNNER | STABLE | E3 | Diagnose/Verify 授权、幂等、取消和日志 | `src/rolo/stages/agent_runner.py`; `src/rolo/stages/downstream.py` | `tests/test_stage_agent_runner.py`; `tests/test_stage_agent_read_models.py` | Runner 不决定业务结论或 acceptance |
| FEAT-DIAGNOSE-CONTRACT | PARTIAL | E3 | Diagnose plan、report、config、Episode 和 handoff | `src/rolo/stages/diagnose/service.py`; `src/rolo/stages/diagnose_contract.py`; `src/rolo/stages/diagnose/episode.py` | `tests/test_diagnosis_contract.py`; `tests/test_handoff_materializers.py`; `tests/test_real_target_contracts.py` | 固定 Linux/ROS 目标切片可闭环；无真实 Episode 时不能形成真实诊断结论 |
| FEAT-VERIFY-CONTRACT | PARTIAL | E3 | Verify plan、acceptance plan、evidence 和 replay | `src/rolo/stages/verify/service.py`; `src/rolo/stages/verify/acceptance.py`; `src/rolo/stages/verify/legacy_adapter.py`; `src/rolo/stages/verify/ssh_provenance.py`; `src/rolo/stages/real_target.py` | `tests/test_verification_acceptance.py`; `tests/test_legacy_provider_adapter.py`; `tests/test_post_r5_provider_boundary.py`; `tests/test_ssh_provenance.py`; `tests/test_handoff_materializers.py`; `tests/test_real_target_contracts.py` | P1 v1 仅可经显式 adapter 转为 v2；SSH 身份快照已可生成 canonical binding，但真实 provider、物理机器人和通用 acceptance oracle 仍是扩展点 |
| FEAT-STAGE-PLUGIN | PARTIAL | E1 | Stage executor/harness entry point 与 manifest | `src/rolo/stages/plugin_manifest.py`; `src/rolo/agent_provider.py` | `tests/test_plugin_manifest.py`; `tests/test_codex_downstream.py` | 插件包安装、隔离运行和跨版本生产验证仍待完成 |
| FEAT-LOCAL-REAL-TARGET | PARTIAL | E3 | profile 绑定的 Linux/ROS Diagnose/Verify provider | `src/rolo/stages/real_target.py`; `src/rolo/targets/profiles.py` | `tests/test_real_target_contracts.py`; `tests/test_target_profiles.py` | 当前是固定 WSL/Linux/ROS 软件目标，不等同于物理机器人 E4 闭环 |
| FEAT-EPISODE-READ-MODEL | PARTIAL | E2 | Episode list/detail、revision、cohort、observation bundle | `src/rolo/episode_read_models.py`; `src/rolo/episode_projection.py`; `src/rolo/episode_observation_bundles.py`; `src/rolo/episode_capture.py`; `src/rolo/api.py` | `tests/test_episode_read_models.py`; `tests/test_episode_projection.py`; `tests/test_episode_observation_bundles.py`; `tests/test_episode_api.py`; `tests/test_episode_capture.py` | 只读、bounded、revision-pinned；不代表实时采集或 remediation |
| FEAT-ROLO-VIS | EXPERIMENTAL | E1 | 同源只读 Web 控制台和授权恢复 | `src/rolo/vis.py`; `src/rolo/api.py` | `tests/test_vis.py`; `tests/test_api.py` | UI 不是安全边界，服务端仍是 authority |
| FEAT-ROLO-MCP | EXPERIMENTAL | E1 | MCP/Agent 控制面访问 | `src/rolo/mcp_server.py` | `tests/test_mcp_server.py` | 不得绕过 HTTP/Stage/Tool Gate |
| FEAT-TARGET-BOOTSTRAP | EXPERIMENTAL | E1 | 目标机 bootstrap plan/request/approve/execute | `src/rolo/targets/bootstrap.py`; `src/rolo/product_cli.py`; `src/rolo/api.py` | `tests/test_bootstrap_cli.py`; `tests/test_bootstrap_api.py`; `tests/test_bootstrap_execution.py` | 依赖目标环境、授权和部署策略 |

## 3. 可信度边界

以下判断禁止从“代码存在”或“测试通过”直接推导：

- Contract 存在不等于完整产品闭环已经交付；
- fake、replay、静态检查和模型输出不等于真实目标机行为；
- Native Tool 观测不等于 Canonical Operation 成功；
- Stage run `SUCCEEDED` 不等于 Diagnose/Verify 结论通过；
- UI、MCP 或 CLI 都不能绕过服务端身份、hash、授权和 Gate 校验。

详细设计和操作规则分别见 [实现地图](IMPLEMENTATION_MAP.md)、[三阶段架构](../architecture/ARCHITECTURE.md)、
[文档治理规则](../DOCUMENT_GOVERNANCE.md)、[开放评审队列](../review/OPEN_DECISIONS.md) 及各领域 Contract。

## 4. 合入同步规则

### PR 内更新

以下任一目录或文件变化时，PR 必须同时更新本文：

1. `src/rolo/api.py`、`pyproject.toml` 或公开 CLI/MCP/Web 入口；
2. `src/rolo/stages/`、`src/rolo/agent_tools/`、`src/rolo/targets/`；
3. `schemas/`、Contract catalog、artifact layout 或 handoff；
4. 新增、删除、启用或暂停用户可见功能；
5. 测试证据等级、目标环境或已知限制发生变化。

只修改内部重构且不改变公开入口、产物、边界或测试证据时，可以在 PR 描述中说明“状态不变”，
但仍需复核本表。

### 合入后同步

`last_synced_commit` 记录本台账最后一次完成代码复核的提交。合入后的自动化可以只更新
该字段和同步时间，不能自动把 `EXPERIMENTAL` 改成 `STABLE`。成熟度变化必须由评审者在
PR 中依据新增证据明确修改，并链接验证命令或测试。

## 5. Codex 开发检查顺序

Codex 或其他开发 Agent 开始工作前，应依次读取：

1. [最高开发准则](../architecture/DEVELOPMENT_PRINCIPLES.md)；
2. [实现地图](IMPLEMENTATION_MAP.md)；
3. 本台账；
4. 相关领域 Contract/Schema；
5. 台账中列出的测试。

交付时必须报告功能 ID、状态是否变化、新增证据、未解决边界和文档是否同步。任何无法
定位到功能 ID、代码路径、测试路径和证据等级的“已支持”表述，都应降级为 `DRAFT` 或
`EXPERIMENTAL`，直到完成评审。

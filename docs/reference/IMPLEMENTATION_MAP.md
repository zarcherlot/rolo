<!-- status: active; authority: reference; owner: docs maintainers; last_reviewed: 2026-08-29 -->

# ROLO 实现地图

本文回答“当前代码在哪里实现、如何串起来、由什么测试保护”。它不重新定义业务概念。
遇到冲突时，优先遵循 [最高开发准则](../architecture/DEVELOPMENT_PRINCIPLES.md)、版本化
Schema、Operation Contract、运行时 Gate 及其测试；阶段契约以对应的 Episode/Diagnose/Verify
文档为准。功能成熟度和证据等级以 [工程状态与可信度台账](ENGINEERING_STATUS.md) 为准。

## 1. 运行入口

| 入口 | 代码 | 用途 |
|---|---|---|
| `rolo` | `src/rolo/product_cli.py` | 面向产品流程的自然语言、目标机、profile、job 和 Adapt 入口 |
| `robotctl` | `src/rolo/cli.py`、`src/rolo/commands/` | 面向开发和运维的生命周期、Registry、Schema、target-evidence 和运行时命令 |
| `rolo-vis` | `src/rolo/vis.py` | 同源只读 Web 控制台；授权动作仍由服务端校验 |
| HTTP 控制面 | `src/rolo/api.py` | `/v1` 查询、阶段 run/取消、授权请求和 read model API |
| `rolo-mcp` | `src/rolo/mcp_server.py` | MCP/Agent 访问控制面和受限工具，不绕过服务端 Gate |

CLI 的公开脚本定义位于 `pyproject.toml`。新增入口必须同时说明输入、产物、失败关闭行为
和对应测试，不能只在 CLI help 中出现。

## 2. 生命周期主线

```text
target evidence / workspace
          │
          ▼
adapt: enrollment → discovery → Agent → bundle → conformance → release/handoff
          │
          ▼
diagnose: frozen Adapt handoff → authorized Stage Agent → diagnosis report/config → handoff
          │
          ▼
verify (optional): diagnosis handoff → acceptance plan → regression/evidence → handoff
```

三个阶段的统一状态评估由 `src/rolo/stages/pipeline.py` 组合，具体状态判断分别由：

- Adapt：`src/rolo/stages/adapt/service.py`；
- Diagnose：`src/rolo/stages/diagnose/service.py`；
- Verify：`src/rolo/stages/verify/service.py`。

`src/rolo/stages/agent_runner.py` 是 Diagnose/Verify 共用的执行边界，负责任务摘要、授权、
幂等、运行状态、日志流、取消、租约恢复和 handoff validator 回调。它本身不授予 release
或 acceptance authority。`src/rolo/user_identity.py` 为授权请求提供当前 OS 用户 principal
和 artifact-root 内持久的本地 session fingerprint；跨用户或跨 session 的恢复必须拒绝。

## 3. Adapt 实现分层

| 层 | 主要模块 | 责任和边界 |
|---|---|---|
| 登记与输入 | `stages/adapt/enrollment.py`、`inputs.py`、`target_evidence.py` | 固定 robot 身份、工作区和目标证据引用 |
| Discovery | `discovery.py`、`heuristic_discovery.py`、`ros_environment.py`、`evidence.py` | 生成机器证据、可编辑 Wiki、候选能力和 discovery manifest |
| 规划与 Agent | `journey.py`、`service.py`、`agent_runner.py`、`agent_provider.py` | 构造摘要绑定的任务；Agent 工作区是临时的，不是权威来源 |
| Bundle 与 Gate | `executor.py`、`conformance.py`、`operation_eligibility.py` | 冻结 Agent 输出，校验身份、入口、Contract、Schema、路由和覆盖率 |
| Catalog 与 State Graph | `operation_registry.py`、`operation_registry_v2.py`、`registry_resolver.py`、`state_graph.py` | 由产品代码确定性生成 Active Tool Catalog 和 State Graph |
| 发布与运行时 | `adapter_runtime.py`、`core/artifacts.py`、`artifact_paths.py` | 写入外部 artifact root，绑定 hash、fingerprint、索引并在运行时复核新鲜度 |
| Native Tool | `agent_tools/native_tools.py`、`session.py`、`broker.py`、`rollout.py` | 只读观测通道；不能进入 Canonical release authority |

Adapt 的核心不变量是“Agent 提案 ≠ Rolo 权威”：Agent 不能写 Tool Catalog，不能用静态声明
证明物理行为、可靠性或安全性；独立 Gate 和运行时校验才是发布与调用边界。详细规则见
[三阶段架构](../architecture/ARCHITECTURE.md)、[Agent-native Tools](../adapt/AGENT_NATIVE_TOOLS.md)
和 [Registry Operation 指南](../operations/REGISTRY_OPERATION_GUIDE.md)。

## 4. Diagnose 与 Verify 实现分层

### Diagnose

- 任务构建：`stages/diagnose/service.py::build_diagnosis_task`；
- 上游校验：Adapt handoff、输入摘要和 target provenance；
- 执行边界：`stages/agent_runner.py` + `stages/downstream.py`；
- 报告校验：`stages/diagnose_contract.py`、`stages/handoffs.py`；
- 只读工具会话：`stages/downstream_tools.py`；
- Episode 发布与验证：`stages/diagnose/episode.py`、`episode_projection.py`；
- 固定 Linux/ROS 目标实现：`stages/real_target.py`，只允许绑定 profile 的只读命令。
- 授权身份：`user_identity.py` 生成当前用户和持久 session fingerprint；`agent_provider.py`
  拒绝声明了不同 stage 的插件，避免 provider/executor 越界。

Diagnose 可以生成冻结配置和严格的 diagnosis report，但不能单凭 Agent 输出改变 release
authority。没有真实 Episode 时只能得出受限或 `INCONCLUSIVE` 的判断。

### Verify

- 任务构建与 acceptance plan：`stages/verify/service.py`、`stages/verify/acceptance.py`；
- 上游校验：结构化 Diagnose handoff；
- 执行边界：共用 `stages/agent_runner.py`；
- 证据校验：`stages/handoffs.py`、`stages/verify/acceptance.py`；
- 离线回放：`stages/verify/acceptance.py` 中的 replay/oracle 路径；
- P1 v1 迁移边界：`stages/verify/legacy_adapter.py`，只接受匹配 plan digest 和 canonical provenance 的单向适配；
- SSH canonical provenance：`stages/verify/ssh_provenance.py`，通过 pinned transport 采集只读目标身份并发布 binding artifact；
- SSH bounded Verify provider：`stages/verify/ssh_target_provider.py`，固定 platform/workspace/companion case 经 adapter 写入 v2 evidence；
- Verify handoff materialization：`SshTargetHealthProvider.materialize_handoff()`，重新验证 v2 evidence 后交给 canonical handoff validator；
- 固定 Linux/ROS 目标实现：`stages/real_target.py`，生成 provenance 绑定的 evidence package。

Verify 的报告和 evidence package 是可审计输入，不自动等同于真实目标机 acceptance。
`local-target` 已覆盖固定 WSL/Linux/ROS 软件目标上的有界只读切片，但真实机器人验收和
通用产品化 oracle 仍需单独的物理目标环境与扩展实现。

本地无目标机的开发路径见 [LOCAL_DIAGNOSE_VERIFY_FAKE.md](../validation/LOCAL_DIAGNOSE_VERIFY_FAKE.md)。

## 5. Registry 与 Episode 的代码对应

### Registry

| 视图 | 当前含义 | 代码入口 |
|---|---|---|
| v1 | 完整产品词汇，294 项，保留兼容和审计用途 | `stages/adapt/operation_registry.py`、`contract_catalog.py` |
| v2 | 默认运行时 Canonical 投影，197 项 | `stages/adapt/operation_registry_v2.py`、`registry_resolver.py` |
| Native family | 22 个 Agent-native 只读 family，不属于 Canonical Registry | `agent_tools/native_tools.py`、`rollout.py` |

Registry 的字段、Contract SHA、迁移关系和门禁仍以 [Registry Operation 指南](../operations/REGISTRY_OPERATION_GUIDE.md)
及生成目录为准；本文只标出代码位置，避免再次复制 294 项定义。

### Episode read model

Episode 原始 record、不可变 publication 和脱敏 projection 由：

- `src/rolo/episode_read_models.py`：模型、枚举、边界和分页/窗口类型；
- `src/rolo/episode_projection.py`：从内部 record 构造对外只读 projection；
- `src/rolo/episode_observation_bundles.py`：观察 bundle 的 producer/校验；
- `src/rolo/episode_capture.py`：从只读 target inspection 生成 metadata-only immutable Episode；
- `src/rolo/api.py`：episodes、revision history、cohort、observation bundle 端点。

四类接口均以 revision pin 和 bounded read 为原则；它们不隐式提供实时采集、写操作、回放
或 remediation。详细字段和状态以根目录对应的 Episode contract 文档为准。

## 6. Artifact 与 Schema

`src/rolo/stages/artifact_paths.py::ArtifactLayout` 是生命周期 artifact 路径的唯一词汇。
`resolve_artifact_ref()` 拒绝绝对路径、`..` 和越出 artifact root 的引用。典型布局如下：

```text
<ROLO_ARTIFACT_DIR>/
├── discovery/<robot>/runs/<discovery_id>/
├── adapt/<robot>/{latest,latest.json,runs/<run_id>/}
├── diagnose/<robot>/{latest,latest.json,runs/<run_id>/}
├── verify/<robot>/{latest,latest.json,runs/<run_id>/}
└── episodes/<robot>/{records,published,observation-records,published-observations}/
```

生成和消费 artifact 时，应优先使用 `ArtifactLayout` 与 `artifact://` 引用，不在新代码中
拼接本地绝对路径。Schema 文件位于 `schemas/`，生成型 Contract 目录由
`src/rolo/contract_catalog.py` 维护。

## 7. 测试保护面

| 实现面 | 主要测试 |
|---|---|
| Adapt journey、bundle、Gate、release | `test_adapt_journey.py`、`test_conformance.py`、`test_adapter_runtime.py` |
| Registry v1/v2、角色和迁移 | `test_registry.py`、`test_registry_v2.py`、`test_registry_migration.py` |
| Native Tool session/broker/rollout | `test_agent_native_tools.py`、`test_native_tool_session.py`、`test_native_rollout.py` |
| Stage Agent 授权、幂等、取消、日志 | `test_stage_agent_runner.py`、`test_stage_agent_read_models.py` |
| Diagnose/Verify contract、fake、handoff、P1 adapter 与 SSH provider | `test_diagnosis_contract.py`、`test_verify_evidence_contract.py`、`test_legacy_provider_adapter.py`、`test_post_r5_provider_boundary.py`、`test_ssh_provenance.py`、`test_ssh_target_provider.py`、`test_ssh_provider_handoff.py`、`test_ssh_provider_recovery.py`、`test_fake_downstream.py`、`test_handoff_materializers.py` |
| 固定 Linux/ROS 目标与 Stage 插件 | `test_real_target_contracts.py`、`test_plugin_manifest.py` |
| Episode projection/read model/API | `test_episode_read_models.py`、`test_episode_projection.py`、`test_episode_api.py` |
| HTTP/MCP/Web 入口 | `test_api.py`、`test_mcp_server.py`、`test_vis.py` |
| Schema 与 Contract 完整性 | `test_schemas.py`、`test_contract_catalog.py` |

新增公共入口或产物时，至少补充一条成功路径、一条拒绝/失败路径，并把测试加入本表；
工程测试不能被描述为真实机器人 acceptance。

## 8. 当前已实现与明确边界

已实现的主线包括：离线/目标证据登记、Bounded Discovery、Adapter Agent 临时工作区、
独立 Conformance Gate、不可变 Adapt release、Diagnose/Verify Stage Agent envelope、授权
与恢复、Episode 只读 read model、固定 Linux/ROS 目标上的只读 Diagnose/Verify provider、
Stage 插件 manifest，以及 Native Tool 的受控观测通道。

以下能力不要从现有代码或 contract 推断为已完成：

- 完整的 Episode Studio、实时流、跨版本 replay 和 remediation 产品闭环；
- 真实目标机上的通用 acceptance oracle；
- Native Tool 对写操作、校准、reset、actuator、power 或 firmware 的授权；
- Agent 自己声明的静态测试、模型结论或 fake 结果成为 release/acceptance authority。

## 9. 更新触发器

以下变更必须复核本文：

1. `pyproject.toml` 增删公开脚本；
2. `src/rolo/api.py` 增删 `/v1` 公共端点；
3. 生命周期阶段、Stage Agent runner 或 handoff contract 变化；
4. `ArtifactLayout`、Schema、Contract catalog 或 Registry 版本变化；
5. 新增/删除测试保护面，或实现边界从 deferred 变为 active。

本文只做“代码 → 文档”的索引，不应成为第二份架构白皮书。若某条内容需要规范性解释，
应回链到权威文档并在此处删除重复表述。

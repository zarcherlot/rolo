<!-- status: active; authority: reference; owner: rolo maintainers; last_reviewed: 2026-09-02; last_synced_commit: 1b4093f1a85e629c05296ae08d32a27dc901da30 -->

# Rolo v2 工程状态

本台账只记录当前 Probe-first 产品链；Trace、Certify、MCP 和 Web UI 不属于本轮交付。
`STABLE` 表示边界和拒绝路径有测试，`PARTIAL` 表示仍需真实目标机或平台证据，`DRAFT`
表示仅有设计。证据等级：E0 文档、E1 单测、E2 离线闭环、E3 固定目标机、E4 真机闭环。

| feature_id | maturity | evidence | user surface | code_paths | test_paths | known limits |
|---|---|---|---|---|---|---|
| FEAT-PROBE-ENROLLMENT | STABLE | E3 | `rolo target profile`; `rolo target inspect-profile` | `src/rolo/targets/profiles.py`; `src/rolo/targets/credentials.py`; `src/rolo/targets/executor.py` | `tests/test_target_profiles.py`; `tests/test_target_credentials.py`; `tests/test_target_executors.py` | 需要用户首次批准 host key；密码只用于一次性置备，运行时不接受密码 |
| FEAT-PROBE-EVIDENCE | STABLE | E3 | `robotctl probe target-evidence` | `src/rolo/stages/adapt/target_evidence.py` | `tests/test_probe_evidence_contract.py`; `tests/test_target_evidence_deployment.py`; `tests/test_ssh_target_e2e.py` | Evidence 是采集时刻事实；可携带签名 source snapshot，但不证明物理安全或行为正确性 |
| FEAT-PROBE-NATIVE-SURFACE | STABLE | E2 | `rolo target tool-surface --profile` | `src/rolo/agent_tools/native_tools.py`; `src/rolo/agent_tools/session_factory.py` | `tests/test_agent_native_tools.py`; `tests/test_probe_session_factory.py` | 当前为四类 family 的只读 surface；缺失命令返回 UNAVAILABLE |
| FEAT-PROBE-TOOL-PLAN | STABLE | E2 | `rolo target tool-plan --profile PLAN.json` | `src/rolo/agent_tools/planning.py`; `src/rolo/agent_tools/session.py` | `tests/test_tool_planning.py`; `tests/test_native_tool_session.py` | Agent 只能规划，Rolo 校验 digest、目标、allowlist、预算和只读模式 |
| FEAT-PROBE-SSH-RUNNER | PARTIAL | E3 | profile-bound remote Native Tool execution | `src/rolo/targets/executor.py`; `src/rolo/agent_tools/native_tools.py` | `tests/test_target_executors.py`; `tests/test_agent_native_tools.py` | Provider 可能依赖目标 OS/Middleware setup、Python packages 和 runtime libraries；环境不全时明确失败 |
| FEAT-PROBE-CONFORMANCE | PARTIAL | E2 | Tool Surface / ToolPlan conformance artifacts | `src/rolo/agent_tools/session.py`; `src/rolo/stages/adapt/conformance.py` | `tests/test_native_tool_session.py`; `tests/test_conformance.py` | Native evidence 不授予 release authority；能力 gap 才进入 Adapter bundle |

## 可信度边界

- Agent 的自然语言、候选工具和计划不是事实；Rolo 的 descriptor、session、digest、结果
  artifact 和 Conformance 才是可审计边界。
- Codex 已知的目标 OS/Middleware CLI 不重复包装；Rolo 只负责固定 argv、目标绑定、环境边界和证据。
- 当 Codex 无法稳定调用目标 OS/Middleware 或 application 的底层接口时，才值得新增 Adapter bundle；新增能力必须
  经过 bounded Probe、TargetEvidence、Adapter bundle 和独立 Conformance。
- 真实目标机验证当前覆盖 mentorpi 的当前 OS/Middleware 只读证据；provider-specific coverage
  仍不是产品级全平台承诺。写操作、驱动变更和
  物理行为验收仍需单独授权。

## 同步规则

修改 `src/rolo/targets/`、`src/rolo/agent_tools/`、目标证据、公共 CLI 或 schema 时，必须
更新本表和对应测试路径。只要证据等级没有提升，不得把 `PARTIAL` 自动改成 `STABLE`。

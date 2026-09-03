<!-- status: active; authority: reference; owner: rolo maintainers; last_reviewed: 2026-09-02; last_synced_commit: 300078e7e6b83ddaa2081fe9753e3e09af6ffb17 -->

# Rolo v2 工程状态

本台账只记录当前 Probe-first 产品链；Trace、Certify、MCP 和 Web UI 不属于本轮交付。
`STABLE` 表示边界和拒绝路径有测试，`PARTIAL` 表示仍需真实目标机或平台证据，`DRAFT`
表示仅有设计。证据等级：E0 文档、E1 单测、E2 离线闭环、E3 固定目标机、E4 真机闭环。

| feature_id | maturity | evidence | user surface | code_paths | test_paths | known limits |
|---|---|---|---|---|---|---|
| FEAT-PROBE-ENROLLMENT | STABLE | E4 | `rolo target profile`; `rolo target inspect-profile` | `src/rolo/targets/profiles.py`; `src/rolo/targets/credentials.py`; `src/rolo/targets/executor.py` | `tests/test_target_credentials.py`; `tests/test_target_executors.py`; `tests/test_product_cli_v2.py` | 需要用户首次批准 host key；密码只用于一次性置备，运行时不接受密码 |
| FEAT-PROBE-EVIDENCE | STABLE | E4 | `rolo probe`; `robotctl probe start` | `src/rolo/stages/probe/target_evidence.py`; `src/rolo/stages/probe/active_discovery.py`; `src/rolo/stages/probe/discovery.py` | `tests/test_probe_evidence_contract.py`; `tests/test_product_cli_v2.py` | Evidence 是采集时刻事实；可携带签名 source snapshot，但不证明物理安全或行为正确性 |
| FEAT-PROBE-NATIVE-SURFACE | STABLE | E4 | `rolo target tool-surface --profile` | `src/rolo/agent_tools/native_tools.py`; `src/rolo/agent_tools/session_factory.py` | `tests/test_agent_native_tools.py`; `tests/test_probe_session_factory.py` | 当前为四类 family 的只读 surface；缺失命令返回 UNAVAILABLE |
| FEAT-PROBE-TOOL-PLAN | STABLE | E4 | `rolo target tool-plan --profile PLAN.json` | `src/rolo/agent_tools/planning.py`; `src/rolo/agent_tools/session.py` | `tests/test_tool_planning.py`; `tests/test_native_tool_session.py`; `tests/test_product_cli_v2.py` | Agent 只能规划，Rolo 校验 digest、目标、allowlist、预算和只读模式 |
| FEAT-PROBE-SSH-RUNNER | STABLE | E4 | profile-bound remote Native Tool execution | `src/rolo/targets/executor.py`; `src/rolo/agent_tools/native_tools.py` | `tests/test_target_executors.py`; `tests/test_agent_native_tools.py`; `tests/test_product_cli_v2.py` | Provider 可能依赖目标 OS/Middleware setup、Python packages 和 runtime libraries；环境不全时明确失败 |
| FEAT-PROBE-CONFORMANCE | STABLE | E4 | Tool Surface / ToolPlan conformance artifacts | `src/rolo/agent_tools/conformance.py`; `src/rolo/product_cli.py` | `tests/test_tool_conformance.py`; `tests/test_native_tool_session.py`; `tests/test_product_cli_v2.py` | Conformance 只固化当前 Tool Surface；不声明 Trace/Certify 或 release authority |
| FEAT-APPLICATION-GAP-BUNDLE | STABLE | E4 | `rolo target application-bundle --profile --application` | `src/rolo/stages/probe/application.py`; `src/rolo/product_cli.py` | `tests/test_application_bundles.py` | MVP 只覆盖 startup/navigation/mapping/manipulation；当前目标未观测到 map route；route presence 不证明应用行为正确；无证据时 Conformance 明确失败 |
| FEAT-APPLICATION-OPERATION-SLICE | STABLE | E4 | `rolo target application-operation --profile --operation` | `src/rolo/stages/probe/application.py`; `src/rolo/product_cli.py` | `tests/test_application_bundles.py` | v1 137 项中先实现 32 个只读 route-binding rules；当前 bundle 是 route-level candidate，不等同于行为/结果验证；R2/R3 明确 DEFERRED；LanderPi 六项 navigation write 均无 supervisor route |
| FEAT-APPLICATION-WRITE-CANARY | PARTIAL | E4 | `rolo target application-write-canary --profile --operation app.base.stop` | `src/rolo/stages/probe/application_write.py`; `src/rolo/targets/executor.py`; `src/rolo/product_cli.py` | `tests/test_application_bundles.py` | 仅固定 zero-Twist stop canary；必须新鲜路由证据和人工确认；PASS 只证明请求接受与路由复查，不证明物理停止或安全认证 |
| FEAT-APPLICATION-MAP-CREATE | PARTIAL | E3 | `rolo target application-map-create --profile` | `src/rolo/stages/probe/application_mapping.py`; `src/rolo/targets/executor.py`; `src/rolo/product_cli.py` | `tests/test_application_mapping.py` | 已在 mentorpi 真机用 `/scan_raw`、真实 URDF TF 和目标 SLAM 入口启动并观察 `/map`；仍只代表会话/地图流存在，不启动运动，不证明覆盖质量；探索仍需独立避障 adapter |
| FEAT-APPLICATION-MAP-EXPLORE-L1 | PARTIAL | E4 | `rolo target application-map-explore-plan --profile`; `rolo target application-map-explore --profile` | `src/rolo/stages/probe/application_exploration.py`; `scripts/rolo_micro_explorer.py`; `src/rolo/targets/executor.py`; `src/rolo/product_cli.py` | `tests/test_application_exploration.py` | L1 已在 mentorpi 完成一次 3.5 秒低速微探索并复核末尾零速；L2 允许单次约 0.5 m + 受限旋转；仍不证明完整覆盖、避障正确性或长期安全 |
| FEAT-MOTION-SAFETY-CONFORMANCE | PARTIAL | E3 | `rolo target safety-conformance --profile`; target-side `scripts/rolo_ros_safety_arbiter.py` | `src/rolo/stages/probe/application_safety.py`; `src/rolo/stages/probe/safety_guard.py`; `src/rolo/product_cli.py`; `scripts/rolo_ros_safety_arbiter.py` | `tests/test_application_safety.py`; `tests/test_safety_guard.py` | LanderPi 已临时 remap 到 safe output，并完成极小角速度→watchdog 归零 canary；正式 artifact/启动管理尚未固化；当前使用有样本的 `/scan_raw`，现有过滤节点未产出 `/scan`；独立急停明确不在本阶段 |

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

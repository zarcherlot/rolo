<!-- status: active; authority: guide; owner: docs maintainers; last_reviewed: 2026-09-02 -->

# Rolo v2

Rolo 是一个给 Codex 类 Agent 使用的机器人目标工具层。v2 只承诺一条小而稳的
Probe 链：把用户的机器人 profile 绑定到目标机，产生带签名的 TargetEvidenceBundle，
再发布 Agent 可消费的四类只读 Tool Surface（hw、linux、ros、app）。Agent 负责理解目标、
规划和解释；Rolo 负责连接安全、固定 argv、证据、预算和 Conformance。

## 用户旅程

```text
首次：profile enrollment -> host-key/identity approval -> target evidence
每次：tool-surface -> Agent ToolPlan -> Rolo tool-plan -> per-call evidence
能力缺口：bounded Probe -> Adapter bundle -> independent Conformance
```

首次 enrollment 可能使用一次性密码置备密钥；日常使用只指定 profile。Rolo 会自动选择
SSH agent 或已登记的 identity file，固定 known_hosts、host-key fingerprint 和 collector
digest。Windows、Linux、WSL 或其他 POSIX 控制器都可以发起 SSH，只要提供 OpenSSH client。

## 快速开始

```bash
uv sync --locked --dev
uv run rolo target profile init ssh://user@robot.example/opt/ros_ws --robot my-robot
uv run rolo target inspect-profile --profile my-robot
uv run rolo target tool-surface --profile my-robot > surface.json
# Agent 根据 surface.json 生成 rolo-tool-plan/v1
uv run rolo target tool-plan --profile my-robot plan.json
```

专家和 enrollment 命令位于 `robotctl probe`：

```bash
uv run robotctl probe target-evidence --help
uv run robotctl probe start --robot my-robot --evidence-mode remote
uv run robotctl probe status --robot my-robot
```

## 标准边界

- Native Tool 是经过 Rolo 验证的 family-level 固定 argv，只读、限时、限输出、可审计。
- `TargetEvidenceBundle` 是目标采集时刻的事实，不等价于物理行为正确或安全。
- ToolPlan 必须带 target、session、surface digest 和 plan digest；Rolo 拒绝任意 shell、
  未登记 tool、过期 session 和 mutating step。
- Linux/ROS CLI 若 Codex 已能可靠调用，不重复包装；只有非 Linux/非 ROS，或 Codex 无法
  稳定理解的中间件/底层调用，才进入 Adapter bundle gap 流程。
- Trace、Certify、MCP 和 Web UI 不是本轮产品依赖，未来只能复用这些 authority。

## 代码与验证

核心代码集中在 `src/rolo/targets/`、`src/rolo/agent_tools/` 和目标证据模块；架构说明见
[`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md)，状态台账见
[`docs/reference/ENGINEERING_STATUS.md`](docs/reference/ENGINEERING_STATUS.md)。提交前运行：

```bash
uv run pytest -q tests/test_target_credentials.py tests/test_target_executors.py \
  tests/test_target_evidence_deployment.py tests/test_agent_native_tools.py \
  tests/test_probe_session_factory.py tests/test_native_tool_session.py \
  tests/test_tool_planning.py
uv run ruff check .
python scripts/check_docs.py
```

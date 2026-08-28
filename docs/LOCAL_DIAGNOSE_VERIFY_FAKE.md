# 本地 Diagnose/Verify contract 与 fake provider 开发

本地可以在没有 Codex 登录、ROS、USB 或真实目标机的情况下开发和回归
Diagnose/Verify 的 contract、授权 Runner 和 handoff materializer。fake executor
只生成明确标记为 `NOT_EXECUTED`/`FAKE_UNEXECUTED` 的合成产物，不代表真实诊断、
回归或 release 结论。

## 启用方式

不要修改默认配置：Diagnose/Verify 的默认 provider 和 executor 仍然是 `codex`。
本地 fake 流程通过进程环境变量显式选择：

```powershell
$env:ROLO_ARTIFACT_DIR = "C:\path\to\artifacts"
$env:CODING_AGENT_PROVIDER = "fake"
$env:CODING_AGENT_EXECUTOR = "fake"
```

启用前，artifact tree 仍需有一个通过 Adapt gate 的最新 handoff，并准备好：

```text
adapt/<robot>/latest/index.json       # 指向并绑定 Adapt handoff
diagnose/<robot>/latest/inputs.json
verify/<robot>/latest/inputs.json
```

## contract / plan / handoff 流程

先只构建任务，确认 provider、executor、输入引用和 `plan_sha256`：

```powershell
uv run rolo diagnose plan --robot <robot>
uv run rolo verify plan --robot <robot>
```

首次运行不确认时只创建 `WAITING_FOR_AUTH` 和短期授权请求，不执行 fake executor：

```powershell
uv run rolo diagnose run --robot <robot>
# 或通过 rolo-vis 的 GET /v1/robots/<robot>/stage-auth-requests 查看 request_ref
```

确认后执行（也可用返回的 `authorization_ref` 恢复同一个 run）：

```powershell
uv run rolo diagnose run --robot <robot> --confirm
uv run rolo verify run --robot <robot> --confirm
```

预期结果：

- Diagnose 生成 `robot-diagnosis-handoff/v1`，包含严格的
  `rolo-diagnosis-report/v1`；Episode 是 fake observation，`decision=INCONCLUSIVE`，
  且注明没有执行目标机 episode。
- Verify 生成 `robot-verification-handoff/v1`，报告使用
  `FAKE_UNEXECUTED`/`ERROR`，因此 stage assessment 为 `DEGRADED`，不会伪装成真实
  acceptance 通过。
- `runs/<run_id>/run.json`、stdout/stderr、handoff 和所有摘要均由现有
  `StageAgentRunner` 与 handoff validator 校验并持久化。

查看阶段状态和产物：

```powershell
uv run rolo diagnose status --robot <robot>
uv run rolo verify status --robot <robot>
```

## 本地回归

```powershell
uv run ruff check src tests
uv run pytest -q tests/test_fake_downstream.py tests/test_codex_downstream.py tests/test_stage_agent_runner.py
```

fake executor 不接入 Adapt 的通用 executor 列表，也不改变 Codex 默认值；后续接入
真实 Diagnose Episode 或 Verify provider 时，只需替换 stage executor，并继续复用同一
contract、授权、artifact hash 和 handoff validator。

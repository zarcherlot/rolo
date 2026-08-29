# 目标机 Diagnose / Verify 调试手册

本手册用于 `codex/registry-redesign-r5` 在真实 Linux/ROS 目标机上的调试与验收。目标机负责提供真实 ROS 图、系统状态、Episode 和 provider 证据；Rolo 负责授权、哈希、handoff、gate 与 release 影响判定。HW USB 不属于本轮产品范围，不因 USB 缺失阻断 Linux/ROS 验收。

## 1. 代码与环境准备

在目标机执行：

```bash
git fetch origin codex/registry-redesign-r5
git switch codex/registry-redesign-r5
git pull --ff-only origin codex/registry-redesign-r5
git rev-parse HEAD
uv sync --frozen
source /opt/ros/humble/setup.bash

export ROS_DOMAIN_ID=50
export ROS_LOCALHOST_ONLY=1
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY

uv run robotctl config show
```

预期：代码版本为待验证远端 HEAD；依赖锁定安装成功；配置输出中的 `ros.rmw_implementation` 为 `rmw_fastrtps_cpp`。记录 `ROS_DOMAIN_ID`、RMW、代理变量和进程上限，避免把目标机注入值误判为代码问题。

## 2. 采集目标机基线

```bash
mkdir -p target-debug
{
  uname -a
  nproc
  ps -eo pid,ppid,comm,args --sort=pid
  ros2 doctor --report
  ros2 node list
  ros2 topic list
  ros2 service list
  ros2 topic echo /tf --once
} 2>&1 | tee target-debug/baseline.txt
```

预期：`ros2 doctor --report` 成功；节点、话题、服务有真实图或明确记录为空；`/tf --once` 成功时保存一条 TF，失败时标注为环境限制。不得用 `lsusb` 或 USB 原始日志作为本轮通过条件。

## 3. Adapt native shadow

```bash
export ADAPT_NATIVE_TOOL_MODE=shadow
export ADAPT_NATIVE_TOOL_ROBOT_IDS=<robot-id>
export ROLO_ARTIFACT_DIR="$PWD/artifacts"
export ROLO_OUTPUT_DIR="$PWD/output"

uv run robotctl adapt start \
  --robot-id <robot-id> \
  --project-root /path/to/robot-workspace \
  2>&1 | tee target-debug/adapt-shadow.txt
```

若默认 128 进程限制出现 `bwrap: Resource temporarily unavailable`，保留第一次结果，再显式重跑：

```bash
ROLO_ADAPTER_MAX_PROCESSES=512 uv run robotctl adapt start \
  --robot-id <robot-id> \
  --project-root /path/to/robot-workspace \
  2>&1 | tee target-debug/adapt-shadow-512.txt
```

预期：Adapt 为 `COMPLETE` 或明确的 `BLOCKED`；native gate 为 `PASS`，`blocking_reasons=[]`；`context_metrics` 记录 RMW、ROS domain、provider/executor 和进程上限；RMW 来自标准 `RMW_IMPLEMENTATION`；middleware 超时若标为 environment-limited 不阻断 gate；本阶段产物 `influences_release=false`。

## 4. Diagnose 阶段

先生成 provider-neutral 计划：

```bash
uv run robotctl diagnose plan --robot <robot-id> \
  2>&1 | tee target-debug/diagnose-plan.txt
```

计划命令只生成任务，不执行 Agent。随后先无确认运行以验证授权暂停：

```bash
uv run robotctl diagnose run --robot <robot-id> \
  2>&1 | tee target-debug/diagnose-auth.txt
```

无确认的 `diagnose run` 预期为 `WAITING_FOR_AUTH`，不得执行副作用操作。获得授权后，用 handoff 中的引用恢复：

```bash
uv run robotctl diagnose run --robot <robot-id> \
  --confirm --authorization-ref <artifact://...> \
  2>&1 | tee target-debug/diagnose-run.txt
```

当前 fake provider 只能验证 contract、CLI/MCP/HTTP 同构和 handoff，不能形成真实诊断结论；因此预期只能是 `INCONCLUSIVE`、`UNVERIFIED_AGENT_OBSERVATION`、`NOT_STARTED` 或 `BLOCKED`，不得出现可影响 release 的 `VERIFIED/PASSED`。真实 Diagnose provider 上线后，必须输出 episode 引用、目标机 provenance/clock/source，并覆盖 baseline → observe → hypothesis → change → smoke → decision 的完整链路。

## 5. Verify 阶段

如已有批准的验收计划，先发布计划：

```bash
uv run robotctl verify acceptance-plan \
  --robot <robot-id> \
  --plan-file /path/to/verify-plan.json \
  --confirm \
  2>&1 | tee target-debug/verify-plan.txt
```

随后先无确认运行 Verify，确认同样进入授权等待：

```bash
uv run robotctl verify run --robot <robot-id> \
  2>&1 | tee target-debug/verify-auth.txt
```

预期为 `WAITING_FOR_AUTH`，不得执行回归动作。获得授权后，按 handoff 引用恢复：

```bash
uv run robotctl verify run --robot <robot-id> \
  --confirm --authorization-ref <artifact://...> \
  2>&1 | tee target-debug/verify-run.txt
```

当前无真实 Verify provider 时，预期为 `NOT_STARTED` 或带明确 `FAKE_UNEXECUTED` 标记的 `DEGRADED`；不得产生 `VERIFIED/PASSED` 或 release 影响。真实 provider 必须证明 bounded cases、oracle、timeout/cancel、safe-stop、rollback 和 evidence 引用均可复现。

## 6. Run 管理与取消

如需停止一个已创建但仍在运行或等待授权的 run，使用持久化取消接口：

```bash
uv run robotctl diagnose cancel --robot <robot-id> --run-id <run-id>
uv run robotctl verify cancel --robot <robot-id> --run-id <run-id>
```

HTTP/MCP 等价入口分别为：

```text
POST /v1/robots/<robot-id>/<stage>/runs/<run-id>/cancel
MCP rolo_stage_cancel(stage, robot_id, run_id)
```

预期返回 `status=CANCELLED`、`cancel_requested=true`；已完成 run 不会被改写。目标机重启后，Rolo 应依据 run 的 lease/heartbeat 将过期 `RUNNING` 标记为 `FAILED`，而不是伪造成功。

## 7. 产物与完整性回收

```bash
find "$ROLO_ARTIFACT_DIR" -type f -print0 | sort -z | xargs -0 sha256sum \
  > target-debug/SHA256SUMS
sha256sum -c target-debug/SHA256SUMS
```

回传以下路径（脱敏后）：

```text
adapt/<robot>/latest.json
adapt/<robot>/runs/*/context_metrics.json
adapt/<robot>/runs/*/native-tool-rollout.json
adapt/<robot>/runs/*/native-tool-summary.json
adapt/<robot>/runs/*/native-tool-gate.json
diagnose/<robot>/latest/handoff.json（若存在）
verify/<robot>/latest/handoff.json（若存在）
target-debug/*
```

不要回传凭据、私有源码、未脱敏环境变量、USB 原始日志或不必要的完整进程参数。

## 8. 故障判定

| 现象 | 处理 | 是否阻断 |
|---|---|---|
| `RMW_IMPLEMENTATION` 未映射 | 检查配置来源和环境优先级，修复后重跑 | 阻断该次验收 |
| `bwrap: Resource temporarily unavailable` | 记录 128 结果，再用 512 重跑；提交两次产物 | 仅阻断失败窗口 |
| middleware timeout 且标记 environment-limited | 保留证据，确认 gate 仍 PASS | 不阻断 gate |
| `/tf` 缺失 | 记录为环境限制；真实 Diagnose 需要可观测 TF 时阻断 Diagnose | 视阶段 |
| HW USB 不可用 | 不执行 USB 采集，不纳入结论 | 不阻断本产品范围 |
| handoff 引用或 SHA256 不匹配 | 停止消费下游阶段并修复 | 阻断 |
| identity、签名、SSH pin 不匹配 | fail-closed，禁止继续 | 阻断 |

## 9. 通过条件

本轮只允许在 Adapt shadow/native 证据完整且 `influences_release=false` 的前提下继续开发。开启 canary 或 release 影响前，还必须分别取得真实 Diagnose Episode、真实 Verify provider 的可复现实例和连续稳定窗口；fake provider、单次成功 shadow 或缺少目标机 provenance 均不满足条件。

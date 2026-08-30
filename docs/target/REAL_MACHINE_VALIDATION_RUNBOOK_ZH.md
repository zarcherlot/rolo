<!-- status: active; authority: guide; owner: ROLO maintainers; last_reviewed: 2026-08-29; source_of_truth: docs/target/POST_MERGE_DEVELOPMENT_AND_REAL_TARGET_RUNBOOK.md -->

# ROLO 真机只读验证 RUNBOOK

本手册用于在真实 Linux/ROS 机器人上验证当前集成线。主路径是 **Rolo 直接运行在目标机**，
使用 main 的 `local-target` provider；控制器到目标机的 SSH provider 目前仍是库级切片，
尚未接入 `robotctl` CLI，不应在本手册中假设它已经可执行。

首轮验证只允许 Linux、workspace、ROS graph 和 companion health 等只读检查。禁止执行
publish、导航、校准、reset、actuator、power、firmware 或任何会改变机器人状态的操作。

## 0. 填写验证变量

在目标机创建独立验证目录，并将下面变量替换为人工批准的值：

```bash
export ROBOT_ID=<approved-robot-id>
export PROJECT_ROOT=/path/to/robot/workspace
export EXPECTED_REVISION=<approved-40-character-commit-sha>
export VALIDATION_ROOT="$HOME/rolo-real-validation/$ROBOT_ID"
export ROLO_ARTIFACT_DIR="$VALIDATION_ROOT/artifacts"
export ROLO_OUTPUT_DIR="$VALIDATION_ROOT/output"
export DEBUG_DIR="$VALIDATION_ROOT/debug"
mkdir -p "$ROLO_ARTIFACT_DIR" "$ROLO_OUTPUT_DIR" "$DEBUG_DIR"
```

`PROJECT_ROOT`、artifact、output 和 debug 目录必须位于源码树之外。不要把 API key、SSH
私钥、代理凭据或完整未脱敏环境变量写入 artifact。

## 1. 固定代码与依赖

验证必须使用已经合入并审核的 `main` revision。不要直接验证移动的工作树或未推送提交：

```bash
git fetch origin --prune
test "$(git rev-parse origin/main)" = "$EXPECTED_REVISION"
git switch --detach "$EXPECTED_REVISION"
export ROLO_REVISION="$(git rev-parse HEAD)"
test "$ROLO_REVISION" = "$EXPECTED_REVISION"
git status --short
uv sync --frozen
```

将 `ROLO_REVISION` 写入报告；若工作树不干净或 revision 无法与审核记录匹配，立即 `HOLD`。

ROS 目标示例：

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=50
export ROS_LOCALHOST_ONLY=1
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ADAPT_NATIVE_TOOL_MODE=off
unset ADAPT_NATIVE_TOOL_RUN_IDS
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
```

记录实际环境，但不要把代理值写入仓库或证据包：

```bash
{
  echo "revision=$ROLO_REVISION"
  echo "robot_id=$ROBOT_ID"
  echo "project_root=$PROJECT_ROOT"
  echo "ros_domain_id=${ROS_DOMAIN_ID:-unset}"
  echo "rmw_implementation=${RMW_IMPLEMENTATION:-unset}"
  echo "python=$(python --version 2>&1)"
  echo "uv=$(uv --version 2>&1)"
  echo "ros_distro=${ROS_DISTRO:-unset}"
} | tee "$DEBUG_DIR/environment.txt"
uv run robotctl config show | tee "$DEBUG_DIR/config.txt"
```

## 2. 固定目标 profile 与身份

`profile init` 只写控制面 profile，不会执行目标写操作：

```bash
uv run rolo target profile init "$PROJECT_ROOT" --robot "$ROBOT_ID"
uv run rolo target profile show --robot "$ROBOT_ID" | tee "$DEBUG_DIR/profile.txt"
```

保存以下只读身份事实：

```bash
{
  uname -a
  id -un
  id -u
  stat -c 'workspace_device=%d workspace_inode=%i workspace_ctime=%Z' "$PROJECT_ROOT"
  sha256sum /etc/machine-id 2>/dev/null || sha256sum /var/lib/dbus/machine-id
} 2>&1 | tee "$DEBUG_DIR/target-identity.txt"
```

如果 workspace、machine-id、用户、profile digest 或 ROS/RMW 与审核记录不一致，停止并
标记 `NO-GO`；不要通过删除 binding artifact 来绕过身份漂移。

## 3. 目标基线

以下命令必须在真实工作负载运行状态下执行：

```bash
{
  uname -a
  nproc
  ps -eo pid,ppid,comm,args --sort=pid
  ros2 doctor --report
  ros2 node list
  ros2 topic list
  ros2 service list
  ros2 topic echo /tf --once
} 2>&1 | tee "$DEBUG_DIR/baseline.txt"
```

判定：

- `ros2 doctor --report` 必须成功，或明确记录为环境限制；
- ROS graph 为空可以记录，但不能伪造为“健康”；
- `/tf --once` 失败时只能标为 `environment-limited`，若本次 Diagnose 依赖 TF，则阻断 Diagnose；
- `lsusb`、USB/IP、写设备和硬件原始日志不属于首轮通过条件。

## 4. Adapt shadow（3～5 个窗口）

先保持 native 工具关闭，确认主链路基线：

```bash
# Adapt 当前只注册 codex executor；local-target 仅用于 Diagnose/Verify。
export CODING_AGENT_PROVIDER=codex
export CODING_AGENT_EXECUTOR=codex
uv run robotctl adapt run --robot "$ROBOT_ID" \
  2>&1 | tee "$DEBUG_DIR/adapt-shadow-01.txt"
```

如遇到 `bwrap: Resource temporarily unavailable`，保留第一次结果后只在目标机显式重跑：

```bash
ROLO_ADAPTER_MAX_PROCESSES=512 \
uv run robotctl adapt run --robot "$ROBOT_ID" \
  2>&1 | tee "$DEBUG_DIR/adapt-shadow-01-process-512.txt"
```

连续窗口每次都记录：revision、profile digest、native gate、blocking reasons、context
metrics、artifact SHA256。shadow 结果必须保持 `influences_release=false`，不得改变
Canonical eligibility、Bundle 或 release。

## 5. Diagnose 真机 Episode

先验证授权暂停，不得直接执行：

```bash
export CODING_AGENT_PROVIDER=local-target
export CODING_AGENT_EXECUTOR=local-target
uv run robotctl diagnose plan --robot "$ROBOT_ID" \
  2>&1 | tee "$DEBUG_DIR/diagnose-plan.txt"
uv run robotctl diagnose run --robot "$ROBOT_ID" \
  2>&1 | tee "$DEBUG_DIR/diagnose-auth.txt"
```

预期状态为 `WAITING_FOR_AUTH`。人工确认授权引用后再恢复：

```bash
uv run robotctl diagnose run --robot "$ROBOT_ID" \
  --confirm --authorization-ref <artifact://authorization-request.json> \
  2>&1 | tee "$DEBUG_DIR/diagnose-run.txt"
```

必须检查：

- 生成唯一 immutable Episode；
- 六个 phase 按顺序存在：`baseline`、`observe`、`hypothesis`、`change`、`smoke`、`decision`；
- `change` 为 `NO_CHANGE`；
- Episode、provenance、target binding 的引用和 SHA256 全部匹配；
- 没有真实 Episode 时只能是 `INCONCLUSIVE`/`DEGRADED`，不能提升为通过。

## 6. Verify 只读计划与执行

创建人工审核的 bounded plan，例如 `$DEBUG_DIR/verify-plan.json`：

```json
{
  "schema_version": "rolo-verification-plan/v1",
  "robot_id": "<approved-robot-id>",
  "cases": [
    {
      "schema_version": "rolo-verification-case/v1",
      "case_id": "linux-uname",
      "operation": "linux.uname",
      "payload": {},
      "timeout_s": 30,
      "oracle": {
        "schema_version": "rolo-verification-oracle/v1",
        "kind": "FIELD_EXISTS",
        "path": "output"
      }
    },
    {
      "schema_version": "rolo-verification-case/v1",
      "case_id": "ros-node-list",
      "operation": "ros.node.list",
      "payload": {},
      "timeout_s": 30,
      "oracle": {
        "schema_version": "rolo-verification-oracle/v1",
        "kind": "FIELD_EXISTS",
        "path": "lines"
      }
    }
  ],
  "max_elapsed_s": 600
}
```

计划只允许当前 `local-target` read-only allowlist：`linux.uname`、`ros.doctor.report`、
`ros.node.list`、`ros.topic.list`、`ros.service.list`、`ros.topic.echo_once`。未知 operation、
写操作或变异 payload 必须在执行前拒绝。

```bash
uv run robotctl verify acceptance-plan \
  --robot "$ROBOT_ID" \
  --plan-file "$DEBUG_DIR/verify-plan.json" \
  --confirm \
  2>&1 | tee "$DEBUG_DIR/verify-plan.txt"

uv run robotctl verify run --robot "$ROBOT_ID" \
  2>&1 | tee "$DEBUG_DIR/verify-auth.txt"
```

确认授权后执行：

```bash
uv run robotctl verify run --robot "$ROBOT_ID" \
  --confirm --authorization-ref <artifact://authorization-request.json> \
  2>&1 | tee "$DEBUG_DIR/verify-run.txt"
```

Verify 通过必须同时满足：case 与 observation 一一对应、evidence package 为 v2、
provenance/binding hash 有效、report 与 evidence case identity 一致、safe-stop/rollback
显式为 `NOT_REQUIRED` 或 `VERIFIED`，且 release authority 仍为 `none`。

## 7. 取消、重启与回退

在运行或授权等待期间取消：

```bash
uv run robotctl diagnose cancel --robot "$ROBOT_ID" --run-id <run-id>
uv run robotctl verify cancel --robot "$ROBOT_ID" --run-id <run-id>
```

预期为 `CANCELLED`，并保留原 run artifact；已完成 run 不得被改写。进程中断时使用操作
系统的受控终止方式，重启后重新检查：

```bash
find "$ROLO_ARTIFACT_DIR" -type f -name 'run.json' -print
find "$ROLO_ARTIFACT_DIR" -type f -name 'handoff.json' -print
```

任何 `RUNNING`、lease 或 lock 异常必须先确认旧进程已退出，再让 Rolo 的 stale recovery
处理；不得手工删除 latest handoff 或 evidence 来“修复”状态。

## 8. 证据包与 SHA256 回收

```bash
find "$ROLO_ARTIFACT_DIR" -type f -print0 | sort -z | xargs -0 sha256sum \
  > "$DEBUG_DIR/SHA256SUMS"
sha256sum -c "$DEBUG_DIR/SHA256SUMS"
git rev-parse HEAD > "$DEBUG_DIR/revision.txt"
```

回传前脱敏并保留：

```text
revision.txt
environment.txt
config.txt
target-identity.txt
baseline.txt
adapt-shadow-*.txt
diagnose-*.txt
verify-*.txt
SHA256SUMS
adapt/<robot>/latest.json
diagnose/<robot>/latest/handoff.json
verify/<robot>/latest/handoff.json
targets/<robot>/bindings/*
targets/<robot>/provenance/*
episodes/<robot>/published/*
```

不要回传私钥、token、API key、完整代理环境变量、未脱敏进程参数或私有源码。

## 9. 判定与停止条件

| 判定 | 条件 |
|---|---|
| `GO` | revision/profile/identity 一致；Adapt shadow 连续 3～5 窗口稳定；Diagnose Episode 完整；Verify v2 evidence/handoff 完整；无高严重度 parity 或 silent drop |
| `HOLD` | 仅环境限制、ROS graph 暂空、可解释 timeout，且证据完整、release-neutral、可重跑 |
| `NO-GO` | identity/host-key/hash 漂移；未知 operation；handoff/evidence 不匹配；写操作意外触发；无法确认旧进程已退出；任何安全边界不清晰 |

首轮真机验证不授予 release authority，不删除 P1 分支，不关闭 v1 wrapper，也不把单次
通过解释为 canary 或物理验收完成。

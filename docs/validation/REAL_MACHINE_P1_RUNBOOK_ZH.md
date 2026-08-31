<!-- status: archived; authority: guide; owner: docs maintainers; last_reviewed: 2026-08-31; source_of_truth: docs/target/REAL_MACHINE_VALIDATION_RUNBOOK_ZH.md -->

# P1 真机只读验证 Runbook（归档跳转页）

执行入口已统一为[真机验证主 Runbook](../target/REAL_MACHINE_VALIDATION_RUNBOOK_ZH.md)。本文件保留历史验证记录，
不再作为独立执行手册；Adapt 目标证据和 route 专项见主 Runbook 的 [Adapt 详细附录](../target/TARGET_MACHINE_ADAPT_VALIDATION_ZH.md)。

本 Runbook 用于验证已合入并审核的 `main` 或当前切片 PR revision。首轮只允许 Linux/ROS
观测和 companion health；不允许导航、校准、reset、actuator、power、firmware 或任何
写操作。`adapt-full-hardening` 不属于本轮范围。

## 1. 固定 revision 与环境

在真机上使用源码树外的证据目录，并将 `<...>` 替换为已批准值：

```bash
export ROBOT_ID=<approved-robot-id>
export PROJECT_ROOT=/path/to/rolo/workspace
export EXPECTED_REVISION=<approved-40-character-commit-sha>
export VALIDATION_ROOT="$HOME/rolo-p1-validation/$ROBOT_ID"
export ROLO_ARTIFACT_DIR="$VALIDATION_ROOT/artifacts"
export ROLO_OUTPUT_DIR="$VALIDATION_ROOT/output"
export DEBUG_DIR="$VALIDATION_ROOT/debug"
mkdir -p "$ROLO_ARTIFACT_DIR" "$ROLO_OUTPUT_DIR" "$DEBUG_DIR"

git fetch origin --prune
test "$(git rev-parse origin/main)" = "$EXPECTED_REVISION"
git switch --detach "$EXPECTED_REVISION"
test "$(git rev-parse HEAD)" = "$EXPECTED_REVISION"
test -z "$(git status --short)"
uv sync --frozen
```

记录 revision、Python、uv、ROS、RMW 和目标身份；不要记录代理值、私钥或 token：

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=50
export ROS_LOCALHOST_ONLY=1
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ADAPT_NATIVE_TOOL_MODE=off
unset ADAPT_NATIVE_TOOL_RUN_IDS ADAPT_NATIVE_TOOL_ROBOT_IDS

{
  echo "revision=$(git rev-parse HEAD)"
  echo "robot_id=$ROBOT_ID"
  echo "python=$(python --version 2>&1)"
  echo "uv=$(uv --version 2>&1)"
  echo "ros_distro=${ROS_DISTRO:-unset}"
  echo "ros_domain_id=${ROS_DOMAIN_ID:-unset}"
  echo "rmw_implementation=${RMW_IMPLEMENTATION:-unset}"
} | tee "$DEBUG_DIR/environment.txt"
```

## 2. 目标身份与只读基线

```bash
uv run rolo target profile init "$PROJECT_ROOT" --robot "$ROBOT_ID"
uv run rolo target profile show --robot "$ROBOT_ID" | tee "$DEBUG_DIR/profile.txt"

{
  uname -a
  id -un
  id -u
  stat -c 'workspace_device=%d workspace_inode=%i workspace_ctime=%Z' "$PROJECT_ROOT"
  sha256sum /etc/machine-id 2>/dev/null || sha256sum /var/lib/dbus/machine-id
  ros2 doctor --report
  ros2 node list
  ros2 topic list
  ros2 service list
} 2>&1 | tee "$DEBUG_DIR/baseline.txt"
```

workspace、machine-id、用户、ROS/RMW 或 profile 与批准记录不一致时立即 `NO-GO`，不得
删除 binding/evidence 绕过校验。

## 3. Adapt shadow 窗口

保持 native 工具关闭，在相同 revision/profile/工作负载下执行 3～5 个窗口：

```bash
# Adapt 当前只注册 codex executor；local-target 仅用于 Diagnose/Verify。
export CODING_AGENT_PROVIDER=codex
export CODING_AGENT_EXECUTOR=codex
export ROLO_ADAPTER_MAX_PROCESSES=512
for window in 01 02 03 04 05; do
  uv run robotctl adapt run --robot "$ROBOT_ID" \
    2>&1 | tee "$DEBUG_DIR/adapt-shadow-$window.txt"
done
```

每个窗口必须保存 run id、native gate、blocking reasons、context metrics 和 artifact
摘要；native/shadow 结果必须保持 `influences_release=false`。任何高严重度 parity、
unknown provider、silent drop 或未解释环境失败都停止本轮。

## 4. Diagnose Episode

先确认未授权执行会停在 `WAITING_FOR_AUTH`：

```bash
export CODING_AGENT_PROVIDER=local-target
export CODING_AGENT_EXECUTOR=local-target
uv run robotctl diagnose plan --robot "$ROBOT_ID" | tee "$DEBUG_DIR/diagnose-plan.txt"
uv run robotctl diagnose run --robot "$ROBOT_ID" | tee "$DEBUG_DIR/diagnose-auth.txt"
```

取得人工批准的 `authorization_ref` 后恢复：

```bash
uv run robotctl diagnose run --robot "$ROBOT_ID" \
  --confirm --authorization-ref <artifact://authorization-request.json> \
  | tee "$DEBUG_DIR/diagnose-run.txt"
```

检查唯一 immutable Episode、六个 phase 顺序（baseline/observe/hypothesis/change/smoke/
decision）、`change=NO_CHANGE`，以及 Episode、provenance、target binding 的引用和
SHA256。没有真实 Episode 时不得判定通过。

## 5. Verify bounded read-only plan

创建人工审核的 `$DEBUG_DIR/verify-plan.json`。首轮只使用以下 allowlist：
`linux.uname`、`ros.doctor.report`、`ros.node.list`、`ros.topic.list`、
`ros.service.list`、`ros.topic.echo_once`。

```json
{
  "schema_version": "rolo-verification-plan/v1",
  "robot_id": "<approved-robot-id>",
  "max_elapsed_s": 600,
  "cases": [
    {
      "schema_version": "rolo-verification-case/v1",
      "case_id": "linux-uname",
      "operation": "linux.uname",
      "payload": {},
      "timeout_s": 30,
      "oracle": {"schema_version":"rolo-verification-oracle/v1","kind":"FIELD_EXISTS","path":"output"}
    },
    {
      "schema_version": "rolo-verification-case/v1",
      "case_id": "ros-node-list",
      "operation": "ros.node.list",
      "payload": {},
      "timeout_s": 30,
      "oracle": {"schema_version":"rolo-verification-oracle/v1","kind":"FIELD_EXISTS","path":"lines"}
    }
  ]
}
```

未知 operation、写操作、变异 payload 或超出 timeout 必须在执行前拒绝：

```bash
uv run robotctl verify acceptance-plan --robot "$ROBOT_ID" \
  --plan-file "$DEBUG_DIR/verify-plan.json" --confirm \
  | tee "$DEBUG_DIR/verify-plan.txt"
uv run robotctl verify run --robot "$ROBOT_ID" | tee "$DEBUG_DIR/verify-auth.txt"
uv run robotctl verify run --robot "$ROBOT_ID" \
  --confirm --authorization-ref <artifact://authorization-request.json> \
  | tee "$DEBUG_DIR/verify-run.txt"
```

通过条件：case 与 observation 一一对应；evidence 为 canonical v2；provenance/binding
hash 有效；report/evidence case identity 一致；safe-stop/rollback 为 `NOT_REQUIRED` 或
`VERIFIED`；release authority 始终为 `none`。

## 6. 固定 SSH target health 切片

在完成上面的 Verify plan 审核后，可单独运行 canonical SSH provider 的固定只读健康检查：

```bash
uv run rolo target verify-health \
  "ssh://<user>@<host>/<absolute-workspace>" \
  --robot "$ROBOT_ID" \
  --package-id rolo-target \
  --package-version <approved-package-version> \
  --known-hosts "$KNOWN_HOSTS" \
  | tee "$DEBUG_DIR/target-verify-health.json"
```

该命令只允许 `uname -s`、workspace directory check 和 `rolo-target --version` 三个
固定 operation；不接受 shell 字符串、不执行目标机写操作。若 `$ROLO_CONFIG_DIR/target-profiles/`
中存在同名 robot profile，目标 URI 必须与 profile 完全一致，profile digest 会绑定到
provenance，且 profile 的 SSH host key 必须已经人工批准；没有 profile 时仅使用规范化
target URI digest。`PASS` 才允许继续，`FAIL`、
`TIMEOUT`、`CANCELLED` 或 transport error 均必须保留 evidence 并停止后续合入。
集成线 CI 的 `real-verify-contract` job 会重复执行 provider plan allowlist、超时、取消、
并发锁、stale-lock recovery、handoff/provenance 以及本命令的 CLI 退出码门禁。

## 7. 取消、重启和负面注入

```bash
uv run robotctl verify cancel --robot "$ROBOT_ID" --run-id <run-id>
uv run robotctl diagnose cancel --robot "$ROBOT_ID" --run-id <run-id>
```

取消应为 `CANCELLED` 并保留原始 run/evidence。对任一 provenance、binding、plan 或
evidence 摘要做篡改时，恢复/手合入必须 fail-closed；不得手工删除 latest handoff。

## 8. 证据包与回传

```bash
git rev-parse HEAD > "$DEBUG_DIR/revision.txt"
find "$ROLO_ARTIFACT_DIR" -type f -print0 | sort -z \
  | xargs -0 sha256sum > "$DEBUG_DIR/SHA256SUMS"
sha256sum -c "$DEBUG_DIR/SHA256SUMS"
```

至少回传：

```text
revision.txt environment.txt profile.txt baseline.txt
adapt-shadow-*.txt diagnose-*.txt verify-*.txt SHA256SUMS
diagnose/<robot>/latest/handoff.json
verify/<robot>/latest/handoff.json
targets/<robot>/bindings/* targets/<robot>/provenance/*
validation-report.md
```

`validation-report.md` 必须写明 revision、robot/provider/executor、窗口 ID、每个 case
状态、环境限制、取消/篡改负面样本、回退结果和最终 `GO/HOLD/NO-GO`。禁止打包私钥、
token、完整未脱敏环境变量或无关原始日志。

## 9. 判定

- `GO`：3～5 个 shadow 窗口稳定通过，真实 Episode 和 Verify v2 evidence 完整，所有
  hash/identity 绑定有效，取消/回退演练通过。
- `HOLD`：样本不足、middleware 环境限制未解释、CI 尚未通过或人工安全责任未就绪。
- `NO-GO`：身份/host-key/provenance/hash 漂移，未知或写 operation 执行，release authority
  被提升，或取消/回退失效。

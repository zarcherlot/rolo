<!-- status: frozen; authority: guide; owner: docs maintainers; last_reviewed: 2026-08-30; source_of_truth: docs/target/POST_MERGE_DEVELOPMENT_AND_REAL_TARGET_RUNBOOK.md -->

# 目标机 / WSL P2 验证步骤

本文档保留 R5 时期的 P0.1 SSH Adapt 产品路径和 P2 shadow/canary 验证记录，
仅作为历史验证参考。当前主线请优先使用
[合并后开发与真实目标机运行手册](POST_MERGE_DEVELOPMENT_AND_REAL_TARGET_RUNBOOK.md)
和[真实目标机验证手册](REAL_MACHINE_VALIDATION_RUNBOOK_ZH.md)；验证必须固定到批准的
`origin/main` 提交，不应再切换到历史分支。
目标机只负责采集真实 Linux、ROS 和产品范围内 HW 证据；代码开发、离线测试和
artifact 分析在本地完成。

## 1. 固定代码和 Python 环境

```bash
git fetch origin main
git switch --detach <approved-main-revision>
git rev-parse HEAD
uv sync --frozen
```

`HEAD` 必须记录在验证报告中，并与本次验证使用的远端提交一致。

历史基线为 `1a36258`；当前验证应在报告中记录批准的 40 字符主线提交 SHA，
并以该提交对应的实现和 schema 为准。

## 2. P0.1 SSH Adapt 产品入口

SSH Adapt 命令在控制端（开发机或 WSL controller）执行，目标机只提供已批准的
SSH collector 和真实运行环境。目标机应先确认 collector 服务、SSH host key、端口
和 target workspace 可用，然后在控制端执行：

```bash
uv run rolo adapt "ssh://<user>@<host>:<port>/<remote-workspace>" \
  --robot <robot-id> \
  --project-root <local-source-root> \
  --active-probe runtime-readonly \
  --discover-only
```

其中 `<local-source-root>` 是控制端可读的机器人源码/工作区；远端 workspace 只由
approved deployment 和 collector 绑定，不从 URI 临时推断权限。

### P0.1 通过条件

- deployment 文件存在，模式为 `remote`；
- URI 中的 user/host 与 deployment 的 `ssh_target` 一致；
- URI 端口与 deployment 的 pinned SSH port 一致；
- target collector 能返回签名、目标机 fingerprint 和有效 nonce 的 evidence bundle；
- Adapt 返回 `DISCOVERY_COMPLETE` 或 `COMPLETE`，并生成 target evidence artifact；
- 没有 approved deployment、host/port 不匹配、workspace 不可读或 host key 不可信时，
  必须在 Agent 启动前返回 `BLOCKED`/参数错误，且不得写 target 或启动 Agent。

## 3. 准备 ROS 运行环境

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=50
export ROS_LOCALHOST_ONLY=1

ros2 doctor --report
ros2 node list
ros2 topic list
ros2 service list
ros2 topic echo /tf --once
```

若本地 WSL 只验证 ROS/native 通道、尚未启动真实目标工作负载，可在独立终端启动最小
只读 fixture：

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=50
export ROS_LOCALHOST_ONLY=1
scripts/run_p2_ros_fixture.sh
```

fixture 只证明 `/tf` 采集链路可执行，不得作为真实机器人行为、canary 稳定性或产品
功能证据。进入真实目标机或 canary 验证前必须改用实际工作负载的 `/tf` 发布者。

如果目标环境需要 Clash 或其他代理才能访问外部网络，记录实际使用的代理变量和
middleware 结果。不要把代理变量写入仓库配置或 artifact 内容。

## 4. 采集产品范围内的 Linux/HW 证据

```bash
uname -a
nproc
ps -eo pid,comm,args
lspci
udevadm info --export-db
```

HW USB (`lsusb`) 当前不属于产品范围，不作为 P2 通过/阻断条件；无需为 USB/IP、
WSL USB 映射或 `lsusb` 缺失追加开发。若命令被执行，只能作为附加环境信息记录。

## 5. 执行 Adapt + Agent-native shadow

```bash
export ADAPT_NATIVE_TOOL_MODE=shadow
export ADAPT_NATIVE_TOOL_ROBOT_IDS=<robot-id>
export PYTHONPATH=src
```

先使用默认资源预算执行一次并记录结果：

```bash
echo "ROLO_ADAPTER_MAX_PROCESSES=${ROLO_ADAPTER_MAX_PROCESSES:-128}"
uv run robotctl adapt run --robot "$ADAPT_NATIVE_TOOL_ROBOT_IDS"
```

如果 WSL/ROS 工作负载因 `bwrap: Resource temporarily unavailable` 失败，只允许在
目标机验证环境中显式提高预算后重跑，并在报告中记录前后差异；不要修改仓库默认值：

```bash
export ROLO_ADAPTER_MAX_PROCESSES=512
uv run robotctl adapt run --robot "$ADAPT_NATIVE_TOOL_ROBOT_IDS"
```

`ADAPT_NATIVE_TOOL_RUN_IDS` 只在精确 canary run 时设置；普通 shadow 不需要。

每次运行保留以下产物：

```text
native-tool-rollout.json
native-tool-summary.json
native-tool-gate.json
native/<robot>/sessions/<session>/calls/*.json
capability-resolution-shadow.json
target-operation-slice-shadow.json
platform-profile.json
context_metrics.json
native-tool-execution-parity.json
```

选中的 shadow/canary session 会由 Rolo 先执行一次确定性的 Linux host baseline，保证
即使 Adapter Agent 不主动调用 native 工具，也能生成至少一个 `calls/*.json` 和对应的
execution parity 证据；Agent 后续调用仍使用同一受预算约束的 session。

## 6. 目标机产物自检

```bash
sha256sum -c SHA256SUMS
```

逐项确认：

- native gate 为 `PASS`，`blocking_reasons` 为空；
- 所有 release-neutral artifact 的 `influences_release` 为 `false`；
- rollout、summary、gate 的 robot/run/session/catalog digest 一致；
- execution parity 没有 `DIFF` 或 silent drop；
- `context_metrics.json` 记录实际 `adapter_max_processes`、ROS domain/RMW 及 Agent
  provider/executor；Diagnose/Verify 缺省 provider/executor 必须仍为 `codex`；
- `UNAVAILABLE` 仅对应已解释的环境限制；
- capability resolution 仅出现可解释的 `RESOLVED`、`UNAVAILABLE` 或 `AMBIGUOUS`；
- Adapt 的 authoritative eligibility、Bundle 和 release 没有被 shadow 结果改变。

建议连续采集 3～5 个 shadow 窗口。单次运行通过只代表环境可执行，不代表可以进入
active 或删除旧 wrapper。

## 7. Canary 前置条件

只有同时满足以下条件，才允许选择低风险 Linux/ROS 只读 capability 进入 canary：

1. 连续 shadow 窗口无高严重度 parity 差异；
2. 无未知 provider、未解释的 `AMBIGUOUS` 或 silent drop；
3. artifact/evidence provenance 完整；
4. 现有 Canonical eligibility/release 回退路径可用；
5. 目标机环境变量、ROS domain 和代理状态已经记录。

HW USB、写操作、calibration、actuator、power、firmware、reset、navigation 和
其他高风险能力不进入本轮 native canary。

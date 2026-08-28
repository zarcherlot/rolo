<!-- status: active; authority: guide; owner: docs maintainers; last_reviewed: 2026-08-28 -->

# 目标机 / WSL P2 验证步骤

本文档用于 `codex/registry-redesign-r5` 后续 P2 shadow/canary 验证。
目标机只负责采集真实 Linux、ROS 和产品范围内 HW 证据；代码开发、离线测试和
artifact 分析在本地完成。

## 1. 固定代码和 Python 环境

```bash
git fetch origin
git switch codex/registry-redesign-r5
git pull --ff-only origin codex/registry-redesign-r5
git rev-parse HEAD
uv sync --frozen
```

`HEAD` 必须记录在验证报告中，并与本次验证使用的远端提交一致。

## 2. 准备 ROS 运行环境

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

如果目标环境需要 Clash 或其他代理才能访问外部网络，记录实际使用的代理变量和
middleware 结果。不要把代理变量写入仓库配置或 artifact 内容。

## 3. 采集产品范围内的 Linux/HW 证据

```bash
uname -a
nproc
ps -eo pid,comm,args
lspci
udevadm info --export-db
```

HW USB (`lsusb`) 当前不属于产品范围，不作为 P2 通过/阻断条件；无需为 USB/IP、
WSL USB 映射或 `lsusb` 缺失追加开发。若命令被执行，只能作为附加环境信息记录。

## 4. 执行 Adapt + Agent-native shadow

```bash
export ADAPT_NATIVE_TOOL_MODE=shadow
export ADAPT_NATIVE_TOOL_ROBOT_IDS=<robot-id>
export PYTHONPATH=src

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
```

## 5. 目标机产物自检

```bash
sha256sum -c SHA256SUMS
```

逐项确认：

- native gate 为 `PASS`，`blocking_reasons` 为空；
- 所有 release-neutral artifact 的 `influences_release` 为 `false`；
- rollout、summary、gate 的 robot/run/session/catalog digest 一致；
- execution parity 没有 `DIFF` 或 silent drop；
- `UNAVAILABLE` 仅对应已解释的环境限制；
- capability resolution 仅出现可解释的 `RESOLVED`、`UNAVAILABLE` 或 `AMBIGUOUS`；
- Adapt 的 authoritative eligibility、Bundle 和 release 没有被 shadow 结果改变。

建议连续采集 3～5 个 shadow 窗口。单次运行通过只代表环境可执行，不代表可以进入
active 或删除旧 wrapper。

## 6. Canary 前置条件

只有同时满足以下条件，才允许选择低风险 Linux/ROS 只读 capability 进入 canary：

1. 连续 shadow 窗口无高严重度 parity 差异；
2. 无未知 provider、未解释的 `AMBIGUOUS` 或 silent drop；
3. artifact/evidence provenance 完整；
4. 现有 Canonical eligibility/release 回退路径可用；
5. 目标机环境变量、ROS domain 和代理状态已经记录。

HW USB、写操作、calibration、actuator、power、firmware、reset、navigation 和
其他高风险能力不进入本轮 native canary。


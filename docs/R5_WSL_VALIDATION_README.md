# R5 WSL 验证

本分支验证 Registry Operation 精简后的 v2 Registry 和 Agent-native Linux/ROS/HW 只读通道。
默认 `agent_native.mode=off`；`shadow` 只记录对比，不改变 eligibility、Gate 或 release。

## 1. 拉取与安装

```bash
git clone --branch codex/registry-redesign-r5 https://github.com/zarcherlot/rolo.git
cd rolo
uv sync --frozen
```

建议：WSL Ubuntu 22.04+、Python 3.11+。ROS 验证需要目标机已安装 ROS 2 并准备好
对应的 `setup.bash`；没有 ROS 或真实硬件时，先完成下面的离线校验即可。

## 2. 离线一致性校验

```bash
uv run python -m rolo.cli tool registry --registry-version v2
uv run python -m rolo.cli tool contract validate --registry-version v2
uv run python scripts/validate_registry_migration.py
uv run pytest -q \
  tests/test_registry_v2.py \
  tests/test_registry_resolver.py \
  tests/test_operation_governance.py \
  tests/test_agent_native_tools.py \
  tests/test_native_tool_session.py \
  tests/test_native_rollout.py \
  tests/test_registry_migration.py
```

预期：v2 Canonical 为 197 项，family-level Agent-native catalog 为 22 项，旧 73 个
Linux/ROS/HW 命令形态均有 parity 映射，报告状态为 `PASS`。

## 3. WSL/真实目标机灰度

先在目标机准备配置（不要把密钥写入 YAML）：

```bash
export ADAPT_NATIVE_TOOL_MODE=shadow
export ADAPT_NATIVE_TOOL_ROBOT_IDS=<robot-id>
export ADAPT_NATIVE_TOOL_RUN_IDS=<run-id>
export PYTHONPATH=src
uv run robotctl adapt run --robot "$ADAPT_NATIVE_TOOL_ROBOT_IDS"
```

若只做本机只读探针，可将 `ADAPT_NATIVE_TOOL_MODE` 保持为 `off`，先运行普通
`adapt run --dry-run`。真实 ROS 目标再按项目配置 `ros.setup_files`，确认 setup 文件
路径和 digest 与目标环境一致。

每次运行重点检查输出目录中的：

```text
native-tool-rollout.json
native-tool-summary.json
native-tool-gate.json
artifact://native/<robot>/sessions/<session>/calls/*.json
```

关注成功/不可用/超时、`environment_limited_count`、输出截断/脱敏、
evidence/artifact 引用和 fallback。`native-tool-gate.json` 是 release-neutral 的健康
判定：未选中为 `NOT_SELECTED`，仅环境依赖导致的超时不会阻断 gate，真实失败/拒绝/截断
或非环境超时会报告 `FAIL`。`shadow` 与 `canary` 不得产生 release 变更。出现异常时把
mode 改回 `off`，无需回滚 Registry。

`native-tool-summary.json`、`native-tool-gate.json` 和 Adapt handoff 之间必须保持
robot/run/session/catalog digest 一致；调用 artifact 的 stdout/stderr 由 hash 保护，
敏感结果文件在 POSIX 目标机写入为 `0600`。重新拉取代码后请重新生成这些 artifacts，
不要复用旧版本的 catalog digest。

## 4. 通过标准

- 离线校验和目标机 shadow 均无 silent drop；
- Linux host/resource/process、ROS graph/observe/TF、HW inventory/status 结果可复现；
- artifact/evidence 可追溯，超时、输出上限和安全拒绝符合预期；
- 至少连续多个 run 窗口无高严重度差异，人工确认后才允许 `canary`，再考虑 `active`；
- 未通过前，不删除旧 wrapper、旧 contract 或 v1 审计材料。

<!-- status: active; authority: guide; owner: ROLO maintainers; last_reviewed: 2026-08-31; source_of_truth: docs/target/REAL_MACHINE_VALIDATION_RUNBOOK_ZH.md -->

# 目标机 Adapt 真机验证手册

本文是[真机验证主 Runbook](REAL_MACHINE_VALIDATION_RUNBOOK_ZH.md)的 Adapt 详细附录，用于在真实机器人目标机（或以目标机应用用户 SSH 登录）验证已合入 `main` 的 Adapt
真机验证线。本轮重点不是验证运动控制，而是验证 Discovery、State Graph、
Adapter binding 和只读运行时路由的完整闭环。

## 1. 验证边界

本次只允许执行以下类型的操作：

- 只读环境检查、Discovery 和 Adapt promotion；
- `describe`、`validate-binding`；
- Catalog 中明确标记为 `VERIFIED` 的只读 operation；
- 生成 secret-free acceptance pack。

不要调用运动、写配置、启动/停止进程、发送速度或执行器命令。发现阶段证明的是“目标通路
存在且绑定一致”，不等于已经证明运动安全、控制正确性、性能或长期可靠性。

## 2. 拉取当前代码

在目标机执行：

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git rev-parse HEAD
```

将上一步输出的 revision 记录到验证目录；真机验证必须固定在本次合入后的
`main` revision，不要在验证过程中混用其他分支或未推送提交。

```bash
git switch --track -c main origin/main  # 仅当本地尚无 main 分支
```

安装锁定依赖并检查基础环境：

```bash
uv sync --frozen
uv run robotctl runtime version
uv run robotctl doctor
```

若目标机是 Debian/Ubuntu，确认适配沙箱依赖已安装：

```bash
command -v bwrap
```

完整 Adapt 在 Linux 上应使用 `scripts/rolo-adapter-sandbox` 或部署指定的
`ROLO_ADAPTER_SANDBOX_LAUNCHER`。如果 `doctor` 或 Adapt 在沙箱自检阶段失败，先保存完整输出，
不要绕过沙箱继续验证。

## 3. 设置验证变量

将下面的值替换为目标机实际路径：

```bash
export ROBOT_ID=wheeltec_real_01
export PROJECT_ROOT=/path/to/wheeltec/_drivers
export URDF_PATH=/path/to/robot.urdf       # 没有 URDF 时删除该变量和参数
export VALIDATION_DIR="$PWD/rolo-target-validation-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$VALIDATION_DIR"
```

记录目标机基础信息，但不要把密钥、token 或私有配置复制到 validation 目录：

```bash
{
  date -Is
  hostname
  uname -a
  git rev-parse HEAD
  uv run robotctl runtime version
} | tee "$VALIDATION_DIR/host.txt"
```

ROS 目标需要确认 setup 文件、ROS domain、RMW 和 overlay 是目标机实际配置；不要在 adapter
源码中写死 topic 或 executable 的绝对路径。非 ROS 工程不需要人为设置 ROS 环境。

## 4. 刷新目标 CLI help allowlist（本轮新增）

目标机若已有旧的 target-evidence collector，普通 `adapt start` 会保留其 pinned
allowlist，不会静默扩展。先显式刷新一次，流程会自动扫描项目声明入口和常规 `.venv/bin`、
`install/*/bin` 目录，只固定实际存在的常规入口文件，并创建不可变 transition 记录。
该步骤只读取文件、计算 SHA-256，不执行目标 CLI。

```bash
export ROLO_CONFIG_ROOT="${ROLO_CONFIG_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/rolo/config}"
export DEPLOYMENT_CONFIG="$ROLO_CONFIG_ROOT/target-evidence/$ROBOT_ID.json"
test -f "$DEPLOYMENT_CONFIG"
export CURRENT_COLLECTOR_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["collector"]["collector_id"])' "$DEPLOYMENT_CONFIG")"
test -n "$CURRENT_COLLECTOR_ID"

uv run robotctl target-evidence collector-refresh \
  --robot "$ROBOT_ID" \
  --project-root "$PROJECT_ROOT" \
  --config-root "$ROLO_CONFIG_ROOT" \
  --expected-collector-id "$CURRENT_COLLECTOR_ID" \
  2>&1 | tee "$VALIDATION_DIR/collector-refresh.txt"
```

预期结果：

- 输出 `status=COLLECTOR_REFRESHED`；
- `help_executables` 至少包含目标项目中实际存在的安全入口，最多 20 个；
- 输出新的 `collector_state`、`transition_path` 和新的 collector ID；
- 旧 deployment/collector 文件仍可读取，transition 中同时记录旧、新 collector ID；
- 此步骤不启动入口，不访问摄像头、ROS、CAN 或其他硬件。

如果目标机尚未 enrollment，则首次初始化时直接省略 `--allow-executable`，让 collector 自动
发现入口：

```bash
uv run robotctl target-evidence collector-init \
  --robot "$ROBOT_ID" \
  --project-root "$PROJECT_ROOT" \
  --descriptor-out "$VALIDATION_DIR/collector-descriptor.json" \
  2>&1 | tee "$VALIDATION_DIR/collector-init.txt"
```

若出现 `expected refresh pin` 或 `already pinned`，不要删除配置或覆盖 secret；重新读取当前
collector ID，确认没有其他任务并发轮换后再重试。

## 5. 先做只读 Discovery

如果需要单独确认发现结果，先执行：

```bash
uv run robotctl target-evidence collect \
  --robot "$ROBOT_ID" \
  --output "$VALIDATION_DIR/target-evidence.json" \
  2>&1 | tee "$VALIDATION_DIR/target-evidence-collect.txt"

uv run robotctl adapt discover run \
  --robot "$ROBOT_ID" \
  --source-root "$PROJECT_ROOT" \
  --active-probe runtime-readonly \
  --target-evidence-bundle "$VALIDATION_DIR/target-evidence.json" \
  --full | tee "$VALIDATION_DIR/discover.txt"
```

预期 `target-evidence collect` 输出 `status=VERIFIED`，并为每个 pinned help executable
记录 `SUCCEEDED`、`FAILED` 或 `TIMEOUT`；单个入口失败不能抹掉其他入口的证据。Discovery
不得再出现 `--active-probe runtime-readonly requires --target-evidence-bundle`。

当前采集器会对 ROS graph 做一次有界双采样，并对最多 128 个 topic 在 20 秒预算内采集
publisher/provider 和接口 schema 摘要。检查 `target-evidence.json` 中 ROS probe 的
`stability` 与 `route_enrichment`：`stability.stable=true` 才表示两次 graph 快照一致；
`route_enrichment.truncated=true` 或缺少某条 route 的 provider/schema 时，只能保留
`PARTIAL` 证据，不能把该 route 提升为已验证操作。若这两个字段完全不存在，说明目标机仍
在使用旧 collector，先更新到包含本轮修复的 `main` revision 后重新 enrollment/collect。

根据工程布局补充 `--build-root`、`--install-root`、`--doc-root`、`--launch-root` 或
`--executable`；不要把不存在的路径写进命令。然后查看摘要：

若目标工作负载是 Nav2，生命周期探针必须指向实际 lifecycle node；不要使用不存在的
`/localization_server`。在与 collector 相同的 ROS Domain/RMW 环境中检查：

```bash
for node in \
  /amcl \
  /map_server \
  /controller_server \
  /planner_server \
  /local_costmap/local_costmap \
  /global_costmap/global_costmap
do
  printf '%s: ' "$node"
  ros2 lifecycle get "$node"
done | tee "$VALIDATION_DIR/nav2-lifecycle.txt"
```

预期六个节点均返回 `active [3]`。若 costmap 使用 namespace 或非 composed 启动方式，先从
`ros2 node list` 取得真实全限定节点名，再逐个探测；不得用父容器或猜测名称代替 lifecycle
node。节点不存在与节点非 active 必须分别记录。

然后查看摘要：

```bash
uv run robotctl adapt discover review --robot "$ROBOT_ID" \
  | tee "$VALIDATION_DIR/discover-review.txt"
uv run robotctl adapt operations summary --robot "$ROBOT_ID" \
  | tee "$VALIDATION_DIR/operations-summary.txt"
uv run robotctl adapt operations list --robot "$ROBOT_ID" --applicability OBSERVED \
  | tee "$VALIDATION_DIR/operations-observed.txt"
```

Discovery 记录中重点确认：

- 状态为 `SUCCEEDED` 或可解释的 `PARTIAL`；
- 目标 fingerprint、evidence digest、collector identity 非空；
- 目标实际存在的 topic/service/action/device/CLI 出现在 route evidence 中；
- 项目已声明的入口与目标 help 探测结果分开显示：`SOURCE_DECLARED` 仅是静态线索，
  `OBSERVED_RUNTIME` 才能形成可绑定 route；未探测入口必须保留 `NOT_PROBED`，不能静默丢失；
- ROS 失败时保留 `ros.json`，查看 `command_diagnostics`，区分 setup 失败、命令失败和空图；
- route 的 `resource_id` 稳定，不依赖本次运行的临时路径；
- 没有把 Wheeltec 专有名称误当成跨平台 canonical operation。

## 6. 执行完整 Adapt journey

推荐先运行 dry-run，确认目标候选和预计范围：

```bash
uv run robotctl adapt run --robot "$ROBOT_ID" --dry-run \
  | tee "$VALIDATION_DIR/adapt-dry-run.txt"
```

预期为 `REQUIRES_CODING`，且 `eligible_operations` 非空；`deferred_operations` 必须有明确、
稳定的原因。如果 dry-run 已经 `BLOCKED`，先保存：

```bash
uv run robotctl adapt candidates inspect OPERATION --robot "$ROBOT_ID"
uv run robotctl adapt operations inspect OPERATION --robot "$ROBOT_ID"
```

确认无误后执行完整流程：

```bash
uv run robotctl adapt start \
  --robot-id "$ROBOT_ID" \
  --project-root "$PROJECT_ROOT" \
  --urdf "$URDF_PATH" \
  --active-probe runtime-readonly \
  --heuristic-agent-timeout 300 \
  --timeout 1800 \
  2>&1 | tee "$VALIDATION_DIR/adapt-start.txt"
```

没有 URDF 时，删除 `--urdf "$URDF_PATH"`。如果使用已配置的远程 collector，则按目标证据
部署手册使用 `--evidence-mode remote`；远程采集失败不能退回 controller 本地探测。

`--heuristic-agent-timeout` 是 discovery planning 的单次预算，也是完整 mapping 阶段
（包括排队和所有并发批次）的总 deadline。调用前会使用与 helper 相同的受控环境检查
endpoint/proxy TCP 可达性及本地 Codex 登录状态；readiness 失败应在连接预算内立即返回，
而不是等待完整模型预算。超时会保留 deterministic fallback，并在
`heuristic/summary.json`、`operation-proposal-validation.json` 中记录
`PROVIDER_TIMEOUT`、prompt/context 字符数及批次完成情况，不会让目标机进程无限等待。
默认不要清空 WSL 中已配置的 `HTTP_PROXY`、`HTTPS_PROXY` 或 `ALL_PROXY`；helper 会只继承
受控 allowlist 中的代理变量。若 readiness 明确失败，应先修复 Agent 登录/网络问题，不要
重复启动多个长时间的 Adapt 进程。planning、mapping 和 Wiki helper 默认使用 `low`
reasoning effort：这些阶段只做受 schema 约束的分类/映射，caller 会确定性补齐证据、身份、
预算和收据并再次验证；不要让模型重复输出 caller-owned 大字段或逐路由执行 shell 工具。

完整成功条件：

- journey 状态为 `COMPLETE`；
- gate 为 `PASSED`；
- handoff、release、target evidence digest 和 fingerprint 均非空；
- Adapter Agent 阶段只生成结构化 bundle，不直接写入产品源代码；
- promotion 阶段执行 `describe` 和 `validate-binding`，不执行 `invoke`。
- 高风险入口即使 help 成功，也只能形成只读证据；不得因 `--help` 成功而自动执行
  `setup-motors`、`teleoperate`、`record`、`replay` 或其他写/运动命令。

## 7. 发布后的只读检查

```bash
uv run robotctl adapt status --robot "$ROBOT_ID" \
  | tee "$VALIDATION_DIR/adapt-status.txt"
uv run robotctl adapt operations summary --robot "$ROBOT_ID" \
  | tee "$VALIDATION_DIR/operations-summary-after.txt"
uv run robotctl adapt operations list --robot "$ROBOT_ID" --registration REGISTERED \
  | tee "$VALIDATION_DIR/operations-registered.txt"
uv run robotctl tool catalog --robot "$ROBOT_ID" \
  | tee "$VALIDATION_DIR/tool-catalog.txt"
uv run robotctl state graph snapshot --robot "$ROBOT_ID" \
  | tee "$VALIDATION_DIR/state-graph.json"
uv run robotctl adapt acceptance-pack --robot "$ROBOT_ID" \
  --output "$VALIDATION_DIR/rolo-adapt-acceptance.json"
```

State Graph 应满足：

- `schema_version` 为 `robot-state-graph/v2`；
- `owner` 为 `ROLO_GATE`；
- 每个 bundled operation 都有 `implements` 和 `routes_to`；
- route 的 endpoint、interface type/schema、provider、runtime revision、evidence origin 与
  Discovery 证据一致；
- route evidence refs 和 semantic bindings 非空或有合理解释；
- 不存在只在当前 Catalog 中出现、但没有 State Graph route 的 `VERIFIED` operation。

## 8. 只读运行时验证

先从 Catalog 和 schema 中确认某个 operation 是 `VERIFIED` 且确实为只读：

```bash
uv run robotctl tool schema OPERATION --robot "$ROBOT_ID" \
  | tee "$VALIDATION_DIR/operation-schema.json"
```

再使用该 operation 的最小合法输入。示例（仅当 Catalog 明确显示该 operation 可用且为只读时）：

```bash
uv run robotctl tool invoke OPERATION \
  --robot "$ROBOT_ID" \
  --input '{}' \
  2>&1 | tee "$VALIDATION_DIR/invoke-readonly.txt"
```

如果该 operation 有多个 route：

1. 不带 `resource_id`、`endpoint`、`topic`、`camera` 等选择字段时，预期 fail closed，并出现
   `explicit route selector is required`；
2. 使用 schema 规定的选择字段重试；adapter 应选择对应 route；
3. 不要用任意字段名绕过选择检查，也不要把运动 operation 当作验证手段。

## 9. 三批次专项验证步骤与预期结果

### 9.1 第一批：多 route selector 精确绑定

先查看 State Graph 和 operation schema，确认目标机确实存在多 route operation：

```bash
uv run robotctl state graph snapshot --robot "$ROBOT_ID" \
  > "$VALIDATION_DIR/state-graph.json"
uv run robotctl tool schema OPERATION --robot "$ROBOT_ID" \
  > "$VALIDATION_DIR/operation-schema.json"
```

对一个明确为只读、且有两个或更多 route 的 `OPERATION` 执行：

```bash
uv run robotctl tool invoke OPERATION \
  --robot "$ROBOT_ID" \
  --input '{}' \
  2>&1 | tee "$VALIDATION_DIR/selector-missing.txt"
```

预期：命令失败，错误包含：

```text
explicit route selector is required
```

然后使用 schema 规定的 selector 重试，例如：

```bash
uv run robotctl tool invoke OPERATION \
  --robot "$ROBOT_ID" \
  --input '{"resource_id":"<真实资源 ID>"}' \
  2>&1 | tee "$VALIDATION_DIR/selector-valid.txt"
```

预期：selector 唯一匹配时才进入 adapter；如果值不存在或匹配多个 route，必须失败，并包含
`operation route selector does not match a gated route` 或 `operation route selector is ambiguous`。
失败请求不得启动目标 CLI、ROS 或硬件进程。

### 9.2 第二批：binding 隔离和 CLI help 预检

重新执行完整 Adapt 或 promotion 后，检查输出中的 promotion 检查项：

```bash
rg -n "validate-binding|target CLI|help|promotion|gate" \
  "$VALIDATION_DIR/adapt-start.txt"
```

预期：

- promotion 执行 `describe`、`validate-binding` 和只读 CLI `--help`；
- 不执行 adapter `invoke`；
- `validate-binding` 只使用 `ROLO_TARGET_ROUTE_BINDINGS_JSON` 和
  `ROLO_VALIDATE_BINDING_ONLY=1`；
- 不因缺少目标 PATH 而报 `TARGET_EXECUTABLE_NOT_FOUND`；
- CLI 的 shebang interpreter 在最终 sandbox 内可见；
- help 非零退出、超时或输出超限时，gate 为失败而不是继续发布。

如果出现以下错误，应保留完整 stderr，不要通过设置 controller 主机 PATH 绕过：

```text
target CLI is not resolvable inside the adapter sandbox
target CLI interpreter is not resolvable inside the adapter sandbox
target CLI help probe failed
```

### 9.3 第三批：启发式冲突和 battery/telemetry

检查候选摘要中是否保留 mapping score、候选列表和歧义状态：

```bash
uv run robotctl adapt operations summary --robot "$ROBOT_ID" \
  | tee "$VALIDATION_DIR/heuristic-summary.txt"
uv run robotctl adapt operations list --robot "$ROBOT_ID" --applicability OBSERVED \
  | tee "$VALIDATION_DIR/heuristic-observed.txt"
```

对发现到的泛化 telemetry topic（例如包含 voltage、current、battery、power 的 topic），检查：

```bash
uv run robotctl adapt candidates inspect hw.power.battery.status --robot "$ROBOT_ID" \
  | tee "$VALIDATION_DIR/battery-candidate.txt"
```

预期：

- `/battery/voltage`、`/power_voltage`、`/pack/current` 等真实 topic 可以形成
  `hw.power.battery.status` candidate；
- candidate 必须带有 topic/interface/provider/schema/runtime evidence；
- 缺少运行时证据时保持 `DISCOVERED_UNVERIFIED` 或 deferred；
- `/telemetry` 同时接近多个 application telemetry operation 时，候选应标记
  `HEURISTIC_MAPPING_AMBIGUOUS`，不能自动成为 `VERIFIED`；
- 不出现 Wheeltec 专有判断、静态 topic 白名单或 controller 路径。

### 9.4 重复运行稳定性

在目标进程和 ROS graph 未改变时，再运行一次只读 Discovery：

```bash
uv run robotctl adapt discover run \
  --robot "$ROBOT_ID" \
  --source-root "$PROJECT_ROOT" \
  --active-probe runtime-readonly \
  --target-evidence-bundle "$VALIDATION_DIR/target-evidence.json" \
  --full | tee "$VALIDATION_DIR/discover-repeat.txt"
uv run robotctl adapt acceptance-pack --robot "$ROBOT_ID" \
  --output "$VALIDATION_DIR/rolo-adapt-acceptance-repeat.json"
```

预期：状态仍为 `COMPLETE`（或同样可解释的 `PARTIAL`），等价证据不会导致无故换 route、
降级或生成新的不一致 release。若 target executable、ROS setup、RMW、ROS domain 或 provider
digest 发生变化，则旧 release 应被标记 stale 并要求重新门禁。

## 10. 本轮重点观察清单

| 优先级 | 观察项 | 通过标准 | 异常时保存 |
|---|---|---|---|
| P0 | State Graph route 完整性 | endpoint/provider/schema/runtime revision 与 evidence 一致 | state graph、discovery report、gate error |
| P0 | `validate-binding` 隔离 | 不读取目标 ROS/PATH/device 上下文；只消费 binding JSON | adapt-start 日志、adapter stderr、沙箱日志 |
| P0 | promotion 边界 | 未执行 `invoke`，未触发硬件或目标 CLI 副作用 | Agent/gate 日志、进程审计 |
| P1 | semantic binding 一致性 | promotion 与 runtime 使用相同 semantic binding 集合 | release manifest、State Graph、catalog |
| P1 | 多 route 选择 | 缺 selector 直接拒绝；合法 selector 可确定路由 | 输入 JSON、返回错误、route document |
| P1 | 跨平台路径 | 不出现 controller 路径、Wheeltec 私有绝对路径或硬编码 ROS topic | bundle 文件名、gate 错误、target evidence |
| P2 | 重复发现稳定性 | 等价证据再次运行后仍为 `COMPLETE`，release 不无故变化 | 两次 acceptance pack、discovery ID |

## 11. 异常记录格式

每个异常单独记录以下信息：

```text
时间（含时区）：
目标机 hostname / ROBOT_ID：
代码提交：
Adapt run / discovery / release ID：
执行命令：
预期行为：
实际行为：
是否触发硬件、ROS、CLI 或写操作：
相关日志或 artifact 路径：
复现次数：
```

请优先上传 `rolo-adapt-acceptance.json`、摘要日志、错误 stderr 和 State Graph；不要上传 SSH
私钥、token、完整私有源码、原始 secret 或包含凭据的环境导出。

## 12. 验证结束回传

在目标机执行：

```bash
sha256sum "$VALIDATION_DIR/rolo-adapt-acceptance.json"
tar --exclude='*.key' --exclude='*.pem' --exclude='*secret*' \
  -czf "$VALIDATION_DIR.tar.gz" "$VALIDATION_DIR"
```

回传以下内容即可：

1. `rolo-adapt-acceptance.json` 及 SHA-256；
2. `adapt-start.txt`、`adapt-status.txt`、`state-graph.json`；
3. 只读 invoke 的输入、输出和错误（如执行过）；
4. 上表中任一异常的完整记录。

# 目标机 Adapt 真机验证手册

本文用于在真实机器人目标机（或以目标机应用用户 SSH 登录）验证当前分支
`codex/adapt-full-hardening`。本轮重点不是验证运动控制，而是验证 Discovery、State Graph、
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
git switch codex/adapt-full-hardening
git pull --ff-only origin codex/adapt-full-hardening
git rev-parse HEAD
```

预期提交为 `52c9669` 或其后续提交。若本地没有该分支：

```bash
git switch --track -c codex/adapt-full-hardening origin/codex/adapt-full-hardening
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

## 4. 先做只读 Discovery

如果需要单独确认发现结果，先执行：

```bash
uv run robotctl adapt discover run \
  --robot "$ROBOT_ID" \
  --source-root "$PROJECT_ROOT" \
  --active-probe runtime-readonly \
  --full | tee "$VALIDATION_DIR/discover.txt"
```

根据工程布局补充 `--build-root`、`--install-root`、`--doc-root`、`--launch-root` 或
`--executable`；不要把不存在的路径写进命令。然后查看摘要：

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
- ROS 失败时保留 `ros.json`，查看 `command_diagnostics`，区分 setup 失败、命令失败和空图；
- route 的 `resource_id` 稳定，不依赖本次运行的临时路径；
- 没有把 Wheeltec 专有名称误当成跨平台 canonical operation。

## 5. 执行完整 Adapt journey

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
  --timeout 1800 \
  2>&1 | tee "$VALIDATION_DIR/adapt-start.txt"
```

没有 URDF 时，删除 `--urdf "$URDF_PATH"`。如果使用已配置的远程 collector，则按目标证据
部署手册使用 `--evidence-mode remote`；远程采集失败不能退回 controller 本地探测。

完整成功条件：

- journey 状态为 `COMPLETE`；
- gate 为 `PASSED`；
- handoff、release、target evidence digest 和 fingerprint 均非空；
- Adapter Agent 阶段只生成结构化 bundle，不直接写入产品源代码；
- promotion 阶段执行 `describe` 和 `validate-binding`，不执行 `invoke`。

## 6. 发布后的只读检查

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

## 7. 只读运行时验证

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

## 8. 本轮重点观察清单

| 优先级 | 观察项 | 通过标准 | 异常时保存 |
|---|---|---|---|
| P0 | State Graph route 完整性 | endpoint/provider/schema/runtime revision 与 evidence 一致 | state graph、discovery report、gate error |
| P0 | `validate-binding` 隔离 | 不读取目标 ROS/PATH/device 上下文；只消费 binding JSON | adapt-start 日志、adapter stderr、沙箱日志 |
| P0 | promotion 边界 | 未执行 `invoke`，未触发硬件或目标 CLI 副作用 | Agent/gate 日志、进程审计 |
| P1 | semantic binding 一致性 | promotion 与 runtime 使用相同 semantic binding 集合 | release manifest、State Graph、catalog |
| P1 | 多 route 选择 | 缺 selector 直接拒绝；合法 selector 可确定路由 | 输入 JSON、返回错误、route document |
| P1 | 跨平台路径 | 不出现 controller 路径、Wheeltec 私有绝对路径或硬编码 ROS topic | bundle 文件名、gate 错误、target evidence |
| P2 | 重复发现稳定性 | 等价证据再次运行后仍为 `COMPLETE`，release 不无故变化 | 两次 acceptance pack、discovery ID |

## 9. 异常记录格式

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

## 10. 验证结束回传

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


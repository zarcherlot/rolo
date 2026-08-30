<!-- status: frozen; authority: reference; owner: ROLO maintainers; last_reviewed: 2026-08-29 -->

# `origin/codex/post-r5-integration` WSL2 验证报告

- 验证时间：2026-08-29（Asia/Shanghai）
- Revision：`043807891edf8ea7d154fec55eb23ed8ebf482a3`
- Git 状态：独立 detached worktree，验证结束时 clean；原用户工作区未切换、未修改
- Robot ID：`wsl2-post-r5-0438078`
- 环境：Ubuntu 22.04 / WSL2，ROS 2 Humble，`rmw_fastrtps_cpp`
- ROS：`ROS_DOMAIN_ID=50`，`ROS_LOCALHOST_ONLY=1`
- 最终判定：**HOLD（当前提交不应据此完成集成线合入）**

## 1. Revision 与 Runbook 偏差

远端 `origin/codex/post-r5-integration` 已重新抓取并精确解析为请求的 revision：

```text
043807891edf8ea7d154fec55eb23ed8ebf482a3
```

字面命令 `git fetch origin --prune` 首次因本机 `remote.origin.fetch` 仍固定引用已删除的
`codex/registry-redesign-r5` 而失败；未改写持久 Git 配置，改用一次性显式 refspec 抓取
`codex/post-r5-integration`，随后远端 ref 与 detached HEAD 均精确匹配上述 SHA。该项属于
本机 origin refspec 维护问题，不是本提交门禁失败。

本提交新增的 `docs/validation/REAL_MACHINE_P1_RUNBOOK_ZH.md` 仍硬编码
`02ad4335f1ed212b36e8cbf29aeaf93d56624113`；source-of-truth 文档
`docs/target/POST_MERGE_DEVELOPMENT_AND_REAL_TARGET_RUNBOOK.md` 又记录
`fc6dcb8ca12d327110fc89ee319ed47d291d93d3`。本轮按用户明确指定的最新远端 SHA 执行，
但文档 revision 已漂移，必须修订后才能称为严格 runbook-compliant。

P1 runbook 在 Adapt 前全局设置 `CODING_AGENT_EXECUTOR=local-target`，而当前实现仅为
Diagnose/Verify 注册 `local-target`；Adapt 的依赖检查返回 `UNSUPPORTED`。本轮保留了三次
启动前拒绝证据，然后仅对 Adapt 使用内置 `codex` executor；Diagnose/Verify 仍使用
`local-target`。

## 2. 合入门禁

| 门禁 | 结果 |
|---|---|
| `uv sync --frozen` | PASS |
| `scripts/check_docs.py` | PASS |
| Registry v2 contract validate | PASS |
| Registry migration validate | PASS |
| `pytest -q` | PASS：861 passed，4 skipped；865 collected |
| `ruff check .` | PASS |

所有门禁退出码均为 0。文档检查未识别上述硬编码 revision 漂移。

## 3. WSL2 Nav2 软件负载

使用 `rolo_wsl_sim/nav2_workload.launch.py` 启动真实 Nav2 节点与合成机器人传感器负载，
不是 `rolo_p2_validation_fixture`：

| 项目 | 结果 |
|---|---:|
| ROS nodes | 19 |
| topics | 47 |
| services | 156 |
| actions | 12 |
| Nav2 lifecycle active | 8 / 8 |
| `map -> base_link` TF | 连续可读 |

`ros2 doctor --report`、graph、lifecycle 与 TF 原始输出均已归档。验证结束后所有本轮 ROS
进程已停止。

## 4. Adapt shadow 窗口

初始按 P1 runbook 使用 `local-target` 的 3 次尝试全部在 Agent 启动前以
`Adapter Agent dependency is not ready: UNSUPPORTED` 拒绝，没有执行目标操作。

使用 Adapt 已注册的 `codex` executor 后，连续三个 shadow 窗口结果如下：

| 窗口 | Run ID | Adapt gate | Native gate/parity | 结果 |
|---|---|---|---|---|
| 01 | `20260829T131728Z-04cd949d` | PASSED | PASS / PASS | COMPLETE |
| 02 | `20260829T132201Z-57e95206` | FAILED | PASS / PASS | FAILED |
| 03 | `20260829T132849Z-98a7d101` | PASSED | PASS / PASS | COMPLETE |

窗口 02 的 Agent 正常退出并生成 `adapter.pyz`，但冻结产物权限为 `0644`。独立 gate 随后
直接执行 zipapp，得到：

```text
bwrap: execvp .../adapter.pyz: Permission denied
```

本轮未修改权限绕过门禁。三个窗口的 native call 均为真实 Linux baseline，parity 为
PASS、`blocking_reasons=[]`、`influences_release=false`；但整体只有 2/3 Adapt gate 通过，
不满足 runbook 对 3～5 个稳定窗口的 GO 条件。

## 5. Diagnose handoff

- 未确认运行：`WAITING_FOR_AUTH`，CLI 预期返回码 2。
- 确认恢复：`SUCCEEDED`。
- Episode：`episode-6d1a71933caf436aa7558ae051a62946`。
- 六阶段严格顺序：`baseline -> observe -> hypothesis -> change -> smoke -> decision`。
- `change.kind=NO_CHANGE`，`applied=false`。
- target binding、provenance、Episode publication、frozen config、diagnosis report 与
  Diagnose handoff 的引用/SHA256 已由生产 validator 复核通过。

另建等待授权的 Diagnose run 后执行 CLI cancel，结果为 `CANCELLED`、
`cancel_requested=true`，已完成 handoff 未被覆盖。

## 6. Local-target Verify

批准计划包含六个只读 case：`linux.uname`、`ros.doctor.report`、`ros.node.list`、
`ros.topic.list`、`ros.service.list`、`ros.topic.echo_once(/tf)`。

- 未确认运行：`WAITING_FOR_AUTH`。
- 确认恢复：`SUCCEEDED`。
- 6 / 6 case PASS。
- canonical evidence：`rolo-verification-evidence/v2`。
- `safe_stop=NOT_REQUIRED`，`rollback=NOT_REQUIRED`，release authority=`none`。
- local-target Verify handoff 已在被 SSH handoff 替换前单独保存。

写操作负面计划 `ros.topic.publish(/cmd_vel)` 被 `acceptance-plan` 接受并发布；确认执行时
provider 在任何 operation invocation 前以
`verification plan contains non-allowlisted operations` 失败关闭。没有发布 ROS 消息或发生
写操作。建议让 `acceptance-plan` 本身拒绝非 allowlist，以匹配“validate bounded read-only
plan”的产品语义。

另建等待授权的 Verify run 后执行 CLI cancel，结果为 `CANCELLED`、
`cancel_requested=true`，已完成 handoff 未被覆盖。

## 7. 固定 SSH 目标与故障矩阵

固定目标：`ssh://sxt@localhost:22/tmp/rolo-post-r5-validation-0438078`。
SSH profile 明确批准 ED25519 host-key：
`SHA256:153bYo06ZmAJLTZgX9fr0TtaHeCtjcE4AnJBkO/PUYs`；认证仅使用临时 ssh-agent。
远端 companion health 为 `rolo-target 0.1.0`。

| 注入 | 结果 |
|---|---|
| timeout | provider report=`FAIL`，case=`TIMEOUT`，失败 evidence 已物化 |
| cancel between cases | report=`CANCELLED`，原始 evidence 保留 |
| concurrent lock | fail-closed：`already active` |
| stale lock（601 s） | stale lock 删除；3 个真实 SSH 只读 case 全 PASS |
| 无 Diagnose handoff | Verify materialization 拒绝 |
| provenance SHA256 篡改 | `verification target provenance hash mismatch` |

在主 artifact root 上重新执行真实 SSH provider 后：

- `target-platform`、`workspace-readiness`、`companion-health`：3 / 3 PASS；
- evidence 为 canonical v2，SSH binding/profile/provenance digest 有效；
- `materialize_handoff()` 成功绑定真实 Diagnose handoff；
- 最终生产 validator 对 Adapt、Diagnose、Verify 三层 handoff 和全部引用摘要复核通过。

临时 SSH 私钥未进入归档；`authorized_keys` 已恢复，恢复前后 SHA256 均为：
`d2c92541450d75302a47c94cb26ed73ec73f7e5b3fc38c35ea66c31517b1f571`。

## 8. 回退与最终判定

- `ADAPT_NATIVE_TOOL_MODE` 已恢复为 `off`；selector 已清空。
- release authority 始终为 `none`。
- 只读 Verify 的 safe-stop/rollback 均为 `NOT_REQUIRED`。
- timeout/cancel/并发失败没有提升 latest handoff；stale lock 恢复成功。
- 最终 pipeline read model 为 Adapt/Diagnose/Verify 全部 `COMPLETE`，但这不覆盖 shadow
  稳定性门禁。

最终结论为 **HOLD**，不是 GO，也不是物理机器人 E4 结论。当前提交不建议完成集成线合入
（此处不涉及远端 `main`）：

1. 修复或规范化可执行 adapter 产物的 mode（尤其 `.pyz`），增加冻结后 execute 回归测试；
2. 修订 P1 runbook 的 SHA 与 Adapt executor 设置，并增加文档漂移门禁；
3. 建议在 `acceptance-plan` 发布阶段拒绝非 allowlist operation；
4. 修复后从全量门禁重新开始，取得至少 3 个连续 Adapt shadow gate PASS，再评审合入。

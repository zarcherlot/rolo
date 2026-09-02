<!-- status: active; authority: design; owner: rolo maintainers; last_reviewed: 2026-09-02 -->

# LanderPi 最小 Diagnose 用例集

这不是完整机器人软件栈诊断，而是针对 LanderPi 当前真实证据设计的最小 Diagnose
vertical slice。它复用 Rolo 的目标绑定、只读 Inspect Tool、受控 bring-up 和 L1/L2
conformance 结果，验证“发现异常 → 形成假设 → 给出下一步 → 复测”的闭环。

## Diagnose 运行原则

每个 case 固定六个阶段：

```text
baseline → observe → hypothesis → change(NO_CHANGE) → smoke → decision
```

- `baseline` 和 `observe` 只消费新鲜 TargetEvidence 和 NativeTool 结果；
- `hypothesis` 由 Agent 根据证据提出，Rolo 只校验引用完整性；
- `change` 默认是 `NO_CHANGE`，不自动修改服务、参数或文件；
- 允许的受控 bring-up 必须有 lease、超时和清理，不能替换持久化运行服务；
- `smoke` 只复测原始症状或 L1/L2 canary，不等同于任务成功；
- `decision` 只能输出 `HEALTHY`、`DEGRADED`、`BLOCKED` 或 `INCONCLUSIVE`，不能伪造物理安全结论。

## 用例矩阵

| ID | 症状/问题 | 最小观察 | 典型假设 | 决策 |
|---|---|---|---|---|
| `LP-D01` | 导航命令未发现 | 基础 graph、已安装 launch/package、受控 Nav2-only graph | 导航包存在但基础 bring-up 未启动 Nav2 | `DEGRADED`，给出 bring-up 下一步 |
| `LP-D02` | 雷达 timeout 或数据退化 | 日志窗口、`/scan` 样本、频率、NaN/Inf 比例 | 驱动偶发 timeout，但 topic 仍有数据 | `DEGRADED`，不得宣称安全导航 |
| `LP-D03` | 全局导航无法建立位姿 | TF frame 集合、`/map`、AMCL 状态、initial pose 证据 | 定位节点存在，但尚未完成重定位 | `BLOCKED`（仅对全局导航），相对运动仍可继续 |
| `LP-D04` | 速度边界不一致 | 静态参数、运行时参数、底盘 launch 限制、odom 窗口 | 配置允许值高于底盘产品约束 | `BLOCKED`，禁止升级到 L3 |
| `LP-D05` | Tool route 不匹配 | operation candidate、subscriber/action info、route recheck | `app.base.stop` 与导航 `/cmd_vel_nav` 是不同链路 | `DEGRADED`，生成窄 route gap |
| `LP-D06` | 写入后是否真正停车 | L1 zero-stop、L2 cancel/stop、odom 复核、进程清理 | 命令返回成功但实际状态未知 | 仅在反馈和收尾均满足时 `HEALTHY` |

## 具体用例

### LP-D01：导航栈未启动

**baseline**：记录基础 `bringup` 的节点、action、topic 集合。

**observe**：扫描目标机 launch/package/config；使用不拉起底盘驱动的 Nav2-only
bring-up；重新读取 `/navigate_to_pose`、`/spin`、`/drive_on_heading` 和 lifecycle 状态。

**hypothesis**：导航源码和 Nav2 依赖存在，但基础服务没有启动导航栈。该假设必须同时
引用静态入口和真实 action graph。

**change**：`NO_CHANGE`；临时 bring-up 结束后恢复原服务。

**smoke/decision**：action 出现且 lifecycle active 时说明“路由可用”；不能据此推断
全局地图或运动安全可用。

### LP-D02：传感器数据退化

**baseline**：记录雷达进程、topic 类型、publisher 数量和目标时间窗口。

**observe**：采集有界日志；读取多条 `/scan`；计算消息间隔、有效 range 比例和 NaN/Inf
比例。单条样本不能作为健康证明。

**hypothesis**：例如“LD19 驱动存在 timeout，但过滤后的 `/scan` 仍可读”。

**change**：`NO_CHANGE`，不重启驱动、不修改串口或参数。

**smoke/decision**：在固定窗口内持续有样本且质量阈值满足才可降级解除；否则保持
`DEGRADED`，禁止 L3 task motion。

### LP-D03：定位前置条件缺失

**baseline**：记录 TF frame、`/map` publisher、AMCL lifecycle 和最近 initial pose。

**observe**：先检查相对运动接口；只有存在地图和重定位入口时才尝试建立
`map → base_footprint`。initial pose 只能使用明确的、目标绑定的输入。

**hypothesis**：没有 map frame 不代表没有导航能力，通常表示尚未初始化定位。

**change**：默认 `NO_CHANGE`；用户允许时可将“发布已知安全起点”作为单独授权动作，
但不能由 discovery 隐式完成。

**smoke/decision**：相对运动 canary 可独立通过；全局导航保持 `BLOCKED`，直到 TF、地图、
定位质量和测距证据同时满足。

### LP-D04：速度边界漂移

**baseline**：读取配置文件中的速度上限、运行时节点参数和底盘实际约束。

**observe**：比较最终生效值；用 odom 反馈确认 L1/L2 的实际速度和加速度，不把配置值
当成物理测量。

**hypothesis**：例如 behavior server 配置为 `3.0 rad/s`，而底盘 launch 约束为
`0.45 rad/s`，存在安全边界漂移。

**change**：`NO_CHANGE`；Diagnose 只给出需要评审的配置修复，不自动写参数。

**smoke/decision**：任何上限冲突都阻断 L3；L1/L2 只能在临时、显式锁定的更低边界下运行。

### LP-D05：Tool route 不匹配

**baseline**：绑定 operation ID、目标 evidence digest、接口类型和 subscriber/action 信息。

**observe**：重新执行 route binding；区分 `/cmd_vel`、`/cmd_vel_nav`、`/spin` 等不同
语义链路，不能因为消息类型相同就合并。

**hypothesis**：`app.base.stop` 的基础停止 route 未被当前 graph 证明，而导航 zero-stop
使用的是另一条 `/cmd_vel_nav → velocity_smoother → /cmd_vel` 链路。

**change**：`NO_CHANGE`，生成窄 gap candidate，不扩大通用 dispatcher。

**smoke/decision**：route recheck 和实际反馈都通过，才允许对应 operation 进入 Tool Surface。

### LP-D06：写入后停车闭环

**baseline**：确认目标处于静止状态，保存初始 odom/位姿和 route evidence。

**observe**：执行 L1 zero-stop 或 L2 bounded motion；保存发送计数、action 状态、cancel
响应、odom 速度/位移和最终零速窗口。

**hypothesis**：命令返回成功不等于机器人停止；必须由反馈证明。

**change**：所有动作结束统一执行 zero-stop；任何超时、越界或失联都触发停车并标记失败。

**smoke/decision**：LanderPi 当前 L1 zero-stop 和 L2 bounded rotation 已满足该闭环，
但不提升全局导航或任务级安全结论。

## Diagnose 输出

MVP 提供两个只读入口（不自动 bring-up、不重启驱动）：

```bash
rolo target diagnose-case --profile <profile> --case LP-D01
rolo target diagnose-case --profile <profile> --case LP-D02
```

命令通过已 enroll 的 `TargetProfile → SSH Connector` 运行固定、限时命令，分别写入
`diagnose/<robot>/cases/<case>/<UTC>/observation.json` 和 `finding.json`。若 profile 下有
可验证的 TargetEvidenceBundle，finding 会绑定其 `payload_sha256`；缺少或校验失败时命令
不会把本地推断伪装成目标证据。

每个 case 输出一条结构化 finding：

```text
case_id
symptom
hypothesis
evidence_refs[]
contradicting_evidence_refs[]
change: NO_CHANGE | AUTHORIZED_TEST
smoke_result
decision
next_probe
```

Agent 可以据此决定下一步 Probe 或请求用户授权；Rolo 负责证据完整性、目标绑定、超时、
清理和 handoff，不负责替 Agent 猜测根因，也不把单次 canary 成功升级为产品级安全保证。

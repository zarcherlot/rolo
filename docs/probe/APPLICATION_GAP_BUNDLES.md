<!-- status: active; authority: normative; owner: rolo maintainers; last_reviewed: 2026-09-02 -->

# Application gap bundle（Rolo v2）

Application 不是第二套大 Registry，而是 Agent 在当前 Tool Surface 不足时提出的一个窄 gap。
Rolo 只接受四个 MVP 应用族：`startup`、`navigation`、`mapping`、`manipulation`。
它们是面向小车用户任务的稳定语义，不绑定某个 OS 或 Middleware。

## 闭环

```text
已验证 TargetEvidenceBundle
          ↓
Rolo 观察 route evidence（不调用 service/action）
          ↓
ApplicationCandidate
          ↓
最小 ApplicationAdapterBundle（operation + route binding + native observation Tool）
          ↓
独立 ApplicationConformance
```

Candidate 只表示“发现了足够的运行时信号”，不表示应用已经启动成功、导航效果正确或机械动作安全。
Bundle 只绑定目标证据 payload digest、operation ID、一个或多个精确的
`OBSERVED_RUNTIME` route 和现有 public native observation Tool 的 typed 参数；不包含任意 shell、
写操作、service/action invocation 或 actuator 命令。

## 四个最小信号集

| application | 最小运行时信号 | 当前缺失时的结果 |
|---|---|---|
| `startup` | lifecycle/ready service，或任一非参数 Middleware runtime route | `NOT_FOUND` |
| `navigation` | 至少两类独立信号：运动指令、定位、测距、坐标系 | `PARTIAL` 或 `NOT_FOUND` |
| `mapping` | map/occupancy/slam/costmap 类状态 route | `NOT_FOUND` |
| `manipulation` | arm/gripper 控制 action 或 joint/servo 状态 | `PARTIAL` 或 `NOT_FOUND` |

信号匹配由 provider probe 的 route 形状完成。公共标准只约束语义和失败边界；provider-specific
命令、消息类型和运行时 setup 仍属于 TargetEvidence 的实现细节。未来新增 provider 只需提供同样的
观测映射和独立 conformance，不扩展这四个应用族的含义。

## CLI

Agent 或用户先取得一份新鲜、签名验证过的目标证据，然后逐一运行：

```bash
rolo target application-bundle --profile my-robot --application startup
rolo target application-bundle --profile my-robot --application navigation
rolo target application-bundle --profile my-robot --application mapping
rolo target application-bundle --profile my-robot --application manipulation
```

命令为每个应用写入 candidate、adapter-bundle 和 conformance 三个 artifact。`PASS` 才会得到
`APPLICATION_BUNDLE_READY`；`PARTIAL`/`NOT_FOUND` 仍保留 bundle 和失败原因，并以非零退出，供 Agent
决定下一步 Probe。这样“地图没有证据”是明确 gap，而不是静态源码或 Agent 记忆造成的假阳性。

当 Agent 已经明确指出一个 v1 operation 时，使用 operation 级入口：

```bash
rolo target application-operation \
  --profile my-robot \
  --operation app.navigation.status
```

operation 级 bundle 目前发布的是通过 route-binding Conformance 的只读候选，并不宣称应用行为
已经被验证；Agent 仍需消费其中绑定的 native observation Tool。未映射的 read operation 返回
`UNSUPPORTED`，R2/R3 operation 返回 `DEFERRED`；两者都不会成为可调用 Tool。

首个写入验证仅提供固定的 `app.base.stop` canary：

```bash
rolo target application-write-canary \
  --profile my-robot \
  --operation app.base.stop \
  --confirmation "I CONFIRM APP.BASE.STOP CANARY"
```

Rolo 会先用只读 graph Tool 证明 `/cmd_vel` 的类型和 subscriber，再通过 pinned SSH connector
发送一次固定 zero-Twist 请求。它不是通用写 Tool；`PASS` 只表示请求被目标 CLI 接受并完成路由复查，
不表示底盘已经停止或具备安全认证。

`app.map.create` 的第一版是独立的、无运动 `SESSION_START` 适配器：

```bash
rolo target application-map-create \
  --profile my-robot \
  --confirmation "I CONFIRM APP.MAP.CREATE"
```

Rolo 只接受证据中精确匹配的 SLAM launch entrypoint 和 `/scan` `LaserScan` 路由，启动
带 TTL 的 SLAM 进程并返回 PID；它不发布速度、不启动探索。探索前仍需另一个经过验证的
避障/急停 adapter。

实现位于 `src/rolo/stages/probe/application.py`，CLI 入口位于 `src/rolo/product_cli.py`，
测试位于 `tests/test_application_bundles.py`。

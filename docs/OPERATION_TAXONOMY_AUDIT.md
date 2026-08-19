# Operation 词汇重叠与歧义审计

## 目的

本审计区分三类情况：实现完全重复、名称相近但应保持不同语义、以及尚未明确边界的
`DRAFT` operation。近义 operation 不能仅因最终落到同一个 ROS topic、service 或厂商
SDK 函数就自动合并；产品语义、授权域、输入输出和后续诊断责任仍可能不同。

## 已确认的实现重复

### `linux.host.inspect` 与 `linux.host.inventory`

当前 `robotctl linux host inspect` 是 `host inventory` 的兼容别名，两者调用同一实现并返回
相同 operation payload。这是实际重复，而不是领域分层。

处理结果：迁移窗口完成后，`linux.host.inspect` 已从产品 Registry 和正式契约目录移除；
CLI 兼容入口继续转发到 `linux.host.inventory`，但不得重新进入 Tool Catalog。

### `ros.node.status` 与 `ros.node.inspect`

历史实现中两者都调用 node info。当前已按产品语义拆分：

建议优先保留两个产品语义但重构实现：

- `ros.node.status` 只回答节点是否可见、ROS 版本和观测时间，输出紧凑状态；
- `ros.node.inspect` 返回 publishers、subscribers、services 等接口详情；
- `ros.node.lifecycle` 继续只表示 ROS 2 managed lifecycle state。

`ros.node.status` 已升级为 `2.0.0`，只通过 node list 返回 `name`、`visible`、ROS 版本和
观测包装；接口详情继续属于 `ros.node.inspect`。

## 必须保持分离的近义 operation

### `app.teleop.velocity` 与 `app.base.velocity`

二者都可能绑定 `/cmd_vel`，但授权域不同。`teleop` 表示人工或受监督的瞬时控制意图；
`base` 表示应用程序对移动底盘的通用运动接口。Adapter 可以复用底层传输实现，但不得
因为 topic 相同而绕过各自的授权、watchdog、速率限制和资源锁。

### normal stop 与 safety stop

`app.teleop.stop`、`app.base.stop` 是普通运动命令；`app.safety.protective_stop` 和
`app.safety.emergency_stop` 属于安全控制域。普通 stop 不得别名或降级为安全 stop，安全
stop 也不能用普通速度零指令冒充。

### `hw.sensor.read` 与应用层 sample/snapshot

`hw.sensor.read` 表示设备或驱动层的有界原始数值读取；`app.imu.sample`、
`app.gnss.sample`、`app.lidar.snapshot` 和 `app.camera.snapshot` 表示经过应用层命名、frame、
时间和可能校准后的领域数据。二者可以共享证据，但不能共享契约摘要。

### `status` 与 `health`

`status` 表示生命周期、可用性或控制状态；`health` 表示故障、退化和诊断结论。输出中的
顶层 `status` 始终是 operation 调用状态，领域状态必须使用 `state`、`health`、
`lifecycle_state` 等独立字段，不能复用顶层 `status`。

### `plan` / `validate` 与 `execute` / `apply`

`navigation.plan`、`manipulation.plan`、`test.plan` 和 `regression.plan` 只返回计划观察或 artifact，
不得调度、启动或授权执行。`calibration.validate` 和 `parameter.validate` 只返回 findings，
不得隐式 apply/set。Adapter 可以复用厂商规划器或校验器，但发现其接口同时产生动作或持久
变更时，不能将该接口绑定到这些只读 operation。

## 尚待明确的 DRAFT 边界

当前已识别的跨 operation 命名与对象边界均已形成产品决策。后续 DRAFT 保留原因主要是
动作安全边界、补偿语义或目标资源身份尚未完成契约化，不授权 Adapter Agent 自行补写。

## 已完成的产品决策

1. `linux.host.inspect` 完成 DEPRECATED 迁移后退出产品 Registry；兼容 CLI 暂时保留。
2. `ros.node.status` 以 2.0 紧凑状态存在，`inspect` 负责接口详情。
3. `ros.topic.echo` 从产品 Registry 移除，只允许 Adapter 将底层 ROS CLI echo 用作实现绑定。
4. 流式读取采用有界采样与显式 session handle 的混合模型。
5. SENSITIVE operation 由 Rolo runtime 基于受保护 OS 身份策略默认拒绝并审计。
6. `app.state.snapshot` 只返回离散应用状态对象；`app.telemetry.snapshot` 返回带名称、单位、
   独立观测时间和 JSON 编码值的指标集合，两者不共享契约摘要。
7. `app.diagnosis.snapshot` 只返回有界观测证据，`app.diagnosis.result` 才返回诊断结论；
   evidence operation 只列 artifact 引用，不直接回传文件内容。
8. `app.test.*` 表示单项测试运行，`app.regression.*` 表示测试集合的聚合运行和结果。
9. `ros.diagnostics.hardware/software` 从产品词汇移除；`ros.diagnostics.snapshot` 2.0 使用
   `category=all|hardware|software` 形成同一证据集合的过滤视图。
10. R1/R2 write 由受保护身份和精确 operation 白名单放行；R3 只接受外部短期绑定能力。
11. 文件、配置和日志必须匹配受保护内容资源分类并返回 artifact 引用；无法排除 SECRET
    的资源保持不可用。
12. Linux host/process/service/container/schedule/time 写操作只承诺请求接受，不承诺状态闭环；
13. `episode` 是有界时间序列记录；inspect/export 只返回 manifest、事件元数据和 artifact
    引用，不解析或复制业务 artifact 内容。`checkpoint` 是不可变的 Rolo 控制面状态锚点；
    restore 只生成新的控制面 revision，不应用真实参数、不恢复进程、不恢复任务，也不触发
    机器人运动。
    ROS managed node activate/deactivate 采用相同语义并固定为 R2 write。
13. `linux.config.apply` 只消费 digest-pinned protected artifact，禁止可变路径；rollback token
    是不具授权能力的 opaque 状态引用，不能绕过 SENSITIVE、write 策略和审计。
14. Map create/import 只创建非激活记录，不启动建图、导航或运动；tuning candidate evaluate
    只计算既有证据，不 apply 候选或启动测试。
15. Task/test/regression/diagnosis 的通用 run/start 一律视为可能间接运动的 R3；每项必须具有
    target-bound 普通 cancel。`app.regression.cancel` 因此加入 Registry，普通 cancel 不等于安全停机。

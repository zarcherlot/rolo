<!-- status: observed; authority: evidence note; last_verified: 2026-09-02 -->

# LanderPi mapping motion safety gate

本次启动了只包含 `slam_toolbox` 的建图服务，并确认 `/scan` 与 `/map` 可用；在开始
探索运动前执行安全闸门检查，结果为 **BLOCKED**：

- `/cmd_vel` 存在底盘订阅者，但没有经过 Rolo 验证的避障输出/仲裁链路；
- `/enable` 的类型为 `std_srvs/srv/Empty`，不能被解释为急停证明；
- 目标源码中的 `/ros_robot_controller/enable_reception` 只控制按钮、摇杆、IMU、SBUS、电量等
  接收线程的发布开关，不能被解释为电机急停或速度仲裁；
- 目标虽安装 `nav2_collision_monitor`，但当前没有对应配置或运行节点；
- 因此没有发送任何非零速度，建图 session 已清理。

已补上第一版 `app.map.create` 适配器，但它的语义被严格限定为 **SESSION_START**：只启动
目标工作区已经存在的 `slam/launch/include/slam_base.launch.py`，固定读取 `/scan`，不发布
速度，也不启动探索。它通过 `rolo target application-map-create` 暴露，返回有界 TTL 和
目标进程 PID；这一步可以在没有运动安全链路时执行。

要从“启动建图会话”继续到探索运动，仍必须提供另一个目标绑定的安全 adapter：固定输入
测距 topic、输出速度 topic、停止行为、超时和故障时 zero-stop，并独立验证急停可达性。
人在环声明可以作为额外 gate，但不能替代上述运行态证据。

已落地 `rolo target safety-conformance --profile mentorpi`。它会在签名快照之外，对
`/scan`、`/cmd_vel`、候选安全输出和急停服务逐个做有界运行态复核，并独立输出五项门：
typed scan、typed command、distinct safe output、watchdog/zero-stop、independent
emergency-stop。当前 LanderPi 结果为 **FAIL**：前两项 PASS，后三项 FAIL；所以仍不允许
探索运动。

代码侧已补上 ROS/provider-independent 的确定性 `safety_guard` 核心：输入命令或测距数据
过期、时间戳异常、测距无效、前方障碍或急停时一律输出零速；正常输入只允许通过配置的线/角速度
上限。该核心本身不冒充目标机运行时证明。LanderPi 当前 `/controller/cmd_vel` 仍有多个直接
发布者，且没有已证明的安全输出与急停语义，因此必须先完成 single-writer 控制路径和独立急停
后端，再把该核心接入目标机并重新执行 Conformance。本阶段按用户要求暂不把急停纳入
仲裁器实现；遥控器只作为现场人工保护，不计入 Rolo 的独立急停证明。

目标侧的第一版实现位于 `scripts/rolo_ros_safety_arbiter.py`。它订阅现有命令汇聚 topic
和 `/scan`，以固定上限和双 watchdog 发布 `/controller/cmd_vel_safe`；缺命令、缺测距、
数据过期、测距无效或前方障碍时发布零速。部署它本身不会改变电机控制，必须再将唯一硬件
写入者 `odom_publisher` 重映射到 `/controller/cmd_vel_safe`，才能形成闭环。

## 速度链路分析（只读）

当前可收敛为下面的单写入者方案：

```text
现有六个命令发布者
        ↓  /controller/cmd_vel（候选输入）
安全仲裁器：/scan + ButtonState + watchdog + 限速
        ↓  /controller/cmd_vel_safe（唯一安全输出）
odom_publisher（唯一当前硬件写入者）
        ↓  ros_robot_controller/set_motor
```

源码证据表明 `odom_publisher` 是 `/controller/cmd_vel` 的当前唯一订阅者，并在回调中
计算底盘速度后发布 `ros_robot_controller/set_motor`。因此实施时应把它的输入重映射为
`/controller/cmd_vel_safe`，让安全仲裁器成为唯一通往该订阅者的输出；不能仅在原
`/controller/cmd_vel` 上再并列增加一个过滤发布者。

## 物理按钮急停边界

`/ros_robot_controller/button` 的 `ButtonState` 只报告 `id` 与 `state`；目标源码将按下、
短按释放、长按等编码成状态值，但没有现成的“急停”语义。安全仲裁器可以把一个明确配置的
物理按钮按下事件做成锁存急停，恢复必须通过独立的人工复位步骤；在确认具体按钮 `id` 和
复位方式前，Conformance 不能把该 topic 记为 independent emergency-stop。

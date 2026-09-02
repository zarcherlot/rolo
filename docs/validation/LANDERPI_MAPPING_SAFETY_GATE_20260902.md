<!-- status: observed; authority: evidence note; last_verified: 2026-09-02 -->

# LanderPi mapping motion safety gate

本次启动了只包含 `slam_toolbox` 的建图服务，并确认 `/scan` 与 `/map` 可用；在开始
探索运动前执行安全闸门检查，结果为 **BLOCKED**：

- `/cmd_vel` 存在底盘订阅者，但没有经过 Rolo 验证的避障输出/仲裁链路；
- `/enable` 的类型为 `std_srvs/srv/Empty`，不能被解释为急停证明；
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
后端，再把该核心接入目标机并重新执行 Conformance。

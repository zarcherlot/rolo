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
安全仲裁器：/scan + watchdog + 限速
        ↓  /controller/cmd_vel_safe（唯一安全输出）
odom_publisher（唯一当前硬件写入者）
        ↓  ros_robot_controller/set_motor
```

源码证据表明 `odom_publisher` 是 `/controller/cmd_vel` 的当前唯一订阅者，并在回调中
计算底盘速度后发布 `ros_robot_controller/set_motor`。因此实施时应把它的输入重映射为
`/controller/cmd_vel_safe`，让安全仲裁器成为唯一通往该订阅者的输出；不能仅在原
`/controller/cmd_vel` 上再并列增加一个过滤发布者。

本轮已在 LanderPi 临时完成该 remap：`/controller/cmd_vel_safe` 当前有 1 个订阅者，
原 `/controller/cmd_vel` 仅剩仲裁器订阅者。目标上的 `/scan` 目前只有发布端点而没有
可收到的样本，仲裁器因此按 fail-closed 规则持续输出零速；这证明了安全默认值，但还
不能把 watchdog 的“有效命令→超时归零”记为 PASS。正式部署仍需把仲裁器纳入目标启动
管理，并先恢复可验证的测距数据流。

随后确认原始 `/scan_raw` 有稳定约 10 Hz 的 `LaserScan` 样本，而现有过滤节点没有产出
`/scan`。因此当前仲裁器实例显式使用 `/scan_raw`（脚本参数可配置），避免把“有 topic
端点”误当作“有测距数据”。在遥控器保护下做了极小角速度 canary：输入 `angular.z=0.01`
连续 3 次，safe 输出为 `0.01`；停止输入后约 0.25 s 内 safe 输出归零并保持。该结果证明
了目标侧 watchdog 的实际行为，但正式 Conformance 仍需把这次有界测试写入独立 artifact，
且不能替代后续启动管理与传感器过滤修复。

## 2026-09-03 `app.map.create` 复验

用户明确确认 `I CONFIRM APP.MAP.CREATE` 后，Rolo 先刷新 mentorpi 的只读
TargetEvidence，再按候选绑定的真实 `/scan_raw` 路由启动目标工作区的
`slam/launch/include/slam_base.launch.py`。本次没有发布任何速度指令。

期间发现目标机原有 `robot_state_publisher` 进程虽存活，却没有有效发布底盘模型
TF；因此 SLAM 曾以 `frame 'lidar_frame'` 丢弃 LaserScan。Rolo 在目标机生成并加载
当前 `MACHINE_TYPE=LanderPi_Mecanum`、`LIDAR_TYPE=LD19` 对应的真实 URDF 后，
确认 `base_footprint -> lidar_frame`，并恢复现有 EKF 的 `odom -> base_footprint`
动态 TF。随后重新启动单个有界 SLAM 会话，复查结果：

- `/scan_raw`：约 10 Hz `sensor_msgs/msg/LaserScan`；
- `/map`：`nav_msgs/msg/OccupancyGrid` publisher 可见，约 10 Hz；
- map 初始栅格约 `67 x 62`、分辨率 `0.05 m`；
- `app.map.create` dispatch/report：`PASS`，含候选、目标证据摘要、session PID 和 report artifact；
- 该 PASS 只代表 SLAM 会话已被目标接受并持续发布地图，不代表已完成环境覆盖、地图质量或物理安全验收。

## 2026-09-03 L1 微探索复验

在上述 SLAM 会话和安全输出预检均通过后，执行了用户确认的固定 L1 计划：
前进 1 秒（计划上限 `0.05 m/s`）、归零 `0.5` 秒、原地旋转 `1.5` 秒、再归零
`0.5` 秒。执行器 PID 为 `1749234`，结束后进程已退出；对
`/controller/cmd_vel_safe` 的复查样本为全零。`/odom` 的短时读数显示约 `0.03 m`
的位移，说明这次是实际硬件闭环而非仅接受命令；地图话题仍保持发布。

该结果只证明一次有界 canary 的执行、归零和目标安全输出连通，不代表自主探索器已
具备完整避障、覆盖规划、恢复或长期运行能力。

## 物理按钮急停边界

`/ros_robot_controller/button` 的 `ButtonState` 只报告 `id` 与 `state`；目标源码将按下、
短按释放、长按等编码成状态值，但没有现成的“急停”语义。安全仲裁器可以把一个明确配置的
物理按钮按下事件做成锁存急停，恢复必须通过独立的人工复位步骤；在确认具体按钮 `id` 和
复位方式前，Conformance 不能把该 topic 记为 independent emergency-stop。

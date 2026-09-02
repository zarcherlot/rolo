<!-- status: observed; authority: evidence note; last_verified: 2026-09-02 -->

# LanderPi navigation route discovery

这是一份目标机观察记录，不是把 ROS 作为 Rolo v2 的固定平台标准。它记录了
`mentorpi` profile 在当前 OS/Middleware 环境上发现到的导航候选路由。

## 发现结果

- `/home/ubuntu/ros2_ws/src/navigation/launch/navigation.launch.py` 存在，并使用
  `map_01.yaml`、`nav2_params.yaml`，机器类型为 `LanderPi_Mecanum`。
- 受控 bring-up 使用 `sim:=false`、`use_teb:=false` 后，Nav2 lifecycle 节点进入
  `active`：`amcl`、`map_server`、`controller_server`、`planner_server`、
  `bt_navigator`、`waypoint_follower`、`velocity_smoother` 等。
- `ros2 action info /navigate_to_pose` 观察到类型为
  `nav2_msgs/action/NavigateToPose`，server 为 `/bt_navigator`。
- `/scan` 能读到 `sensor_msgs/msg/LaserScan` 样本；bring-up 日志仍有 LD19 timeout，
  因此这是“路由可用 + 传感器证据不稳定”，不是运动安全或导航成功证明。
- 验证结束后已终止临时导航 launch，并恢复 `start_app_node.service`；没有发送任何导航 goal。

## 为什么之前没有发现导航指令

之前的 discovery 只观察了当时正在运行的基础 bring-up。该 launch 没有启动 Nav2，
所以 graph 中没有 `/navigate_to_pose`、`/compute_path_to_pose` 等 action；而导航入口
藏在 workspace 源码和 `navigation.sh` 中，且还依赖 `.robotrc` 的环境变量。只扫描当前
graph 会得到正确但不完整的 `NOT_FOUND`。本次补充了三层发现：文件系统入口、启动依赖、
受控 bring-up 后的真实 action graph。

## 候选映射

### 1. 启动导航栈（bring-up，不发送 goal）

在目标容器内以 `ubuntu` 用户执行，`.zshrc` 会加载 ROS 和 workspace 环境：

```bash
docker exec -u ubuntu MentorPi zsh -lc \
  'source /home/ubuntu/ros2_ws/.zshrc; \
   ros2 launch navigation navigation.launch.py \
     map:=map_01 sim:=false use_teb:=false'
```

产品脚本还会停止 `start_app_node.service`，因为该 launch 会再次拉起底盘和传感器。
Rolo 的 Tool 不应无条件执行 systemd stop；应把服务冲突、传感器健康和人工确认作为
独立 gate。

### 2. 导航目标（仅作为后续写入 Tool 的路由候选）

```bash
ros2 action send_goal /navigate_to_pose \
  nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}}"
```

这条命令会产生真实运动，当前仅用于说明 `app.navigation.start` 的可能 route
binding，禁止由 discovery/conformance 自动执行。真正发布前还必须有新鲜 TF、定位、
地图、测距、静止状态、速度上限、取消/停车和人在环授权。

### 无运动写入 conformance（已在真机执行）

在受控 Nav2-only bring-up 后，Rolo 发布当前位置（`map: (0, 0)`）作为目标，目标被
`/bt_navigator` 接受后立即调用 action cancel：

```text
server=true
accepted=true
cancel_requested=true
cancel_response=1
result_status=5 (CANCELED)
```

取消后 3 秒 `/odom` 观察窗口：`max_linear=0.0 m/s`、`max_angular=8.1e-05 rad/s`，
位置从 `(0.0, 0.0)` 到 `(0.0, 0.0)`。这证明了 action 接受/取消/无运动停车路径，
不证明导航到目标的行为正确性。

当前配置文件仍声明 velocity smoother 的上限为 `0.26 m/s`、`3.0 rad/s`；其中角速度
上限与底盘 launch 的 `0.45 rad/s` 约束不一致。因此速度边界只能被发现，尚未被允许
自动放行，必须先由 Rolo Tool 在运行时读取并校验最终生效参数。

## Rolo v2 结论

当前可以发布的最小结果是：

```text
Candidate: app.navigation.start
route: /navigate_to_pose
type: nav2_msgs/action/NavigateToPose
state: ROUTE_OBSERVED_BUT_WRITE_NOT_CONFORMED
```

`/navigate_to_pose` 的出现只完成了 TargetEvidence 和 route binding；它还没有通过
写入行为正确性或物理安全 conformance。`app.navigation.status`、`pose`、`quality`
等只读 operation 仍应优先使用 Rolo 已验证的 graph/TF/topic inspect Tools。

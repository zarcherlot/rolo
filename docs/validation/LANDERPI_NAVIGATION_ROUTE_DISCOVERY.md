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

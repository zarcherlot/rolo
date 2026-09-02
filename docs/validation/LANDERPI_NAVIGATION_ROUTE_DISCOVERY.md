<!-- status: observed; authority: evidence note; last_verified: 2026-09-02 -->

# LanderPi navigation route discovery

这是一份目标机观察记录，不是把 ROS 作为 Rolo v2 的固定平台标准。它记录了
`mentorpi` profile 在当前 OS/Middleware 环境上发现到的导航候选路由。

## 发现结果

- `/home/ubuntu/ros2_ws/src/navigation/launch/navigation.launch.py` 存在，默认参数名为
  `map_01`，并使用 `nav2_params.yaml`，机器类型为 `LanderPi_Mecanum`。这只是 launch
  默认值，不是当前环境正在使用的地图证明。
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

## 地图身份纠正

目标机同时存在多个地图候选：`install/slam/share/slam/maps/map_01.yaml`、
`install/slam/share/slam/maps/map_02.yaml`，以及源码目录下的 `src/slam/maps/map_01.yaml`。
其中 install 与 source 的 `map_01.yaml` 内容 hash 不同。baseline 运行态没有 `map_server`
或 `/map` publisher，因此不能从静态文件或 launch 默认参数推断当前地图。后续定位启动
必须先从实际 `map_server` 参数或启动命令取得 active map 路径，并将 YAML/PGM hash 写入
TargetEvidence；若没有 active map 证据，D03 保持 `BLOCKED`，禁止加载任意候选地图。

## Probe 的自举边界

Probe 不要求用户预先提供 robot workspace。Target enrollment 成功后，Rolo 可以在目标机
执行有界的全盘 inventory：先只读取文件名、权限、大小、时间和可执行文件元数据，再对
命中的 launch/package/config/服务文件做定向读取。扫描必须有目录、文件数、字节数、耗时、
敏感路径和输出 digest 限制；它发现的是候选入口，不把静态文件当成运行时事实。随后由
Agent 选择最小 Probe，Rolo 负责受控 bring-up 和新鲜 Runtime Evidence。

这样用户只需完成 enrollment，并可声明“设备处于安全位置”；不再需要手工寻找 workspace
或编写 shell。安全位置声明降低交互负担，但不替代 Rolo 的速度、超时、取消和停车证据。

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

这条命令会产生真实运动，当前仅用于说明全局导航 `app.navigation.start` 的可能 route
binding，禁止由 discovery/conformance 自动执行。真正发布前还必须有新鲜 TF、定位、
地图、测距、静止状态、速度上限、取消/停车和人在环授权。

如果没有 `map → base_footprint`，Probe 不应直接判定“导航不可用”，而应先尝试目标机
实际暴露的相对运动接口，例如 `/drive_on_heading` 或 `/spin`。它们不依赖全局地图，
适合先验证底盘控制、取消和停车；只有发现地图与重定位入口后，才把候选升级为
`/navigate_to_pose` 全局导航。

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

## 统一的写入 canary 分级

所有 OS/Middleware provider 统一使用同一套分级，不把 ROS CLI 细节暴露给 Agent：

1. **Level 1 — zero-stop**：重复发布零速度并观察实际速度，自动执行，验证写入、路由和停车。
2. **Level 2 — bounded motion**：统一为小角度旋转或极短距离/航向动作；由 adapter 映射到
   `/spin`、`/drive_on_heading` 或等价接口，固定角度、速度、时限、cancel 和 zero-stop。
3. **Level 3 — task motion**：真实目标导航，必须具备地图/定位/测距/速度边界等完整 evidence，
   不由 discovery 自动执行。

用户的安全位置声明可使 Level 1/2 尽量 hands-off，但每一级仍必须由 Rolo 采集可审计的
   执行结果，而不是只记录“命令返回成功”。

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

后续 L1/L2 真机 conformance 的完整结果见
[`landerpi-l1-l2-20260902.json`](evidence/landerpi-l1-l2-20260902.json)。L1 zero-stop
和 L2 bounded rotation 均已通过；这两个结果仍不等同于全局导航任务成功。

<!-- status: observed; authority: evidence note; last_verified: 2026-09-02 -->

# LanderPi application observation Tool conformance

基于新鲜 TargetEvidence（`collected_at=2026-09-02T12:16:59.953567Z`，
`payload_sha256=6f13c00281a6d3896e4232e045844ab2be9bfd3cccbfdec02db0346359388eac`），
Rolo 在不执行写入的前提下完成了两个 application operation 的 Candidate、最小 Adapter
和独立 route-binding Conformance。

| Operation | Candidate | Adapter observation | Conformance | 目标路由 |
|---|---|---|---|---|
| `app.localization.pose` | `CANDIDATE` | `native.middleware.observe.sample` | `PASS` | `/odom` (`nav_msgs/msg/Odometry`) |
| `app.navigation.status` | `CANDIDATE` | `native.middleware.graph.inspect.topic_describe` | `PASS` | `/cmd_vel`、`/odom` |

产物位于本机 artifact store：

- `application/mentorpi/operations/app_localization_pose/app-operation-bundle-ddd423e99aac63763028c258/`
- `application/mentorpi/operations/app_navigation_status/app-operation-bundle-2b35a28c9dd3778b76325b07/`

这里的 `PASS` 只表示 Adapter 对新鲜运行态 route 的绑定和只读观察契约通过。`/odom`
是相对里程计 pose，不等同于全局 `map` pose；`app.navigation.status` 也不等同于
导航 action 已启动。全局导航仍受 `LP-D03` 的定位前置条件阻断。

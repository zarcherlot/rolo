<!-- status: active; authority: reference; owner: rolo maintainers; last_reviewed: 2026-09-02 -->

# v1 application operation inventory → v2 verification backlog

The v1 application contract set is the semantic source for Rolo's application work. It contains
137 operations: 77 read operations (65 R0 and 12 bounded R1 observations) and 60 write operations
(23 R2 and 35 R3). The list is a backlog and vocabulary source, not a v2 runtime registry.

## v2 disposition

1. **Read R0**: first priority. Agent may request discovery; Rolo designs a bounded Probe, binds
   exact target evidence, emits a minimal Adapter bundle, and runs independent Conformance.
2. **Read R1**: second priority after R0 route semantics are stable; sampling/watch/export remains
   explicitly bounded by time, item, byte, and sensitivity budgets.
3. **Write R2/R3**: not exposed by the current Probe Tool Surface. They require a later execution
   stage with explicit authorization, quiescence/interlock, cancellation, and physical review.
4. A v1 operation is not `VERIFIED` merely because its name exists. It must have a target-observed
   route, a precise input/output contract, and an independent Conformance report.

The four application families (`startup`, `navigation`, `mapping`, `manipulation`) are discovery
worksets. The operation ID is the reusable Agent-facing semantic identity.

## Complete v1 list by domain

`read` and `write` below are the access values in the v1 contract source.

| domain | read operations | write operations |
|---|---|---|
| base | `app.base.status` | `app.base.velocity`, `app.base.move_distance`, `app.base.rotate`, `app.base.stop`, `app.base.recover` |
| calibration | `app.calibration.list`, `app.calibration.inspect`, `app.calibration.status`, `app.calibration.validate` | `app.calibration.run`, `app.calibration.apply`, `app.calibration.rollback` |
| camera | `app.camera.snapshot`, `app.camera.list`, `app.camera.status`, `app.camera.inspect`, `app.camera.calibration.status` | `app.camera.stream.start`, `app.camera.stream.stop` |
| diagnosis | `app.diagnosis.status`, `app.diagnosis.snapshot`, `app.diagnosis.result`, `app.diagnosis.evidence` | `app.diagnosis.run`, `app.diagnosis.cancel` |
| event | `app.event.list`, `app.event.inspect` | — |
| gnss | `app.gnss.list`, `app.gnss.status`, `app.gnss.inspect`, `app.gnss.sample` | — |
| gripper | `app.gripper.status` | `app.gripper.open`, `app.gripper.close`, `app.gripper.set`, `app.gripper.stop` |
| imu | `app.imu.list`, `app.imu.status`, `app.imu.inspect`, `app.imu.calibration.status`, `app.imu.sample` | — |
| lidar | `app.lidar.list`, `app.lidar.status`, `app.lidar.inspect`, `app.lidar.calibration.status`, `app.lidar.snapshot` | — |
| localization | `app.localization.status`, `app.localization.pose`, `app.localization.quality` | `app.localization.initialize`, `app.localization.reset`, `app.localization.relocalize` |
| manipulation | `app.manipulation.status`, `app.manipulation.plan` | `app.manipulation.execute`, `app.manipulation.cancel`, `app.manipulation.stop`, `app.manipulation.home` |
| map | `app.map.inspect`, `app.map.list`, `app.map.export` | `app.map.create`, `app.map.save`, `app.map.load`, `app.map.clear`, `app.map.import` |
| navigation | `app.navigation.status`, `app.navigation.costmap.inspect`, `app.navigation.path.inspect`, `app.navigation.plan` | `app.navigation.start`, `app.navigation.pause`, `app.navigation.resume`, `app.navigation.cancel`, `app.navigation.stop`, `app.navigation.recover` |
| odometry | `app.odometry.status`, `app.odometry.sample` | `app.odometry.reset` |
| parameter | `app.parameter.list`, `app.parameter.inspect`, `app.parameter.get`, `app.parameter.validate` | `app.parameter.set`, `app.parameter.rollback` |
| regression | `app.regression.status`, `app.regression.result`, `app.regression.plan` | `app.regression.run`, `app.regression.cancel` |
| robot | `app.robot.discover`, `app.robot.status`, `app.robot.health` | `app.robot.start`, `app.robot.stop`, `app.robot.restart` |
| safety | `app.safety.status`, `app.safety.limits.inspect`, `app.safety.zones.inspect`, `app.safety.interlocks.inspect`, `app.safety.approval.status` | `app.safety.emergency_stop`, `app.safety.protective_stop`, `app.safety.stop.clear` |
| state | `app.state.watch`, `app.state.snapshot` | — |
| task | `app.task.list`, `app.task.describe`, `app.task.status`, `app.task.result` | `app.task.start`, `app.task.cancel`, `app.task.pause`, `app.task.resume`, `app.task.stop` |
| telemetry | `app.telemetry.watch`, `app.telemetry.snapshot`, `app.telemetry.export` | — |
| teleop | — | `app.teleop.velocity`, `app.teleop.pose`, `app.teleop.joint`, `app.teleop.stop` |
| test | `app.test.list`, `app.test.describe`, `app.test.status`, `app.test.result`, `app.test.evidence`, `app.test.plan` | `app.test.run`, `app.test.cancel` |
| tuning | `app.tuning.status`, `app.tuning.candidate.evaluate` | `app.tuning.baseline.create`, `app.tuning.candidate.create`, `app.tuning.commit`, `app.tuning.rollback` |

## First LanderPi slice

The first operation slice is intentionally small and route-observation only:

| operation | Probe signal | expected LanderPi route evidence |
|---|---|---|
| `app.robot.discover` | runtime started | non-parameter Middleware route or bounded entrypoint evidence |
| `app.robot.status` | runtime started | lifecycle/status route; absence is a real gap |
| `app.base.status` | motion command | `cmd_vel`-shaped route and its interface digest |
| `app.localization.status` | localization | `odom`/odometry route and frame metadata |
| `app.odometry.status` | localization | odometry route |
| `app.lidar.status` | range | scan/laser route |
| `app.lidar.snapshot` | range | bounded sensor observation route (no stream start) |
| `app.navigation.status` | motion + localization | at least two independent signals |
| `app.map.inspect` | map state | map/occupancy/SLAM route; current target may reject it honestly |
| `app.navigation.costmap.inspect` | costmap | costmap route; no map route is inferred |
| `app.navigation.path.inspect` | path | path route; no plan is executed |
| `app.manipulation.status` | arm/joint state | arm control or joint-state route |
| `app.gripper.status` | gripper/joint state | gripper control or joint-state route |

For each row the Agent can request one operation. Rolo records the request, target evidence digest,
matched/missing signals, candidate digest, minimal route bindings, and an independent Conformance
verdict. A passing *binding* bundle also names an existing public native observation Tool
(`graph.inspect` or `observe.sample`) with typed route arguments; Rolo never emits a new arbitrary
executable. In this first slice, Conformance is explicitly route-binding conformance: the Agent may
then consume the bound observation Tool and interpret its result. A later operation-result
Conformance must be added before claiming normalized application behavior. A `NOT_FOUND` result
creates a documented gap and never becomes a callable Tool.

The historical source is `src/rolo/operation_contracts/app.yaml` at the pre-v2 registry commit;
the v2 implementation deliberately keeps that source out of the runtime package and evolves this
backlog one verified operation at a time.

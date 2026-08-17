# rolo automatic discovery

The discovery subsystem inventories a robot without exposing an unrestricted shell. It uses fixed,
bounded read-only probes for hardware, Linux and the live ROS graph, plus a non-executing source
scanner for application workspaces.

On ARM64 targets it normalizes device-tree models into `nvidia_jetson_orin`, `rockchip_rk3588`, or
`raspberry_pi`. Unknown boards remain `unknown` until their platform manifest and adapter have been
added; discovery never guesses a vendor driver from CPU architecture alone.

## Run

```bash
robotctl discover run --robot my_robot_01 --source-root /opt/robot-application
robotctl discover show --robot my_robot_01
robotctl tool catalog --robot my_robot_01
robotctl tool schema hw.inventory.scan --robot my_robot_01
```

The four initial canonical commands are also directly callable:

```bash
robotctl hw inventory scan
robotctl linux host inspect
robotctl ros graph snapshot
robotctl app robot discover --source-root /opt/robot-application
```

## Artifacts

A successful or partial run writes:

```text
artifacts/discovery/<robot_id>/latest/
├── report.json
├── capability_manifest.json
├── hw.json
├── linux.json
├── ros.json
├── application.json
└── tool_catalog.json
```

The source scanner recognizes `pyproject.toml`, setuptools, CMake, Cargo, ROS `package.xml`, launch
files, configuration files, Python console scripts and statically visible ROS publisher,
subscription, service and action names. It records manifest hashes and the Git revision when
available. It never executes README snippets or newly discovered binaries.

Semantic bindings inferred from source or a live ROS graph are emitted as
`DISCOVERED_UNVERIFIED`. Corresponding write tools remain unavailable until an adapter has been
built and passed schema, dry-run, idempotency, cancellation, safety and physical-result conformance
tests. This prevents documentation or naming heuristics from becoming an actuator command.

## Robot startup

The ARM64 release dynamically enrolls one robot identity and installs three ordered services:
`rolo-bootstrap-agentd.service`, `rolo-discovery.service`, and
`rolo-agentd.service`. The bootstrap daemon exposes only non-motion identity, safety-profile,
and clock status. Discovery requires that daemon, scans the enrolled profile and
`${ROBOT_DISCOVERY_SOURCE_ROOT}`, and persists its report. The full agentd requires a non-`FAILED`
discovery result; a `PARTIAL` result starts it in `DEGRADED`. If discovery fails, systemd keeps the
bootstrap daemon available and does not start the full agentd. The default source root is
`/opt/robot-application` and can be changed in
`/etc/rolo/rolo.env`.

# Robot Loop automatic discovery

The discovery subsystem inventories a robot without exposing an unrestricted shell. It uses fixed,
bounded read-only probes for hardware, Linux and the live ROS graph, plus a non-executing source
scanner for application workspaces.

On ARM64 targets it normalizes device-tree models into `nvidia_jetson_orin`, `rockchip_rk3588`, or
`raspberry_pi`. Unknown boards remain `unknown` until their platform manifest and adapter have been
added; discovery never guesses a vendor driver from CPU architecture alone.

## Run

```bash
robotctl discover run --robot robot_a --source-root /opt/robot-application
robotctl discover show --robot robot_a
robotctl tool catalog --robot robot_a
robotctl tool schema hw.inventory.scan --robot robot_a
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

The ARM64 release installs `robot-loop-discovery.service`. On boot it scans the selected robot
profile and `${ROBOT_DISCOVERY_SOURCE_ROOT}` before `robot-loop-agentd` starts. The default source
root is `/opt/robot-application` and can be changed in `/etc/robot-loop/robot-loop.env`.

# rolo automatic discovery

The discovery subsystem inventories a robot without exposing an unrestricted shell. It uses fixed,
bounded read-only probes for hardware, Linux and the live ROS graph, plus a non-executing source
scanner for application workspaces.

On ARM64 targets it normalizes device-tree models into `nvidia_jetson_orin`, `rockchip_rk3588`, or
`raspberry_pi`. Unknown boards remain `unknown` until their platform manifest and adapter have been
added; discovery never guesses a vendor driver from CPU architecture alone.

## Run

```bash
uv run robotctl discover run --robot "$ROBOT_ID" \
  --urdf /path/to/your_robot.urdf \
  --source-root /path/to/robot-application
uv run robotctl discover show --robot "$ROBOT_ID"
uv run robotctl tool catalog --robot "$ROBOT_ID"
uv run robotctl tool schema hw.inventory.scan --robot "$ROBOT_ID"
```

The four initial canonical commands are also directly callable:

```bash
uv run robotctl hw inventory scan
uv run robotctl linux host inspect
uv run robotctl ros graph snapshot
uv run robotctl app robot discover --source-root /path/to/robot-application
```

## Artifacts

A successful or partial run writes:

```text
artifacts/discovery/<robot_id>/latest/
├── report.json
├── capability_manifest.json
├── discovered_capability.json
├── semantic_context.json
├── hw.json
├── linux.json
├── ros.json
├── application.json
└── tool_catalog.json
```

The source scanner recognizes `pyproject.toml`, setuptools, CMake, Cargo, ROS `package.xml`, launch
files, configuration files, Python console scripts and statically visible ROS publisher,
subscription, service and action names. It records manifest hashes and the Git revision when
available. It never executes README snippets, launch files, configurations, or newly discovered
binaries. Common maximum linear/angular velocity keys in launch and config files are captured as
source-attributed semantic candidates.

Semantic bindings inferred from source or a live ROS graph are emitted as
`DISCOVERED_UNVERIFIED`. Corresponding write tools remain unavailable until an adapter has been
built and passed schema, dry-run, idempotency, cancellation, safety and physical-result conformance
tests. This prevents documentation or naming heuristics from becoming an actuator command.
Likewise, velocity candidates remain `DISCOVERED_UNVERIFIED` with `safety_authority: none`. The
same semantic context is written into Build, Debug, and Test agent inputs; only controlled physical
validation and explicit approval may promote a candidate to a hard motion limit.

Before starting probes, discovery loads the URDF path explicitly supplied through `--urdf`, records
its resolved path and SHA-256, and performs full structural and semantic parsing. Invalid declared
data stops discovery. Successful parsing writes `discovered_capability.json`; it never changes
`motion_safety_status` from `UNAPPROVED` by itself.

## Robot startup

rolo does not install background services. From the Git checkout, start each long-running process
with uv in its own terminal when needed:

```bash
uv run robotctl bootstrap-agentd --robot "$ROBOT_ID"
uv run robotctl agentd --robot "$ROBOT_ID"
uv run robotctl serve
```

Run discovery before the full agent daemon. The bootstrap daemon exposes only non-motion identity,
identity registration, URDF discovery state, unapproved motion state, and clock status. A `PARTIAL` discovery result makes the full agent daemon report
`DEGRADED`; a failed result blocks full readiness while leaving the explicitly started bootstrap
daemon available.

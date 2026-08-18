# rolo automatic discovery

The discovery subsystem inventories a robot without exposing an unrestricted shell. It uses fixed,
bounded read-only probes for hardware, Linux and the live ROS graph, plus a non-executing source
scanner for application workspaces.

Application discovery resolves only Python and ROS direct dependencies declared by source and launch
evidence. It does not scan the host package database or install target dependencies. See
[`SOFTWARE_DISCOVERY.md`](SOFTWARE_DISCOVERY.md) for the normative limits and report contract.

On ARM64 targets it normalizes device-tree models into `nvidia_jetson_orin`, `rockchip_rk3588`, or
`raspberry_pi`. Unknown boards remain `unknown` until their platform manifest and adapter have been
added; discovery never guesses a vendor driver from CPU architecture alone.

## Run

```bash
uv run robotctl adapt discover run --robot "$ROBOT_ID" \
  --urdf /path/to/your_robot.urdf \
  --source-root /path/to/robot-application
uv run robotctl adapt discover review --robot "$ROBOT_ID"
uv run robotctl adapt discover show --robot "$ROBOT_ID"
uv run robotctl tool catalog --robot "$ROBOT_ID"
uv run robotctl tool schema hw.inventory.scan --robot "$ROBOT_ID"
```

The canonical bootstrap introspection commands are directly callable before Adapt completes:

```bash
uv run robotctl hw inventory scan
uv run robotctl linux host inventory
uv run robotctl linux service list
uv run robotctl linux service inspect NAME
uv run robotctl linux container list
uv run robotctl linux container inspect NAME
uv run robotctl linux schedule list
uv run robotctl linux schedule inspect NAME
uv run robotctl linux process list
uv run robotctl linux process inspect PID
uv run robotctl linux binary describe /path/to/executable
uv run robotctl linux cli probe /path/to/executable --arg=--help
uv run robotctl linux config locate --process PID
uv run robotctl linux network listeners
uv run robotctl middleware inspect
uv run robotctl ros graph snapshot
uv run robotctl ros node status /node_name
uv run robotctl app robot discover --source-root /path/to/robot-application
```

These R0 operations use bounded argv-only probes, structured JSON evidence, and secret redaction.
They remain available before an Adapt handoff; Adapt records them in the tool catalog and may replace
their platform adapters only after conformance.

## Artifacts

A successful or partial run writes:

```text
artifacts/discovery/<robot_id>/
├── latest.json                 # discovery ID plus report and manifest hashes
└── runs/<discovery_id>/
    ├── report.json
    ├── active_discovery_report.json
    ├── active_discovery_report.md
    ├── robot_wiki.md              # editable robot Wiki; excluded from manifest hashes
    ├── manifest.json
    ├── capability_manifest.json
    ├── discovered_capability.json
    ├── semantic_context.json
    ├── direct_dependencies.json
    ├── software_summary.json
    ├── hw.json
    ├── linux.json
    ├── ros.json
    ├── application.json
    └── tool_catalog.json
```

`robot_wiki.md` is the human-maintained system view. The chief engineer may edit it directly;
`manifest.json` covers machine evidence only, so Wiki corrections do not invalidate discovery.

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
same semantic context is written into Adapt, Diagnose, and Verify agent inputs; only controlled physical
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

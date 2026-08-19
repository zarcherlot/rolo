# rolo automatic discovery

The discovery subsystem inventories a robot without exposing an unrestricted shell. Application
claims are led by build/deployed artifacts, documentation/launch files, and bounded read-only
probes. The source scanner is non-executing and supporting-only; it fills bounded gaps but cannot
override primary evidence.

Application discovery resolves only Python and ROS direct dependencies declared by source and launch
evidence. It does not scan the host package database or install target dependencies. See
[`SOFTWARE_DISCOVERY.md`](SOFTWARE_DISCOVERY.md) for the normative limits and report contract.

On ARM64 targets it normalizes device-tree models into `nvidia_jetson_orin`, `rockchip_rk3588`, or
`raspberry_pi`. Unknown boards remain `unknown` until their platform manifest and adapter have been
added; discovery never guesses a vendor driver from CPU architecture alone.

Declared robot structure, geometry, drive model, and sensors come from the explicitly supplied
URDF. Observed architecture, compute platform, devices, buses, and thermal zones come from the
running host through device tree, `/sys`, `/dev`, and bounded read-only commands. BSP files are not
required. Non-Linux hosts or unavailable hardware-enumeration facilities produce `PARTIAL` evidence
instead of rejecting otherwise usable hardware.

URDF hardware declarations and observed components are reconciled by component name. Read-only
hardware observations take precedence over conflicting URDF fields, and the Wiki records the
declared value, observed value, and adopted value. A component that is present only in the URDF is
shown normally. The generic probe currently enumerates video/input/IIO devices, serial and I2C
interfaces, USB/PCI/network buses, the compute board, and thermal zones. Motor-controller,
encoder, firmware, lidar/IMU model, and vendor board-driver details require a hardware-specific
read-only adapter to publish standardized `components` evidence.

## Run

```bash
uv run robotctl adapt discover run --robot "$ROBOT_ID" \
  --urdf /path/to/your_robot.urdf \
  --build-root /path/to/robot-application/build \
  --doc-root /path/to/robot-application/docs \
  --source-root /path/to/robot-application
uv run robotctl adapt discover review --robot "$ROBOT_ID"
uv run robotctl adapt discover show --robot "$ROBOT_ID"
uv run robotctl tool registry
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
They remain directly available before an Adapt handoff. `tool registry` is the product definition;
`tool catalog` and `tool schema` read only the latest independently gated robot release.

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
    ├── wiki_generation.json       # model-polish or deterministic-fallback provenance
    ├── manifest.json
    ├── capability_manifest.json
    ├── discovered_capability.json
    ├── semantic_context.json
    ├── direct_dependencies.json
    ├── software_summary.json
    ├── hw.json
    ├── linux.json
    ├── ros.json
    └── application.json
```

`robot_wiki.md` is the editable system view passed to downstream work. Adapt requires that it can be
loaded, while `manifest.json` covers machine evidence only so Wiki edits do not invalidate discovery.
Untrusted operation candidates are stored once in `report.json` rather than copied to a second file.

The source scanner recognizes `pyproject.toml`, setuptools, CMake, Cargo, ROS `package.xml`, launch
files, configuration files, Python console scripts and statically visible ROS publisher,
subscription, service and action names. It records manifest hashes and the Git revision when
available. It never executes README snippets, launch files, configurations, or newly discovered
binaries. Common maximum linear/angular velocity keys in launch and config files are captured as
source-attributed semantic candidates.

Python launch files use AST parsing and XML launch files use structured XML parsing. Commented
Python nodes are ignored; node-specific packages, executables, names, conditions, remappings and
URDF references are written to the machine report and editable Wiki as `STATIC_UNVERIFIED`.
Dynamic substitutions that cannot be resolved without execution remain unknown.

Semantic bindings inferred from source or a live ROS graph are emitted as operation candidates with
`DISCOVERED_UNVERIFIED` status. They do not constitute a Tool Catalog. The trusted Adapt gate
matches them only to product-defined operations and builds the Active Tool Catalog after bundle and
conformance checks. This prevents documentation or naming heuristics from becoming an operation
definition or actuator command.
Likewise, velocity candidates remain `DISCOVERED_UNVERIFIED` with `safety_authority: none`. The
same semantic context is written into Adapt, Diagnose, and Verify agent inputs; only controlled physical
validation and explicit approval may promote a candidate to a hard motion limit.

When supplied, discovery loads the URDF path from `--urdf`, records its resolved path and SHA-256,
and performs full structural and semantic parsing. Invalid declared data stops discovery. When it
is omitted, discovery records `NOT_PROVIDED`, continues with registered/default hardware context and
host probes, and leaves missing semantics unresolved. Successful parsing writes
`discovered_capability.json`; it never changes `motion_safety_status` from `UNAPPROVED` by itself.

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

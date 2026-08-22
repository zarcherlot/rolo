# Wheeltec static-source Adapt validation

This validation exercises the Adapt discovery and heuristic orchestration boundary against an
unbuilt ROS driver source tree. It is intentionally not a target-host or release qualification.

## Fixture

- Source: `C:\Users\zarch\Desktop\adapt-validation-data\wheeltec_drivers`
- Build root: not supplied
- Install root: not supplied
- Explicit executable: not supplied
- Target ROS runtime: not observed (`--active-probe none`)
- Heuristic mode: `shadow`

The source directory contains ROS packages, launch/config files, URDFs, camera/base/lidar drivers,
messages, and supporting libraries. Rolo runs on the developer workstation, not on the Wheeltec
target.

## Local-only result

The provider-disabled run validates the deterministic and fail-closed path without transmitting
source-derived context to an Agent service:

- Discovery status: `PARTIAL`
- Application probe: `SUCCEEDED`
- Semantic bindings: 3
- Deterministic unverified Operation candidates: 2
- Candidate Operations: `app.camera.snapshot`, `app.teleop.velocity`
- Eligible Operations: 0
- Deferred reason: `TARGET_ROUTE_NOT_OBSERVED`
- Registry identity: 294 Operations, SHA-256
  `298c56e193a22b7e59e16cc19c31f4ac4c16dee1ea51298824a756ec871d173d`
- Heuristic status: `FALLBACK` (`provider not configured`)
- Heuristic target contract slice: 20 Operations
- Release influence: false

The run persists the frozen discovery planning context, bounded mapping request, deterministic
fallback validation, developer-facing summary, and an AdaptPlan reference. It also appends the
Heuristic Adapt analysis to the Robot Wiki.

## Missing evidence reported

The local-only run reports eight release-blocking evidence gaps:

1. `BUILD_ARTIFACTS`
2. `EXECUTABLE_HELP`
3. `INSTALL_ARTIFACTS`
4. `INTERFACE_SCHEMA`
5. `ROS_RUNTIME_GRAPH`
6. `ROUTE_PROVIDER_IDENTITY`
7. `TARGET_HARDWARE_INVENTORY`
8. `TARGET_RUNTIME_REVISION`

This is the required behavior for a static project. Source declarations remain
`DISCOVERED_UNVERIFIED`; developer-host hardware is not attributed to the robot, and no Tool Catalog
or release authority is produced.

## Agent-enabled validation

An Agent-enabled run additionally sends a bounded, source-derived planning/mapping context to the
configured Codex provider and should persist:

- `adapt-discovery-plan.json` from `rolo-adapt-discovery`;
- `operation-proposal-bundle.json` from `rolo-operation-mapping`;
- deterministic `operation-proposal-validation.json`;
- Agent-reported unknowns and requested verification merged into `missing_evidence`.

Because this can transmit source-derived content to an external model provider, it requires explicit
fixture-owner authorization. The local-only result above is the safe default validation when that
authorization is absent.

# Canonical-CLI-driven software discovery

## Scope

Build-stage discovery identifies what a robot application appears to do, how its executables are
invoked, which interfaces they expose, and which direct Python or ROS dependencies they declare.
It produces immutable evidence for a user to confirm before a Coding Agent builds adapters.

Discovery is deliberately not a host inventory or installer:

- it does not call `dpkg-query`, `rpm`, `apt`, `pip install`, or `conda install`;
- it does not infer an operating-system package from an executable path;
- it does not enumerate unrelated packages in the host environment;
- it does not compute a transitive dependency closure or vulnerability inventory; and
- it does not execute launch files, README commands, or newly discovered binaries.

The canonical CLI defines the functionality that the Build stage must provide. Source manifests,
launch declarations, documentation, explicitly supplied executables, and optional read-only ROS
runtime evidence explain how the supplied application can provide that functionality.

## Command and evidence inputs

```text
robotctl build discover run
  --robot ID
  --urdf PATH
  [--source-root PATH ...]
  [--build-root PATH ...]
  [--install-root PATH ...]
  [--executable PATH ...]
  [--doc-root PATH ...]
  [--launch-root PATH ...]
  [--active-probe none|help|runtime-readonly]
```

At least one `--source-root`, `--install-root`, or `--executable` is required. Documentation,
launch, and build roots are supplemental. Discovery never substitutes the current directory for a
missing source root.

Paths are normalized to absolute paths. Missing, unreadable, empty, or truncated evidence remains
visible in coverage records and warnings.

### Degradation levels

| Level | Minimum usable evidence | Analysis | Confidence ceiling |
|---|---|---|---|
| `SOURCE_FIRST` | source root | manifests, source, targets, launch/config and docs | high |
| `ARTIFACT_DOC` | executable/install root and documentation | binary metadata, docs, static launch, optional help/runtime | medium |
| `BINARY_ONLY` | executable/install root only | binary metadata, optional help/runtime and naming evidence | low |

All levels produce a report. `BINARY_ONLY` findings remain `DISCOVERED_UNVERIFIED` and are intended
for explicit user review.

## Probe safety and limits

`none` performs no executable or ROS-runtime active probe. `help` may invoke only executables
explicitly supplied with `--executable`, using a sanitized environment, no shell, a five-second
timeout, and bounded output. `runtime-readonly` additionally inspects an already-running ROS graph.

Launch files are parsed statically. Discovery never invokes `ros2 launch`, loads a plugin, starts a
service, or creates a robot process.

Current limits are:

| Evidence | Limit | Result when exceeded |
|---|---:|---|
| walked files per evidence class | 10,000 | partial coverage and warning |
| executable records | 200 | partial artifact coverage |
| explicit help probes | 20 | remaining probes marked blocked by limit |
| retained help output | 200 KiB | output-limit status |
| documentation or launch files | 500 each | partial coverage |
| one executable hash | 256 MiB | hash omitted with reason |
| aggregate executable hashing | 2 GiB | remaining hashes omitted |
| direct dependency candidates | 1,000 | omitted count and `PARTIAL` resolution |

## Source and executable analysis

Source analysis recognizes `pyproject.toml`, setuptools, CMake, Cargo, ROS `package.xml`, launch
files, configuration files, Python console scripts, CMake targets, statically visible ROS
interfaces, and common protocol tokens. It records manifest hashes and a Git revision when one is
available.

Each executable record includes:

- stable executable ID, name, path, origin and SHA-256 when permitted;
- file format, architecture and version evidence;
- source, build, install, documentation and launch analysis;
- invocation entrypoint, arguments, subcommands, environment and help-probe result;
- ROS, network, IPC and hardware-bus communication findings;
- canonical capability candidates and their confidence;
- direct dependency candidate IDs; and
- safety classification, side effects and unresolved evidence.

## Direct dependency resolution

Only direct dependencies explicitly declared by supplied source or static launch evidence are
resolved.

### Python

PEP 508 declarations are normalized with environment markers and PEP 440 constraints. Applicable
candidates are queried through `importlib.metadata` in the Python interpreter running rolo.

### ROS

ROS dependencies come from `package.xml` and static launch package references. Resolution reads
package resources and manifests under bounded `AMENT_PREFIX_PATH` prefixes. If no readable ament
prefix exists, ROS candidates are `UNKNOWN`, not `MISSING`.

Each candidate has one status:

- `INSTALLED`: local metadata exists and satisfies any declared version constraint;
- `MISSING`: a usable local metadata index exists but the candidate is absent;
- `VERSION_CONFLICT`: an installed version violates the declaration; or
- `UNKNOWN`: evidence is insufficient or cannot be compared safely.

Missing and version-conflicting required candidates enter `BuildInputs.unresolved_dependencies`.
An executable without dependency declarations is also explicit `UNKNOWN`. Discovery reports these
states but never creates or executes an installation plan.

## Active discovery report

Every run writes schema-validated JSON and a human-readable Markdown rendering. The report contains
compact dependency candidates once and refers to them by candidate ID from category and executable
records.

```yaml
schema_version: robot-active-discovery-report/v1
discovery_id: disc-...
robot_id: rover
technical_status: PARTIAL
confirmation_status: AWAITING_USER_CONFIRMATION
discovery_mode: {level: SOURCE_FIRST, confidence: HIGH, reason: "..."}
inputs: {}
coverage: {}
executables:
  - executable_id: exe-...
    name: navigation
    path: /opt/robot-app/bin/navigation
    origin: EXPLICIT
    sha256: null
    source_analysis: {}
    artifact_analysis: {}
    documentation_analysis: {}
    launch_analysis: {}
    invocation: {}
    communication:
      ros: {}
      network: {}
      ipc: {}
      hardware_bus: {}
      confidence: LOW
      evidence_refs: []
    capability_candidates: []
    dependencies:
      declared: []
      installed: [depcand-...]
      missing: []
      unknown: []
      version_conflicts: []
    safety: {}
    evidence: {}
canonical_operation_summary: []
dependency_summary:
  report_ref: artifact://discovery/rover/runs/disc-.../direct_dependencies.json
  candidates:
    - {candidate_id: depcand-..., name: rclpy, ecosystem: python, required: true, status: INSTALLED}
  required: [depcand-...]
  installed: [depcand-...]
  missing: []
  unknown: []
  conflicting: []
  unresolved_executables: []
global_conflicts: []
unknowns: []
warnings: []
confirmation:
  required: true
  prompt: Confirm executable, invocation, communication, capability, dependency, and safety findings.
  confirm_command: robotctl build discover confirm --robot rover --discovery-id disc-...
created_at: 2026-08-18T00:00:00Z
```

Raw source, documentation and help output are not embedded in the report or normal Coding Agent
context. Bounded hashes and artifact references preserve traceability.

## User confirmation

Every run prompts the user to verify executable identity, invocation, communication, capability,
dependency and safety findings:

```text
robotctl build discover confirm --robot ID --discovery-id DISCOVERY_ID
robotctl build discover confirm --robot ID --discovery-id DISCOVERY_ID \
  --decision correct --corrections corrections.yaml
```

The confirmation records the exact report SHA-256, robot ID and discovery ID. A run accepts only one
decision. A changed report, stale confirmation, rejection, or correction request blocks Build plan
execution. The discovery report remains immutable; current confirmation state is derived from the
separate confirmation artifact rather than copied into mutable summaries.

## Artifacts

```text
artifacts/discovery/<robot_id>/
|-- latest.json
`-- runs/<discovery_id>/
    |-- report.json
    |-- active_discovery_report.json
    |-- active_discovery_report.md
    |-- direct_dependencies.json
    |-- software_summary.json
    |-- capability_manifest.json
    |-- discovered_capability.json
    |-- semantic_context.json
    |-- hw.json
    |-- linux.json
    |-- ros.json
    |-- application.json
    `-- tool_catalog.json
```

`runs/<discovery_id>/` is the immutable fact source. `latest.json` contains only the current
discovery ID and report SHA-256; readers validate the hash before loading the run. Build, Debug and
Test retain their own small `latest/inputs.json` convenience handoffs.

`software_summary.json` is the bounded dependency summary used in normal Coding Agent context.
`direct_dependencies.json` contains detailed candidate evidence and is accessed by reference.

## Build gates

- failed technical discovery blocks Build;
- partial or unknown evidence remains visible and degrades readiness;
- missing and version-conflicting required direct dependencies remain unresolved;
- unknown dependency state is never treated as compatible;
- user confirmation must match the exact immutable active report; and
- write or motion operations remain unverified until adapter conformance, controlled validation and
  required approval complete.

## Acceptance criteria

Tests must prove that:

- all three evidence modes produce bounded reports;
- newly discovered executables and launch files are not executed;
- help probes run only for explicit executables and respect time/output/count limits;
- Python and ROS direct dependencies distinguish installed, missing, conflicting and unknown state;
- the 1,000-candidate limit records the omitted count and returns `PARTIAL`;
- no host package-manager query or target dependency installation occurs;
- dependency details are referenced by stable candidate IDs rather than copied repeatedly;
- `latest.json` resolves to an immutable report with a matching SHA-256; and
- Build cannot proceed without a confirmation bound to that report.

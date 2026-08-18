# Canonical-CLI-driven software discovery

## Scope

Adapt-stage discovery identifies what a robot application appears to do, how its executables are
invoked, which interfaces they expose, and which direct Python or ROS dependencies they declare.
It produces immutable machine evidence plus an editable robot Wiki before an Adapter Agent
implements adapters.

Discovery is deliberately not a host inventory or installer:

- it does not call `dpkg-query`, `rpm`, `apt`, `pip install`, or `conda install`;
- it does not infer an operating-system package from an executable path;
- it does not enumerate unrelated packages in the host environment;
- it does not compute a transitive dependency closure or vulnerability inventory; and
- it does not execute launch files, README commands, or newly discovered binaries.

The canonical CLI defines the functionality that the Adapt stage must provide. Source manifests,
launch declarations, documentation, explicitly supplied executables, and optional read-only ROS
runtime evidence explain how the supplied application can provide that functionality.

## Command and evidence inputs

```text
robotctl adapt discover run
  --robot ID
  --urdf PATH
  [--source-root PATH ...]
  [--build-root PATH ...]
  [--install-root PATH ...]
  [--executable PATH ...]
  [--doc-root PATH ...]
  [--launch-root PATH ...]
  [--active-probe none|help|runtime-readonly]
  [--full]
```

At least one `--source-root`, `--install-root`, or `--executable` is required. Documentation,
launch, and build roots are supplemental. Discovery never substitutes the current directory for a
missing source root.

Paths are normalized to absolute paths. Missing, unreadable, empty, or truncated evidence remains
visible in coverage records and warnings.

### Degradation levels

| Level | Minimum usable evidence | Analysis | Confidence ceiling |
|---|---|---|---|
| `SOURCE_FIRST` | recognizable source or manifest evidence | manifests, source, targets, launch/config and docs | high |
| `ARTIFACT_DOC` | existing explicit executable or executable found under an install root, plus readable documentation | binary metadata, docs, static launch, optional help/runtime | medium |
| `BINARY_ONLY` | existing explicit executable or executable found under an install root, without readable documentation | binary metadata, optional help/runtime and naming evidence | low |

All levels produce a report. `BINARY_ONLY` findings remain `DISCOVERED_UNVERIFIED` and are intended
for explicit user review.

Mode selection uses collected evidence, not merely supplied paths. A source root that contains no
recognizable source or manifest evidence does not qualify for `SOURCE_FIRST`. Documentation alone
does not qualify for `ARTIFACT_DOC`, and an empty or non-executable install root does not qualify for
`BINARY_ONLY`. If none of the three minimum evidence sets is collected, discovery rejects the run
with `no usable primary evidence was collected` instead of publishing a misleading mode.

`--full` prints the complete top-level `DiscoveryReport`. Executable-level details remain in the
immutable `active_discovery_report.json` referenced by that report.

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

### Binary linked-library introspection

Binary linked-library introspection is intentionally not part of the current dependency resolver.
The current report identifies executable format, architecture and content hash, while Python and
ROS dependency resolution remains declaration-driven. Consequently, artifact-only and binary-only
runs may report dependency declarations as unknown even when the executable contains ELF, PE or
Mach-O linkage metadata.

This capability is useful, but it is not required for source-first adaptation. It should be added
when artifact-only deployment becomes a supported acceptance path or when conformance failures need
to distinguish a missing shared library from an adapter defect. The recommended scope is bounded,
static metadata parsing only:

- read ELF `DT_NEEDED`, PE import tables and Mach-O load commands without loading the binary;
- record library names, binary architecture/ABI evidence and bounded resolution attempts separately
  from Python and ROS declared dependencies;
- report unresolved or conflicting libraries without installing packages or guessing a distribution
  package name; and
- do not run `ldd` or an equivalent loader-based command on untrusted binaries, because that crosses
  the static-evidence boundary and can execute target-controlled loader behavior.

Until that work is implemented, binary linkage is an explicit coverage gap rather than evidence that
the binary has no external dependencies.

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

Missing and version-conflicting required candidates enter `AdaptInputs.unresolved_dependencies`.
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
created_at: 2026-08-18T00:00:00Z
```

Raw source, documentation and help output are not embedded in the report or normal Adapter Agent
context. Bounded hashes and artifact references preserve traceability.

## Editable robot Wiki

Every run produces `robot_wiki.md`, which renders the node/communication graph, hardware and host
summary, executable purposes, dependencies, unknowns, warnings, and maintenance guidance:

```text
robotctl adapt discover review --robot ID
```

The robot's hardware/software chief engineer may directly edit this Markdown file. It is not hashed
and editing it does not invalidate the discovery manifest. `adapt run` consumes the current Wiki as
human-maintained engineering context; explicit factual corrections take precedence over inferred
discovery, while commands embedded in the document remain data rather than instructions to execute.

## Artifacts

```text
artifacts/discovery/<robot_id>/
|-- latest.json
`-- runs/<discovery_id>/
    |-- report.json
    |-- active_discovery_report.json
    |-- active_discovery_report.md
    |-- robot_wiki.md              # editable, intentionally not hashed
    |-- manifest.json
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

`runs/<discovery_id>/` combines one immutable machine-evidence snapshot with its editable Wiki.
`latest.json` contains the current discovery ID, report SHA-256, and machine-evidence manifest
SHA-256; readers validate every manifested JSON file before loading the run. `robot_wiki.md` is
explicitly excluded. Adapt, Diagnose, and Verify retain only small `latest/inputs.json` indexes;
they do not copy discovery evidence into stage run directories.

`software_summary.json` is the bounded dependency summary used in normal Adapter Agent context.
`direct_dependencies.json` contains detailed candidate evidence and is accessed by reference.

## Adapt gates

- failed technical discovery blocks Adapt;
- partial or unknown evidence remains visible and degrades readiness;
- missing and version-conflicting required direct dependencies remain unresolved;
- unknown dependency state is never treated as compatible;
- the robot Wiki must exist but remains editable and outside the machine-evidence manifest; and
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
- Adapt rejects changed machine evidence but accepts professional edits to `robot_wiki.md`; and
- Adapter Agent completion cannot publish a handoff; the independent gate inside `adapt run`
  validates frozen output, exact operation coverage, State Graph identity, schemas, safety, and
  physical write evidence before updating `adapt/<robot>/latest.json`.

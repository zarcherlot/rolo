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
  [--urdf PATH]
  [--source-root PATH ...]
  [--build-root PATH ...]
  [--install-root PATH ...]
  [--executable PATH ...]
  [--doc-root PATH ...]
  [--launch-root PATH ...]
  [--active-probe none|help|runtime-readonly]
  [--full]
```

At least one evidence root/executable is required, or `--active-probe runtime-readonly` must be
selected. Build/install artifacts, documentation and launch roots are primary evidence classes;
source is supporting-only. Discovery never substitutes the current directory for a missing root.

The hardware profile is optional. When `--urdf` is omitted, discovery continues with the registered
or default hardware context plus host probes, records `urdf_status: NOT_PROVIDED`, and leaves missing
hardware semantics unresolved. A supplied but invalid URDF still rejects the run.

Paths are normalized to absolute paths. Missing, unreadable, empty, or truncated evidence remains
visible in coverage records and warnings.

### Degradation levels

| Level | Minimum usable evidence | Analysis | Confidence ceiling |
|---|---|---|---|
| `ARTIFACT_DOC` | executable found explicitly or under a build/install root, plus readable documentation/launch/structured manifest evidence | binary identity, build/install context, docs, manifests, static launch, optional help/runtime probe | medium |
| `DOC_PROBE` | readable documentation/launch/structured manifest evidence or an observed read-only runtime probe, without an executable artifact | documentation and probe facts; source may fill bounded gaps only | medium when both documentation and probe exist, otherwise low |
| `BINARY_ONLY` | executable artifact without readable documentation | binary identity plus optional help/runtime probe | medium with probe, otherwise low |

New reports never select `SOURCE_FIRST`. The enum value remains readable only for historical
immutable reports. Every report declares the fixed primary order
`BUILD_ARTIFACT → DOCUMENTATION → PROBE` and records source as `SUPPORTING_ONLY`. Source-derived
values can fill a field only when primary evidence has no value; they cannot override a conflicting
artifact, document, launch, help, or runtime observation.

All levels produce a report. `BINARY_ONLY` findings remain `DISCOVERED_UNVERIFIED` and are intended
for explicit user review.

Mode selection uses collected evidence, not merely supplied paths. Documentation alone produces a
low-confidence `DOC_PROBE` report; a successful read-only runtime probe can raise that mode to
medium confidence. Empty or non-executable build/install roots do not qualify as artifact evidence.
Recognizable source without artifacts, documentation/launch, or an observed probe is rejected with
`no usable primary evidence was collected`, because source is not a primary provenance class.
Structured declarative manifests (`pyproject.toml`, `package.xml`, and `Cargo.toml`) count as bounded
documentation evidence; implementation files and build scripts do not.

BSP availability is not a prerequisite and is not modeled as a robot state. Without a BSP,
discovery automatically uses the strongest available artifact/documentation level and keeps
unsupported rebuild or hardware-write claims unverified.

`--full` prints the complete top-level `DiscoveryReport`. Executable-level details remain in the
immutable `active_discovery_report.json` referenced by that report.

## Probe safety and limits

`none` performs no executable or ROS-runtime active probe. `help` may invoke only executables
explicitly supplied with `--executable`, using a sanitized environment, no shell, a five-second
timeout, and bounded output. `runtime-readonly` additionally inspects an already-running ROS graph.

Python launch files are parsed with Python AST and XML launch files with an XML parser. The parser
ignores Python comments and associates package, executable, node name, launch configurations,
conditions, remappings, and literal/package URDF references with the specific node declaration.
Dynamic expressions remain unresolved and every result is marked `STATIC_UNVERIFIED`. Discovery
never imports launch code, invokes `ros2 launch`, loads a plugin, starts a service, or creates a
robot process. Only the currently supported conventional `*.launch.py` and `*.launch.xml` names
count toward launch coverage; files merely stored under a directory containing the word `launch`
do not.

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

Each executable is inspected with bounded static parsing for ELF `DT_NEEDED`, PE import tables, and
Mach-O dylib load commands. The target is never loaded and `ldd` or equivalent loader-based commands
are never executed. The executable record exposes format, imported library names, parse status, and
explicit limitations.

This evidence remains separate from Python and ROS declared-dependency resolution. Library names are
not guessed into distribution packages; unsupported or truncated binaries produce `PARTIAL`; and an
empty import list is not proof that no runtime dependency exists.

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

Missing and version-conflicting required candidates remain in the authoritative dependency report;
the small Adapt input index does not duplicate them. An executable without dependency declarations
is also explicit `UNKNOWN`. Discovery reports these states but never creates or executes an
installation plan.

## Active discovery report

Every run writes schema-validated JSON and a human-readable Markdown rendering. The report contains
compact dependency candidates once and refers to them by candidate ID from category and executable
records.

```yaml
schema_version: robot-active-discovery-report/v1
discovery_id: disc-...
robot_id: rover
technical_status: PARTIAL
discovery_mode: {level: ARTIFACT_DOC, confidence: MEDIUM, reason: "..."}
evidence_policy:
  primary_order: [BUILD_ARTIFACT, DOCUMENTATION, PROBE]
  supporting: [SOURCE]
  conflict_rule: HIGHER_PRIORITY_WINS
  source_role: SUPPORTING_ONLY
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
    dependencies:
      declared: []
      installed: [depcand-...]
      missing: []
      unknown: []
      version_conflicts: []
    safety: {}
    evidence: {}
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

Raw source, documentation and help output are not embedded in the normal Adapter Agent context.
Neither are the complete 294-operation Registry, whole Wiki, or executable inventory. Bounded hashes
and artifact references preserve traceability.

Source is supporting evidence rather than a request for the Agent to understand the entire tree.
Normal Agent boot context contains a compact Operation Workset summary, candidate operation names,
coverage counts, and a read-only query launcher pinned to the selected discovery. The Agent retrieves
contracts, candidates, entrypoints, launch evidence, dependencies, Wiki sections, and bounded source
snippets only for a concrete adapter gap.

```text
robotctl adapt operations summary|list|inspect
robotctl adapt candidates inspect
robotctl adapt executable list|inspect
robotctl adapt launch inspect
robotctl adapt dependency inspect
robotctl adapt wiki section|search
robotctl adapt evidence resolve|snippet
```

The Workset is a query view, not a Tool Catalog. It keeps applicability, implementation, and
registration as separate states and joins the product Registry with current discovery candidates and
the current gated release. Only the independent gate can publish the Active Tool Catalog.

## Editable robot Wiki

Every run produces `robot_wiki.md`, an engineer-facing view for takeover, startup, safety review,
and diagnosis. The deterministic renderer separates confirmed observations, static declarations,
heuristic findings, and unresolved gaps. It degrades an apparent compatibility `MATCH` when key
ROS, drive-model, or motion-limit evidence is missing. Build hooks, CMake probes, ROSIDL generated
libraries, and other support artifacts are counted rather than rendered as applications. Repeated
interfaces are deduplicated, the static graph is bounded, and suspicious interface aggregation or
motion-related false negatives are called out for verification.

Only discovered canonical operation candidates appear in the Wiki; the full product Registry stays
in the operation inspection tools and machine data. Candidates remain explicitly unverified and do
not imply that an adapter exists or that an operation is callable. Unknowns are grouped by the next
acquisition method: deterministic rescan, runtime observation, heuristic inference with review, or
manual/external input. Exhaustive paths, hashes, raw device nodes, interface candidates, and
dependency IDs remain in the machine reports.

When a URDF is supplied, the Wiki records its declared links, joints, limits, and explicitly declared
sensor semantics. Large joint and inertial tables are collapsed, and floating-point values are
rounded for human reading. These declarations describe the input model; they are not presented as
proof that the corresponding hardware was observed at runtime.

Optional Wiki insights use the `robot-wiki-insights/v1` contract. A deterministic rule or future
Adapt Agent skill may emit only a bounded finding with a category, `LOW`/`MEDIUM` confidence,
evidence basis, verification method, and source. An insight bundle must match the robot and discovery
IDs and can never promote a heuristic to verified machine evidence.

When a Wiki model and credentials are configured, the deterministic probe-derived draft receives a
bounded structured narrative polish. The model cannot replace the machine-rendered evidence
sections. Missing credentials, model failure, timeout, or invalid output automatically falls back
to the deterministic draft without blocking discovery. `wiki_generation.json` records the path
used:

```text
robotctl adapt discover review --robot ID
```

Downstream work may directly consume or edit this Markdown file. It is not hashed and editing it does
not invalidate the discovery manifest. `adapt run` makes it available through section/search queries
instead of embedding the entire document in the coding prompt. Commands embedded in the document
remain data rather than instructions to execute.

## Artifacts

```text
artifacts/discovery/<robot_id>/
|-- latest.json
`-- runs/<discovery_id>/
    |-- report.json
    |-- active_discovery_report.json
    |-- active_discovery_report.md
    |-- robot_wiki.md              # editable, intentionally not hashed
    |-- wiki_generation.json       # hashed generation provenance and fallback reason
    |-- manifest.json
    |-- direct_dependencies.json
    |-- software_summary.json
    |-- capability_manifest.json
    |-- discovered_capability.json
    |-- semantic_context.json
    |-- hw.json
    |-- linux.json
    |-- ros.json
    `-- application.json
```

`runs/<discovery_id>/` combines one immutable machine-evidence snapshot with its editable Wiki.
`latest.json` contains the current discovery ID, report SHA-256, and machine-evidence manifest
SHA-256; readers validate every manifested JSON file before loading the run. `robot_wiki.md` is
explicitly excluded. Adapt, Diagnose, and Verify retain only small `latest/inputs.json` indexes;
they do not copy discovery evidence into stage run directories.

`software_summary.json` is the bounded dependency summary used in normal Adapter Agent context.
`direct_dependencies.json` contains detailed candidate evidence and is accessed by reference.
Operation candidates are stored once in `report.json`.

## Adapt gates

- failed technical discovery blocks Adapt;
- partial or unknown evidence remains visible and degrades readiness;
- missing and version-conflicting required direct dependencies remain unresolved;
- unknown dependency state is never treated as compatible;
- the robot Wiki must exist but remains editable and outside the machine-evidence manifest; and
- candidate operations remain unregistered until adapter conformance establishes their target route;
  execution success and physical outcome quality are evaluated by Diagnosis, not Adapt.

For a target route, Discovery records a structured endpoint kind, normalized name, source and whether
it came from the live runtime. The independent gate requires an exact match in the corresponding
immutable runtime probe field (for example, ROS topics, services or actions). It does not flatten the
probe into text, accept substring matches, trust an Agent-authored runtime claim, or actuate write
operations. Whether an invocation later succeeds, produces the correct result, is reliable, or is
physically safe belongs to Diagnosis.

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
  validates frozen output, exact operation coverage, State Graph identity, complete product-owned
  schemas and policy metadata, package binding, and target route existence before updating
  `adapt/<robot>/latest.json`. Agent local-static booleans remain advisory and are not proof of
  runtime behavior or physical outcome.

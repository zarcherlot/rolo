# Canonical-CLI-driven software discovery

## Status and scope

This document defines the implemented foundation and target design for Build-stage software
discovery. The current implementation has three-level active application discovery, immutable
report confirmation, a generated tool catalog, and deterministic direct dependency resolution.
Relevance resolution currently uses Python project declarations, ROS package/launch declarations,
the static ament index, and the metadata API of the Python interpreter running rolo. There is no
host-wide package inventory and no operating-system package-manager query. Transitive dependency
closure, deep inspection, vulnerability adapters, and batched agent review remain roadmap work.

The design has two complementary inputs:

```text
canonical CLI registry + source manifests + launch/ROS evidence
                              |
                              v
             direct dependency and capability findings
```

The canonical CLI registry answers which functionality is required. Source and ROS declarations
identify the direct runtime dependencies for that functionality. Resolution is a deterministic
program responsibility; a Coding Agent may consume the findings but does not enumerate the host.

## Required behavior

Build discovery MUST:

1. use the canonical CLI registry as the primary filter for relevant software;
2. supplement CLI relevance with evidence from source manifests, running processes, ROS, URDF,
   services, and loaded plugins;
3. deeply inspect relevant packages only;
4. batch any agent-facing package analysis within an explicit context budget; and
5. preserve read-only discovery and never execute newly discovered binaries.

## Active application discovery inputs and degradation

Application discovery accepts complementary evidence roots. Every path option may be repeated:

```text
--source-root PATH       source workspace or overlay
--build-root PATH        compiler intermediates; supplemental only
--install-root PATH      installed tree or executable package root
--executable PATH        an explicitly selected executable
--doc-root PATH          manuals, READMEs, examples, and interface documents
--launch-root PATH       launch, configuration, and package manifests
--active-probe MODE      none, help, or runtime-readonly
```

At least one `--source-root`, `--install-root`, or `--executable` MUST be supplied. Documentation,
launch, and build-intermediate roots cannot satisfy the minimum input requirement by themselves.
The command MUST NOT silently substitute the current working directory when `--source-root` is
omitted.

Paths are normalized to absolute paths. A supplied primary path satisfies CLI input validation, but
only evidence that can actually be read affects the degradation level. Missing paths, empty source
trees, file-count limits, and executable-report limits are recorded as partial coverage and
warnings. A documentation or launch option may name either one file or a directory.

The resolver selects one degradation level from the valid evidence that was actually collected:

| Level | Minimum evidence | Primary analysis | Confidence ceiling |
|---|---|---|---|
| `SOURCE_FIRST` | source root | manifests, source, build targets, launch/config, docs, optional artifacts and runtime | high |
| `ARTIFACT_DOC` | install root or explicit executable, plus usable documentation | binary metadata, docs, static launch, explicit `--help`, existing ROS graph | medium |
| `BINARY_ONLY` | install root or explicit executable, without usable source or docs | binary metadata, explicit `--help`, existing ROS graph, naming heuristics | low |

All three levels produce a report. Missing evidence lowers confidence and remains visible; it does
not disappear from the report. `BINARY_ONLY` capability mappings MUST remain
`DISCOVERED_UNVERIFIED` until the user confirms the discovery and conformance evidence is added.

### Active-probe safety

`none` adds no executable or ROS-runtime active probe; application evidence collection is static.
The pre-existing read-only hardware and operating-system discovery layers still run independently.
`help` may run only executables explicitly supplied through `--executable`; executables merely
found under a root MUST NOT be run. `runtime-readonly` adds read-only inspection of an
already-running ROS graph. Help probes use a sanitized environment, bounded output, a short
timeout, and no shell.

Launch files are parsed statically during discovery. Discovery MUST NOT invoke `ros2 launch`, load
a plugin, start a service, or create a robot process. Launch execution can initialize drivers,
controllers, or motion and therefore belongs to a separately approved validation workflow after
the discovery report is confirmed.

The report includes at most 200 executable records. This is a report-size boundary, not silent
success: additional candidates set artifact coverage to `PARTIAL` and produce a warning. Directory
walking is independently bounded at 10,000 files per evidence class. Raw `--help` output is capped
at 200 KiB and stored as a referenced artifact; the report contains only parsed usage, option, and
subcommand findings. A run executes at most 20 explicit help probes, parses at most 500 external
documentation files and 500 launch files, hashes no executable larger than 256 MiB, and hashes at
most 2 GiB of executable bytes in aggregate. Reaching any boundary is visible as partial coverage,
`BLOCKED_BY_POLICY`, an unresolved item, or a warning as applicable.

### Current implementation status

Implemented in the current branch:

- all input options and minimum-input validation above;
- degradation based on evidence actually collected, including rejection of an empty source tree as
  high-confidence source evidence;
- source manifests, entrypoints, CMake targets, declared dependencies, ROS interfaces, protocol
  tokens, documentation, artifacts, and static launch declarations;
- bounded `--help` for explicitly supplied executables only and read-only ROS graph attribution;
- JSON and Markdown reports, an active confirmation prompt, immutable one-decision confirmation,
  and an exact-report-SHA-256 Build gate; and
- bounded active-discovery findings in the confirmed Coding Agent handoff without raw source,
  documentation or help output;
- PEP 508/440 Python declaration parsing, including environment-marker filtering and installed
  version comparison through `importlib.metadata`;
- ROS dependency/version comparison through `package.xml` declarations and read-only ament-index
  metadata;
- `package_relevance.json`, software-summary counts, and Build
  unresolved inputs for missing, unknown, policy-blocked, and version-conflicting dependencies.

Deferred work includes transitive dependency closure, binary linkage-to-package resolution,
canonical-registry package selectors beyond currently discovered direct evidence, cross-ecosystem
package equivalence, package file/checksum inspection, vulnerability adapters, optional agent
batching, and runtime launch validation. Deferred or unavailable evidence stays empty, `UNKNOWN`,
or `NOT_PROBED`; it is never inferred as a clean result.

## Active discovery report and confirmation gate

Every run writes a schema-validated JSON report and a human-readable Markdown rendering:

```text
artifacts/discovery/<robot_id>/runs/<discovery_id>/
|-- active_discovery_report.json
|-- active_discovery_report.md
`-- confirmation.json                 # created only by the confirmation command
```

The report status is independent of user confirmation. A technically successful run still starts
with `confirmation_status: AWAITING_USER_CONFIRMATION`. The normal command output MUST point to the
report and actively prompt the user to review executable identity, invocation, communication,
capability, dependency, and safety findings.

```text
robotctl build discover confirm --robot <id> --discovery-id <discovery-id>
robotctl build discover confirm --robot <id> --discovery-id <discovery-id> \
  --decision correct --corrections corrections.yaml
```

Confirmation is a separate immutable attestation containing the report SHA-256, decision, time,
and optional corrections-file hash. Build planning MUST remain `AWAITING_CONFIRMATION` unless an
`accept` attestation matches the exact active-discovery report hash. Rejecting or correcting a
report does not mutate it; corrections require another discovery run. A formerly accepted
attestation whose report no longer matches is exposed to Build as `INVALID_OR_STALE`, and execution
rechecks the hash before any Coding Agent dependency preparation or workspace mutation.

The minimum report contract is:

```yaml
schema_version: robot-active-discovery-report/v1
discovery_id: disc-...
robot_id: rover
technical_status: SUCCEEDED       # SUCCEEDED, PARTIAL, or FAILED
confirmation_status: AWAITING_USER_CONFIRMATION
discovery_mode:
  level: SOURCE_FIRST             # SOURCE_FIRST, ARTIFACT_DOC, or BINARY_ONLY
  confidence: HIGH
  reason: source evidence was collected
inputs:
  source_roots: []
  build_roots: []
  install_roots: []
  executables: []
  document_roots: []
  launch_roots: []
  active_probe: none
coverage:
  source: {status: COMPLETE, records: 0, truncated: false}
  artifacts: {status: NOT_PROVIDED, records: 0, truncated: false}
  documentation: {status: NOT_PROVIDED, records: 0, truncated: false}
  launch: {status: NOT_PROVIDED, records: 0, truncated: false}
  help_probes: {status: NOT_PROBED, records: 0, truncated: false}
  ros_runtime: {status: NOT_PROBED, records: 0, truncated: false}
executables:
  - executable_id: exe-navigation
    name: navigation
    path: /opt/robot-app/bin/navigation
    origin: DISCOVERED_ARTIFACT
    sha256: "..."
    file_format: ELF
    architecture: arm64
    version: {value: null, source: null, confidence: LOW}
    source_analysis:
      available: true
      projects: []
      languages: []
      build_systems: []
      build_targets: []
      entrypoint_symbols: []
      declared_dependencies: []
      dependency_declarations: []
      parameters: []
      source_revisions: []
      manifest_sha256: {}
      evidence_refs: []
    artifact_analysis:
      install_root: null
      build_roots: []
      intermediate_outputs: []
      linked_libraries: []
      plugins: []
      configuration_files: []
    documentation_analysis:
      available: false
      references: []
      reference_sha256: {}
      documented_commands: []
      documented_parameters: []
      conflicts: []
      stale_warnings: []
    launch_analysis:
      available: false
      references: []
      reference_sha256: {}
      packages: []
      declared_executable: null
      nodes: []
      arguments: []
      remappings: []
    invocation:
      entrypoint: /opt/robot-app/bin/navigation
      arguments: []
      subcommands: []
      required_environment: {}
      startup_sequence: []
      shutdown_method: null
      exit_codes: []
      health_check: null
      help_probe: {status: NOT_PROBED, output_ref: null, timeout_s: 5, usage: [], parameters: [], subcommands: []}
    communication:
      ros: {nodes: [], publishers: [], subscribers: [], services: [], actions: [], parameters: [], tf_frames: [], remappings: []}
      network: {protocols: [], listen_endpoints: [], remote_endpoints: [], authentication: null, schemas: []}
      ipc: {unix_sockets: [], shared_memory: [], dbus: []}
      hardware_bus: {serial: [], can: [], i2c: [], spi: []}
      confidence: LOW
      evidence_refs: []
    capability_candidates: []
    dependencies:
      declared: []
      resolved: []
      binary_linked: []
      runtime_observed: []
      missing: []
      unknown: []
      version_conflicts: []
      install_candidates: []
    safety:
      access: read
      risk: R0
      possible_side_effects: []
      device_access: []
      network_access: []
      privilege_required: false
      motion_possible: false
    evidence: {source: [], artifacts: [], documentation: [], help: [], ros_runtime: [], conflicts: [], unresolved: []}
canonical_operation_summary: []
dependency_summary:
  required: []
  resolved: []
  missing: []
  unknown: []
  conflicting: []
  installation_plan_ref: null
global_conflicts: []
unknowns: []
warnings: []
confirmation:
  required: true
  prompt: Confirm executable, invocation, communication, capability, dependency, and safety findings.
  confirm_command: robotctl build discover confirm --robot rover --discovery-id disc-...
  correction_command: robotctl build discover confirm --robot rover --discovery-id disc-... --decision correct --corrections corrections.yaml
created_at: 2026-08-18T00:00:00Z
```

Reports store hashes and artifact references instead of embedding arbitrary document, source, help,
or binary content. Conflicting source, documentation, help, and runtime claims are retained as
separate evidence.

## Dependency discovery and installation policy

Host package inventory is outside active application discovery. Standard CLI operations identify
the functionality they require; source manifests and static launch declarations identify direct
Python and ROS dependency candidates. Discovery queries only those candidates through
`importlib.metadata` and the sourced ament index. It never enumerates the operating-system package
database and never infers a Debian/RPM package from an executable path.

A run considers at most 1,000 direct candidates. `MISSING` is emitted only when the applicable local
metadata source confirms absence. No readable ament index and invalid or uncomparable version
metadata remain `UNKNOWN`. An installed dependency that fails its declared constraints is
`VERSION_CONFLICT`. Python declarations whose environment marker evaluates false are omitted as
not applicable to the current interpreter. Binary-only applications without declarations remain
unresolved instead of being mapped to an operating-system package by heuristic.

Discovery is always read-only and MUST NOT run `pip install`, `conda install`, `apt`, or any other
dependency mutation. The current implementation emits missing/conflicting findings and unresolved
Build inputs but does not generate or execute an installation plan. A future Build installation
plan may execute only after report confirmation and explicit policy approval, and only in a
project-local virtual environment or dedicated non-base conda environment. Automatic installation
MUST NOT use `sudo`, mutate global/base environments, mix unpinned pip and conda resolution, or use
unapproved indexes/channels. Installation is followed by rediscovery and CLI conformance.

Application projects remain responsible for declaring reproducible dependencies and their intended
pip/conda environment. Discovery analyzes those declarations only far enough to report required,
missing, unknown, or conflicting direct dependencies; it does not compute a transitive closure,
analyze every package in an environment, or autonomously repair that environment. Installation is
a separate, explicit Build policy action, never an implicit discovery side effect.

The result for each direct candidate records its ecosystem, declaration scope, evidence source,
requested constraints, installed identity/version, and one terminal status: `INSTALLED`, `MISSING`,
`VERSION_CONFLICT`, or `UNKNOWN`. This is dependency evidence, not an environment inventory.

## Canonical CLI registry

The canonical CLI registry is an input contract, not merely a catalog generated after discovery.
Each operation MUST declare its risk, access mode, discovery selectors, evidence policy, and active
probe policy. A future registry entry should have this shape:

```yaml
operation: app.localization.status
canonical_cli: robotctl app localization status
layer: application
risk: R0
access: read
package_selectors:
  exact: [robot-localization]
  ros: [nav2_amcl]
source_selectors:
  manifests: [package.xml, pyproject.toml]
  symbols: [nav_msgs/msg/Odometry]
ros_selectors:
  topic_types: [nav_msgs/msg/Odometry]
  name_tokens: [odom, localization]
evidence_policy:
  minimum_independent_sources: 1
deep_inspection:
  enabled: true
active_probe:
  allowed: true
  read_only: true
  timeout_s: 5
```

Selectors MUST be explicit and versioned. Package-name substring matching alone is insufficient to
promote a capability. Evidence records retain their source and confidence; conflicts are preserved
rather than overwritten.

The resolver evaluates every registered standard operation and emits one of:

- `AVAILABLE`: an existing adapter passed the required read-only or conformance evidence;
- `DISCOVERED_UNVERIFIED`: relevant providers or bindings were found but are not verified;
- `MISSING_DEPENDENCY`: the operation has an implementation candidate with unmet dependencies;
- `UNSUPPORTED`: applicable discovery completed and found no provider;
- `NOT_PROBED`: required collectors or probes did not complete; or
- `BLOCKED_BY_POLICY`: active verification is prohibited by safety policy.

An operation MUST remain in the result even when no implementation is found. Absence from the tool
catalog is not a valid substitute for `UNSUPPORTED` or `NOT_PROBED`.

## Relevance resolution

The target resolver assigns package relevance using deterministic evidence in this order:

1. direct match to a canonical CLI package, ROS, plugin, executable, or source selector;
2. direct declaration in a discovered source manifest for a matching operation;
3. declaration from a running robot process, service, loaded plugin, or ROS package prefix;
4. reference from URDF or robot configuration; and
5. transitive dependency of a package selected by steps 1-4.

Normalized relevance levels are:

- `DIRECT`: matched by a standard CLI selector or direct runtime/source/URDF evidence;
- `TRANSITIVE`: in the dependency closure of a `DIRECT` package;
- `ENVIRONMENT`: visible in the same runtime, ROS overlay, or language environment but not selected;

Canonical CLI selectors are the primary filter. Runtime, source, and URDF evidence may add relevant
packages when a vendor-specific implementation is not yet represented in the registry. Such
additions MUST be attributed and remain unverified until the registry or an adapter is updated.

The current resolver implements the `DIRECT` subset from Python/ROS manifests and static launch
packages. It does not yet compute `TRANSITIVE` or `ENVIRONMENT` relationships and does not yet feed
canonical-registry package selectors, running processes, URDF package references, linked libraries,
services, or loaded plugins into candidate generation. Each candidate records its source evidence,
scope, affected executable IDs, requested constraints, installed identity/version, terminal status,
and diagnostic reason in `package_relevance.json`.

## Deep inspection

Deep inspection runs only for `DIRECT` packages and their bounded `TRANSITIVE` dependency closure.
It collects:

- declared dependencies and the resolved dependency graph;
- hashes of explicitly approved project/runtime files when needed; and
- vulnerability matches from an explicitly configured database or scanner.

Vulnerability output MUST record scanner name, scanner version, database version, database age,
match method, and collection time. If no usable vulnerability database is available, status is
`UNKNOWN`; absence of results MUST NOT be reported as "no vulnerabilities".

Deep inspection MUST NOT:

- execute a package binary, maintainer script, launch file, README command, or discovered plugin;
- obtain elevated privileges;
- follow symlinks outside approved package roots;
- read device, procfs, sysfs, socket, secret, or unbounded virtual files as package content; or
- contact a remote vulnerability or package service unless a separate policy explicitly enables
  network access.

If file hashing is enabled, policy MUST bound file count, individual file size, aggregate bytes,
elapsed time, and allowed roots.

## Limits, completeness, and batching

Artifact collection limits and Coding Agent context limits are separate controls.

### Resolution safety limits

Recommended initial defaults are:

| Limit | Default | Required behavior at the limit |
|---|---:|---|
| direct relevance candidates | 1,000 | record omitted count; mark `PARTIAL` |
| dependency nodes | 20,000 | mark closure incomplete |
| dependency edges | 100,000 | mark closure incomplete |
| dependency depth | unlimited while node/edge/time limits permit | report the stopping limit |
| hashed files per package | 10,000 | mark hash coverage partial |
| aggregate bytes hashed per package | 2 GiB | mark hash coverage partial |
| individual file size hashed | 256 MiB | record skipped file and reason |

Candidate omission or a dependency/hash boundary is explicit and makes the corresponding result
`PARTIAL`. The target policy shape for roadmap deep inspection is:

```yaml
software_discovery:
  max_direct_candidates: 1000
  dependency_max_nodes: 20000
  dependency_max_edges: 100000
  hash_max_files_per_package: 10000
  hash_max_bytes_per_package: 2147483648
  hash_max_individual_file_bytes: 268435456
agent_handoff:
  context_window_tokens: null  # resolve from the selected model or configure explicitly
  discovery_context_fraction: 0.25
  reserved_context_fraction: 0.50
  discovery_context_absolute_cap_tokens: 32000
```

The absolute token cap is an upper bound, not an allocation promise. The effective budget is still
reduced when the selected model has a smaller known context window.

### Coding Agent context budget

The normal Build prompt receives only:

- canonical CLI capability results;
- missing dependencies, conflicts, and stale vulnerability-data warnings; and
- bounded direct dependency summaries with artifact references.

The agent-facing discovery budget MUST be calculated from the selected model context window. The
default usable budget for discovery material is the smaller of a configured absolute cap and 25%
of the model context window. At least 50% of the context window MUST remain reserved for repository
context, instructions, tool results, and the final answer. If the model context size cannot be
resolved from the selected provider and model, `context_window_tokens` MUST be configured
explicitly. Otherwise optional agent batch analysis is `NOT_PROBED`; deterministic relevance still
completes without sending dependency batches to an agent.

When relevant package summaries exceed the discovery budget, they are split into deterministic
batches ordered by `(relevance, operation, manager, package_id)`. Every batch includes:

```json
{
  "batch_id": "packages-0003-of-0012",
  "source_relevance_sha256": "...",
  "first_candidate_id": "...",
  "last_candidate_id": "...",
  "record_count": 500,
  "estimated_tokens": 18000
}
```

Each optional agent batch produces schema-validated findings. A deterministic merger deduplicates
findings by stable IDs and verifies that every expected batch completed before producing the final
summary. Missing batches make the analysis `PARTIAL`; they MUST NOT disappear from the audit trail.
Token counting SHOULD use the selected model tokenizer. A documented conservative byte-based
estimate is permitted only as a fallback.

## Artifacts

The implemented software artifact layout is:

```text
artifacts/discovery/<robot_id>/latest/
|-- software_summary.json
`-- package_relevance.json
```

Planned deep-inspection and optional agent-review artifacts extend it as follows:

```text
artifacts/discovery/<robot_id>/latest/
|-- dependency_graph.json
|-- dependency_findings.json
|-- deep_inspection/
|   `-- <package-id>.json
|-- vulnerability_findings.json
`-- agent_batches/
    |-- index.json
    `-- packages-0001.json
```

`software_summary.json` is the only software artifact included directly in the normal Coding Agent
context. `package_relevance.json` is accessed by reference when detailed dependency evidence is
required.

## Build-stage gates

Discovery and Build assessment use these rules:

- a missing `DIRECT` dependency for a required standard operation blocks that operation;
- an installed direct dependency with an unsatisfied version constraint remains an explicit
  `VERSION_CONFLICT` unresolved Build input;
- unknown vulnerability state produces a warning, not a clean result;
- a critical vulnerability in a directly relevant runtime package is a policy finding and may block
  Build according to configured severity policy;
- unknown direct dependency state MUST NOT be labeled compatible merely because no conflict was
  observed; and
- write or motion operations remain `DISCOVERED_UNVERIFIED` until adapter conformance, controlled
  physical validation, and required approval complete.

## Implementation sequence and acceptance criteria

Implementation proceeds in this order. Direct Python/ROS relevance, bounded handoff, and report
references are implemented; the remaining items keep their order as roadmap work:

1. introduce normalized relevance and finding schemas;
2. add ROS and current-Python metadata resolvers;
3. make the canonical CLI registry a versioned discovery input;
4. implement deterministic relevance resolution and dependency comparison;
5. add bounded file/checksum and vulnerability adapters; and
6. add context-aware batching and deterministic merge only for tasks that require agent review.

Acceptance requires tests proving that:

- candidate-limit stops are reported as `PARTIAL` with the exact limit named;
- every canonical CLI operation receives an explicit resolution state;
- only CLI-, runtime-, source-, ROS-, or URDF-relevant packages receive deep inspection;
- write and motion candidates are never executed during discovery;
- agent batches never exceed their computed budget and missing batches prevent a complete result;
- secrets and package file contents are absent from prompts and summary artifacts; and
- identical manifests, ROS indexes, and policies produce deterministic normalized results.

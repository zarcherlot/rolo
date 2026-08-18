# Software inventory and canonical-CLI-driven discovery

## Status and scope

This document defines the target design for Build-stage software discovery. The current
implementation has a streaming, chunked `dpkg-query` baseline inventory and a generated tool
catalog; it does not yet implement the additional ecosystem collectors, relevance resolver, deep
inspection, or batched agent handoff specified here.

The design has two complementary inputs:

```text
installed packages + source + processes + ROS + URDF
                         |
                         v
                 normalized host facts
                         |
canonical CLI registry -> relevance resolver -> capability evidence and dependency findings
```

The package inventory answers "what is installed?" The canonical CLI registry answers "which of
those packages can provide or support a standard operation?" Collection and relevance resolution
are deterministic program responsibilities. A Coding Agent may consume their artifacts, but it is
not responsible for deciding whether collection was complete.

## Required behavior

Build discovery MUST:

1. collect baseline metadata for every package visible to each supported and applicable collector;
2. report collector coverage, errors, limits, and completeness without silent truncation;
3. use the canonical CLI registry as the primary filter for relevant software;
4. supplement CLI relevance with evidence from source manifests, running processes, ROS, URDF,
   services, and loaded plugins;
5. deeply inspect relevant packages only;
6. keep full inventory artifacts outside the Coding Agent prompt;
7. batch any agent-facing package analysis within an explicit context budget; and
8. preserve read-only discovery and never execute newly discovered binaries.

"Complete inventory" means that every applicable supported collector completed within policy and
reported all records known to that collector. It does not mean that rolo can prove the absence of
software installed outside all known package managers. Unsupported or unavailable collectors MUST
be reported and make coverage explicit.

## Baseline package metadata

Every normalized package record MUST contain:

```json
{
  "schema_version": "robot-software-package/v1",
  "package_id": "dpkg:arm64:ros-humble-nav2-bringup",
  "name": "ros-humble-nav2-bringup",
  "version": "1.1.18-1jammy",
  "architecture": "arm64",
  "status": "installed",
  "manager": "dpkg",
  "origin": "packages.ros.org",
  "install_root": "/opt/ros/humble",
  "collector": "linux.dpkg",
  "collector_provenance": "dpkg-query",
  "collected_at": "2026-08-17T00:00:00Z"
}
```

`origin` is the installation repository, channel, overlay, or other package source when it can be
determined without network access. `collector_provenance` identifies how the record was obtained.
Unknown fields remain `null`; discovery MUST NOT guess them.

Initial collectors SHOULD cover:

- the native operating-system package database (`dpkg` first, with adapters for `rpm`, `apk`, and
  `pacman` when those platforms are supported);
- ROS packages and their prefixes from the ament index for each sourced base installation and
  overlay;
- distributions visible to the Python interpreter running rolo through metadata-only APIs;
- declared project dependencies in `package.xml`, `pyproject.toml`, and supported build manifests;
- optional ecosystem collectors such as Snap, Flatpak, conda, npm, and Cargo only when detected
  and enabled by policy.

A collector MUST emit a status record even when it cannot run:

```json
{
  "collector": "linux.rpm",
  "status": "NOT_APPLICABLE",
  "record_count": 0,
  "complete": true,
  "truncated": false,
  "reason": "rpm package database was not detected"
}
```

Collector status values are `SUCCEEDED`, `PARTIAL`, `FAILED`, `UNAVAILABLE`, and
`NOT_APPLICABLE`. `complete` MUST be false for `PARTIAL`, `FAILED`, or any limit-induced stop.

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

The resolver assigns package relevance using deterministic evidence in this order:

1. direct match to a canonical CLI package, ROS, plugin, executable, or source selector;
2. direct declaration in a discovered source manifest for a matching operation;
3. ownership of a running robot process, service executable, loaded plugin, or ROS package prefix;
4. reference from URDF or robot configuration; and
5. transitive dependency of a package selected by steps 1-4.

Normalized relevance levels are:

- `DIRECT`: matched by a standard CLI selector or direct runtime/source/URDF evidence;
- `TRANSITIVE`: in the dependency closure of a `DIRECT` package;
- `ENVIRONMENT`: visible in the same runtime, ROS overlay, or language environment but not selected;
- `INVENTORY_ONLY`: installed with no discovered relationship to a standard operation.

Canonical CLI selectors are the primary filter. Runtime, source, and URDF evidence may add relevant
packages when a vendor-specific implementation is not yet represented in the registry. Such
additions MUST be attributed and remain unverified until the registry or an adapter is updated.

## Deep inspection

Deep inspection runs only for `DIRECT` packages and their bounded `TRANSITIVE` dependency closure.
It collects:

- declared dependencies and the resolved dependency graph;
- package-owned file paths;
- package-manager-provided checksums where available;
- hashes of policy-approved regular files when authoritative checksums are unavailable;
- package source, signature, and repository metadata when locally available; and
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

Prefer package-manager checksums over rereading installed files. If file hashing is enabled, policy
MUST bound file count, individual file size, aggregate bytes, elapsed time, and allowed roots.

## Limits, completeness, and batching

Artifact collection limits and Coding Agent context limits are separate controls.

### Collector safety limits

Recommended initial defaults are:

| Limit | Default | Required behavior at the limit |
|---|---:|---|
| collector timeout | 30 s | stop collector; mark `PARTIAL` |
| raw bytes per collector | 50 MiB | finish current record; close chunk; mark `PARTIAL` if more records remain |
| records per artifact chunk | 1,000 | open the next chunk; do not truncate |
| bytes per artifact chunk | 2 MiB | open the next chunk; do not truncate |
| dependency nodes | 20,000 | mark closure incomplete |
| dependency edges | 100,000 | mark closure incomplete |
| dependency depth | unlimited while node/edge/time limits permit | report the stopping limit |
| hashed files per package | 10,000 | mark hash coverage partial |
| aggregate bytes hashed per package | 2 GiB | mark hash coverage partial |
| individual file size hashed | 256 MiB | record skipped file and reason |

Chunk rollover is not truncation. A collector is complete when all records were written across all
chunks. Hitting a collector-wide byte, time, dependency, or hash limit is truncation and MUST be
visible in its status and in the Build-stage unresolved dependencies.

For example, 2,505 `dpkg-query` records produce three chunks containing 1,000, 1,000, and 505
records. The index covers all three chunks and the collector remains `SUCCEEDED`; the 1,000-record
limit is a rollover boundary, not a total inventory cap.

The implementation MUST stream or page collector output. It MUST NOT capture an unbounded package
inventory in one subprocess buffer or one in-memory JSON object.

The existing general-purpose `max_command_output_bytes` and `max_discovered_items` settings MUST
NOT be reused to silently cap the normalized package inventory. Package collectors need independent
streaming and chunk limits. The target policy shape is:

```yaml
software_inventory:
  collector_timeout_s: 30
  max_raw_bytes_per_collector: 52428800
  records_per_chunk: 1000
  bytes_per_chunk: 2097152
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

Full inventory chunks MUST NOT be embedded in `capability_manifest` or a Coding Agent prompt. The
normal Build prompt receives only:

- collector coverage and completeness;
- counts by manager, architecture, status, and relevance;
- canonical CLI capability results;
- missing dependencies, conflicts, and stale vulnerability-data warnings;
- relevant package summaries; and
- artifact references for full inventory and deep-inspection results.

The agent-facing discovery budget MUST be calculated from the selected model context window. The
default usable budget for discovery material is the smaller of a configured absolute cap and 25%
of the model context window. At least 50% of the context window MUST remain reserved for repository
context, instructions, tool results, and the final answer. If the model context size cannot be
resolved from the selected provider and model, `context_window_tokens` MUST be configured
explicitly. Otherwise agent batch analysis is `NOT_PROBED`; discovery still writes the complete
inventory and deterministic relevance artifacts without sending package batches to an agent.

When relevant package summaries exceed the discovery budget, they are split into deterministic
batches ordered by `(relevance, operation, manager, package_id)`. Every batch includes:

```json
{
  "batch_id": "packages-0003-of-0012",
  "source_inventory_sha256": "...",
  "first_package_id": "...",
  "last_package_id": "...",
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

The target artifact layout is:

```text
artifacts/discovery/<robot_id>/latest/
|-- software_summary.json
|-- package_inventory/
|   |-- index.json
|   |-- dpkg-0001.jsonl
|   |-- python-0001.jsonl
|   `-- ros-0001.jsonl
|-- package_relevance.json
|-- dependency_graph.json
|-- dependency_findings.json
|-- deep_inspection/
|   `-- <package-id>.json
|-- vulnerability_findings.json
`-- agent_batches/
    |-- index.json
    `-- packages-0001.json
```

`package_inventory/index.json` records chunk hashes, record counts, collector states, limits, and
overall completeness. Full inventory artifacts are immutable for a discovery run. Summaries MUST
reference the discovery ID and inventory hash so results from different snapshots cannot be mixed.

`software_summary.json` is the only package artifact included directly in the normal Coding Agent
context. Other artifacts are accessed by reference when a task specifically requires them.

## Build-stage gates

Discovery and Build assessment use these rules:

- a missing `DIRECT` dependency for a required standard operation blocks that operation;
- a collector that is applicable but incomplete makes software discovery `PARTIAL`;
- unknown vulnerability state produces a warning, not a clean result;
- a critical vulnerability in a directly relevant runtime package is a policy finding and may block
  Build according to configured severity policy;
- incomplete inventory MUST NOT be labeled compatible merely because no conflict was observed; and
- write or motion operations remain `DISCOVERED_UNVERIFIED` until adapter conformance, controlled
  physical validation, and required approval complete.

## Implementation sequence and acceptance criteria

Implementation should proceed in this order:

1. introduce normalized package, collector-status, chunk-index, relevance, and finding schemas;
2. replace bounded in-memory `dpkg-query` capture with a streaming, chunked collector;
3. add ROS and current-Python metadata collectors;
4. make the canonical CLI registry a versioned discovery input;
5. implement deterministic relevance resolution and dependency comparison;
6. add bounded file/checksum and vulnerability adapters;
7. remove full software inventory from the default Coding Agent context and add summaries/references;
8. add context-aware batching and deterministic merge only for tasks that require agent review.

Acceptance requires tests proving that:

- more than 1,000 packages are retained without loss across chunks;
- chunking does not change normalized inventory content or hashes;
- limit-induced stops are reported as `PARTIAL` with the exact limit named;
- unsupported collectors are distinguishable from empty collectors;
- every canonical CLI operation receives an explicit resolution state;
- only CLI-, runtime-, source-, ROS-, or URDF-relevant packages receive deep inspection;
- write and motion candidates are never executed during discovery;
- agent batches never exceed their computed budget and missing batches prevent a complete result;
- secrets and package file contents are absent from prompts and summary artifacts; and
- identical package databases and policies produce deterministic normalized results.

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

## Authorized real-Agent result

The fixture owner explicitly authorized transmission of the bounded source-derived context. A real
Codex run was then completed in `shadow` mode with model `gpt-5.4`:

- Discovery ID: `disc-20260822T094205-483f7c96`
- Heuristic status: `AGENT_COMPLETED`
- Registry slice: 20 of 294 Operations
- Inferred Operations: `app.camera.snapshot`, `app.teleop.velocity`
- Accepted proposals: 2 of 2
- Rejected proposals: 0
- Invalid evidence references: 0
- Applied candidates: 0 (`shadow` mode)
- Eligible Operations: 0
- Deferred reason for both deterministic candidates: `TARGET_ROUTE_NOT_OBSERVED`
- Missing evidence: 16 items
- Release influence: false

`rolo-adapt-discovery` correctly proposed no repeated action: the source-interface query was already
complete and the remaining gaps require `BUILT_WORKSPACE`, `TARGET_HOST`, or `RUNTIME_ROS`. It
preserved 38 unresolved ROS dependencies as Unknowns.

`rolo-operation-mapping` proposed the two evidence-bound Operations above and requested runtime
route observation for `/image_raw` and `/cmd_vel`. The deterministic Validator accepted both as
proposals, but neither proposal was allowed to become Verified, eligible, registered, or released.

An isolated `rolo-wiki-authoring` caller validation against the same frozen discovery produced seven
merged findings and eight exact Unknown assessments. Provenance was caller-pinned to skill version
`1.0.0` and model `gpt-5.4`; evidence references and Unknown text both passed their caller-owned
allowlists without fallback.

The canonical Agent artifacts are under:

```text
.validation-wheeltec/artifacts/discovery/demo_diff/runs/
  disc-20260822T094205-483f7c96/heuristic/
```

## Real-provider debugging findings

The real run exposed integration failures that fixture providers could not reveal:

1. Codex temporary workspaces are intentionally not Git repositories. Providers must pass
   `--skip-git-repo-check` while retaining `--sandbox read-only` and `--ephemeral`.
2. Canonical Pydantic schemas are richer than the Codex Structured Outputs subset. The provider
   schema copy removes unsupported property-count keywords, marks every object property required,
   closes unused dynamic objects, fixes provenance hash-map keys to the caller-known set, and prunes
   unreachable definitions. The canonical schemas and post-generation Pydantic validation remain
   unchanged.
3. Agent self-reported model and skill versions are not trusted. Configured model identity and the
   trusted Wiki skill version are caller-owned provenance.
4. Wiki evidence references and Unknown assessments must be supplied as bounded exact allowlists.
   Natural-language path instructions alone caused correct fail-closed rejection.
5. The installed Codex CLI and desktop model cache were schema-skewed in this environment. Explicitly
   pinning `CODING_AGENT_MODEL=gpt-5.4` avoided treating the stale cache as model selection authority.
6. WebSocket requests timed out and Codex recovered through HTTPS. Provider timeouts therefore need
   to cover the transport fallback as well as model generation.

## Same-discovery three-Agent acceptance

The current integration baseline was rerun after the provider-boundary fixes with all three trusted
skills enabled in one canonical discovery. The run retained the fixture owner's existing bounded
source-context authorization, used model `gpt-5.4`, disabled the unrelated prose polisher, and kept
heuristic activation in `shadow` mode:

- Discovery ID: `disc-20260822T112439-323df424`
- `rolo-adapt-discovery` fallback: none
- `rolo-operation-mapping` fallback: none
- `rolo-wiki-authoring` fallback: none
- Target Operation slice: 20 of 294
- Accepted proposals: 2 of 2
- Invalid evidence references: 0
- False-positive rate: 0
- Inferred Operations: `app.camera.snapshot`, `app.teleop.velocity`
- Applied candidates: 0; release influence: false
- Wiki findings: 6 total, 4 Agent-authored
- Wiki Unknown assessments: 38, all Agent-authored and allowlist validated
- Release-blocking evidence gaps: 16

The immutable artifacts are under:

```text
.validation-wheeltec-full-head3/artifacts/discovery/demo_diff/runs/
  disc-20260822T112439-323df424/
```

This run supersedes the earlier isolated Wiki caller check as the canonical real-Agent acceptance.
It still does not qualify a target release: the two source-derived routes remain unobserved on a
target runtime, no candidate was applied, and no robot operation was invoked.

## Deterministic hardcoding audit

The repeated two-Operation result was traced to two production-code dictionaries rather than to a
Wheeltec repository-name special case. One dictionary recognized a small fixed set of ROS topic
tokens; a second converted only velocity, odometry, map, and camera semantics into Operations. The
source scanner was already finding additional literal interfaces, including `imu` and
`odom_combined`, but the old candidate builder did not expose the full rule result. It also did not
recover `/scan` from the vendor lidar parameter file because that YAML contains a tab that strict
YAML parsers reject.

The corrected current-HEAD run uses Registry-validated data rules and bounded extraction of literal
topic parameters from inert configuration and C++ defaults:

- Discovery ID: `disc-20260823T031945-6730876e`
- Heuristic status: `AGENT_COMPLETED`
- Discovery Planning fallback: none
- Semantic bindings: 5
- Operation candidates: 5
- `app.camera.snapshot` → `/image_raw`
- `app.imu.sample` → `/imu`
- `app.lidar.snapshot` → `/scan`
- `app.localization.status` → `/odom_combined`
- `app.teleop.velocity` → `/cmd_vel`
- Mapping proposals: 5 accepted, 0 rejected
- Invalid evidence references and false positives: 0
- Wiki Agent: 4 Agent findings and 4 Agent Unknown assessments
- Missing evidence: 18; release influence: false

All five remain `DISCOVERED_UNVERIFIED`; this result expands static applicability without creating
runtime truth or release authority. The immutable report is under:

```text
.validation-wheeltec-hardcode-agent3/artifacts/discovery/demo_diff/runs/
  disc-20260823T031945-6730876e/
```

The Agent Mapping boundary now exposes stable short `ev:<digest>` IDs in its output schema. Each
Operation receives only its own deterministic evidence, route, executable, and hardware allowlists.
The provider resolves accepted IDs back to canonical source references before normal validation, so
long Windows paths cannot be abbreviated by the Agent and cross-Operation references remain
fail-closed.

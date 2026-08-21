# Adapt Capability Development Plan

## 1. Objective

Reduce the Registry Operation and prompt burden seen by the Adapt Agent while keeping the
current product baseline compatible. Establish platform-neutral capability and provider
extension points for future OS and middleware support, without implementing a provider for a
specific OS or middleware in this development cycle.

The implementation must preserve the current 294-operation Registry, operation identifiers,
contract digests, active releases, adapter bundles, Linux behavior, and ROS behavior.

## 2. Scope

### 2.1 Included

- Classify all current operations as `AGENT_NATIVE`, `PRODUCT_BUILTIN`, `TARGET_ADAPTER`, or
  `PLATFORM_SPECIFIC` in a governance overlay that does not change Registry digests.
- Introduce a deterministic `TargetOperationSlice` with dependency closure.
- Inject only the current task and its target-adapter operations into the Adapt Agent context.
- Replace the full Agent snapshot with a lightweight global index plus focused operation detail.
- Add bounded operation list, search, pagination, and batch inspection.
- Add prompt and inspection-response budgets and telemetry.
- Define platform-neutral semantic layers: `hardware`, `os`, `middleware`, and `application`.
- Define platform-neutral capability, provider manifest, platform profile, provider SPI, and
  capability resolver contracts.
- Validate the extension contracts with fake providers and shadow resolver artifacts.
- Retain the existing Linux and ROS paths unchanged as the compatibility baseline.

### 2.2 Deferred until productization

- Windows, FreeRTOS, Linux, QNX, Zephyr, or other OS provider implementation or refactoring.
- ROS, CyberRT, DDS-vendor, or other middleware provider implementation or refactoring.
- PowerShell, serial, JTAG/RTT, vendor RPC, or remote provider transports.
- Renaming `linux.*` to `os.*`, `ros.*` to `middleware.*`, or changing current layer values.
- Removing any of the current 294 Registry Operations.
- Dual production Tool Catalogs, Adapter Bundle v3, and production provider deployment.
- OS policy gateways, engineering/admin catalogs, and real cross-platform conformance matrices.

## 3. Baseline compatibility constraints

The first two implementation phases must satisfy all of the following:

- Registry Operation count remains 294.
- Existing operation names and serialized layer values remain unchanged.
- Existing contract SHA-256 values and the v1 Registry/Catalog digest remain unchanged.
- Existing adapter bundles and active releases continue to load.
- Existing invocation policies and audit consumers remain valid.
- Existing Linux and ROS CLI and discovery behavior remain unchanged.
- Existing `linux.json`, `ros.json`, and discovery probe keys remain available.
- New capability and provider artifacts do not participate in production publication gates.

## 4. Development workstreams

### 4.1 Operation governance

Create a complete operation-disposition ledger with these fields:

- current operation and layer;
- target semantic layer;
- execution class;
- portable-semantics flag;
- future capability identifier;
- migration status and rationale.

The ledger is an overlay and must not be incorporated into the v1 Registry digest.

### 4.2 Adapt Agent context

Implement `TargetOperationSlice` using observed candidates and eligible task operations as
seeds. Deterministically include paired, compensation, replacement, observation, stop, and
rollback dependencies when required.

Only `TARGET_ADAPTER` operations become adapter coding work. `AGENT_NATIVE` operations may be
used for bounded evidence discovery, and `PRODUCT_BUILTIN` operations remain product-owned.

The Agent boot context must contain the current task, slice identifier, focused operations,
deferred summary, artifact references, and safety constraints. The complete Adapt Plan remains
an artifact and is not embedded in full.

Default budgets:

- boot context: at most 2,000 tokens;
- operation list: 20 default and 50 maximum;
- batch inspection: at most 8 operations;
- one inspection response: at most 16 KiB;
- one task: at most 20 primary target-adapter operations.

### 4.3 Platform-neutral capability foundation

Define, but do not bind to real platforms:

- `CapabilityDescriptor`;
- `ProviderManifest`;
- `PlatformProfile`;
- provider SPI;
- deterministic `CapabilityResolver` result;
- shadow resolution artifact.

Provider kinds, transport kinds, OS families, and middleware kinds must be open strings rather
than closed Windows/Linux/FreeRTOS/ROS/CyberRT enums. Unknown providers and missing
capabilities are valid states. Platform-specific data belongs in bounded extension objects.

The four target semantic layers are a new overlay. Current v1 Registry layer values remain the
source of truth until a future product migration.

### 4.4 Verification

Add tests for:

- the complete operation-disposition ledger;
- deterministic slice and dependency closure;
- list pagination, search, truncation, and batch bounds;
- prompt and response size budgets;
- Registry growth by 1,000 unrelated operations without material prompt growth;
- fake providers representing full OS, RTOS-like, service-less, filesystem-less,
  graph-middleware, and channel-only capability sets;
- unknown provider and transport kinds;
- shadow resolver behavior for unavailable and ambiguous capabilities;
- unchanged current Linux/ROS CLI behavior, bundles, releases, and v1 digests.

## 5. Worktree ownership

### `codex/adapt-operation-governance`

Owns the disposition ledger, its schema and validation, and governance documentation.

### `codex/adapt-context-slice`

Owns `TargetOperationSlice`, compact Agent context, focused snapshot, bounded query commands,
budgets, telemetry, and their tests.

### `codex/adapt-capability-spi`

Owns platform-neutral capability models, provider contracts, resolver, fake providers, shadow
artifacts, and their tests. It must not implement a specific OS or middleware provider.

### `codex/adapt-capability-integration`

Owns merges, conflict resolution, schema export, generated schemas, shared documentation,
cross-workstream tests, and final acceptance. High-conflict generated files are updated here
after feature branches merge.

Merge order:

1. operation governance;
2. capability SPI;
3. context slice;
4. integration schemas, documentation, and full verification.

## 6. Delivery phases

### Phase 1: context governance

Deliver the disposition ledger, target slice, compact prompt, focused snapshot, bounded query
surface, and budget telemetry. The production Registry and runtime remain unchanged.

### Phase 2: platform-neutral extension points

Deliver capability/provider schemas, provider SPI, resolver, fake-provider conformance, and
shadow artifacts. They do not participate in active publication or invocation.

### Productization phase (deferred)

Select supported OS and middleware based on product requirements, then implement and validate
the corresponding providers, transports, production resolver, new Registry/Catalog versions,
and compatibility migration.

## 7. Acceptance criteria

- All existing tests that define current behavior continue to pass.
- The current Registry remains at 294 operations and its v1 digest is unchanged.
- Existing releases and bundles do not become stale because of this work.
- The Adapt Agent sees and implements only the bounded current target slice.
- Adding unrelated Registry Operations does not linearly increase the boot prompt.
- Capability contracts model environments without process, service, filesystem, graph, or
  shell assumptions.
- No specific new OS or middleware provider is added in this cycle.

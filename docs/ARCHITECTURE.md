# rolo three-stage architecture

rolo exposes one ordered lifecycle:

```text
adapt -> diagnose -> verify (optional formal acceptance)
```

The names describe rolo's agents and avoid colliding with the user's development commands.

## Stage contracts

| Stage | Required input and work | Required output | Agent role |
|---|---|---|---|
| `adapt` | bounded host/application discovery, editable robot Wiki, product operation matching, adapter implementation, State Graph construction, independent conformance | robot Wiki, immutable machine-evidence manifest, gated Active Tool Catalog, State Graph baseline, conformance report, adapt handoff | Adapter Agent; Codex by default |
| `diagnose` | validated adapt handoff, unresolved semantics, user diagnosis/safety constraints | diagnosis, validated/rejected semantics, frozen configuration, tuning evidence, diagnosis handoff | Diagnosis Agent; `robot_use` optional |
| `verify` | validated diagnosis handoff and admitted acceptance constraints | full regression, report, evidence package, verification handoff | Verification Agent when selected |

Formal verification is optional; affected smoke and safety regression after every retained diagnosis
change is not optional.

## Source layout

```text
src/rolo/stages/
├── adapt/       # discovery, Adapter Agent run, frozen output, gate, handoff
├── diagnose/    # Diagnosis Agent gate, constrained tuning, robot_use
└── verify/      # optional formal verification gate
```

`artifact_paths.py` is the single path vocabulary. Stage artifacts exist only under `adapt/`,
`diagnose/`, and `verify/`. `cli.py` assembles command groups, while shared services remain outside
stage packages.

## Evidence and handoff flow

1. Discovery writes probe results, capability/semantic evidence, operation candidates, and a report into
   `discovery/<robot>/runs/<discovery_id>/`.
2. `robot_wiki.md` presents the stack as an editable engineering Wiki. Probe facts and tables are
   rendered deterministically; an optional model adds only a bounded narrative summary and falls
   back automatically. The Wiki is intentionally excluded from hashes so the robot's chief
   Wiki can be consumed and edited downstream; `wiki_generation.json` retains generation
   provenance in the machine manifest.
3. `manifest.json` hashes the machine-readable evidence. `latest.json` is only an atomic index;
   readers revalidate the manifest and report before use.
4. `adapt run` derives an in-memory plan carrying the manifest identity and current Wiki reference,
   then revalidates machine evidence before preparing or starting the Adapter Agent. Its boot
   context is a compact Operation Workset summary, not the complete Registry, Wiki, or executable
   inventory. A read-only launcher pinned to that discovery lets the Agent retrieve one contract,
   candidate, executable, launch record, dependency view, Wiki section, or evidence snippet at a time.
5. The product-owned Canonical Operation Registry defines the complete operation vocabulary,
   while independently versioned YAML contracts define canonical CLI, schemas, errors, semantics,
   risk and access policy. Each adapter entry and Tool Catalog descriptor binds the exact contract
   version and SHA-256; runtime rejects mismatches. Discovery cannot add operations
   to this Registry; it can only associate host evidence with existing operation IDs.
   The standardization scope and maturity gates are documented in
   [`OPERATION_CONTRACT_STANDARDIZATION.md`](OPERATION_CONTRACT_STANDARDIZATION.md).
6. `adapt run` creates a fresh temporary adapter project outside the rolo source tree. The Adapter
   Agent writes a standalone `robot-adapter-rpc/v1` implementation, a `robot-adapter-bundle/v2`
   manifest listing one entrypoint plus bounded support files by SHA-256, a State Graph proposal,
   and conformance files. It never writes a Tool Catalog. The project is deleted after the run.
7. The same `adapt run` freezes those proposed files before an independent rolo gate validates
   identities, eligible-operation coverage, complete product-owned schemas and policy metadata,
   package bindings, and verified route availability. Rolo discards the Agent graph proposal as an
   authority source and deterministically builds the published `robot-state-graph/v2` from the
   gated bundle and discovery routes. The Adapter Agent's local-static booleans
   are retained as advisory audit input; they are not represented as Rolo proof of runtime
   behavior, idempotency, cancellation, reliability, or safety. The gate also executes the
   package's bounded `describe` command and requires every
   generated operation to resolve to exactly one bundle entrypoint. The Agent reports only
   `LOCAL_STATIC` deterministic tests for bundle candidates; it does not report on Rolo builtin
   operations. Rolo owns and validates builtin contracts independently. Rolo also establishes that
   an exactly normalized Route Evidence v2 endpoint was observed, without requiring the operation
   itself to report success. Route identity covers ROS topic/service/action, CLI, and device routes
   and can bind interface type/schema digest, provider identity, runtime revision, and observation
   time when the target exposes them.
   Adapt does not judge physical outcome
   correctness, reliability, performance, or safety; those are Diagnosis responsibilities.
   The gate matches candidate endpoint evidence against immutable runtime introspection; it does not
   trust an Adapter Agent self-assessment and does not actuate the operation to prove availability.
   Source, documentation, mocks, and simulation cannot satisfy production target-runtime
   availability. Test-only simulated providers exercise the same gate in automated acceptance tests,
   but are neither configured nor shipped as production defaults.
   Rolo composes the Active Tool Catalog from the product Registry, discovery candidates, builtin
   implementations and the verified bundle; unknown or extra bundle operations are rejected.
   Eligibility is per operation. A nongateable contract, missing declared route, or unobserved target
   route leaves only that operation `UNAVAILABLE` with a deferral reason; it does not block unrelated
   eligible operations.
8. A passed gate publishes an immutable release under external `ROLO_OUTPUT_DIR`, binds every adapter
   file,
   Active Tool Catalog, State Graph, conformance and gate report by hash, writes the audit handoff, and only
   then transactionally updates both current indexes with compensation rollback. A failed publication
   restores both prior indexes and removes the incomplete release. The release also binds a stable
   operation-scoped target fingerprint. Runtime access rejects a release after relevant route,
   executable, hardware, platform, or admitted ROS runtime-context facts change. Newly discovered
   facts unrelated to the bundle do not force needless regeneration. Scoped executable and hardware
   evidence is selected only through exact `executable_id` and `hardware_resource_id` references;
   names and substrings are never used as release bindings. Before the atomic current pointer moves,
   the candidate passes the same manifest, complete file-set, identity, contract, catalog, State
   Graph, conformance, passed-gate, and freshness checks used by runtime loading. A rejected
   candidate cannot replace the existing current release.
9. The Adapter Agent queries a bounded workspace-local snapshot and exact artifact Schemas. Its
   deterministic handoff pack validates paths and hashes, runs only an advisory bounded `describe`
   inside the Agent sandbox (never `invoke`), returns only final file payloads in a structured result,
   and removes Agent-created workspace files. Rolo
   reconstructs and gates the
   snapshot without trusting Agent filesystem access.
10. Diagnose validates the full adapt handoff; Verify validates a structured diagnosis handoff.
   Merely creating a file at a handoff path never opens the next gate.

The Adapter Agent provider is configurable through `CODING_AGENT_*` settings for compatibility.
Secrets remain process-local; plans and audit artifacts contain only secret-free configuration.
`ROLO_OUTPUT_DIR` must resolve outside the rolo source checkout. Runtime invocation reads only its
atomic `robots/<robot>/current.json` and calls the hash-verified adapter through the generic
`robotctl tool invoke OPERATION --robot ID --input JSON` dispatcher. Generated adapter and hardware
 provider processes share one argv-only runner with a sanitized environment, private temporary home,
 bounded stdout/stderr, timeout, process-tree termination, and POSIX resource limits. Generated code
 additionally requires a protected deployment-owned OS sandbox launcher. Without one, execution
 fails closed; the explicit unsandboxed development switch is limited to tests and offline demos.
 The launcher owns least-privilege service identity, filesystem and device allowlists, network policy,
 and platform-specific containment.

Discovery records only the explicit `AdapterRuntimeContext` contract: allowlisted, non-secret ROS
and middleware fields such as ROS domain, RMW implementation, profile file and existing overlay
paths. Unknown fields are forbidden in a release, while missing optional fields remain absent. The
gate binds its canonical form into release v2 and
the target fingerprint; `describe` and invocation receive that same context through the bounded
runner. Credentials and unrelated host environment variables are never admitted. Runtime catalog,
schema, State Graph and invoke access always revalidates the release against latest discovery; this
freshness check has no optional bypass.

The retained Adapt artifacts are deliberately small and centralized:

```text
adapt/<robot>/
├── latest/inputs.json             # mutable discovery-to-Adapt input index
├── latest.json                    # atomic index to the last passed handoff
└── runs/<run_id>/
    ├── prompt.txt
    ├── events.jsonl
    ├── stderr.log
    ├── result.json
    ├── run.json
    ├── output-snapshot/           # normalized immutable Agent proposals + hashes
    ├── gated-output/              # Rolo-owned Tool Catalog created after conformance
    ├── gate.json
    ├── handoff.json
    └── summary.json
```

The P0 acceptance boundaries and executable verification matrix are recorded in
[`P0_ADAPT_ACCEPTANCE.md`](P0_ADAPT_ACCEPTANCE.md).

The derived plan is not a mutable `latest/plan.json`; it is carried in the audit prompt. The output
schema is temporary, and a successful raw final message is normalized into `result.json` rather
than retained as a duplicate.

## Current implementation maturity

- Adapt implements enrollment, bounded discovery, an editable whole-stack robot Wiki, machine-only
  manifest validation, an isolated Adapter Agent project, bundle entrypoint validation, frozen
  output, independent conformance, external immutable release publication, and downstream
  validation. Robot-specific adapters never enter the rolo product source tree.
- Diagnose contains `robot_use`, a validated adapt-handoff gate, and a structured diagnosis-handoff
  contract. Closed-loop diagnosis transactions, tuning, and handoff production remain work.
- Verify contains validated upstream and structured output gates. Runtime acceptance DSL, oracle
  registry, autonomous execution, and evidence packaging remain work. Repository tests under
  `tests/` are engineering tests, not robot acceptance runs.

## CLI

```text
uv run robotctl adapt status|run|agent-config|enroll|discover
uv run robotctl diagnose status|robot-use
uv run robotctl verify status
uv run robotctl pipeline-status
```

The top-level `tool`, `hw`, `linux`, `middleware`, `ros`, and `app` commands remain the canonical
semantic introspection surface.

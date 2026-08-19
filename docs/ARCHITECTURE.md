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
   canonical CLI, schemas, error contract, risk and access policy. Discovery cannot add operations
   to this Registry; it can only associate host evidence with existing operation IDs.
6. `adapt run` creates a fresh temporary adapter project outside the rolo source tree. The Adapter
   Agent writes only a standalone `robot-adapter-rpc/v1` package, bundle manifest, State Graph, and
   conformance files. It never writes a Tool Catalog. The project is deleted after the run.
7. The same `adapt run` freezes those proposed files before an independent rolo gate validates
   identities, exact operation coverage, schemas, errors, idempotency, cancellation, declared
   risk/access metadata, and verified route availability. It also executes the
   package's bounded `describe` command and requires every
   generated operation to resolve to exactly one bundle entrypoint. The Agent reports only
   `LOCAL_STATIC` deterministic tests. Rolo independently establishes that an exactly normalized,
   structured target endpoint was observed, without requiring the operation itself to report success.
   Adapt does not judge physical outcome
   correctness, reliability, performance, or safety; those are Diagnosis responsibilities.
   The gate matches candidate endpoint evidence against immutable runtime introspection; it does not
   trust an Adapter Agent self-assessment and does not actuate the operation to prove availability.
   Source, documentation, mocks, and simulation cannot satisfy target-runtime availability.
   Rolo composes the Active Tool Catalog from the product Registry, discovery candidates, builtin
   implementations and the verified bundle; unknown or extra bundle operations are rejected.
8. A passed gate publishes an immutable release under external `ROLO_OUTPUT_DIR`, binds the package,
   Active Tool Catalog, State Graph, conformance and gate report by hash, writes the audit handoff, and only
   then transactionally updates both current indexes with compensation rollback. A failed publication
   restores both prior indexes and removes the incomplete release.
9. Diagnose validates the full adapt handoff; Verify validates a structured diagnosis handoff.
   Merely creating a file at a handoff path never opens the next gate.

The Adapter Agent provider is configurable through `CODING_AGENT_*` settings for compatibility.
Secrets remain process-local; plans and audit artifacts contain only secret-free configuration.
`ROLO_OUTPUT_DIR` must resolve outside the rolo source checkout. Runtime invocation reads only its
atomic `robots/<robot>/current.json` and calls the hash-verified adapter through the generic
`robotctl tool invoke OPERATION --robot ID --input JSON` dispatcher.

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

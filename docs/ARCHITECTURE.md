# rolo three-stage architecture

rolo exposes one ordered lifecycle:

```text
adapt -> diagnose -> verify (optional formal acceptance)
```

The names describe rolo's agents and avoid colliding with the user's development commands.

## Stage contracts

| Stage | Required input and work | Required output | Agent role |
|---|---|---|---|
| `adapt` | bounded host/application discovery, chief-engineer-maintained robot Wiki, canonical CLI implementation, State Graph construction, independent conformance | editable robot Wiki, immutable machine-evidence manifest, verified tool catalog, State Graph baseline, conformance report, adapt handoff | Adapter Agent; Codex by default |
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

1. Discovery writes probe results, capability/semantic evidence, tool candidates, and a report into
   `discovery/<robot>/runs/<discovery_id>/`.
2. `robot_wiki.md` presents the stack as an editable engineering Wiki. It is intentionally excluded
   from hashes so the robot's chief engineer can correct and extend it directly.
3. `manifest.json` hashes the machine-readable evidence. `latest.json` is only an atomic index;
   readers revalidate the manifest and report before use.
4. `adapt run` derives an in-memory plan carrying the manifest identity and current Wiki reference,
   then revalidates machine evidence before preparing or starting the Adapter Agent.
5. The Adapter Agent writes proposed workspace-relative tool catalog, State Graph, and conformance
   files. Executor success does not publish a handoff.
6. The same `adapt run` freezes those proposed files before an independent rolo gate validates
   identities, exact operation coverage, schemas, errors, idempotency, cancellation, safety,
   verified availability, and physical-result evidence for write/R3 operations.
7. A passed gate writes the immutable handoff under `adapt/<robot>/runs/<run_id>/` and atomically
   publishes only the hash-bound index `adapt/<robot>/latest.json`. A failed gate never changes the
   latest index.
8. Diagnose validates the full adapt handoff; Verify validates a structured diagnosis handoff.
   Merely creating a file at a handoff path never opens the next gate.

The Adapter Agent provider is configurable through `CODING_AGENT_*` settings for compatibility.
Secrets remain process-local; plans and audit artifacts contain only secret-free configuration.

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
    ├── gate.json
    ├── handoff.json
    └── summary.json
```

The derived plan is not a mutable `latest/plan.json`; it is carried in the audit prompt. The output
schema is temporary, and a successful raw final message is normalized into `result.json` rather
than retained as a duplicate.

## Current implementation maturity

- Adapt implements enrollment, bounded discovery, an editable whole-stack robot Wiki, machine-only
  manifest validation, a unified Adapter Agent run, frozen output, independent conformance,
  immutable handoff publication, and downstream validation. The Agent still owns
  repository-specific adapter and State Graph implementation.
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

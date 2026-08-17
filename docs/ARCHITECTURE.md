# rolo three-stage architecture

rolo exposes one ordered lifecycle while keeping safety, artifacts, schemas, services, and hardware
adapters as shared infrastructure.

```text
build -> debug -> test (optional formal acceptance)
```

## Stage contracts

| Stage | Inputs and work | Required output | Agent role |
|---|---|---|---|
| `build` | identity-only initialization, discovery-time URDF loading/parsing, bounded `hw/linux/ros/application` probes, unresolved semantics, discovered candidates, CLI implementation, conformance, State Graph construction | probes, discovered capability, semantic context, tool catalog, verified canonical CLI, State Graph baseline, build handoff | Coding Agent; Codex by default, vendor/model configurable |
| `debug` | build handoff, unresolved semantics, unverified source candidates, and user debug/safety constraints | diagnosis, validated/rejected semantics, frozen configuration, tuning evidence, debug handoff | Diagnosis Agent; `robot_use` optional |
| `test` | debug handoff, semantic validation context, and admitted acceptance constraints | final regression, semantic evidence, report, evidence package, test handoff | Test Agent when the optional stage is selected |

Optional formal testing does not make safety regression optional. Every debug-stage change must run
the affected smoke and safety regressions before it can be retained.

## Source layout

```text
src/rolo/stages/
├── build/    # enroll, probe, generate coding plan, CLI conformance, State Graph gate
├── debug/    # Diagnosis Agent loop, constrained tuning, robot_use
└── test/     # optional formal test generation and acceptance gate
```

`agentd.py`, `api.py`, and `runtime.py` remain shared services. Shared configuration, domain models,
artifacts, and the robot registry live under `src/rolo/core/`. Compatibility modules at
`rolo.enrollment`, `rolo.discovery`, and `rolo.robot_use` preserve top-level imports.

## Artifact flow

`robotctl init` registers only `robot_id` and runs doctor, robot-list validation, and repository
tests. It does not accept a URDF or approve motion. Discovery receives a URDF path explicitly,
records its path/hash, parses the full file, persists each probe, and writes `semantic_context.json` plus Build, Debug, and Test input
artifacts. The semantic context carries unresolved URDF fields and source-attributed launch/config
candidates. Candidates are explicitly unverified and have no safety authority. The build inputs
reference the probe artifacts, capability manifest, semantic context, binding candidates, and tool catalog. The
Coding Agent consumes those inputs and produces the verified CLI/State Graph handoff at
`build/<robot_id>/latest/handoff.json`, which gates the Diagnosis Agent.

The Stage 1 provider contract defaults to Codex but is vendor-neutral. `CODING_AGENT_PROVIDER`,
`CODING_AGENT_BASE_URL`, and `CODING_AGENT_MODEL` select a vendor, its official/default endpoint or
a compatible relay, and a model. `CODING_AGENT_API_KEY` remains process-local secret input. Plans
record only secret-free provider metadata and whether a key is configured. The explicit Codex
executor uses saved `codex login` authentication when no key is configured, runs non-interactively
with the `workspace-write` sandbox, and retains JSONL events plus a schema-validated final result.
It never promotes its own output to the build handoff.

The dependency lifecycle is `configuration -> allowlisted install -> verification -> execution`.
The uv workspace may install a missing executor and verify its version without automating login. The
build execution gate verifies the installed executable and authentication again, persists a
secret-free dependency report, and blocks execution unless the configured executor is ready.

## Current implementation maturity

- Build implements enrollment, bounded discovery, probe persistence, build inputs,
  a machine-readable Coding Agent plan, an allowlisted dependency installer and verifier, and an
  explicit Codex executor with audit artifacts.
  Adapter completeness, promotion, conformance execution, and the real State Graph store remain
  implementation work.
- Debug contains the `robot_use` supervision service and a hard build-handoff gate. Closed-loop
  diagnosis, transactions, tuning, and debug handoff production remain implementation work.
- Test exposes an optional stage gate. Runtime test DSL, Oracle registry, autonomous execution,
  final regression, and evidence packaging remain implementation work. Repository tests under
  `tests/` are engineering tests and are not Stage 3 robot acceptance tests.

## CLI

The stage-oriented commands are canonical for lifecycle orchestration:

```text
uv run robotctl build status|plan|agent-config|enroll|discover|tool
uv run robotctl debug status|robot-use
uv run robotctl test status
uv run robotctl pipeline-status
```

Top-level `enroll`, `discover`, `tool`, and layer commands remain available through `uv run robotctl`.

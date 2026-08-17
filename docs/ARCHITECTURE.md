# rolo three-stage architecture

rolo exposes one ordered lifecycle while keeping safety, artifacts, schemas, services, and hardware
adapters as shared infrastructure.

```text
build -> debug -> test (optional formal acceptance)
```

## Stage contracts

| Stage | Inputs and work | Required output | Agent role |
|---|---|---|---|
| `build` | bundle, enrollment, bounded `hw/linux/ros/application` probes, discovered candidates, CLI implementation, conformance, State Graph construction | probes, capability manifest, semantic binding candidates, tool catalog, verified canonical CLI, State Graph baseline, build handoff | Coding Agent; Codex by default, vendor/model configurable |
| `debug` | build handoff and user debug/safety constraints | diagnosis, frozen configuration, tuning evidence, debug handoff | Diagnosis Agent; `robot_use` optional |
| `test` | debug handoff and admitted acceptance constraints | final regression, report, evidence package, test handoff | Test Agent when the optional stage is selected |

Optional formal testing does not make safety regression optional. Every debug-stage change must run
the affected smoke and safety regressions before it can be retained.

## Source layout

```text
src/rolo/stages/
├── build/    # install, enroll, probe, generate coding plan, CLI conformance, State Graph gate
├── debug/    # Diagnosis Agent loop, constrained tuning, robot_use
└── test/     # optional formal test generation and acceptance gate
```

`agentd.py`, `api.py`, and `runtime.py` remain shared services. Shared configuration, domain models,
artifacts, and the robot registry live under `src/rolo/core/`. Compatibility modules at
`rolo.bundle`, `rolo.enrollment`, `rolo.discovery`, and `rolo.robot_use` preserve top-level imports.

## Artifact flow

Discovery persists each probe and writes `build/<robot_id>/latest/inputs.json`. The build inputs
reference the probe artifacts, capability manifest, binding candidates, and tool catalog. The
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
Deployment may install a missing executor and verify its version without automating login. The
build execution gate verifies the installed executable and authentication again, persists a
secret-free dependency report, and blocks execution unless the configured executor is ready.

## Current implementation maturity

- Build implements bundle creation, enrollment, bounded discovery, probe persistence, build inputs,
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
robotctl build status|plan|agent-config|bundle|enroll|discover|tool
robotctl debug status|robot-use
robotctl test status
robotctl pipeline-status
```

Legacy top-level `bundle`, `enroll`, `discover`, `tool`, and layer commands remain available.

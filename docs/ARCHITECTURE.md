# Robot Loop four-stage architecture

Robot Loop exposes one ordered lifecycle while keeping safety, artifacts, schemas, services, and
hardware adapters as shared infrastructure.

```text
deploy -> build -> debug -> test (optional formal acceptance)
```

## Stage contracts

| Stage | Deterministic inputs | Required output | Agent role |
|---|---|---|---|
| `deploy` | bundle, platform/profile, dependency scripts, bounded probes | `deploy/<robot_id>/latest/handoff.json` | Skill optional; scripts remain authoritative |
| `build` | deployment handoff and discovered candidates | verified canonical CLI, conformance report, State Graph baseline, build handoff | Coding Agent and build Skills required |
| `debug` | build handoff and user debug/safety constraints | frozen configuration, debug evidence, debug handoff | Debug Skill required; `robot_use` optional |
| `test` | debug handoff and admitted acceptance constraints | final regression, report, evidence package, test handoff | Optional formal stage; test Skills required when selected |

The optional fourth stage does not make safety regression optional. Every Stage 3 change must still
run the affected smoke and safety regressions before it can be retained.

## Source layout

```text
src/rolo/stages/
├── deploy/   # bundle, enrollment, dependency/discovery handoff
├── build/    # coding plan, canonical CLI/conformance/State Graph gate
├── debug/    # constrained debugging, tuning, robot_use
└── test/     # optional formal test generation and acceptance gate
```

`agentd.py`, `api.py`, and `runtime.py` remain shared services. Shared configuration, domain models,
artifacts, and the robot registry live under `src/rolo/core/`. Compatibility modules at
`rolo.bundle`, `rolo.enrollment`, `rolo.discovery`, and `rolo.robot_use` preserve the pre-stage
imports while new code imports the stage-owned implementations directly.

## Current implementation maturity

- Deploy produces a versioned handoff and is implemented for the current bounded discovery path.
- Build produces a machine-readable Coding Agent/Skill plan. Adapter generation, promotion,
  conformance execution, and the real State Graph store remain implementation work.
- Debug currently contains the `robot_use` supervision service and a hard build-handoff gate.
  Closed-loop diagnosis, transactions, tuning, and debug handoff production remain implementation
  work.
- Test currently exposes an optional stage gate. Runtime test DSL, Oracle registry, autonomous test
  execution, final regression, and evidence packaging remain implementation work. Repository tests
  under `tests/` are engineering tests and are not Stage 4 robot acceptance tests.

## CLI

The stage-oriented commands are canonical for lifecycle orchestration:

```text
robotctl deploy status|bundle|enroll|discover
robotctl build status|plan|tool
robotctl debug status|robot-use
robotctl test status
robotctl pipeline-status
```

Legacy top-level commands remain available during migration.

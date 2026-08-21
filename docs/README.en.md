<p align="center">
  <img src="../rolo-logo.svg" width="720" alt="rolo Loop Exit — robot only loop once">
</p>

<p align="center">
  <strong>Evolve with every execution</strong><br>
</p>

<p align="center">
  <a href="../README.md">中文</a> · English
</p>

## What is rolo?

rolo (robot only loop once) is an embodied robotics development principle: with every use-case
execution, construct a slice of its inputs, process, results, and external observations so the robot
can autonomously explain and correct problems.

> [!NOTE]
> The current version is an MVP under development. The mock backend is suitable for local
> validation, but it does not replace physical safety controls, emergency stops, collision
> detection, or human authorization on a real robot.

## rolo features

### One run, one complete evidence loop

rolo does not treat a successful command return as task completion. Every execution should leave a
replayable, explainable, and reproducible episode containing:

- issued commands and actual robot execution state;
- sensor data, system telemetry, and camera frames;
- parameter, software, and capability configuration versions;
- test verdicts, anomalous intervals, and diagnostic conclusions.

### Canonical CLI

Heterogeneous degrees of freedom, actuators, sensors, and compute platforms are exposed through a
canonical CLI. Higher-level agents receive consistent command formats, units, coordinate frames,
timestamps, error codes, and rollback semantics across four layers:

- **Hardware**: sensors, actuators, buses, firmware, power, and hardware state;
- **Linux**: processes, services, networking, resources, files, and host performance;
- **Middleware**: nodes, topics, services, actions, TF, parameters, and diagnostics;
- **Application**: mapping, localization, navigation, manipulation, testing, tuning, and task state.

The product Canonical Operation Registry currently defines **294 operations**: 40 Hardware,
63 Linux, 41 Middleware, and 150 Application operations (including 13 rolo control-plane
operations). See the [complete four-layer list](CANONICAL_OPERATIONS.md). This is the product
vocabulary, not a claim that every robot implements every operation; a robot-specific Active Tool
Catalog is created only after the Adapt gate passes.
All 294 operations now have explicit product contracts: 62 are `RELEASED`, 232 are `GATEABLE`,
and none remain `DRAFT`. `GATEABLE` still means that a target needs discovery evidence, an adapter,
and conformance before the operation can become `VERIFIED` in that target's Tool Catalog.
See the [Registry Operation guide](REGISTRY_OPERATION_GUIDE.md) for contract lifecycle,
promotion/demotion, R0-R3 risk, data classification, and invocation rules.

### Active discovery

After initial configuration registers a unique `robot_id`, rolo creates a maintainable robot Wiki.
It brings compute platforms, system versions, sensors, actuators, buses, Linux services, the ROS
graph, local source code, startup entry points, communication protocols, dependencies, and risks
into one full-stack map. Teams no longer need to piece together “how this robot actually works”
from a senior engineer's memory, scattered READMEs, vendor manuals, and field scripts.

### `robot_use`

`robot_use` combines onboard or third-person cameras such as VICON with timestamped keyframes,
task state, commands, odometry, and telemetry for multimodal analysis:

- low-frequency periodic supervision and state-change triggers;
- mandatory validation after test steps;
- high-frequency supervision triggered by anomalous telemetry;
- overlapping windows and multi-frame temporal understanding;
- coarse-to-fine video review when the error time is unknown.

### Autonomous testing

Users can express structured constraints for speed, acceleration, target error, obstacle clearance,
exclusion zones, maximum duration, sensor use, and fault conditions. rolo aims to verify that these
constraints are explicit, executable, and observable, then generate coverage matrices,
nominal/boundary/failure tests, state-transition and combinatorial tests, metamorphic and
fault-injection tests, test oracles, risk levels, and execution order.

### Autonomous tuning

Algorithm parameters are represented through a shared registry containing canonical names, units,
current and default values, bounds, dependencies, restart or calibration requirements, risk levels,
and rollback methods. Tuning follows the lifecycle: establish a baseline → generate candidates →
run a controlled trial → evaluate → regress → promote or roll back.

### Autonomous and auditable operation

rolo uses a State Graph to manage discovery, calibration, operation, mapping, localization,
navigation, testing, diagnosis, tuning, and regression. Long-running tasks can create checkpoints
that record the current configuration, active work, test progress, and evidence indexes. Multiple
robots can run the same Agent and test DSL while preserving independent identities, parameters,
state, and evidence.

## Quick start

### Installation and configuration

```bash
git clone https://github.com/zarcherlot/rolo.git
cd rolo
uv sync --frozen

uv run robotctl init --robot-id your_robot_id
```

### Access the management API

The API listens only on the robot's loopback interface by default. For remote access, create an SSH
port forward:

```bash
ssh -L 8080:127.0.0.1:8080 robot@ROBOT_IP
```

With the tunnel active, open `http://127.0.0.1:8080/docs`. The API and all probes continue to run on
the target robot.

### Three-stage workflow

| Stage | Primary output | Agent requirement |
|---|---|---|
| `adapt` | editable robot Wiki, machine evidence, canonical CLI, State Graph, conformance, adapt handoff | Adapter Agent; Codex by default |
| `diagnose` | constrained diagnosis, tuning evidence, frozen configuration, diagnosis handoff | Diagnosis Agent; `robot_use` optional |
| `verify` | optional formal cases, full regression, report, evidence, verification handoff | Verification Agent |

Check the overall status:

```bash
uv run robotctl pipeline-status --robot "$ROBOT_ID"
```

#### Stage 1: adapt

Adapt aims to deliver two core assets:

1. a maintainable robot Wiki that the R&D team can understand;
2. an evidence-backed canonical CLI, State Graph, and downstream handoff that pass an independent
   gate.

It lets an embodied robotics team quickly answer which boards and peripherals make up the robot,
which programs it runs and how they start, how nodes and protocols connect, which dependencies are
missing, which capabilities are only inferred, and which interfaces are safe to expose to an
Agent. New team members, algorithm engineers, embedded developers, operations, and test engineers
all see the same system-wide picture.

The flow is “discover and generate the Wiki → Adapter Agent retrieves evidence → perform adapt”:

```bash
# --urdf is optional; missing hardware semantics remain unresolved
uv run robotctl adapt discover run --robot "$ROBOT_ID" \
  --urdf /path/to/your_robot.urdf \
  --build-root /path/to/robot-application/build \
  --install-root /path/to/robot-application/install \
  --doc-root /path/to/robot-application/docs \
  --launch-root /path/to/robot-application/launch \
  --source-root /path/to/robot-application \
  --active-probe runtime-readonly  # supporting source; target route presence only
uv run robotctl adapt discover review --robot "$ROBOT_ID"
uv run robotctl adapt operations summary --robot "$ROBOT_ID"
uv run robotctl adapt operations list --robot "$ROBOT_ID" \
  --applicability OBSERVED --registration NOT_REGISTERED
uv run robotctl adapt run --robot "$ROBOT_ID"
# Optional parent for an automatically deleted workspace outside the rolo checkout:
uv run robotctl adapt run --robot "$ROBOT_ID" --scratch-root /path/outside/rolo
```

Adapt gates operations independently. Target-observed routes can become `VERIFIED` without waiting
for unrelated missing routes; deferred candidates remain `UNAVAILABLE` with a reason. Runtime
verifies the multi-file adapter, Rolo-owned State Graph, and target fingerprint. Adapt does not
execute write operations to judge behavior; that work starts in Diagnose. See
[`ADAPT_DEVICE_HANDS_ON.md`](ADAPT_DEVICE_HANDS_ON.md) for the real-device procedure.

```text
robot_wiki.md
├── Full-stack summary
│   ├── Discovery status, mode, and confidence
│   └── Hardware/software compatibility, unknowns, and warnings
├── Hardware and robot specifications
│   ├── Compute platform, CPU architecture, and drive model
│   ├── Key specifications such as velocity limits
│   └── Sensors, host devices, and hardware buses
├── Host and software stack
│   ├── Operating system, ROS distribution, RMW, and Domain ID
│   └── Tool availability and version evidence
├── Application and function overview
│   └── Purpose, entry point, nodes, interfaces, protocols, dependencies, and risks per program
├── ROS and communication topology
│   ├── Node, Topic, Service, and Action inventory
│   └── Program-to-interface relationship graph
├── Dependencies, differences, and unknowns
│   └── Missing dependencies, version conflicts, compatibility differences, and risks
└── Maintenance guidance
    └── Engineering purpose, owner, deployment relationships, startup order, and version baseline
```

See [`AUTODISCOVERY.md`](AUTODISCOVERY.md) for the host introspection CLI,
[`SOFTWARE_DISCOVERY.md`](SOFTWARE_DISCOVERY.md) for the software discovery and evidence contract,
and [`.env.example`](../.env.example) for Adapter Agent configuration.

#### Stage 2: diagnosis

The Diagnosis Agent reads the adapt handoff and user constraints, then performs closed-loop
diagnosis and tuning. When image-model supervision is needed, configure the backend securely
outside the source repository and submit timestamped images with structured telemetry:

```bash
export ROBOT_USE_BACKEND=openai
export OPENAI_API_KEY="..."
export OPENAI_MODEL="an-image-capable-model-available-to-your-project"

uv run robotctl diagnose status --robot "$ROBOT_ID"
uv run robotctl diagnose robot-use poll --robot "$ROBOT_ID" --image /tmp/frame.jpg
```

`robot_use` provides semantic supervision only. It performs no local visual detection and has no
authority over robot safety. Tuning must remain within user constraints and hard safety boundaries,
and every change must run the affected smoke, safety, and regression checks.

#### Stage 3: verification

Stage 3 checks formal acceptance readiness. Once the corresponding Verification Agent capabilities
are implemented, it generates cases, runs full regression, and packages evidence:

```bash
uv run robotctl verify status --robot "$ROBOT_ID"
```

## Project layout

```text
src/rolo/stages/adapt/            Stage 1: discovery, adapters, conformance, and handoff publication
src/rolo/stages/diagnose/         Stage 2: Diagnosis Agent loop, tuning, and robot_use
src/rolo/stages/verify/           Stage 3: optional autonomous verification and acceptance
src/rolo/commands/                robotctl interfaces grouped by command domain
src/rolo/core/                    Shared configuration, domain models, artifacts, and robot registry
src/rolo/integrations/robot_use/  External supervision backends for robot_use
src/rolo/                         Shared API, agentd, and runtime
tests/                            Offline unit tests, API tests, and fixtures
schemas/                          Exported JSON Schemas
```

## Contributing

Issues describing the robot platform, reproduction steps, and expected behavior are welcome. Keep
pull requests small and verifiable. Before submitting, run:

```powershell
uv run pytest
uv run ruff check .
```

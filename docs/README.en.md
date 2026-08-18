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

rolo (robot only loop once) is an embodied robotics development principle: execute one clearly
bounded use case, capture its inputs, execution, observations, and results, and enable the robot to
autonomously explain, close the loop on, and correct problems.

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

### Active discovery

After initial configuration registers a unique `robot_id`, active discovery creates an editable
robot Wiki alongside machine-readable evidence. It maps compute platforms, system versions,
sensors, actuators, buses, Linux services, the ROS graph, local source projects, communication
protocols, and vendor or application entry points. The chief engineer may directly correct the
Wiki; it is deliberately excluded from evidence hashes.

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

After configuring the robot, advance through the three stages. Run
`uv run robotctl pipeline-status --robot "$ROBOT_ID"` from the repository at any time to inspect
the overall status.

| Stage | Primary output | Agent requirement |
|---|---|---|
| `adapt` | editable robot Wiki, machine evidence, canonical CLI, State Graph, conformance, adapt handoff | Adapter Agent; Codex by default |
| `diagnose` | constrained diagnosis, tuning evidence, frozen configuration, diagnosis handoff | Diagnosis Agent; `robot_use` optional |
| `verify` | optional formal cases, full regression, report, evidence, verification handoff | Verification Agent |

#### Stage 1: adapt

Adapt turns the robot's existing hardware, Linux, ROS, and application capabilities into a
verifiable unified interface. Read-only discovery produces a capability manifest, semantic binding
candidates, a tool catalog, and the inputs required by the Adapter Agent. Software dependencies
come only from source and launch declarations; discovery neither inventories host packages nor
installs target-project dependencies.

Discovery first produces an editable whole-stack robot Wiki. The chief engineer may correct or
extend it directly, without a separate confirmation step. One `adapt run` then reads the maintained
Wiki, derives the plan in memory, prepares and runs the Agent, freezes its outputs, applies the
independent gate, and atomically publishes the handoff:

```bash
uv run robotctl adapt discover run --robot "$ROBOT_ID" \
  --urdf /path/to/your_robot.urdf \
  --source-root /path/to/robot-application
uv run robotctl adapt discover review --robot "$ROBOT_ID"
uv run robotctl adapt run --robot "$ROBOT_ID" --workspace /path/to/robot-application
uv run robotctl adapt status --robot "$ROBOT_ID"
```

Add `--dry-run` to `adapt run` to inspect the derived plan without starting the Agent. The former
public `plan`, `agent-prepare`, `execute`, and `promote` steps are intentionally absent.

The editable Wiki is human engineering context, while the hashed JSON manifest preserves machine
evidence. The robot may enter Diagnose only after independent CLI conformance, the State Graph
baseline, and the adapt handoff all pass. See
[`SOFTWARE_DISCOVERY.md`](SOFTWARE_DISCOVERY.md) for discovery inputs, evidence degradation, active
probes, and corrections; see [`.env.example`](../.env.example) for Adapter Agent configuration.

#### Stage 2: closed-loop debugging and diagnosis

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

#### Stage 3: testing

Stage 3 checks formal acceptance readiness. Once the corresponding Verify Skills are implemented, a
Verification Agent generates cases, runs full regression, and packages evidence:

```bash
uv run robotctl verify status --robot "$ROBOT_ID"
```

## Project layout

```text
src/rolo/stages/adapt/      Stage 1: discovery, adapters, conformance, and handoff publication
src/rolo/stages/diagnose/   Stage 2: Diagnosis Agent loop, tuning, and robot_use
src/rolo/stages/verify/     Stage 3: optional autonomous verification and acceptance
src/rolo/commands/       robotctl interfaces grouped by command domain
src/rolo/core/           Shared configuration, domain models, artifacts, and robot registry
src/rolo/integrations/robot_use/  External supervision backends for robot_use
src/rolo/                Shared API, agentd, and runtime
tests/fixtures/robots/    Mock robot capability fixtures
tests/fixtures/profiles/  URDF profile fixtures
schemas/                 Exported JSON Schemas
tests/                   Offline unit tests, API tests, and fixtures
rolo-logo.svg            Final rolo SVG identity
```

## Contributing

Issues describing the robot platform, reproduction steps, and expected behavior are welcome. Keep
pull requests small and verifiable. Before submitting, run:

```powershell
uv run pytest
uv run ruff check .
```

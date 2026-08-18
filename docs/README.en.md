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

After initial configuration registers a unique `robot_id`, active discovery generates a normalized
capability manifest, semantic binding candidates, and a CLI tool catalog. Discovery covers compute
platforms, system versions, sensors, actuators, buses, Linux services, the ROS graph, local source
projects, and existing vendor or application entry points.

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
| `build` | registration, probes, capability manifest, semantic binding candidates, tool catalog, canonical CLI, State Graph, build handoff | Coding Agent; Codex by default |
| `debug` | constrained closed-loop diagnosis, tuning evidence, frozen configuration, debug handoff | Diagnosis Agent; `robot_use` optional |
| `test` | optional formal cases, full regression, report, and evidence package | Test Agent |

#### Stage 1: build

Build combines registration, discovery, canonical CLI construction, and the State Graph gate.
Initial configuration registers the user-assigned `robot_id`. From the repository, inspect identity
and discovery state, or rerun bounded read-only discovery against the robot's URDF and local
application source:

```bash
uv run robotctl build enroll show
uv run robotctl build discover show --robot "$ROBOT_ID"
uv run robotctl build discover run --robot "$ROBOT_ID" \
  --urdf /path/to/your_robot.urdf \
  --source-root /path/to/robot-application
```

Discovery inventories hardware, the host software stack, the ROS graph, and local source projects.
It persists the four `hw/linux/ros/application` probes and writes the capability manifest, semantic
binding candidates, tool catalog, and build inputs.

Software discovery resolves only Python and ROS direct dependencies declared by source or launch
evidence. Local metadata classifies them as installed, missing, version-conflicting, or unknown;
discovery neither scans the host package database nor installs target-project dependencies. See
[`SOFTWARE_DISCOVERY.md`](SOFTWARE_DISCOVERY.md) for the complete contract.

The Coding Agent then reads the build inputs, creates a build plan, and implements and inspects each
layer adapter through the canonical CLI. A local `.env` can select the model or configure an API
key, including for a compatible relay.

```dotenv
CODING_AGENT_PROVIDER=codex
CODING_AGENT_EXECUTOR=codex
CODING_AGENT_AUTO_INSTALL=true
CODING_AGENT_REQUIRE_AUTH=true
CODING_AGENT_EXECUTABLE=codex

CODING_AGENT_BASE_URL=
CODING_AGENT_MODEL=
CODING_AGENT_API_KEY=
```

```bash
uv run robotctl build agent-config
uv run robotctl build agent-prepare
uv run robotctl build plan --robot "$ROBOT_ID"
uv run robotctl build execute --robot "$ROBOT_ID" --workspace /path/to/robot-application
uv run robotctl tool catalog --robot "$ROBOT_ID"
uv run robotctl hw inventory scan
uv run robotctl linux host inspect
uv run robotctl ros graph snapshot
uv run robotctl app robot discover
uv run robotctl build status --robot "$ROBOT_ID"
```

Debugging is allowed only after canonical CLI conformance and the State Graph baseline pass.

#### Stage 2: closed-loop debugging and diagnosis

The Diagnosis Agent reads the build handoff and user constraints, then performs closed-loop
diagnosis and tuning. When image-model supervision is needed, configure the backend securely
outside the source repository and submit timestamped images with structured telemetry:

```bash
export ROBOT_USE_BACKEND=openai
export OPENAI_API_KEY="..."
export OPENAI_MODEL="an-image-capable-model-available-to-your-project"

uv run robotctl debug status --robot "$ROBOT_ID"
uv run robotctl debug robot-use poll --robot "$ROBOT_ID" --image /tmp/frame.jpg
```

`robot_use` provides semantic supervision only. It performs no local visual detection and has no
authority over robot safety. Tuning must remain within user constraints and hard safety boundaries,
and every change must run the affected smoke, safety, and regression checks.

#### Stage 3: testing

Stage 3 checks formal acceptance readiness. Once the corresponding Test Skills are implemented, a
Test Agent generates cases, runs full regression, and packages evidence:

```bash
uv run robotctl test status --robot "$ROBOT_ID"
```

## Project layout

```text
src/rolo/stages/build/   Stage 1: registration, probe discovery, CLI construction, State Graph gate
src/rolo/stages/debug/   Stage 2: Diagnosis Agent loop, tuning, and robot_use
src/rolo/stages/test/    Stage 3: optional autonomous testing and formal acceptance
src/rolo/core/           Shared configuration, domain models, artifacts, and robot registry
src/rolo/                Shared API, agentd, and runtime
configs/local/           Capability manifests for local mock robots
configs/profiles/        URDF profile format examples
schemas/                 Exported JSON Schemas
tests/                   Offline unit and API tests
scripts/                 Development helpers
rolo-logo.svg            Final rolo SVG identity
```

## Contributing

Issues describing the robot platform, reproduction steps, and expected behavior are welcome. Keep
pull requests small and verifiable. Before submitting, run:

```powershell
uv run pytest
uv run ruff check .
```

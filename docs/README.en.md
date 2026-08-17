<p align="center">
  <img src="../rolo-logo.svg" width="720" alt="rolo Loop Exit — robot only loop once">
</p>

<p align="center">
  <strong>Run once. Observe fully. Reproduce exactly.</strong><br>
  A local-first, open-source toolkit for robot debugging and supervision.
</p>

<p align="center">
  <a href="../README.md">中文</a> · English
</p>

## What is rolo?

**rolo** is short for **robot only loop once**. It captures a robotics development principle: run one bounded task loop at a time, retain its inputs, execution, observations, and result, then make failures explainable, reproducible, and fixable.

The final wordmark uses four independent lowercase letters. The single cobalt exit on the last `o` marks a definite end to one execution and a handoff to observation, reproduction, and the next decision—not an endless cycle.

This repository currently provides a local development harness for the Robot Debugging Agent engineering specification. The default profile runs without ROS, Docker, a camera, or an OpenAI API key. Example robots are represented by mock adapters while the production-facing CLI, API contracts, dynamic enrollment, capability manifests, execution monitor, and `robot_use` supervision path remain intact.

## Current capabilities

- Local-first: the default `mock` backend sends no images or data outside the machine.
- One interface: a FastAPI control plane and the `robotctl` CLI cover heterogeneous robots.
- Dynamic enrollment: assign any valid `robot_id` at installation and derive its capability config from differential-drive or Ackermann templates; identity is never compiled into the bundle.
- Automatic discovery: read-only probes inventory hardware, Linux, the ROS graph, and local application projects.
- Visual supervision: timestamped image storyboards and structured telemetry flow through a replaceable `robot_use` backend.
- Heterogeneous deployment: one ARM64 bundle supports Jetson Orin, RK3588, and Raspberry Pi 4/5 with robot-specific profiles selected during installation.
- Offline tests: core unit and API tests require neither a physical robot nor a cloud service.

> [!NOTE]
> This is an early MVP. The mock backend is useful for local validation, but it does not replace physical safety controls, emergency stops, collision detection, or human authorization on a real robot.

## Product capabilities

rolo is designed for autonomous debugging and testing on physical robots. It organizes every run as a bounded loop: define the task, execute actions, observe continuously, judge the result, preserve evidence, and let new evidence determine the next run.

> [!IMPORTANT]
> This section describes the complete product direction. Treat “Current capabilities” and the repository tests as the source of truth for what is available today; autonomous testing, tuning, and multi-robot orchestration will be delivered incrementally as the project evolves.

### 1. One run, one complete evidence loop

rolo does not treat a successful command return as task completion. Every execution should leave a replayable, explainable, and reproducible episode containing:

- issued commands and actual robot execution state;
- sensor data, system telemetry, and camera frames;
- parameter, software, and capability configuration versions;
- test verdicts, anomalous intervals, and diagnostic conclusions.

### 2. Canonical CLI

Heterogeneous degrees of freedom, actuators, sensors, and compute platforms are exposed through a canonical CLI. Higher-level agents receive consistent command formats, units, coordinate frames, timestamps, error codes, and rollback semantics across four layers:

- **Hardware**: sensors, actuators, buses, firmware, power, and hardware state;
- **Linux**: processes, services, networking, resources, files, and host performance;
- **Middleware**: nodes, topics, services, actions, TF, parameters, and diagnostics;
- **Application**: mapping, localization, navigation, manipulation, testing, tuning, and task state.

### 3. Active discovery

At first deployment, rolo assigns a unique `robot_id` and uses active discovery to generate a normalized capability manifest, semantic binding candidates, and a CLI tool catalog. Discovery covers compute and OS details, sensors, actuators, buses, Linux services, the ROS graph, local source projects, and existing vendor or application entry points.

### 4. `robot_use`

`robot_use` combines onboard or third-person cameras such as VICON with timestamped keyframes, task state, commands, odometry, and telemetry for multimodal analysis:

- low-frequency periodic supervision and state-change triggers;
- mandatory validation after test steps;
- high-frequency supervision triggered by anomalous telemetry;
- overlapping windows and multi-frame temporal understanding;
- coarse-to-fine video review when the error time is unknown.

### 5. Autonomous testing

Users can express structured constraints for speed, acceleration, target error, obstacle clearance, exclusion zones, maximum duration, sensor usage, and fault conditions. rolo's goal is to validate that constraints are explicit, executable, and observable, then derive coverage matrices, nominal/boundary/failure tests, state-transition and combinatorial tests, metamorphic and fault-injection tests, test oracles, risk levels, and execution order.

### 6. Autonomous tuning

Algorithm parameters are represented through a shared registry containing canonical names, units, current and default values, bounds, dependencies, restart or calibration requirements, risk levels, and rollback methods. Tuning follows a lifecycle of baseline → candidates → controlled trial → evaluation → regression → promote or roll back.

### 7. Autonomous and auditable operation

rolo uses state graphs to manage discovery, calibration, operation, mapping, localization, navigation, testing, diagnosis, tuning, and regression. Long-running tasks can create checkpoints containing configuration, active work, test progress, and evidence indexes. Multiple robots can run the same agent and test DSL while preserving independent identities, parameters, state, and evidence.

## Quick start

### Prerequisites

- Windows PowerShell 5.1+
- [`uv`](https://docs.astral.sh/uv/)
- Python 3.12 managed by `uv`

ROS 2 and FFmpeg are optional in the local mock profile. They become relevant when real robot and camera adapters are connected.

### Install and run

```powershell
Copy-Item .env.example .env
uv sync --dev
uv run robotctl doctor
uv run robotctl robots
uv run robotctl serve
```

The API is available at `http://127.0.0.1:8080`; interactive OpenAPI documentation is at `http://127.0.0.1:8080/docs`.

### Use case: three-stage robot workflow

After local installation, advance one robot through three stages. At any time, inspect the entire pipeline with `uv run robotctl pipeline-status --robot demo_diff`.

| Stage | Primary output | Agent requirement |
|---|---|---|
| `build` | bundle, probes, capability manifest, binding candidates, tool catalog, canonical CLI, State Graph, build handoff | Coding Agent |
| `debug` | constrained diagnosis, tuning evidence, frozen config, debug handoff | Diagnosis Agent; `robot_use` optional |
| `test` | optional formal cases, full regression, report, and evidence package | Test Agent when selected |

#### Stage 1: build

Build combines installation, enrollment, discovery, canonical CLI construction, and the State Graph gate. The physical-robot baseline is ARM64 + Ubuntu 22.04 + ROS 2 Humble. First build the universal archive and enroll one identity from the robot's physical structure:

```powershell
.\scripts\build_bundles.ps1
```

The archive is written to `dist/release/rolo-0.1.0-arm64.zip`. Extract it on the target and run:

```bash
sudo bash install.sh my_robot_01 differential_drive --confirm-safety-profile
```

Local development can skip the archive. When enrolling a physical robot into an empty config root, first verify its structure, sensors, and hard safety bounds:

```powershell
$env:ROBOT_LOOP_CONFIG_DIR = "C:\robot-loop-config"
uv run robotctl build enroll profiles
uv run robotctl build enroll init --robot-id my_robot_01 --profile differential_drive --confirm-safety-profile
uv run robotctl build enroll show
```

Each instance owns one `robot_id`; replacing its identity or structure profile requires a separate migration. Then follow the production sequence: start the minimal daemon, run read-only discovery, and start the full agentd:

```powershell
# Terminal 1
uv run robotctl bootstrap-agentd --robot demo_diff --port 8100

# Terminal 2
uv run robotctl build discover run --robot demo_diff --source-root C:\path\to\robot-application
uv run robotctl build discover show --robot demo_diff
uv run robotctl agentd --robot demo_diff --port 8101
```

Discovery inventories hardware, the host software stack, the ROS graph, and local source projects. It persists `hw/linux/ros/application` probes and writes the capability manifest, semantic binding candidates, tool catalog, and build inputs. If ROS, the BSP, or vendor drivers are missing, bootstrap agentd remains available and the full agentd runs `DEGRADED`; a failed discovery prevents the full agentd from starting. New bindings and calibration remain unavailable until verified. See [`AUTODISCOVERY.md`](AUTODISCOVERY.md) for evidence and safety boundaries.

The Coding Agent then reads the build inputs, creates the build plan, and implements and inspects the layer adapters through the canonical CLI:

```powershell
uv run robotctl build plan --robot demo_diff
uv run robotctl tool catalog --robot demo_diff
uv run robotctl hw inventory scan
uv run robotctl linux host inspect
uv run robotctl ros graph snapshot
uv run robotctl app robot discover
uv run robotctl build status --robot demo_diff
```

Debugging is gated on canonical CLI conformance and a valid State Graph baseline.

#### Stage 2: closed-loop diagnosis, debugging, and `robot_use`

The Diagnosis Agent reads the build handoff and user constraints, then performs closed-loop diagnosis and tuning. The default `robot_use` backend is the local `mock`. For image-model supervision, configure the backend securely outside source control, then submit timestamped images and structured telemetry:

```powershell
$env:ROBOT_USE_BACKEND = "openai"
$env:OPENAI_API_KEY = "..."
$env:OPENAI_MODEL = "an-image-capable-model-available-to-your-project"

uv run robotctl debug status --robot demo_diff
uv run robotctl debug robot-use poll --robot demo_diff --image C:\path\to\frame.jpg
```

`robot_use` supplies semantic supervision only: it performs no local visual detection and has no authority over robot safety. Tuning remains bounded by user constraints and hard safety limits, and every change requires affected smoke, safety, and regression checks.

#### Stage 3: optional formal testing

Stage 3 checks formal acceptance readiness and, once the corresponding Test Skills are implemented, uses a Test Agent to generate cases, run full regression, and package evidence:

```powershell
uv run robotctl test status --robot demo_diff
```

Formal acceptance is optional, but safety and affected regression checks during debugging are mandatory. The current MVP does not yet implement the complete autonomous acceptance runner, and production-grade offline ARM64 installation still needs a wheelhouse. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for stage contracts and implementation maturity.

## Project layout

```text
src/rolo/stages/build/   Stage 1 install, enroll, probe, build CLI, and gate the State Graph
src/rolo/stages/debug/   Stage 2 Diagnosis Agent loop, tuning, and robot_use
src/rolo/stages/test/    Stage 3 optional autonomous acceptance testing
src/rolo/core/           Shared configuration, domain models, artifacts, and registry
src/rolo/                Shared API, agentd, runtime, and compatibility imports
configs/local/        Capability manifests for local mock examples
configs/profiles/     Enrollable structure and sensor templates
configs/deployment/   Common deployment and service configuration
configs/platforms/    ARM64 compatibility and supported-compute manifest
configs/robot_use.yaml
configs/discovery.yaml
schemas/              Exported JSON Schemas
tests/                Offline unit and API tests
scripts/              Development and bundle-build helpers
rolo-logo.svg         Final rolo SVG identity
artifacts/            Runtime output, ignored by Git
```

## Contributing

Issues that include a robot platform, reproduction steps, and expected behavior are welcome. Pull requests should stay small and verifiable. Before submitting, run:

```powershell
uv run pytest
uv run ruff check .
```

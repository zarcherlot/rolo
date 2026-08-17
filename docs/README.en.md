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

**rolo** (**robot only loop once**) is an embodied robotics development principle: execute one clearly bounded use case at a time, preserve its inputs, execution, observations, and results, and enable the robot to autonomously explain, close the loop on, and correct problems.

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

### Runtime requirements

rolo is installed and runs on the target robot. agentd, probes, and runtime artifacts always reflect the robot environment; deployment and subsequent operations may be performed from a local console or over SSH.

| Item | Minimum requirement |
|---|---|
| Processor architecture | ARM64 |
| Operating system | Ubuntu LTS 20.04+; validated on 20.04, 22.04, and 24.04 |
| Python | Python 3.10+ with `venv` |
| System environment | systemd and Bash |
| Access and utilities | `sudo` and `unzip`; SSH/SCP for remote deployment |
| Dependency access | Access to the Python package index configured for the target environment during installation |

Ubuntu 20.04 provides Python 3.8 by default; install Python 3.10+ and the matching `venv` package before deployment. Fully offline deployment requires an ARM64 wheelhouse in the bundle.

Connect ROS 2, the BSP, vendor drivers, and FFmpeg according to the robot's actual capabilities. The ROS probe checks the active environment first and can discover Foxy, Humble, or Jazzy for Ubuntu 20.04, 22.04, or 24.04, as well as other distributions under `/opt/ros`. Missing optional dependencies do not block the base installation; doctor and the probes mark affected capabilities with a warning, `DEGRADED`, or `UNAVAILABLE`.

### Build and deploy

When using an existing release archive, begin with the copy and installation steps. Building an archive from source additionally requires PowerShell 5.1+, [`uv`](https://docs.astral.sh/uv/), and Python 3.10+:

```powershell
.\scripts\build_bundles.ps1
scp .\dist\release\rolo-0.1.0-arm64.zip robot@ROBOT_IP:/tmp/
ssh robot@ROBOT_IP
```

After connecting to the target robot, run:

```bash
cd /tmp
unzip rolo-0.1.0-arm64.zip
cd rolo-0.1.0-arm64
sudo bash install.sh my_robot_01 differential_drive --confirm-safety-profile

sudo -i
set -a
source /etc/rolo/rolo.env
set +a
ROBOTCTL=/opt/rolo/venv/bin/robotctl
$ROBOTCTL doctor
$ROBOTCTL robots
```

After installation, the rolo package, agentd, probes, and runtime artifacts all reside on the target robot. Subsequent examples assume the root shell above with `$ROBOTCTL` set.

### Access the control plane

The API listens on the robot's loopback interface by default. For remote access, create an SSH port forward:

```bash
ssh -L 8080:127.0.0.1:8080 robot@ROBOT_IP
```

With the tunnel active, open `http://127.0.0.1:8080/docs`. The API and all probes continue to run on the target robot.

### Use case: three-stage workflow

After deploying to the robot, advance it through three stages. At any time, run `$ROBOTCTL pipeline-status --robot my_robot_01` in the robot shell to inspect the pipeline.

| Stage | Primary output | Agent requirement |
|---|---|---|
| `build` | bundle, probes, capability manifest, binding candidates, tool catalog, canonical CLI, State Graph, build handoff | Coding Agent; Codex by default, other vendors configurable |
| `debug` | constrained diagnosis, tuning evidence, frozen config, debug handoff | Diagnosis Agent; `robot_use` optional |
| `test` | optional formal cases, full regression, report, and evidence package | Test Agent when selected |

#### Stage 1: build

Build combines installation, enrollment, discovery, canonical CLI construction, and the State Graph gate. The installer has already enrolled the one `robot_id` selected from the robot's physical structure; changing its identity or profile requires a separate migration. On the robot, systemd enforces `bootstrap-agentd -> discovery -> agentd`. Inspect the identity and discovery state, or rerun bounded discovery against application source that also resides on the robot:

```bash
$ROBOTCTL build enroll show
systemctl status rolo-bootstrap-agentd.service rolo-discovery.service rolo-agentd.service
$ROBOTCTL build discover show --robot my_robot_01
$ROBOTCTL build discover run --robot my_robot_01 --source-root /opt/robot-application
```

Discovery inventories hardware, the host software stack, the ROS graph, and local source projects. It persists `hw/linux/ros/application` probes and writes the capability manifest, semantic binding candidates, tool catalog, and build inputs. If ROS, the BSP, or vendor drivers are missing, bootstrap agentd remains available and the full agentd runs `DEGRADED`; a failed discovery prevents the full agentd from starting. New bindings and calibration remain unavailable until verified. See [`AUTODISCOVERY.md`](AUTODISCOVERY.md) for evidence and safety boundaries.

The Coding Agent then reads the build inputs, creates the build plan, and implements and inspects the layer adapters through the canonical CLI. The default executor is the local `codex exec` command. No API key is required when the device has already completed `codex login`. Users may also select a model or connect another vendor or relay that supports the Responses API. An API key, when needed, is read only from the executor environment and is never written to argv, the Build Plan, or artifacts:

```bash
export CODING_AGENT_PROVIDER=codex
export CODING_AGENT_EXECUTOR=codex
export CODING_AGENT_AUTO_INSTALL=true
export CODING_AGENT_REQUIRE_AUTH=true
# Optional: leave empty for the provider's official/default endpoint.
export CODING_AGENT_BASE_URL=""
export CODING_AGENT_API_KEY=""
# Optional: leave empty to use the provider or Codex default model.
export CODING_AGENT_MODEL=""

$ROBOTCTL build agent-config
$ROBOTCTL build agent-prepare
$ROBOTCTL build plan --robot my_robot_01
$ROBOTCTL build execute --robot my_robot_01 --workspace /opt/robot-application
$ROBOTCTL tool catalog --robot my_robot_01
$ROBOTCTL hw inventory scan
$ROBOTCTL linux host inspect
$ROBOTCTL ros graph snapshot
$ROBOTCTL app robot discover
$ROBOTCTL build status --robot my_robot_01
```

The deployment bundle reads `coding_agent` from `configs/deployment/common.yaml`. By default it runs the allowlisted official Codex Linux installer as the `rolo` service user, then calls `agent-prepare --skip-auth` to verify the executable and version. A Base URL cannot replace the installation source. The first deployment still requires the user to run `codex login --device-auth` as the same operating-system user; authentication is never silently automated.

The complete chain is configuration, automatic installation when missing, version and authentication verification, then explicit execution. `build execute` repeats the dependency gate and will not start a model unless readiness is `READY`. Its audit is written to `coding-agent/dependency/latest.json`. `build plan` only creates the plan and never edits source. The executor uses the `workspace-write` sandbox, a bounded timeout, and structured output. It retains JSONL events, standard error, and secret-free run metadata, and it cannot directly publish `handoff.json`; the separate conformance gate owns that promotion.

For another vendor or relay, set `CODING_AGENT_PROVIDER` to its identifier and configure its `CODING_AGENT_BASE_URL` and model. Set `CODING_AGENT_API_KEY` in the process environment only when that service requires authentication. The Build Plan persists only the provider, Base URL, model, API-key environment-variable name, and whether a key is configured; it never persists the key itself.

See [`CODEX_SETUP.md`](CODEX_SETUP.md) for robot-side automatic installation, device-code login,
verification commands, and files written on the robot.

Debugging is gated on canonical CLI conformance and a valid State Graph baseline.

#### Stage 2: closed-loop diagnosis, debugging, and `robot_use`

The Diagnosis Agent reads the build handoff and user constraints, then performs closed-loop diagnosis and tuning. The default `robot_use` backend is the local `mock`. For image-model supervision, configure the backend securely outside source control, then submit timestamped images and structured telemetry:

```bash
export ROBOT_USE_BACKEND=openai
export OPENAI_API_KEY="..."
export OPENAI_MODEL="an-image-capable-model-available-to-your-project"

$ROBOTCTL debug status --robot my_robot_01
$ROBOTCTL debug robot-use poll --robot my_robot_01 --image /tmp/frame.jpg
```

`robot_use` supplies semantic supervision only: it performs no local visual detection and has no authority over robot safety. Tuning remains bounded by user constraints and hard safety limits, and every change requires affected smoke, safety, and regression checks.

#### Stage 3: optional formal testing

Stage 3 checks formal acceptance readiness and, once the corresponding Test Skills are implemented, uses a Test Agent to generate cases, run full regression, and package evidence:

```bash
$ROBOTCTL test status --robot my_robot_01
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

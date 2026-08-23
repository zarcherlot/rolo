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

uv run robotctl adapt start \
  --robot-id your_robot_id \
  --project-root /path/to/robot-workspace \
  --urdf /path/to/robot.urdf  # optional
```

`adapt start` is the shortest safe product path. It enrolls the identity, idempotently establishes a
local collector, collects and verifies fresh signed target evidence, runs readiness checks, finds
conventional build/install/document/launch evidence, performs read-only runtime discovery,
generates the editable Wiki, and—when target-observed routes exist—continues through the Adapter
Agent, independent gate, State Graph, Tool Catalog, handoff, and release. Use `--discover-only` when
only the Wiki and discovery evidence are needed. See
[`ADAPT_SHORT_JOURNEY.md`](ADAPT_SHORT_JOURNEY.md) for boundaries and fallback commands.

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

The normal product flow is one command:

```bash
uv run robotctl adapt start \
  --robot-id "$ROBOT_ID" \
  --project-root /path/to/robot-application \
  --urdf /path/to/your_robot.urdf
```

For Rolo development and step-by-step troubleshooting, the same underlying services remain
available as granular commands:

```bash
# --urdf is optional; missing hardware semantics remain unresolved
uv run robotctl adapt discover run --robot "$ROBOT_ID" \
  --urdf /path/to/your_robot.urdf \
  --build-root /path/to/robot-application/build \
  --install-root /path/to/robot-application/install \
  --doc-root /path/to/robot-application/docs \
  --launch-root /path/to/robot-application/launch \
  --source-root /path/to/robot-application \
  --active-probe runtime-readonly \
  --target-evidence-bundle /path/to/fresh-signed-target-bundle.json
uv run robotctl adapt discover review --robot "$ROBOT_ID"
uv run robotctl adapt operations summary --robot "$ROBOT_ID"
uv run robotctl adapt operations list --robot "$ROBOT_ID" \
  --applicability OBSERVED --registration NOT_REGISTERED
uv run robotctl adapt run --robot "$ROBOT_ID"
# Optional parent for an automatically deleted workspace outside the rolo checkout:
uv run robotctl adapt run --robot "$ROBOT_ID" --scratch-root /path/outside/rolo
```

Generated adapter `describe` and `invoke` execution fails closed unless a protected target-side OS
sandbox launcher is configured. Rolo calls it as
`launcher --cwd RELEASE_ROOT -- ADAPTER_ARGV...`; the deployment launcher owns service-identity,
filesystem, device, and network isolation. Set `ROLO_ADAPTER_SANDBOX_LAUNCHER` to that protected
executable. `ROLO_ADAPTER_UNSANDBOXED_DEV=1` is restricted to tests and offline demos. A non-loopback
`ROLO_HOST` additionally requires a high-entropy `ROLO_API_TOKEN` and Bearer authentication.

The Wiki heuristic Agent skill is enabled by default and runs in a read-only sandbox. If it is
unavailable or returns invalid output, discovery automatically falls back to deterministic rules.
Set `WIKI_INSIGHTS_AGENT_ENABLED=false` to disable it.

Adapt gates operations independently. Target-observed routes can become `VERIFIED` without waiting
for unrelated missing routes; deferred candidates remain `UNAVAILABLE` with a reason. Runtime
verifies the multi-file adapter, Rolo-owned State Graph, operation-scoped target fingerprint, and
allowlisted ROS runtime context. Adapt does not
execute write operations to judge behavior; that work starts in Diagnose. See
[`ADAPT_DEVICE_HANDS_ON.md`](ADAPT_DEVICE_HANDS_ON.md) for the real-device procedure.
Choose target-local Rolo or the pinned remote read-only collector during installation as described
in [`TARGET_EVIDENCE_DEPLOYMENT.md`](TARGET_EVIDENCE_DEPLOYMENT.md).

```text
robot_wiki.md
├── Full-stack summary
│   ├── Discovery status, mode, compatibility, and key evidence boundaries
│   └── Evidence-backed, low/medium-confidence heuristic findings pending verification
├── Changes since the previous discovery
│   └── Platform, ROS, application, device, operation-candidate, and unknown changes
├── Startup and health checks
│   └── Launch entries, argument defaults, includes, startup order, shutdown, and health gaps
├── Hardware and robot specifications
│   ├── Compute platform, CPU architecture, and drive model
│   ├── URDF structure, geometry, and key safety specifications
│   └── Physical device candidates, internal pipeline endpoints, unmerged endpoints, and buses
├── Host and software stack
│   ├── Operating system and configuration sources/candidates for ROS, RMW, and Domain ID
│   └── Tool availability and version evidence
├── Applications and startup topology
│   ├── pyproject/setuptools/CMake entries, launch evidence, and risks
│   └── Python/C++ ROS interfaces attributed by source file/target, plus unattributed candidates
├── ROS and communication topology
│   └── Live graph and edge-bounded static candidate graph
├── Engineering operation candidates
│   └── Only candidates supported by this discovery, without duplicating the full registry
├── Dependencies, differences, and unknowns
│   └── Acquisition-method-grouped gaps, dependencies, and compatibility differences
└── Chief engineer maintenance guidance and automatic-discovery appendix
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
skills/rolo-wiki-authoring/        Optional read-only Wiki heuristic Agent skill
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

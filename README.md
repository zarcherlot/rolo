# Robot Loop

`robot_loop` is the local development harness for the engineering specification in
[`robot_debugging_agent_6h_demo_spec.md`](robot_debugging_agent_6h_demo_spec.md).

The local profile deliberately runs without ROS, Docker, a camera, or an OpenAI API key. Two
heterogeneous demo robots are represented by mock adapters while the canonical CLI, API contracts,
dynamic enrollment, capability manifests, execution monitor, and `robot_use` supervision path
remain the same.

## Prerequisites

- Windows PowerShell 5.1+
- `uv`
- Python 3.12 managed by `uv`

ROS 2 and FFmpeg are optional for the local mock profile and will be required only when the real
robot/camera adapters are implemented.

## Setup

```powershell
Copy-Item .env.example .env
uv sync --dev
uv run robotctl doctor
uv run robotctl robots
uv run robotctl serve
```

The API is available at `http://127.0.0.1:8080`; interactive OpenAPI documentation is at
`http://127.0.0.1:8080/docs`.

Optional mock robot-side daemons can be started in separate terminals:

```powershell
uv run robotctl agentd --robot demo_diff --port 8101
uv run robotctl agentd --robot demo_ackermann --port 8102
```

Before using an empty configuration directory with a real robot, review its structure, sensors,
and hard safety boundary, then explicitly confirm the selected profile:

```powershell
$env:ROBOT_LOOP_CONFIG_DIR = "C:\robot-loop-config"
uv run robotctl enroll profiles
uv run robotctl enroll init --robot-id my_robot_01 --profile differential_drive --confirm-safety-profile
uv run robotctl enroll show
```

Each installation owns one `robot_id`. Replacing an enrolled identity or changing its structural
profile requires a separate migration procedure.

## Common ARM64 installation bundle

The deployment baseline is ARM64 + Ubuntu 22.04 + ROS 2 Humble. One identity-free archive supports
NVIDIA Jetson Orin, RK3588, and Raspberry Pi 4/5. The installer enrolls an arbitrary robot identity
from a structural profile while startup discovery identifies the actual compute platform. The
application runtime and schemas remain byte-for-byte identical.

Build the common archive on the development machine:

```powershell
.\scripts\build_bundles.ps1
```

This creates `dist/release/robot-loop-0.1.0-arm64.zip`. Transfer the same archive to each robot,
then choose a profile based on its physical structure and sensors—not its SoC:

```bash
sudo bash install.sh my_robot_01 differential_drive --confirm-safety-profile
```

The installer verifies ARM64, Ubuntu 22.04, ROS 2 Humble, and every payload checksum before
generating the robot capability configuration. Newly discovered bindings and calibration remain
unavailable until explicitly verified. Runtime configuration and artifacts remain local to each
robot, and the archive never contains an API key.

The current MVP archive resolves Python dependencies from the robot's configured package index.
For an offline production install, add an ARM64 wheelhouse. Jetson, RK3588, and Raspberry Pi
ROS/vendor drivers remain different implementations behind the same canonical adapter contract.

Run tests and lint:

```powershell
uv run pytest
uv run ruff check .
```

## Automatic discovery and canonical CLI

Run bounded read-only discovery against a local application workspace:

```powershell
uv run robotctl discover run --robot demo_diff --source-root C:\path\to\robot-application
uv run robotctl discover show --robot demo_diff
uv run robotctl tool catalog --robot demo_diff
```

The program inventories hardware, the host software stack, the live ROS graph and local source
projects, then writes a normalized capability manifest, semantic binding candidates and a canonical
tool catalog under `artifacts/discovery/<robot_id>/latest`. Direct layer entrypoints include
`robotctl hw inventory scan`, `robotctl linux host inspect`, `robotctl ros graph snapshot` and
`robotctl app robot discover`. See [`AUTODISCOVERY.md`](AUTODISCOVERY.md) for the evidence and safety
model.

## `robot_use` backends

The default backend is `mock` and never sends images or data outside the machine. To enable the
OpenAI backend, set the environment variables outside source control:

```powershell
$env:ROBOT_USE_BACKEND = "openai"
$env:OPENAI_API_KEY = "..."
$env:OPENAI_MODEL = "an-image-capable-model-available-to-your-project"
```

The implementation sends timestamped image storyboards plus structured telemetry. It does not
perform local visual detection and it does not grant the model safety authority.

## Project layout

```text
src/robot_loop/       API, CLI, domain models and adapters
configs/local/        Local mock robot capability manifests
configs/profiles/     Enrollable robot structure and sensor templates
configs/deployment/   Common deployment and service manifest
configs/platforms/    Shared ARM64 compatibility and supported-compute manifest
configs/robot_use.yaml
configs/discovery.yaml
schemas/              Exported JSON schemas
tests/                Offline unit and API tests
scripts/dev.ps1       Setup/check/run helper
scripts/build_bundles.ps1
artifacts/             Runtime output, ignored by git
```
